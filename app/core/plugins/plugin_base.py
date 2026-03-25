from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtWidgets import QWidget


@dataclass(slots=True)
class PluginMeta:
    plugin_id: str
    name: str
    version: str
    description: str = ""
    icon: str = "APPLICATION"
    entry_position: str = "top"
    i18n: dict[str, dict[str, str]] | None = None


@dataclass(slots=True)
class PluginContext:
    logger: Any
    signal_bus: Any
    service_coordinator: Any
    language_code: str = "zh_cn"
    resolve_i18n: Callable[[str, dict[str, dict[str, str]] | None], str] | None = None

    def tr(self, value: str, i18n_map: dict[str, dict[str, str]] | None = None) -> str:
        if self.resolve_i18n is None:
            return str(value or "")
        return self.resolve_i18n(str(value or ""), i18n_map)


class PluginBase(ABC):
    meta: PluginMeta

    @abstractmethod
    def on_load(self, ctx: PluginContext) -> None:
        pass

    @abstractmethod
    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        pass

    @abstractmethod
    def on_unload(self) -> None:
        pass

    @abstractmethod
    def on_enable_changed(self, enabled: bool) -> None:
        pass
