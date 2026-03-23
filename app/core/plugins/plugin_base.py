from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QWidget


@dataclass(slots=True)
class PluginMeta:
    plugin_id: str
    name: str
    version: str
    description: str = ""
    icon: str = "APPLICATION"
    entry_position: str = "top"


@dataclass(slots=True)
class PluginContext:
    logger: Any
    signal_bus: Any
    service_coordinator: Any


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
