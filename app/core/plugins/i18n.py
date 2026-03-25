from __future__ import annotations

from collections.abc import Mapping

from app.common.config import cfg, Language


def get_current_ui_language_code() -> str:
    """返回当前 UI 语言代码。"""
    current = cfg.get(cfg.language)
    if current == Language.CHINESE_TRADITIONAL:
        return "zh_hk"
    if current == Language.ENGLISH:
        return "en_us"
    if current == Language.JAPANESE:
        return "ja_jp"
    return "zh_cn"


def _build_lang_fallback_chain(language_code: str) -> list[str]:
    normalized = str(language_code or "zh_cn").strip().lower().replace("-", "_")
    candidates = [normalized]

    if "_" in normalized:
        base = normalized.split("_", 1)[0]
        candidates.append(base)

    if normalized.startswith("zh"):
        candidates.extend(["zh_cn", "zh_hk", "zh"])
    elif normalized.startswith("ja"):
        candidates.extend(["ja_jp", "ja"])
    elif normalized.startswith("en"):
        candidates.extend(["en_us", "en"])

    candidates.extend(["en_us", "en", "zh_cn"])

    uniq: list[str] = []
    seen: set[str] = set()
    for code in candidates:
        key = str(code or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(key)
    return uniq


def resolve_plugin_i18n_text(
    value: str,
    i18n_map: Mapping[str, Mapping[str, str]] | None,
    *,
    language_code: str | None = None,
) -> str:
    """解析插件文本中的 $key 国际化占位。

    规则：
    - 非 `$` 开头文本：原样返回
    - `$key`：按当前语言从 i18n_map 中取值
    - 未命中：返回原始文本
    """
    text = str(value or "")
    if not text.startswith("$"):
        return text

    key = text[1:].strip()
    if not key or not i18n_map:
        return text

    lang = language_code or get_current_ui_language_code()
    for code in _build_lang_fallback_chain(lang):
        table = i18n_map.get(code)
        if not isinstance(table, Mapping):
            continue
        translated = table.get(key)
        if translated is None:
            continue
        translated_text = str(translated)
        if translated_text:
            return translated_text

    return text