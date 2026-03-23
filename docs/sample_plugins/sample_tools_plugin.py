from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from app.core.plugins.plugin_base import PluginBase, PluginMeta, PluginContext


class SampleToolsPlugin(PluginBase):
    meta = PluginMeta(
        plugin_id="sample.tools",
        name="工具按钮",
        version="0.1.0",
        description="提供快速提示消息触发按钮",
        icon="TOOL",
    )

    def __init__(self) -> None:
        self._ctx: PluginContext | None = None
        self._widget: QWidget | None = None

    def on_load(self, ctx: PluginContext) -> None:
        self._ctx = ctx

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        if self._widget is not None:
            return self._widget

        root = QWidget(parent)
        layout = QVBoxLayout(root)

        layout.addWidget(QLabel("工具按钮 Sample"))

        info_btn = QPushButton("发 Info")
        warn_btn = QPushButton("发 Warning")

        info_btn.clicked.connect(lambda: self._emit("info", "这是工具插件的提示消息"))
        warn_btn.clicked.connect(lambda: self._emit("warning", "这是工具插件的警告消息"))

        layout.addWidget(info_btn)
        layout.addWidget(warn_btn)
        layout.addStretch(1)

        self._widget = root
        return root

    def on_unload(self) -> None:
        self._ctx = None
        self._widget = None

    def on_enable_changed(self, enabled: bool) -> None:
        if self._ctx:
            self._ctx.logger.info("SampleToolsPlugin enabled=%s", enabled)

    def _emit(self, level: str, message: str) -> None:
        if self._ctx is None:
            return
        self._ctx.signal_bus.info_bar_requested.emit(level, message)


def create_plugin() -> PluginBase:
    return SampleToolsPlugin()
