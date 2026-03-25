"""插件系统导出。"""

from app.core.plugins.plugin_base import PluginBase, PluginMeta, PluginContext
from app.core.plugins.plugin_manager import PluginManager, PluginLoadResult
from app.core.plugins.i18n import get_current_ui_language_code, resolve_plugin_i18n_text

__all__ = [
    "PluginBase",
    "PluginMeta",
    "PluginContext",
    "PluginManager",
    "PluginLoadResult",
    "get_current_ui_language_code",
    "resolve_plugin_i18n_text",
]
