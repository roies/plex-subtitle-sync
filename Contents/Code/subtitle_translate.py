"""
Offline subtitle translation using argostranslate (MIT license, no API key).

First run per language pair: downloads the ~100MB model automatically.
Subsequent runs: fully offline.

Usage:
    translated_srt = translate_srt(srt_text, target_lang='he', source_lang='en')
"""

import logging
import re
from typing import Optional

log = logging.getLogger('subtitle_autosync')

# SRT block: index line, timestamp line(s), then text lines, then blank line
_BLOCK_RE = re.compile(
    r'(\d+\n)'                                      # cue number
    r'([\d:,.]+ --> [\d:,.]+[^\n]*\n)'              # timestamp line
    r'((?:.+\n)+)',                                  # one or more text lines
    re.MULTILINE,
)


def translate_srt(srt_text: str, target_lang: str, source_lang: str = 'en') -> str:
    """Translate all subtitle text lines in an SRT string, preserve timestamps."""
    if target_lang == source_lang:
        return srt_text

    translator = _get_translator(source_lang, target_lang)
    if translator is None:
        log.error('No argostranslate model for %s→%s — skipping translation', source_lang, target_lang)
        return srt_text

    def translate_block(match):
        index_line = match.group(1)
        ts_line    = match.group(2)
        text_block = match.group(3)
        # strip HTML-like tags before translating, restore after
        translated = translator.translate(text_block.strip())
        return f'{index_line}{ts_line}{translated}\n'

    return _BLOCK_RE.sub(translate_block, srt_text)


def _get_translator(source_lang: str, target_lang: str):
    """Return an argostranslate translator, installing the model on first use."""
    try:
        import argostranslate.package
        import argostranslate.translate
    except ImportError:
        log.error('argostranslate not installed — run: pip install argostranslate')
        return None

    # Check if already installed
    installed = argostranslate.translate.get_installed_languages()
    src = next((l for l in installed if l.code == source_lang), None)
    if src:
        tgt = next((t for t in src.translations_to if t.code == target_lang), None)
        if tgt:
            return src.get_translation(tgt)

    # Not installed — download it
    log.info('Downloading argostranslate model %s→%s (one-time, ~100MB)…', source_lang, target_lang)
    try:
        argostranslate.package.update_package_index()
        available = argostranslate.package.get_available_packages()
        pkg = next(
            (p for p in available if p.from_code == source_lang and p.to_code == target_lang),
            None,
        )
        if pkg is None:
            log.error('No argostranslate package available for %s→%s', source_lang, target_lang)
            return None
        argostranslate.package.install_from_path(pkg.download())
        log.info('Model installed.')
        # retry after install
        return _get_translator(source_lang, target_lang)
    except Exception as exc:
        log.error('Failed to install argostranslate model: %s', exc)
        return None
