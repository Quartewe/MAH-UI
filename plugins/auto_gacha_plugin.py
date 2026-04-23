from __future__ import annotations

import asyncio
import re
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
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
    ScrollArea,
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
        self._counter_preview_scroll: ScrollArea | None = None
        self._counter_preview_container: QWidget | None = None
        self._counter_preview_layout: QVBoxLayout | None = None
        self._counter_preview_empty_label: BodyLabel | None = None
        self._counter_preview_items: list[SimpleCardWidget] = []

        self._running_task: asyncio.Task | None = None
        self._stop_task: asyncio.Task | None = None
        self._manual_stop_requested = False
        self._is_running = False

    def on_load(self, ctx: PluginContext) -> None:
        self._ctx = ctx
        self._ctx.signal_bus.task_flow_finished.connect(self._on_task_flow_finished)
        self._ctx.signal_bus.log_output.connect(self._on_log_output)
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

            try:
                self._ctx.signal_bus.log_output.disconnect(self._on_log_output)
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
        self._counter_preview_scroll = None
        self._counter_preview_container = None
        self._counter_preview_layout = None
        self._counter_preview_empty_label = None
        self._counter_preview_items = []
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

        history_title = BodyLabel("计数截图记录", monitor_page)
        history_title.setStyleSheet("font-size: 22px; font-weight: 600;")
        monitor_layout.addWidget(history_title, 0, Qt.AlignmentFlag.AlignLeft)

        self._counter_preview_scroll = ScrollArea(monitor_page)
        self._counter_preview_scroll.setWidgetResizable(True)
        self._counter_preview_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._counter_preview_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._counter_preview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._counter_preview_scroll.setMinimumHeight(330)
        self._counter_preview_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._counter_preview_scroll.setStyleSheet(
            "QScrollArea {"
            "background: transparent;"
            "border: none;"
            "}"
            "QScrollBar:vertical {"
            "background: transparent;"
            "width: 8px;"
            "margin: 2px 0 2px 0;"
            "}"
            "QScrollBar::handle:vertical {"
            "background: rgba(180, 180, 180, 0.65);"
            "min-height: 28px;"
            "border-radius: 4px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            "background: rgba(210, 210, 210, 0.85);"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "height: 0px;"
            "}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            "background: transparent;"
            "}"
        )

        self._counter_preview_container = QWidget(self._counter_preview_scroll)
        self._counter_preview_layout = QVBoxLayout(self._counter_preview_container)
        self._counter_preview_layout.setContentsMargins(0, 0, 0, 0)
        self._counter_preview_layout.setSpacing(10)
        self._counter_preview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._counter_preview_empty_label = BodyLabel("暂无记录", self._counter_preview_container)
        self._counter_preview_empty_label.setStyleSheet("font-size: 18px;")
        self._counter_preview_layout.addWidget(self._counter_preview_empty_label)

        self._counter_preview_scroll.setWidget(self._counter_preview_container)
        monitor_layout.addWidget(self._counter_preview_scroll, 1)

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
        self._set_status(f"状态：运行中（AutoGacha.Record.max_hit={count}）")

        pipeline_override = {
            "AutoGacha.Record": {
                "action": {
                    "param": {
                        "custom_action_param": int(count)
                    }
                }
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
        self._reset_counter_preview()

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

    def _on_task_flow_finished(self, payload: dict[str, Any]) -> None:
        if not self._is_running:
            return
        reason = str(payload.get("reason", "") or "")
        if reason:
            self._set_status(f"状态：{reason}")

    def _on_log_output(self, level: str, text: str) -> None:
        _ = level
        if "[COUNTER]" not in text:
            return

        count = self._extract_counter_value(text)
        if count is None:
            return
        self._update_counter_preview(count)

    def _extract_counter_value(self, text: str) -> int | None:
        counter_text = text[text.find("[COUNTER]") :]

        # 优先匹配结构化字段，避免抓到目标值等无关数字。
        match = re.search(r"\bcount=(\d+)\b", counter_text)
        if match:
            return int(match.group(1))

        match = re.search(r"\[COUNTER\][^\d]*(\d+)", counter_text)
        if match:
            return int(match.group(1))
        return None

    def _update_counter_preview(self, count: int) -> None:
        if self._counter_preview_layout is None:
            return

        if self._counter_preview_empty_label is not None:
            self._counter_preview_empty_label.hide()

        pixmap = self._capture_cached_frame_pixmap()
        item = self._build_counter_preview_item(count, pixmap)
        self._counter_preview_layout.addWidget(item)
        self._counter_preview_items.append(item)

        max_items = 40
        if len(self._counter_preview_items) > max_items:
            first_item = self._counter_preview_items.pop(0)
            self._counter_preview_layout.removeWidget(first_item)
            first_item.deleteLater()

        self._scroll_counter_preview_to_bottom()

    def _reset_counter_preview(self) -> None:
        if self._counter_preview_layout is None:
            return

        for item in self._counter_preview_items:
            self._counter_preview_layout.removeWidget(item)
            item.deleteLater()
        self._counter_preview_items.clear()

        if self._counter_preview_empty_label is not None:
            self._counter_preview_empty_label.show()

        if self._counter_preview_scroll is not None:
            scroll_bar = self._counter_preview_scroll.verticalScrollBar()
            scroll_bar.setValue(0)

    def _build_counter_preview_item(
        self,
        count: int,
        pixmap: QPixmap | None,
    ) -> SimpleCardWidget:
        parent = self._counter_preview_container
        card = SimpleCardWidget(parent)
        card.setClickEnabled(False)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        title = BodyLabel(f"第{count}次: 召唤结果", card)
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        card_layout.addWidget(title)

        image_label = QLabel(card)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        target_width = self._get_preview_target_width()
        fallback_height = max(160, int(target_width * 9 / 16))
        image_label.setFixedSize(target_width, fallback_height)
        image_label.setStyleSheet(
            "QLabel {"
            "border: 1px solid rgba(120, 120, 120, 0.5);"
            "border-radius: 8px;"
            "background: rgba(0, 0, 0, 0.05);"
            "font-size: 16px;"
            "}"
        )

        if pixmap is None or pixmap.isNull():
            image_label.setText("暂无图片")
        else:
            scaled = pixmap.scaled(
                target_width,
                560,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            image_label.setText("")
            image_label.setFixedSize(scaled.size())
            image_label.setPixmap(scaled)

        card_layout.addWidget(image_label)
        return card

    def _get_preview_target_width(self) -> int:
        default_width = 390
        if self._counter_preview_scroll is None:
            return default_width
        try:
            viewport = self._counter_preview_scroll.viewport()
            if viewport is None:
                return default_width
            width = int(viewport.width()) - 20
            if width <= 0:
                return default_width
            return max(220, min(width, 880))
        except Exception:
            return default_width

    def _scroll_counter_preview_to_bottom(self) -> None:
        if self._counter_preview_scroll is None:
            return
        scroll_bar = self._counter_preview_scroll.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def _get_controller(self):
        if self._ctx is None or self._ctx.service_coordinator is None:
            return None
        try:
            if hasattr(self._ctx.service_coordinator, "run_manager"):
                task_flow = self._ctx.service_coordinator.run_manager
                if task_flow and hasattr(task_flow, "maafw"):
                    return getattr(task_flow.maafw, "controller", None)
        except Exception:
            return None
        return None

    def _capture_cached_frame_pixmap(self) -> QPixmap | None:
        controller = self._get_controller()
        if controller is None:
            return None

        cached = None
        try:
            cached_attr = getattr(controller, "cached_image", None)
            if cached_attr is not None:
                cached = cached_attr() if callable(cached_attr) else cached_attr
        except Exception:
            cached = None

        # cached_image 为空时兜底抓取一帧，避免统计项只有标题没有图片。
        if cached is None:
            try:
                post_screencap = getattr(controller, "post_screencap", None)
                if post_screencap is not None:
                    raw = post_screencap().wait().get()
                    if raw is not None:
                        cached = raw
            except Exception:
                cached = None

        if cached is None:
            return None

        try:
            import numpy as np  # type: ignore

            if not isinstance(cached, np.ndarray):
                return None
            if cached.ndim != 3 or cached.shape[2] < 3:
                return None

            h = int(cached.shape[0])
            w = int(cached.shape[1])
            if h <= 0 or w <= 0:
                return None

            bgr = cached[:, :, :3]
            rgb = bgr[..., ::-1]
            if rgb.dtype != np.uint8:
                rgb = np.clip(rgb, 0, 255).astype(np.uint8)

            rgb = np.ascontiguousarray(rgb)
            qimg = QImage(
                rgb.data,
                w,
                h,
                3 * w,
                QImage.Format.Format_RGB888,
            ).copy()
            return QPixmap.fromImage(qimg)
        except Exception:
            return None

    def _set_status(self, text: str) -> None:
        if self._status_label is not None:
            self._status_label.setText(text)


def create_plugin() -> PluginBase:
    return AutoGachaPlugin()
