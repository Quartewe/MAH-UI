"""Helpers for task option binding storage.

The interface ``binding`` field declares that a source option can be stored
inside a target option entry. Config state keeps target options as arrays and
uses ``_binding_active`` to identify the current target value.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Dict, Iterable, Optional, Tuple


BINDING_ACTIVE_KEY = "_binding_active"
ENTRY_RESERVED_KEYS = {"value", "children", "hidden"}


def get_binding_targets(option_config: Dict[str, Any]) -> list[str]:
    binding = option_config.get("binding")
    if isinstance(binding, str):
        return [binding] if binding else []
    if isinstance(binding, list):
        return [item for item in binding if isinstance(item, str) and item]
    return []


def resolve_binding_target(
    form_structure: Dict[str, Any],
    source_key: str,
    *,
    logger: Any = None,
) -> Optional[str]:
    source_config = form_structure.get(source_key)
    if not isinstance(source_config, dict):
        return None

    targets = get_binding_targets(source_config)
    if not targets:
        return None

    matched = [target for target in targets if target in form_structure]
    if len(matched) > 1:
        message = (
            f"binding 配置错误: option '{source_key}' 在同一任务中同时命中多个 "
            f"target: {matched}"
        )
        if logger is not None:
            logger.error(message)
        return None

    return matched[0] if matched else None


def iter_binding_sources(
    form_structure: Dict[str, Any], *, logger: Any = None
) -> Iterable[Tuple[str, str]]:
    for source_key, source_config in form_structure.items():
        if not isinstance(source_config, dict):
            continue
        if not get_binding_targets(source_config):
            continue
        target_key = resolve_binding_target(
            form_structure, source_key, logger=logger
        )
        if target_key:
            yield source_key, target_key


def option_payload_value(option_payload: Any) -> Any:
    if isinstance(option_payload, dict) and "value" in option_payload:
        return option_payload.get("value")
    return option_payload


def binding_value_key(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def ensure_entry_payload(option_payload: Any) -> Dict[str, Any]:
    if isinstance(option_payload, dict):
        entry = deepcopy(option_payload)
        if "value" not in entry:
            entry = {"value": entry}
        return entry
    return {"value": deepcopy(option_payload)}


def normalize_target_entries(option_payload: Any) -> list[Dict[str, Any]]:
    if isinstance(option_payload, list):
        entries = [
            ensure_entry_payload(item)
            for item in option_payload
            if isinstance(item, dict) or item is not None
        ]
    elif option_payload is None:
        entries = []
    else:
        entries = [ensure_entry_payload(option_payload)]

    return dedupe_entries_by_value(entries)


def dedupe_entries_by_value(entries: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    value_index: dict[str, int] = {}

    for entry in entries:
        if not isinstance(entry, dict) or "value" not in entry:
            continue
        key = binding_value_key(entry.get("value"))
        if key in value_index:
            result[value_index[key]] = deepcopy(entry)
        else:
            value_index[key] = len(result)
            result.append(deepcopy(entry))

    return result


def get_binding_active_map(task_options: Dict[str, Any]) -> Dict[str, Any]:
    active_map = task_options.get(BINDING_ACTIVE_KEY)
    return dict(active_map) if isinstance(active_map, dict) else {}


def get_active_value(task_options: Dict[str, Any], target_key: str) -> Any:
    active_map = get_binding_active_map(task_options)
    if target_key in active_map:
        return active_map[target_key]

    option_payload = task_options.get(target_key)
    if isinstance(option_payload, list):
        entries = normalize_target_entries(option_payload)
        return entries[0].get("value") if entries else None
    return option_payload_value(option_payload)


def select_active_entry(
    entries: list[Dict[str, Any]], active_value: Any
) -> Optional[Dict[str, Any]]:
    if not entries:
        return None

    if active_value is not None:
        active_key = binding_value_key(active_value)
        for entry in entries:
            if binding_value_key(entry.get("value")) == active_key:
                return deepcopy(entry)

    return deepcopy(entries[0])


def get_active_target_entry(
    task_options: Dict[str, Any], target_key: str
) -> Optional[Dict[str, Any]]:
    entries = normalize_target_entries(task_options.get(target_key))
    active_value = get_active_value(task_options, target_key)
    return select_active_entry(entries, active_value)


def deep_merge_dict(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    for key, value in source.items():
        if (
            key in target
            and isinstance(target[key], dict)
            and isinstance(value, dict)
        ):
            deep_merge_dict(target[key], value)
        else:
            target[key] = deepcopy(value)


def upsert_entry_by_value(
    entries: list[Dict[str, Any]], entry: Dict[str, Any]
) -> list[Dict[str, Any]]:
    normalized_entries = normalize_target_entries(entries)
    normalized_entry = ensure_entry_payload(entry)
    entry_key = binding_value_key(normalized_entry.get("value"))

    result: list[Dict[str, Any]] = []
    replaced = False

    for existing in normalized_entries:
        if binding_value_key(existing.get("value")) == entry_key:
            merged = deepcopy(existing)
            deep_merge_dict(merged, normalized_entry)
            result.append(merged)
            replaced = True
        else:
            result.append(deepcopy(existing))

    if not replaced:
        result.append(normalized_entry)

    return dedupe_entries_by_value(result)
