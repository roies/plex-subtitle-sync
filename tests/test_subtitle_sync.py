import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Contents.Code.subtitle_sync import PlexPoller, run_ffsubsync


class TestPlexPoller(unittest.TestCase):

    def _make_session_xml(self, video_file: str, sub_file: str, session_key='1', rating_key='42') -> ET.Element:
        xml = f"""<MediaContainer>
          <Video sessionKey="{session_key}" ratingKey="{rating_key}">
            <Media>
              <Part file="{video_file}">
                <Stream streamType="3" id="99" selected="1" file="{sub_file}" />
              </Part>
            </Media>
          </Video>
        </MediaContainer>"""
        return ET.fromstring(xml)

    def test_selected_subtitle_found(self):
        poller = PlexPoller()
        root = self._make_session_xml('/movies/film.mp4', '/movies/film.srt')
        video = root.find('Video')
        stream = poller._find_selected_subtitle(video)
        self.assertIsNotNone(stream)
        self.assertEqual(stream.get('file'), '/movies/film.srt')

    def test_no_selected_subtitle_returns_none(self):
        poller = PlexPoller()
        xml = ET.fromstring('<MediaContainer><Video sessionKey="1" ratingKey="2"><Media><Part file="/f.mp4"><Stream streamType="3" id="1"/></Part></Media></Video></MediaContainer>')
        video = xml.find('Video')
        self.assertIsNone(poller._find_selected_subtitle(video))

    def test_video_file_path_exists(self):
        poller = PlexPoller()
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / 'film.mp4'
            video.write_bytes(b'')
            xml = ET.fromstring(f'<Video><Media><Part file="{video}"/></Media></Video>')
            self.assertEqual(poller._video_file_path(xml), str(video))

    def test_run_ffsubsync_missing_returns_false(self):
        # ffs binary won't exist here — should return False gracefully
        result = run_ffsubsync('/nonexistent/video.mp4', '/nonexistent/sub.srt')
        self.assertFalse(result)

    def test_resolve_subtitle_local_file(self):
        poller = PlexPoller()
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / 'film.srt'
            sub.write_text('1\n00:00:01,000 --> 00:00:02,000\nHello\n', encoding='utf-8')
            stream = ET.fromstring(f'<Stream streamType="3" selected="1" file="{sub}"/>')
            result = poller._resolve_subtitle_path(stream, rating_key='1')
            self.assertEqual(result, sub)

    def test_duplicate_session_not_reprocessed(self):
        poller = PlexPoller()
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / 'film.mp4'
            video.write_bytes(b'')
            sub = Path(d) / 'film.srt'
            sub.write_text('1\n00:00:01,000 --> 00:00:02,000\nHello\n', encoding='utf-8')

            root = self._make_session_xml(str(video), str(sub))
            video_el = root.find('Video')

            calls = []
            with patch('Contents.Code.subtitle_sync.run_ffsubsync', side_effect=lambda v, s: calls.append(1) or True):
                poller._handle_session(video_el)
                poller._handle_session(video_el)  # second call — same session key

            self.assertEqual(len(calls), 1, 'ffsubsync should only run once per session+subtitle')


if __name__ == '__main__':
    unittest.main()

