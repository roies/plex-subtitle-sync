import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Contents.Code.subtitle_translate import translate_srt

SAMPLE_SRT = """\
1
00:00:01,000 --> 00:00:02,000
Hello world

2
00:00:03,000 --> 00:00:04,500
How are you?

"""


class TestTranslateSrt(unittest.TestCase):

    def _mock_translator(self, output: str):
        t = MagicMock()
        t.translate.return_value = output
        return t

    def test_same_language_returns_unchanged(self):
        result = translate_srt(SAMPLE_SRT, target_lang='en', source_lang='en')
        self.assertEqual(result, SAMPLE_SRT)

    def test_timestamps_preserved(self):
        mock_t = self._mock_translator('שלום עולם')
        with patch('Contents.Code.subtitle_translate._get_translator', return_value=mock_t):
            result = translate_srt(SAMPLE_SRT, target_lang='he')
        self.assertIn('00:00:01,000 --> 00:00:02,000', result)
        self.assertIn('00:00:03,000 --> 00:00:04,500', result)

    def test_cue_numbers_preserved(self):
        mock_t = self._mock_translator('שלום עולם')
        with patch('Contents.Code.subtitle_translate._get_translator', return_value=mock_t):
            result = translate_srt(SAMPLE_SRT, target_lang='he')
        self.assertIn('1\n', result)
        self.assertIn('2\n', result)

    def test_text_is_translated(self):
        mock_t = self._mock_translator('Hola mundo')
        with patch('Contents.Code.subtitle_translate._get_translator', return_value=mock_t):
            result = translate_srt(SAMPLE_SRT, target_lang='es')
        self.assertIn('Hola mundo', result)

    def test_translator_called_per_block(self):
        mock_t = self._mock_translator('...')
        with patch('Contents.Code.subtitle_translate._get_translator', return_value=mock_t):
            translate_srt(SAMPLE_SRT, target_lang='fr')
        self.assertEqual(mock_t.translate.call_count, 2)  # 2 cue blocks

    def test_missing_argostranslate_returns_original(self):
        with patch('Contents.Code.subtitle_translate._get_translator', return_value=None):
            result = translate_srt(SAMPLE_SRT, target_lang='de')
        self.assertEqual(result, SAMPLE_SRT)


class TestGetTranslator(unittest.TestCase):

    def test_returns_none_when_argostranslate_missing(self):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith('argostranslate'):
                raise ImportError('mocked missing')
            return real_import(name, *args, **kwargs)

        from Contents.Code import subtitle_translate
        with patch('builtins.__import__', side_effect=mock_import):
            result = subtitle_translate._get_translator('en', 'fr')
        self.assertIsNone(result)


class TestTranslateSubtitleFile(unittest.TestCase):

    def test_file_is_rewritten_with_translation(self):
        import tempfile
        from Contents.Code.subtitle_sync import translate_subtitle_file

        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / 'film.srt'
            sub.write_text(SAMPLE_SRT, encoding='utf-8')

            mock_t = MagicMock()
            mock_t.translate.return_value = 'Bonjour'
            with patch('Contents.Code.subtitle_translate._get_translator', return_value=mock_t):
                translate_subtitle_file(sub, target_lang='fr')

            content = sub.read_text(encoding='utf-8')
            self.assertIn('Bonjour', content)
            self.assertIn('00:00:01,000 --> 00:00:02,000', content)


class TestHandleSessionWithTranslation(unittest.TestCase):

    def test_translation_called_after_sync(self):
        import tempfile
        import xml.etree.ElementTree as ET
        from Contents.Code.subtitle_sync import PlexPoller

        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / 'film.mp4'
            video.write_bytes(b'')
            sub = Path(d) / 'film.srt'
            sub.write_text(SAMPLE_SRT, encoding='utf-8')

            xml = ET.fromstring(
                f'<MediaContainer><Video sessionKey="1" ratingKey="42">'
                f'<Media><Part file="{video}">'
                f'<Stream streamType="3" id="1" selected="1" file="{sub}"/>'
                f'</Part></Media></Video></MediaContainer>')
            video_el = xml.find('Video')

            poller = PlexPoller(target_lang='fr')
            translate_calls = []

            with patch('Contents.Code.subtitle_sync.run_ffsubsync', return_value=True), \
                 patch('Contents.Code.subtitle_sync.translate_subtitle_file',
                       side_effect=lambda p, tl, sl: translate_calls.append(p)) as mock_tr, \
                 patch.object(poller, '_refresh'):
                poller._handle_session(video_el)

            self.assertEqual(len(translate_calls), 1)

    def test_translation_skipped_when_no_target_lang(self):
        import tempfile
        import xml.etree.ElementTree as ET
        from Contents.Code.subtitle_sync import PlexPoller

        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / 'film.mp4'
            video.write_bytes(b'')
            sub = Path(d) / 'film.srt'
            sub.write_text(SAMPLE_SRT, encoding='utf-8')

            xml = ET.fromstring(
                f'<MediaContainer><Video sessionKey="1" ratingKey="42">'
                f'<Media><Part file="{video}">'
                f'<Stream streamType="3" id="1" selected="1" file="{sub}"/>'
                f'</Part></Media></Video></MediaContainer>')
            video_el = xml.find('Video')

            poller = PlexPoller(target_lang='')  # no translation
            with patch('Contents.Code.subtitle_sync.run_ffsubsync', return_value=True), \
                 patch('Contents.Code.subtitle_sync.translate_subtitle_file') as mock_tr, \
                 patch.object(poller, '_refresh'):
                poller._handle_session(video_el)

            mock_tr.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
