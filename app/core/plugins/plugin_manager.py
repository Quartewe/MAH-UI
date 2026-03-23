from __future__ import annotations

import importlib.util
import shutil
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.core.plugins.plugin_base import PluginBase, PluginContext


@dataclass(slots=True)
class PluginLoadResult:
    plugin_id: str
    ok: bool
    message: str = ""


class PluginManager:
    def __init__(self, plugin_dir: Path, ctx: PluginContext):
        self.plugin_dir = plugin_dir
        self.ctx = ctx
        self.loaded_plugins: dict[str, PluginBase] = {}
        self.enabled_map: dict[str, bool] = {}
        self.failed_plugins: dict[str, str] = {}
        self._pending_nav_entries: list[tuple[str, PluginBase]] = []

    def discover_plugin_files(self) -> list[Path]:
        if not self.plugin_dir.exists():
            self.plugin_dir.mkdir(parents=True, exist_ok=True)
            return []
        return sorted(
            p
            for p in self.plugin_dir.glob("*.py")
            if p.is_file() and not p.name.startswith("_")
        )

    def load_all(self) -> list[PluginLoadResult]:
        self._pending_nav_entries.clear()
        results: list[PluginLoadResult] = []
        for file_path in self.discover_plugin_files():
            result = self.load_one(file_path)
            results.append(result)
        return results

    def pop_pending_nav_entries(self) -> list[tuple[str, PluginBase]]:
        entries = list(self._pending_nav_entries)
        self._pending_nav_entries.clear()
        return entries

    def load_one(self, file_path: Path) -> PluginLoadResult:
        module_name = f"mfw_plugin_{file_path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                raise RuntimeError("无法创建模块规格")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, "create_plugin"):
                raise RuntimeError("插件缺少 create_plugin()")

            plugin = module.create_plugin()
            if plugin is None or not isinstance(plugin, PluginBase):
                raise RuntimeError("create_plugin() 必须返回 PluginBase 实例")

            meta = plugin.meta
            plugin_id = str(getattr(meta, "plugin_id", "")).strip()
            name = str(getattr(meta, "name", "")).strip()

            if not plugin_id:
                raise RuntimeError("plugin_id 不能为空")
            if not name:
                raise RuntimeError("name 不能为空")
            if plugin_id in self.loaded_plugins:
                return PluginLoadResult(plugin_id=plugin_id, ok=True, message="已加载")

            plugin.on_load(self.ctx)
            self.loaded_plugins[plugin_id] = plugin
            self.enabled_map.setdefault(plugin_id, True)
            self.failed_plugins.pop(plugin_id, None)

            if self.enabled_map.get(plugin_id, True):
                self._pending_nav_entries.append((plugin_id, plugin))

            self.ctx.logger.info("插件加载成功: %s (%s)", name, plugin_id)
            return PluginLoadResult(plugin_id=plugin_id, ok=True, message="ok")
        except Exception as exc:
            plugin_id = file_path.stem
            self.failed_plugins[plugin_id] = f"{exc}\n{traceback.format_exc()}"
            self.ctx.logger.error("插件加载失败 %s: %s", file_path.name, exc)
            return PluginLoadResult(plugin_id=plugin_id, ok=False, message=str(exc))

    def import_plugin_file(self, source_path: str | Path) -> PluginLoadResult:
        source = Path(source_path)
        if not source.exists() or source.suffix.lower() != ".py":
            return PluginLoadResult(plugin_id=source.stem or "unknown", ok=False, message="仅支持导入 .py 文件")

        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        target = self.plugin_dir / source.name
        if target.exists():
            stem = source.stem
            suffix = source.suffix
            idx = 1
            while True:
                candidate = self.plugin_dir / f"{stem}_{idx}{suffix}"
                if not candidate.exists():
                    target = candidate
                    break
                idx += 1

        shutil.copy2(source, target)
        self.ctx.logger.info("插件文件已导入: %s -> %s", source, target)
        return self.load_one(target)

    def get_sorted_loaded_plugins(self) -> list[PluginBase]:
        return list(self.loaded_plugins.values())

    def is_enabled(self, plugin_id: str) -> bool:
        return bool(self.enabled_map.get(plugin_id, True))

    def set_enabled(self, plugin_id: str, enabled: bool) -> bool:
        plugin = self.loaded_plugins.get(plugin_id)
        if plugin is None:
            return False
        enabled_bool = bool(enabled)
        self.enabled_map[plugin_id] = enabled_bool
        try:
            plugin.on_enable_changed(enabled_bool)
        except Exception as exc:
            self.ctx.logger.warning("设置插件启用状态失败 %s: %s", plugin_id, exc)
        return True

    def apply_pending_nav_entries(
        self, register_callback: Callable[[str, PluginBase], None]
    ) -> int:
        entries = self.pop_pending_nav_entries()
        count = 0
        for plugin_id, plugin in entries:
            register_callback(plugin_id, plugin)
            count += 1
        return count
