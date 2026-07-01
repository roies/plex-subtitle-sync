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

_LANGUAGE_ALIASES = {
    'english': 'en', 'eng': 'en', 'en': 'en', 'en-us': 'en', 'en-gb': 'en',
    'hebrew': 'he', 'heb': 'he', 'he': 'he',
    'french': 'fr', 'fra': 'fr', 'fre': 'fr', 'fr': 'fr',
    'spanish': 'es', 'spa': 'es', 'es': 'es',
    'german': 'de', 'deu': 'de', 'de': 'de',
    'arabic': 'ar', 'ara': 'ar', 'ar': 'ar',
    'russian': 'ru', 'rus': 'ru', 'ru': 'ru',
    'italian': 'it', 'ita': 'it', 'it': 'it',
    'portuguese': 'pt', 'por': 'pt', 'pt': 'pt',
    'turkish': 'tr', 'tur': 'tr', 'tr': 'tr',
    'chinese': 'zh', 'zho': 'zh', 'zh': 'zh',
    'japanese': 'ja', 'jpn': 'ja', 'ja': 'ja',
    'korean': 'ko', 'kor': 'ko', 'ko': 'ko',
    'dutch': 'nl', 'nld': 'nl', 'nl': 'nl',
    'polish': 'pl', 'pol': 'pl', 'pl': 'pl',
}

# SRT block: index line, timestamp line(s), then text lines, then blank line
_BLOCK_RE = re.compile(
    r'(\d+\n)'                                      # cue number
    r'([\d:,.]+ --> [\d:,.]+[^\n]*\n)'              # timestamp line
    r'((?:.+\n)+)',                                  # one or more text lines
    re.MULTILINE,
)


def normalize_language_code(lang: Optional[str]) -> Optional[str]:
    """Normalize a language label to a short ISO-like code when possible."""
    if not lang:
        return None
    normalized = lang.strip().lower().replace('_', '-')
    if not normalized or normalized == 'und':
        return None
    if '-' in normalized:
        normalized = normalized.split('-', 1)[0]
    return _LANGUAGE_ALIASES.get(normalized, normalized)


def translate_srt(srt_text: str, target_lang: str, source_lang: str = 'en') -> str:
    """Translate all subtitle text lines in an SRT string, preserve timestamps."""
    normalized_source = normalize_language_code(source_lang) or source_lang
    normalized_target = normalize_language_code(target_lang) or target_lang
    if normalized_target == normalized_source:
        return srt_text

    translator = _get_translator(normalized_source, normalized_target)
    if translator is None:
        log.error('No argostranslate model for %s→%s — skipping translation', source_lang, target_lang)
        return srt_text

    def translate_block(match):
        index_line = match.group(1)
        ts_line    = match.group(2)
        text_block = match.group(3)
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
