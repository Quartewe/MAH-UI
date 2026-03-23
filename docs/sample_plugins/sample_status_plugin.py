from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from app.core.plugins.plugin_base import PluginBase, PluginMeta, PluginContext


class SampleStatusPlugin(PluginBase):
    meta = PluginMeta(
        plugin_id="sample.status",
        name="状态面板",
        version="0.1.0",
        description="展示当前时间并可手动刷新",
        icon="INFO",
    )

    def __init__(self) -> None:
        self._ctx: PluginContext | None = None
        self._widget: QWidget | None = None
        self._time_label: QLabel | None = None

    def on_load(self, ctx: PluginContext) -> None:
        self._ctx = ctx
        self._ctx.logger.info("SampleStatusPlugin 已加载")

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        if self._widget is not None:
            return self._widget
        root = QWidget(parent)
        layout = QVBoxLayout(root)

        title = QLabel("状态面板 Sample")
        self._time_label = QLabel("")
        refresh_btn = QPushButton("刷新时间")
        refresh_btn.clicked.connect(self._refresh_time)

        layout.addWidget(title)
        layout.addWidget(self._time_label)
        layout.addWidget(refresh_btn)
        layout.addStretch(1)

        self._widget = root
        self._refresh_time()
        return root

    def on_unload(self) -> None:
        self._ctx = None
        self._widget = None

    def on_enable_changed(self, enabled: bool) -> None:
        if self._ctx:
            self._ctx.logger.info("SampleStatusPlugin enabled=%s", enabled)

    def _refresh_time(self) -> None:
        if self._time_label is not None:
            self._time_label.setText(f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def create_plugin() -> PluginBase:
    return SampleStatusPlugin()
