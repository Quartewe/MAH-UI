from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from app.core.plugins.plugin_base import PluginBase, PluginMeta, PluginContext


class SampleHelloPlugin(PluginBase):
    meta = PluginMeta(
        plugin_id="sample.hello",
        name="Sample 插件",
        version="0.1.0",
        description="示例欢迎页，提供基础消息发送能力",
        icon="MESSAGE",
        entry_position="top",
    )

    def __init__(self) -> None:
        self._ctx: PluginContext | None = None
        self._widget: QWidget | None = None
        self._enabled = True

    def on_load(self, ctx: PluginContext) -> None:
        self._ctx = ctx
        self._ctx.logger.info("SampleHelloPlugin 已加载")

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        if self._widget is not None:
            return self._widget

        root = QWidget(parent)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("这是一个 Sample 插件页面")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._status = QLabel("状态：已启用")

        test_button = QPushButton("发送一条测试消息")
        test_button.clicked.connect(self._on_test_clicked)

        layout.addWidget(title)
        layout.addWidget(self._status)
        layout.addWidget(test_button)
        layout.addStretch(1)

        self._widget = root
        return root

    def on_unload(self) -> None:
        if self._ctx:
            self._ctx.logger.info("SampleHelloPlugin 已卸载")
        self._ctx = None
        self._widget = None

    def on_enable_changed(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if hasattr(self, "_status") and self._status is not None:
            self._status.setText("状态：已启用" if self._enabled else "状态：已禁用")
        if self._ctx:
            self._ctx.logger.info("SampleHelloPlugin 启用状态变更: %s", self._enabled)

    def _on_test_clicked(self) -> None:
        if self._ctx:
            self._ctx.signal_bus.info_bar_requested.emit("success", "Sample 插件：消息发送成功")
            self._ctx.logger.info("SampleHelloPlugin 触发测试按钮")


def create_plugin() -> PluginBase:
    return SampleHelloPlugin()
