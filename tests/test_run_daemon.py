import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_daemon import load_config, resolve_runtime_settings


class TestConfigLoading(unittest.TestCase):
    def test_load_config_reads_json_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'config.json'
            path.write_text(json.dumps({'url': 'http://example:32400', 'target_lang': 'fr'}), encoding='utf-8')
            self.assertEqual(load_config(path)['url'], 'http://example:32400')

    def test_resolve_runtime_settings_prefers_cli_over_config_and_env(self):
        args = Namespace(url='http://cli', token='cli-token', interval=3, target_lang='de', source_lang='fr')
        config = {'url': 'http://config', 'token': 'config-token', 'interval': 6, 'target_lang': 'es', 'source_lang': 'it'}
        env = {'PLEX_URL': 'http://env', 'PLEX_TOKEN': 'env-token', 'POLL_INTERVAL': '9', 'TARGET_LANG': 'pt', 'SOURCE_LANG': 'nl'}
        settings = resolve_runtime_settings(args, config, env)
        self.assertEqual(settings['url'], 'http://cli')
        self.assertEqual(settings['token'], 'cli-token')
        self.assertEqual(settings['interval'], 3)
        self.assertEqual(settings['target_lang'], 'de')
        self.assertEqual(settings['source_lang'], 'fr')

    def test_resolve_runtime_settings_falls_back_to_config_and_env(self):
        args = Namespace(url=None, token=None, interval=None, target_lang=None, source_lang=None)
        config = {'url': 'http://config', 'token': 'config-token', 'interval': 6, 'target_lang': 'es'}
        env = {'PLEX_URL': 'http://env', 'PLEX_TOKEN': 'env-token', 'POLL_INTERVAL': '9', 'TARGET_LANG': 'pt', 'SOURCE_LANG': 'nl'}
        settings = resolve_runtime_settings(args, config, env)
        self.assertEqual(settings['url'], 'http://config')
        self.assertEqual(settings['token'], 'config-token')
        self.assertEqual(settings['interval'], 6)
        self.assertEqual(settings['target_lang'], 'es')
        self.assertEqual(settings['source_lang'], 'nl')


if __name__ == '__main__':
    unittest.main(verbosity=2)
