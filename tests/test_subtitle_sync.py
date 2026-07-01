import sys
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Contents.Code.subtitle_sync import PlexPoller, run_ffsubsync


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_xml(video_file: str, sub_file: str = '', sub_key: str = '',
                 session_key: str = '1', rating_key: str = '42',
                 sub_id: str = '99') -> ET.Element:
    sub_file_attr = f'file="{sub_file}"' if sub_file else ''
    sub_key_attr  = f'key="{sub_key}"' if sub_key else ''
    return ET.fromstring(f"""
        <MediaContainer>
          <Video sessionKey="{session_key}" ratingKey="{rating_key}">
            <Media>
              <Part file="{video_file}">
                <Stream streamType="3" id="{sub_id}" selected="1"
                        {sub_file_attr} {sub_key_attr} />
              </Part>
            </Media>
          </Video>
        </MediaContainer>""")


# ---------------------------------------------------------------------------
# Subtitle detection
# ---------------------------------------------------------------------------

class TestFindSelectedSubtitle(unittest.TestCase):

    def test_finds_selected_stream(self):
        poller = PlexPoller()
        video = _session_xml('/f.mp4', '/f.srt').find('Video')
        stream = poller._find_selected_subtitle(video)
        self.assertIsNotNone(stream)
        self.assertEqual(stream.get('file'), '/f.srt')

    def test_ignores_unselected_stream(self):
        poller = PlexPoller()
        xml = ET.fromstring(
            '<Video sessionKey="1" ratingKey="2">'
            '  <Stream streamType="3" id="1"/>'   # no selected="1"
            '</Video>')
        self.assertIsNone(poller._find_selected_subtitle(xml))

    def test_ignores_non_subtitle_streams(self):
        poller = PlexPoller()
        xml = ET.fromstring(
            '<Video sessionKey="1" ratingKey="2">'
            '  <Stream streamType="1" id="1" selected="1"/>'  # audio, not subtitle
            '</Video>')
        self.assertIsNone(poller._find_selected_subtitle(xml))


# ---------------------------------------------------------------------------
# Video file resolution
# ---------------------------------------------------------------------------

class TestVideoFilePath(unittest.TestCase):

    def test_returns_existing_file(self):
        poller = PlexPoller()
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / 'film.mp4'
            video.write_bytes(b'')
            xml = ET.fromstring(f'<Video><Media><Part file="{video}"/></Media></Video>')
            self.assertEqual(poller._video_file_path(xml), str(video))

    def test_returns_none_for_missing_file(self):
        poller = PlexPoller()
        xml = ET.fromstring('<Video><Media><Part file="/nonexistent/film.mp4"/></Media></Video>')
        self.assertIsNone(poller._video_file_path(xml))

    def test_returns_none_when_no_part(self):
        poller = PlexPoller()
        xml = ET.fromstring('<Video><Media/></Video>')
        self.assertIsNone(poller._video_file_path(xml))


# ---------------------------------------------------------------------------
# Subtitle path resolution
# ---------------------------------------------------------------------------

class TestResolveSubtitlePath(unittest.TestCase):

    def test_local_sidecar_returned_directly(self):
        poller = PlexPoller()
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / 'film.srt'
            sub.write_text('1\n00:00:01,000 --> 00:00:02,000\nHi\n', encoding='utf-8')
            stream = ET.fromstring(f'<Stream streamType="3" selected="1" file="{sub}"/>')
            self.assertEqual(poller._resolve_subtitle_path(stream, '1'), sub)

    def test_online_sub_downloaded_alongside_video(self):
        poller = PlexPoller()
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / 'film.mp4'
            video.write_bytes(b'')
            sub_content = b'1\n00:00:01,000 --> 00:00:02,000\nHi\n'

            # No local file attr — has a stream key (online subtitle)
            stream = ET.fromstring('<Stream streamType="3" selected="1" key="/subtitles/99"/>')

            meta_xml = ET.fromstring(
                f'<MediaContainer><Video><Media>'
                f'<Part file="{video}"/>'
                f'</Media></Video></MediaContainer>')

            with patch.object(poller, '_api', return_value=meta_xml), \
                 patch.object(poller, '_api_download', side_effect=lambda key, dest: dest.write_bytes(sub_content)):
                result = poller._resolve_subtitle_path(stream, rating_key='42')

            expected = video.with_suffix('.autosync.srt')
            self.assertEqual(result, expected)
            self.assertEqual(expected.read_bytes(), sub_content)

    def test_online_sub_falls_back_to_tempdir_when_no_video_meta(self):
        poller = PlexPoller()
        stream = ET.fromstring('<Stream streamType="3" selected="1" key="/subtitles/99"/>')

        with patch.object(poller, '_api', return_value=None), \
             patch.object(poller, '_api_download', side_effect=lambda key, dest: dest.write_bytes(b'')):
            result = poller._resolve_subtitle_path(stream, rating_key='42')

        self.assertIsNotNone(result)
        self.assertIn('autosync_42', result.name)

    def test_returns_none_when_download_fails(self):
        poller = PlexPoller()
        stream = ET.fromstring('<Stream streamType="3" selected="1" key="/subtitles/99"/>')
        with patch.object(poller, '_api', return_value=None), \
             patch.object(poller, '_api_download', side_effect=Exception('network error')):
            result = poller._resolve_subtitle_path(stream, rating_key='42')
        self.assertIsNone(result)

    def test_returns_none_with_no_file_and_no_key(self):
        poller = PlexPoller()
        stream = ET.fromstring('<Stream streamType="3" selected="1"/>')
        self.assertIsNone(poller._resolve_subtitle_path(stream, '1'))


