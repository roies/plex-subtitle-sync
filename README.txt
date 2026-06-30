Subtitle Auto Fix
==================

Automatically fixes subtitle offset for any subtitle active in Plex — including
online/downloaded subtitles — without any user involvement.

How it works
------------
1. A daemon polls the Plex Media Server API (/status/sessions) every 15 seconds.
2. When a video starts playing with a subtitle selected, the daemon:
   a. Gets the subtitle file path from the PMS API (works for local sidecars AND
      online subtitles Plex has downloaded to its cache).
   b. Runs `ffsubsync` (MIT license) against the video's audio to auto-detect the
      correct offset and rewrites the subtitle file in place.
   c. Triggers a Plex metadata refresh so the fixed subtitle loads immediately.
3. Each session+subtitle combo is only processed once (no repeated re-syncing).

No config files. No manual delay values. No license required.

Requirements
------------
- Python 3.8+
- ffmpeg installed and on PATH (used by ffsubsync)
- ffsubsync:  pip install ffsubsync

Quick start
-----------
  pip install ffsubsync
  python run_daemon.py                               # local Plex, no auth
  python run_daemon.py --token YOUR_PLEX_TOKEN       # with auth
  python run_daemon.py --url http://192.168.1.5:32400 --token TOKEN

As a background service (Linux/systemd)
----------------------------------------
  sudo cp subtitle-autosync.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now subtitle-autosync

Getting your Plex token (if needed)
-------------------------------------
  Settings → Account → "Get your Plex token" (at the bottom of that page)
  Or: https://support.plex.tv/articles/204059436

Online subtitle support
-----------------------
When you select an online subtitle in Plex, Plex downloads it and stores it
locally. The daemon finds this cached file via the PMS API and syncs it.
If the stream has no local path, the daemon downloads it and saves it as
<videoname>.autosync.srt alongside the video, which Plex picks up as an
external subtitle after the metadata refresh.

Tests
-----
  python -m pytest tests/            # requires ffsubsync installed
  python tests/test_subtitle_sync.py # standalone, no pytest needed

