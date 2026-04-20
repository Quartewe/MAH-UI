from __future__ import annotations

import asyncio
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    PrimaryPushButton,
    SimpleCardWidget,
    SpinBox,
    SubtitleLabel,
)

from app.core.plugins.plugin_base import PluginBase, PluginContext, PluginMeta
from app.view.task_interface.components.MonitorWidget import MonitorWidget
from app.utils.startup_dialog import (
    DialogButton,
    StartupDialog,
    StartupDialogConfig,
    StartupDialogType,
)


class AutoGachaPlugin(PluginBase):
    meta = PluginMeta(
        plugin_id="mah.auto_gacha.assistant",
        name="战友积分",
        version="0.1.0",
        description="按确认流程执行 AutoGacha 并实时显示模拟器监控画面",
        icon="APPLICATION",
    )

    def __init__(self) -> None:
        self._ctx: PluginContext | None = None
        self._widget: QWidget | None = None
        self._enabled = True

        self._page_stack: QStackedWidget | None = None
        self._count_spin: SpinBox | None = None
        self._start_button: PrimaryPushButton | None = None
        self._status_label: BodyLabel | None = None
        self._right_title: SubtitleLabel | None = None
        self._right_stack: QStackedWidget | None = None
        self._guide_browser: QTextBrowser | None = None
        self._monitor_widget: MonitorWidget | None = None

        self._running_task: asyncio.Task | None = None
        self._stop_task: asyncio.Task | None = None
        self._manual_stop_requested = False
        self._is_running = False

    def on_load(self, ctx: PluginContext) -> None:
        self._ctx = ctx
        self._ctx.signal_bus.task_flow_finished.connect(self._on_task_flow_finished)
        self._ctx.logger.info("AutoGachaPlugin 已加载")

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        if self._widget is not None:
            return self._widget

        root = QWidget(parent)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(0)

        self._page_stack = QStackedWidget(root)
        self._page_stack.addWidget(self._build_first_page(self._page_stack))
        self._page_stack.addWidget(self._build_second_page(self._page_stack))
        self._page_stack.setCurrentIndex(0)

        root_layout.addWidget(self._page_stack)
        self._widget = root
        return root

    def on_unload(self) -> None:
        if self._ctx is not None:
            try:
                self._ctx.signal_bus.task_flow_finished.disconnect(
                    self._on_task_flow_finished
                )
            except (RuntimeError, TypeError):
                pass

            if self._is_running and self._ctx.service_coordinator is not None:
                asyncio.create_task(self._ctx.service_coordinator.stop_task_flow())

        self._ctx = None
        self._widget = None
        self._page_stack = None
        self._count_spin = None
        self._start_button = None
        self._status_label = None
        self._right_title = None
        self._right_stack = None
        self._guide_browser = None
        self._monitor_widget = None
        self._running_task = None
        self._stop_task = None
        self._manual_stop_requested = False
        self._is_running = False

    def on_enable_changed(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if self._widget is not None:
            self._widget.setEnabled(self._enabled)
        if self._ctx is not None:
            self._ctx.logger.info("AutoGachaPlugin enabled=%s", self._enabled)

    def _build_first_page(self, parent: QWidget) -> QWidget:
        page = QWidget(parent)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)

        layout.addStretch(1)

        card = SimpleCardWidget(page)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 28, 24, 24)
        card_layout.setSpacing(16)

        title = QLabel("警告!", card)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 36px; font-weight: 700; color: #d13438;")

        desc = QLabel(card)
        desc.setTextFormat(Qt.TextFormat.RichText)
        desc.setText(
            "请注意，本流程虽然做了兜底措施，但是"
            "<span style='color:#d13438; font-weight:700;'>无法保证</span>"
            "不会误抽卡，所以不建议使用该功能。"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("font-size: 24px; line-height: 1.4;")

        confirm_btn = PrimaryPushButton("我知道了", card)
        confirm_btn.setMinimumHeight(48)
        confirm_btn.clicked.connect(self._on_first_page_confirm)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(confirm_btn)
        btn_layout.addStretch(1)

        card_layout.addWidget(title)
        card_layout.addWidget(desc)
        card_layout.addLayout(btn_layout)

        layout.addWidget(card)
        layout.addStretch(1)

        return page

    def _build_second_page(self, parent: QWidget) -> QWidget:
        page = QWidget(parent)
        root_layout = QHBoxLayout(page)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        left_card = SimpleCardWidget(page)
        left_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(14)

        left_title = SubtitleLabel("参数设置", left_card)
        left_layout.addWidget(left_title)

        count_label = BodyLabel("抽几次10连", left_card)
        left_layout.addWidget(count_label)

        self._count_spin = SpinBox(left_card)
        self._count_spin.setRange(0, 9999)
        self._count_spin.setValue(0)
        self._count_spin.setSingleStep(1)
        left_layout.addWidget(self._count_spin)

        self._start_button = PrimaryPushButton("开始", left_card)
        self._start_button.setMinimumHeight(44)
        self._start_button.clicked.connect(self._on_start_button_clicked)
        left_layout.addWidget(self._start_button)

        self._status_label = BodyLabel("状态：待命", left_card)
        self._status_label.setWordWrap(True)
        left_layout.addWidget(self._status_label)

        left_layout.addStretch(1)

        right_card = SimpleCardWidget(page)
        right_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(12)

        self._right_title = SubtitleLabel("我应该怎么做", right_card)
        self._right_title.setStyleSheet("font-size: 28px; font-weight: 700;")
        right_layout.addWidget(self._right_title)

        self._right_stack = QStackedWidget(right_card)

        guide_page = QWidget(self._right_stack)
        guide_layout = QVBoxLayout(guide_page)
        guide_layout.setContentsMargins(0, 0, 0, 0)
        guide_layout.setSpacing(0)
        self._guide_browser = QTextBrowser(guide_page)
        self._guide_browser.setReadOnly(True)
        self._guide_browser.setOpenExternalLinks(False)
        self._guide_browser.setFrameShape(QFrame.Shape.NoFrame)
        self._guide_browser.setStyleSheet(
            "QTextBrowser {"
            "border: none;"
            "background: transparent;"
            "font-size: 24px;"
            "}"
        )
        guide_layout.addWidget(self._guide_browser)

        monitor_page = QWidget(self._right_stack)
        monitor_layout = QVBoxLayout(monitor_page)
        monitor_layout.setContentsMargins(0, 0, 0, 0)
        monitor_layout.setSpacing(10)

        monitor_hint = BodyLabel("模拟器实时监控", monitor_page)
        monitor_hint.setStyleSheet("font-size: 24px; font-weight: 600;")
        monitor_layout.addWidget(monitor_hint, 0, Qt.AlignmentFlag.AlignLeft)

        if self._ctx is not None and self._ctx.service_coordinator is not None:
            self._monitor_widget = MonitorWidget(self._ctx.service_coordinator, monitor_page)
            monitor_layout.addWidget(self._monitor_widget, 0, Qt.AlignmentFlag.AlignLeft)
        else:
            fallback = BodyLabel("监控组件初始化失败：未获得服务上下文", monitor_page)
            fallback.setWordWrap(True)
            fallback.setStyleSheet("font-size: 22px; color: #d13438;")
            monitor_layout.addWidget(fallback)
        monitor_layout.addStretch(1)

        self._right_stack.addWidget(guide_page)
        self._right_stack.addWidget(monitor_page)
        right_layout.addWidget(self._right_stack)

        root_layout.addWidget(left_card, 4)
        root_layout.addWidget(right_card, 6)

        self._show_guide_text()
        return page

    def _show_guide_text(self) -> None:
        if self._right_title is not None:
            self._right_title.setText("我应该怎么做:")
        if self._right_stack is not None:
            self._right_stack.setCurrentIndex(0)
        if self._guide_browser is not None:
            self._guide_browser.setHtml(
                "<div style='font-size:26px;'>"
                "1. 把画面手动设置到"
                "<span style='color:#d13438; font-weight:700;'>高级战友积分画面</span>"
                "</div>"
                "<div style='font-size:26px;'>2. 设置好你要的数据</div>"
                "<div style='font-size:26px;'>"
                "3. 点击"
                "<span style='color:#d13438; font-weight:700;'>开始</span>"
                "</div>"
            )

    def _on_first_page_confirm(self) -> None:
        if not self._show_first_dialog():
            return
        if self._page_stack is not None:
            self._page_stack.setCurrentIndex(1)

    def _show_repo_confirm_dialog(
        self,
        *,
        title: str,
        content: str,
        confirm_text: str,
        cancel_text: str,
        confirm_on_left: bool,
    ) -> bool:
        return_button = DialogButton(text=cancel_text, is_primary=True)
        confirm_button = DialogButton(text=confirm_text, is_primary=False)
        buttons = [confirm_button, return_button] if confirm_on_left else [return_button, confirm_button]

        config = StartupDialogConfig(
            dialog_type=StartupDialogType.WARNING,
            title=title,
            content=content,
            buttons=buttons,
        )
        dialog = StartupDialog(config, self._widget)
        self._tune_dialog_buttons(dialog, return_text=cancel_text, confirm_text=confirm_text)
        dialog.exec()
        clicked = dialog.clicked_button
        return clicked is not None and clicked.text == confirm_text

    def _tune_dialog_buttons(
        self,
        dialog: StartupDialog,
        *,
        return_text: str,
        confirm_text: str,
    ) -> None:
        for button in dialog.findChildren(QPushButton):
            if button.text() == return_text:
                button.setMinimumHeight(56)
                button.setMinimumWidth(200)
                font = button.font()
                font.setPointSize(max(font.pointSize(), 14))
                font.setBold(True)
                button.setFont(font)
            elif button.text() == confirm_text:
                button.setMinimumHeight(40)
                button.setMinimumWidth(110)
                font = button.font()
                font.setPointSize(max(font.pointSize(), 12))
                button.setFont(font)

    def _show_first_dialog(self) -> bool:
        return self._show_repo_confirm_dialog(
            title="确认",
            content="真的要这么做吗",
            confirm_text="确定",
            cancel_text="不了谢谢",
            confirm_on_left=True,
        )

    def _show_second_dialog(self) -> bool:
        return self._show_repo_confirm_dialog(
            title="最后确认",
            content="你真的调好了吗?",
            confirm_text="让我们开始吧",
            cancel_text="并没有",
            confirm_on_left=False,
        )

    def _on_start_button_clicked(self) -> None:
        if not self._enabled:
            return
        if self._is_running:
            self._request_stop_pipeline()
            return

        if not self._show_second_dialog():
            return

        count = 1
        if self._count_spin is not None:
            count = int(self._count_spin.value())
        self._launch_pipeline(count)

    def _launch_pipeline(self, count: int) -> None:
        if self._ctx is None:
            return
        if self._running_task is not None and not self._running_task.done():
            return

        self._manual_stop_requested = False
        self._enter_running_state()
        self._set_status(f"状态：运行中（AutoGacha.Count.max_hit={count}）")

        pipeline_override = {
            "AutoGacha.Count": {
                "max_hit": int(count),
            }
        }
        self._running_task = asyncio.create_task(self._run_pipeline(pipeline_override))

    async def _run_pipeline(self, pipeline_override: dict[str, Any]) -> None:
        ok = False
        try:
            if self._ctx is None:
                return
            ok = await self._ctx.invoke_pipeline_task(
                entry="AutoGacha.Entry",
                pipeline_override=pipeline_override,
                merge_default_override=True,
                reset_runtime_after_task=True,
            )
            if ok:
                self._set_status("状态：流程执行完成")
            elif self._manual_stop_requested:
                self._set_status("状态：已手动停止")
            else:
                self._set_status("状态：流程未完成")
        except Exception as exc:
            if self._ctx is not None:
                self._ctx.logger.exception("AutoGachaPlugin 执行异常: %s", exc)
            self._set_status(f"状态：执行异常 - {exc}")
        finally:
            self._running_task = None
            self._stop_task = None
            self._leave_running_state()

    def _request_stop_pipeline(self) -> None:
        if self._ctx is None or self._ctx.service_coordinator is None:
            return
        if self._stop_task is not None and not self._stop_task.done():
            return

        self._manual_stop_requested = True
        if self._start_button is not None:
            self._start_button.setText("停止中...")
            self._start_button.setEnabled(False)
        self._set_status("状态：停止中...")

        self._stop_task = asyncio.create_task(self._stop_pipeline())

    async def _stop_pipeline(self) -> None:
        try:
            if self._ctx is None or self._ctx.service_coordinator is None:
                return
            await self._ctx.service_coordinator.stop_task_flow()
        except Exception as exc:
            if self._ctx is not None:
                self._ctx.logger.exception("AutoGachaPlugin 停止任务失败: %s", exc)
            self._set_status(f"状态：停止失败 - {exc}")

    def _enter_running_state(self) -> None:
        self._is_running = True

        if self._right_title is not None:
            self._right_title.setText("实时监控")
        if self._right_stack is not None:
            self._right_stack.setCurrentIndex(1)

        if self._start_button is not None:
            self._start_button.setText("停止")
            self._start_button.setEnabled(True)
        if self._count_spin is not None:
            self._count_spin.setEnabled(False)
        if self._status_label is not None:
            self._status_label.setText("状态：运行中")

    def _leave_running_state(self) -> None:
        if not self._is_running:
            return

        self._is_running = False

        if self._start_button is not None:
            self._start_button.setText("开始")
            self._start_button.setEnabled(True)
        if self._count_spin is not None:
            self._count_spin.setEnabled(True)

        self._show_guide_text()

    def _on_task_flow_finished(self, payload: dict[str, Any]) -> None:
        if not self._is_running:
            return
        reason = str(payload.get("reason", "") or "")
        if reason:
            self._set_status(f"状态：{reason}")

    def _set_status(self, text: str) -> None:
        if self._status_label is not None:
            self._status_label.setText(text)


def create_plugin() -> PluginBase:
    return AutoGachaPlugin()
