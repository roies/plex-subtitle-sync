#!/usr/bin/env python3
"""
Standalone daemon — run this directly (outside the Plex plugin host) if needed.

Usage:
    python run_daemon.py
    python run_daemon.py --url http://192.168.1.10:32400 --token YOUR_TOKEN

Config via environment variables (alternative to flags):
    PLEX_URL      — default: http://localhost:32400
    PLEX_TOKEN    — default: (empty, works for local unauthenticated connections)
    POLL_INTERVAL — seconds between polls, default: 15
    TARGET_LANG   — translate subtitles to this language code, e.g. 'he', 'fr', 'es'
                    (default: empty = no translation)
    SOURCE_LANG   — source language code (default: 'en')
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
    parser = argparse.ArgumentParser(description='Plex subtitle auto-sync daemon')
    parser.add_argument('--url', default=os.environ.get('PLEX_URL', 'http://localhost:32400'))
    parser.add_argument('--token', default=os.environ.get('PLEX_TOKEN', ''))
    parser.add_argument('--interval', type=int,
                        default=int(os.environ.get('POLL_INTERVAL', '15')),
                        help='Seconds between polls (default: 15)')
    parser.add_argument('--target-lang', default=os.environ.get('TARGET_LANG', ''),
                        help='Translate subtitles to this language code, e.g. he, fr, es')
    parser.add_argument('--source-lang', default=os.environ.get('SOURCE_LANG', 'en'),
                        help='Source language of subtitles (default: en)')
    args = parser.parse_args()

    log.info('Starting — PMS: %s  interval: %ds  translate: %s',
             args.url, args.interval, args.target_lang or 'off')
    log.info('Make sure ffsubsync is installed: pip install ffsubsync')
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
