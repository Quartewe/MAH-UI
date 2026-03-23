from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton

from app.core.plugins.plugin_base import PluginBase, PluginMeta, PluginContext

from qfluentwidgets import FluentIcon

FluentIcon.LIBRARY


class CharacterInfoPlugin(PluginBase):
    meta = PluginMeta(
        plugin_id="character.info",
        name="角色信息",
        version="0.1.0",
        description="显示角色信息",
        icon="LIBRARY",
    )

    def __init__(self) -> None:
        self._ctx: PluginContext | None = None
        self._widget: QWidget | None = None
        self._output: QLabel | None = None
        self._input: QLineEdit | None = None

    def on_load(self, ctx: PluginContext) -> None:
        self._ctx = ctx

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        if self._widget is not None:
            return self._widget

        root = QWidget(parent)
        layout = QVBoxLayout(root)

        self._input = QLineEdit(root)
        self._input.setPlaceholderText("输入任意文本")
        self._output = QLabel("输出：")
        btn = QPushButton("回显")
        btn.clicked.connect(self._echo)

        layout.addWidget(QLabel("角色信息"))
        layout.addWidget(self._input)
        layout.addWidget(btn)
        layout.addWidget(self._output)
        layout.addStretch(1)

        self._widget = root
        return root

    def on_unload(self) -> None:
        self._ctx = None
        self._widget = None

    def on_enable_changed(self, enabled: bool) -> None:
        if self._ctx:
            self._ctx.logger.info("CharacterInfoPlugin enabled=%s", enabled)

    def _echo(self) -> None:
        if self._output is None or self._input is None:
            return
        text = self._input.text().strip()
        self._output.setText(f"输出：{text or '(空)'}")


def create_plugin() -> PluginBase:
    return CharacterInfoPlugin()
