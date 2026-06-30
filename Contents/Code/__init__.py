import logging
import threading
import time

from .subtitle_sync import PlexPoller

log = logging.getLogger('subtitle_autosync')


class SubtitleAutoFixPlugin:
    title = 'Subtitle Auto Fix'

    def __init__(self, plex_url='http://localhost:32400', token='', poll_interval=15,
                 target_lang='', source_lang='en'):
        self.poller = PlexPoller(plex_url=plex_url, token=token, poll_interval=poll_interval,
                                 target_lang=target_lang, source_lang=source_lang)
        self._running = False

    def start(self):
        self._running = True
        thread = threading.Thread(target=self._loop, daemon=True)
        thread.start()
        log.info('Subtitle Auto Fix started — polling every %ds', self.poller.poll_interval)

    def _loop(self):
        while self._running:
            try:
                self.poller.tick()
            except Exception as exc:
                log.exception('Unexpected error in poll loop: %s', exc)
            time.sleep(self.poller.poll_interval)

    def stop(self):
        self._running = False


_plugin = None


def Start():
    global _plugin
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [subtitle_autosync] %(levelname)s %(message)s')
    _plugin = SubtitleAutoFixPlugin()
    _plugin.start()
    return _plugin


def ValidatePrefs():
    return True