# ---------------------------------------------------------------------------
# Handle session / deduplication
# ---------------------------------------------------------------------------

class TestHandleSession(unittest.TestCase):

    def _setup(self, d):
        video = Path(d) / 'film.mp4'
        video.write_bytes(b'')
        sub = Path(d) / 'film.srt'
        sub.write_text('1\n00:00:01,000 --> 00:00:02,000\nHi\n', encoding='utf-8')
        return video, sub

    def test_ffsubsync_called_and_refresh_triggered(self):
        poller = PlexPoller()
        with tempfile.TemporaryDirectory() as d:
            video, sub = self._setup(d)
            video_el = _session_xml(str(video), str(sub)).find('Video')

            with patch('Contents.Code.subtitle_sync.run_ffsubsync', return_value=True) as mock_ffs, \
                 patch.object(poller, '_refresh') as mock_refresh:
                poller._handle_session(video_el)

            mock_ffs.assert_called_once_with(str(video), str(sub))
            mock_refresh.assert_called_once_with('42')

    def test_refresh_not_called_when_ffsubsync_fails(self):
        poller = PlexPoller()
        with tempfile.TemporaryDirectory() as d:
            video, sub = self._setup(d)
            video_el = _session_xml(str(video), str(sub)).find('Video')

            with patch('Contents.Code.subtitle_sync.run_ffsubsync', return_value=False), \
                 patch.object(poller, '_refresh') as mock_refresh:
                poller._handle_session(video_el)

            mock_refresh.assert_not_called()

    def test_translation_uses_detected_subtitle_language(self):
        poller = PlexPoller(target_lang='he')
        with tempfile.TemporaryDirectory() as d:
            video, sub = self._setup(d)
            video_el = ET.fromstring(
                f'<MediaContainer><Video sessionKey="1" ratingKey="42">'
                f'<Media><Part file="{video}"><Stream streamType="3" id="1" selected="1" '
                f'file="{sub}" language="fr"/></Part></Media></Video></MediaContainer>').find('Video')

            with patch('Contents.Code.subtitle_sync.run_ffsubsync', return_value=True), \
                 patch('Contents.Code.subtitle_sync.translate_subtitle_file') as mock_translate, \
                 patch.object(poller, '_refresh'):
                poller._handle_session(video_el)

            self.assertEqual(mock_translate.call_count, 1)
            self.assertEqual(mock_translate.call_args.args[1], 'he')
            self.assertEqual(mock_translate.call_args.args[2], 'fr')

    def test_translation_skipped_when_subtitle_is_already_target_language(self):
        poller = PlexPoller(target_lang='he')
        with tempfile.TemporaryDirectory() as d:
            video, sub = self._setup(d)
            video_el = ET.fromstring(
                f'<MediaContainer><Video sessionKey="1" ratingKey="42">'
                f'<Media><Part file="{video}"><Stream streamType="3" id="1" selected="1" '
                f'file="{sub}" language="he"/></Part></Media></Video></MediaContainer>').find('Video')

            with patch('Contents.Code.subtitle_sync.run_ffsubsync', return_value=True), \
                 patch('Contents.Code.subtitle_sync.translate_subtitle_file') as mock_translate, \
                 patch.object(poller, '_refresh'):
                poller._handle_session(video_el)

            mock_translate.assert_not_called()

    def test_duplicate_session_not_reprocessed(self):
        poller = PlexPoller()
        with tempfile.TemporaryDirectory() as d:
            video, sub = self._setup(d)
            video_el = _session_xml(str(video), str(sub)).find('Video')

            calls = []
            with patch('Contents.Code.subtitle_sync.run_ffsubsync',
                       side_effect=lambda v, s: calls.append(1) or True):
                poller._handle_session(video_el)
                poller._handle_session(video_el)

            self.assertEqual(len(calls), 1)

    def test_subtitle_switch_triggers_reprocess(self):
        """Switching subtitle mid-session (different sub_id) must re-sync."""
        poller = PlexPoller()
        with tempfile.TemporaryDirectory() as d:
            video, sub = self._setup(d)
            sub2 = Path(d) / 'film.fr.srt'
            sub2.write_text('1\n00:00:01,000 --> 00:00:02,000\nBonjour\n', encoding='utf-8')

            el1 = _session_xml(str(video), str(sub),  sub_id='99').find('Video')
            el2 = _session_xml(str(video), str(sub2), sub_id='100').find('Video')

            calls = []
            with patch('Contents.Code.subtitle_sync.run_ffsubsync',
                       side_effect=lambda v, s: calls.append(s) or True), \
                 patch.object(poller, '_refresh'):
                poller._handle_session(el1)
                poller._handle_session(el2)

            self.assertEqual(len(calls), 2)

    def test_skips_session_without_subtitle(self):
        poller = PlexPoller()
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / 'film.mp4'
            video.write_bytes(b'')
            xml = ET.fromstring(
                f'<Video sessionKey="1" ratingKey="42">'
                f'<Media><Part file="{video}"/></Media></Video>')
            with patch('Contents.Code.subtitle_sync.run_ffsubsync') as mock_ffs:
                poller._handle_session(xml)
            mock_ffs.assert_not_called()


