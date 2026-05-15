# -*- coding: utf-8 -*-
"""JSON-backed translator.

Usage:
    from i18n import Translator, t
    Translator.load("ar")          # or "en"
    print(t("fetch"))              # "جلب الجودات"
    print(t("downloads_count", count=3))  # supports str.format kwargs

Falls back to English when a key is missing in the active language."""

import json
import os
from typing import Dict, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))


class Translator:
    """Singleton-style translator. Holds the active and fallback bundles."""

    _active: Dict[str, str] = {}
    _fallback: Dict[str, str] = {}
    _lang: str = "en"

    AVAILABLE = ("ar", "en")

    @classmethod
    def load(cls, lang: str) -> str:
        """Load a language bundle. Returns the language actually loaded."""
        if lang not in cls.AVAILABLE:
            lang = "en"
        # Always load English as fallback
        cls._fallback = cls._load_bundle("en")
        if lang == "en":
            cls._active = cls._fallback
        else:
            cls._active = cls._load_bundle(lang)
        cls._lang = lang
        return lang

    @classmethod
    def _load_bundle(cls, lang: str) -> Dict[str, str]:
        path = os.path.join(_HERE, f"{lang}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def lang(cls) -> str:
        return cls._lang

    @classmethod
    def is_rtl(cls) -> bool:
        return cls._lang == "ar"

    @classmethod
    def t(cls, key: str, **kwargs) -> str:
        raw = cls._active.get(key)
        if raw is None:
            raw = cls._fallback.get(key, key)
        if kwargs:
            try:
                return raw.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return raw
        return raw


def t(key: str, **kwargs) -> str:
    """Convenience shortcut: from i18n import t."""
    return Translator.t(key, **kwargs)
