#!/usr/bin/env python3
"""
Plex Auto Subs — standalone daemon.

Polls Plex Media Server for active playback sessions, auto-syncs subtitle
timing with ffsubsync, and auto-translates to Hebrew with argostranslate.
Fully automatic — no user involvement needed.

Usage:
    plex-auto-subs                                  # local Plex, no auth
    plex-auto-subs --token YOUR_TOKEN               # with auth
    plex-auto-subs --url http://192.168.1.5:32400 --token TOKEN

Config via environment variables:
    PLEX_URL      — default: http://localhost:32400
    PLEX_TOKEN    — default: (empty)
    POLL_INTERVAL — seconds between polls, default: 15
    TARGET_LANG   — translate to this language code, default: he (Hebrew)
    SOURCE_LANG   — subtitle source language, default: en
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from Contents.Code.subtitle_sync import PlexPoller

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [subtitle_autosync] %(levelname)s %(message)s',
)
log = logging.getLogger('subtitle_autosync')


def main():
    parser = argparse.ArgumentParser(description='Plex Auto Subs — auto-sync and translate subtitles')
    parser.add_argument('--url', default=os.environ.get('PLEX_URL', 'http://localhost:32400'))
    parser.add_argument('--token', default=os.environ.get('PLEX_TOKEN', ''))
    parser.add_argument('--interval', type=int,
                        default=int(os.environ.get('POLL_INTERVAL', '15')),
                        help='Seconds between polls (default: 15)')
    parser.add_argument('--target-lang', default=os.environ.get('TARGET_LANG', 'he'),
                        help='Translate subtitles to this language code (default: he)')
    parser.add_argument('--source-lang', default=os.environ.get('SOURCE_LANG', 'en'),
                        help='Source language of subtitles (default: en)')
    args = parser.parse_args()

    log.info('Plex Auto Subs starting — PMS: %s  interval: %ds  translate: %s',
             args.url, args.interval, args.target_lang or 'off')
    log.info('Requires: ffsubsync + argostranslate  (pip install plex-auto-subs)')
    if args.target_lang:
        log.info('Translation enabled (%s→%s) — install: pip install argostranslate',
                 args.source_lang, args.target_lang)

    poller = PlexPoller(plex_url=args.url, token=args.token, poll_interval=args.interval,
                        target_lang=args.target_lang, source_lang=args.source_lang)

    while True:
        try:
            poller.tick()
        except KeyboardInterrupt:
            log.info('Stopped.')
            break
        except Exception as exc:
            log.exception('Unexpected error: %s', exc)
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