# ---------------------------------------------------------------------------
# tick() integration
# ---------------------------------------------------------------------------

class TestTick(unittest.TestCase):

    def test_tick_processes_all_sessions(self):
        poller = PlexPoller()
        with tempfile.TemporaryDirectory() as d:
            v1, s1 = Path(d) / 'a.mp4', Path(d) / 'a.srt'
            v2, s2 = Path(d) / 'b.mp4', Path(d) / 'b.srt'
            for v in (v1, v2): v.write_bytes(b'')
            for s in (s1, s2): s.write_text('1\n00:00:01,000 --> 00:00:02,000\nHi\n', encoding='utf-8')

            sessions_xml = ET.fromstring(f"""
                <MediaContainer>
                  <Video sessionKey="1" ratingKey="10">
                    <Media><Part file="{v1}">
                      <Stream streamType="3" id="1" selected="1" file="{s1}"/>
                    </Part></Media>
                  </Video>
                  <Video sessionKey="2" ratingKey="20">
                    <Media><Part file="{v2}">
                      <Stream streamType="3" id="2" selected="1" file="{s2}"/>
                    </Part></Media>
                  </Video>
                </MediaContainer>""")

            with patch.object(poller, '_api', return_value=sessions_xml), \
                 patch('Contents.Code.subtitle_sync.run_ffsubsync', return_value=True) as mock_ffs, \
                 patch.object(poller, '_refresh'):
                poller.tick()

            self.assertEqual(mock_ffs.call_count, 2)

    def test_tick_is_resilient_to_api_failure(self):
        poller = PlexPoller()
        with patch.object(poller, '_api', return_value=None):
            # should not raise
            poller.tick()


# ---------------------------------------------------------------------------
# run_ffsubsync
# ---------------------------------------------------------------------------

class TestRunFfsubsync(unittest.TestCase):

    def test_returns_false_when_binary_missing(self):
        self.assertFalse(run_ffsubsync('/v.mp4', '/s.srt'))

    def test_returns_true_on_zero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch('subprocess.run', return_value=mock_result):
            self.assertTrue(run_ffsubsync('/v.mp4', '/s.srt'))

    def test_returns_false_on_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = 'error details'
        with patch('subprocess.run', return_value=mock_result):
            self.assertFalse(run_ffsubsync('/v.mp4', '/s.srt'))

    def test_returns_false_on_timeout(self):
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('ffs', 300)):
            self.assertFalse(run_ffsubsync('/v.mp4', '/s.srt'))

    def test_passes_correct_command(self):
        mock_result = MagicMock(returncode=0)
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            run_ffsubsync('/video.mp4', '/sub.srt')
            args = mock_run.call_args[0][0]
            self.assertEqual(args, ['ffs', '/video.mp4', '-i', '/sub.srt', '-o', '/sub.srt'])


if __name__ == '__main__':
    unittest.main(verbosity=2)

