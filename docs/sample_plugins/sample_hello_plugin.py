from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from app.core.plugins.plugin_base import PluginBase, PluginMeta, PluginContext


class SampleHelloPlugin(PluginBase):
    meta = PluginMeta(
        plugin_id="sample.hello",
        name="$plugin_name",
        version="0.1.0",
        description="$plugin_desc",
        icon="MESSAGE",
        entry_position="top",
        i18n={
            "zh_cn": {
                "plugin_name": "Sample 插件",
                "plugin_desc": "示例欢迎页，提供基础消息发送能力",
                "title": "这是一个 Sample 插件页面",
                "status_enabled": "状态：已启用",
                "status_disabled": "状态：已禁用",
                "test_button": "发送一条测试消息",
                "toast_success": "Sample 插件：消息发送成功",
            },
            "en_us": {
                "plugin_name": "Sample Plugin",
                "plugin_desc": "A sample welcome page with basic messaging",
                "title": "This is a Sample plugin page",
                "status_enabled": "Status: Enabled",
                "status_disabled": "Status: Disabled",
                "test_button": "Send a test message",
                "toast_success": "Sample plugin: message sent",
            },
            "ja_jp": {
                "plugin_name": "サンプルプラグイン",
                "plugin_desc": "基本的なメッセージ送信を備えたサンプルページ",
                "title": "これはサンプルプラグインのページです",
                "status_enabled": "状態：有効",
                "status_disabled": "状態：無効",
                "test_button": "テストメッセージを送信",
                "toast_success": "サンプルプラグイン：メッセージ送信成功",
            },
        },
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

        title = QLabel(self._tr("$title"))
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._status = QLabel(self._tr("$status_enabled"))

        test_button = QPushButton(self._tr("$test_button"))
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
            self._status.setText(
                self._tr("$status_enabled")
                if self._enabled
                else self._tr("$status_disabled")
            )
        if self._ctx:
            self._ctx.logger.info("SampleHelloPlugin 启用状态变更: %s", self._enabled)

    def _on_test_clicked(self) -> None:
        if self._ctx:
            self._ctx.signal_bus.info_bar_requested.emit("success", self._tr("$toast_success"))
            self._ctx.logger.info("SampleHelloPlugin 触发测试按钮")

    def _tr(self, value: str) -> str:
        if self._ctx is None:
            return value
        return self._ctx.tr(value, self.meta.i18n)


def create_plugin() -> PluginBase:
    return SampleHelloPlugin()
