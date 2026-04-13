from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

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
    run_pipeline_task: (
        Callable[[str, dict[str, Any] | None, bool, bool], Awaitable[bool]] | None
    ) = None

    def tr(self, value: str, i18n_map: dict[str, dict[str, str]] | None = None) -> str:
        if self.resolve_i18n is None:
            return str(value or "")
        return self.resolve_i18n(str(value or ""), i18n_map)

    async def invoke_pipeline_task(
        self,
        entry: str,
        pipeline_override: dict[str, Any] | None = None,
        merge_default_override: bool = True,
        reset_runtime_after_task: bool = True,
    ) -> bool:
        """供插件调用 MaaFW pipeline 任务的统一入口。"""
        if self.run_pipeline_task is None:
            raise RuntimeError("PluginContext.run_pipeline_task 未绑定")
        return await self.run_pipeline_task(
            entry,
            pipeline_override,
            merge_default_override,
            reset_runtime_after_task,
        )


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
