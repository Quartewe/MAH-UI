from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from app.core.plugins.plugin_base import PluginBase, PluginMeta, PluginContext


class SampleCounterPlugin(PluginBase):
    meta = PluginMeta(
        plugin_id="sample.counter",
        name="计数器",
        version="0.1.0",
        description="简单计数与重置示例",
        icon="CALCULATOR",
    )

    def __init__(self) -> None:
        self._ctx: PluginContext | None = None
        self._widget: QWidget | None = None
        self._count = 0
        self._label: QLabel | None = None

    def on_load(self, ctx: PluginContext) -> None:
        self._ctx = ctx

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        if self._widget is not None:
            return self._widget

        root = QWidget(parent)
        layout = QVBoxLayout(root)

        self._label = QLabel("当前计数：0")
        add_btn = QPushButton("+1")
        reset_btn = QPushButton("重置")

        add_btn.clicked.connect(self._inc)
        reset_btn.clicked.connect(self._reset)

        layout.addWidget(QLabel("计数器 Sample"))
        layout.addWidget(self._label)
        layout.addWidget(add_btn)
        layout.addWidget(reset_btn)
        layout.addStretch(1)

        self._widget = root
        return root

    def on_unload(self) -> None:
        self._ctx = None
        self._widget = None

    def on_enable_changed(self, enabled: bool) -> None:
        if self._ctx:
            self._ctx.logger.info("SampleCounterPlugin enabled=%s", enabled)

    def _inc(self) -> None:
        self._count += 1
        if self._label:
            self._label.setText(f"当前计数：{self._count}")

    def _reset(self) -> None:
        self._count = 0
        if self._label:
            self._label.setText("当前计数：0")


def create_plugin() -> PluginBase:
    return SampleCounterPlugin()
