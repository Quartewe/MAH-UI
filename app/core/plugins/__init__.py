"""插件系统导出。"""

from app.core.plugins.plugin_base import PluginBase, PluginMeta, PluginContext
from app.core.plugins.plugin_manager import PluginManager, PluginLoadResult

__all__ = [
    "PluginBase",
    "PluginMeta",
    "PluginContext",
    "PluginManager",
    "PluginLoadResult",
]
