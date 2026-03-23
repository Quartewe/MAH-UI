"""
Show 选项项
只读展示型选项：动态加载并显示 shows 列表内容
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import jsonc
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    PushButton,
    SimpleCardWidget,
    ToolButton,
    ToolTipFilter,
    ToolTipPosition,
    FluentIcon as FIF,
)

from app.core.service.interface_manager import get_interface_manager
from app.core.service.i18n_service import get_i18n_service
from app.utils.logger import logger
from app.utils.markdown_helper import render_markdown
from app.view.task_interface.components.ImagePreviewDialog import ImagePreviewDialog
from .base import OptionItemBase


class ShowOptionItem(OptionItemBase):
    """只读展示型选项项（不产生可编辑值）"""

    def __init__(
        self, key: str, config: Dict[str, Any], parent: Optional["OptionItemBase"] = None
    ):
        config["type"] = "show"
        super().__init__(key, config, parent)
        self.init_ui()
        self.init_config()
        self._animation_enabled = True

    def init_ui(self):
        label_text = self.config.get("label", self.key)
        self.label = self._create_label_with_optional_icon(
            label_text,
            self.config.get("icon"),
            self.main_option_layout,
            self.config.get("description"),
        )

        card = SimpleCardWidget()
        card.setBorderRadius(8)
        card_layout = self._safe_get_card_layout(card)

        shows = self._extract_shows(self.config)
        if not shows:
            empty_label = BodyLabel(self.tr("No show items configured"))
            card_layout.addWidget(empty_label)
        else:
            for index, show_item in enumerate(shows):
                normalized = self._normalize_show_node(show_item, fallback_name=f"Item {index + 1}")
                node_widget = self._create_show_node_widget(normalized, depth=0)
                card_layout.addWidget(node_widget)

        self.control_widget = card
        self.main_option_layout.addWidget(card)

    def _safe_get_card_layout(self, card: SimpleCardWidget):
        from PySide6.QtWidgets import QVBoxLayout

        layout = card.layout()
        if layout is None:
            layout = QVBoxLayout(card)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(8)
        return layout

    def _extract_shows(self, config: Dict[str, Any]) -> list[Dict[str, Any]]:
        """提取 shows 列表。"""
        shows = config.get("shows")
        if isinstance(shows, list):
            result: list[Dict[str, Any]] = []
            for item in shows:
                if isinstance(item, dict):
                    result.append(item)
                elif isinstance(item, str):
                    result.append({"path": item})
            return result
        return []

    def _normalize_show_node(self, node: Dict[str, Any], fallback_name: str = "") -> Dict[str, Any]:
        """标准化单个 show 节点，并合并 cases/inputs 的基础展示规范。"""
        normalized = dict(node)
        normalized.setdefault("name", fallback_name or "")

        # cases / inputs 的基础规范合并：作为子展示节点递归处理
        children: list[Dict[str, Any]] = []
        for child in normalized.get("shows", []) if isinstance(normalized.get("shows"), list) else []:
            if isinstance(child, dict):
                children.append(child)

        for case in normalized.get("cases", []) if isinstance(normalized.get("cases"), list) else []:
            if isinstance(case, dict):
                children.append(case)

        for input_item in normalized.get("inputs", []) if isinstance(normalized.get("inputs"), list) else []:
            if isinstance(input_item, dict):
                children.append(input_item)

        if children:
            normalized["shows"] = children

        return normalized

    def _get_node_title(self, node: Dict[str, Any]) -> str:
        label = node.get("label")
        if label:
            return str(label)
        name = node.get("name")
        if name:
            return str(name)
        title = node.get("title")
        if title:
            return str(title)
        return self.tr("Show Item")

    def _get_node_description(self, node: Dict[str, Any]) -> str:
        desc = node.get("description") or node.get("doc")
        return str(desc) if desc else ""

    def _extract_node_path(self, node: Dict[str, Any]) -> str:
        path = node.get("path") or node.get("value") or ""
        path_text = str(path)
        if not path_text:
            return ""
        try:
            i18n = get_i18n_service()
            return i18n.translate_text(path_text)
        except Exception:
            return path_text

    def _extract_node_mode(self, node: Dict[str, Any]) -> str:
        mode = node.get("mode") or ""
        return str(mode).strip().lower()

    def _create_show_node_widget(self, node: Dict[str, Any], depth: int = 0) -> QWidget:
        container = SimpleCardWidget()
        container.setBorderRadius(8)
        container_layout = self._safe_get_card_layout(container)
        container_layout.setContentsMargins(10 + depth * 4, 8, 10, 8)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(6)

        self._add_icon_to_layout(title_layout, node.get("icon"))

        title_label = BodyLabel(self._get_node_title(node))
        title_layout.addWidget(title_label)

        desc = self._get_node_description(node)
        if desc:
            indicator = self._create_description_indicator(desc)
            title_layout.addWidget(indicator)

        title_layout.addStretch()
        header_layout.addWidget(title_container, 1)

        refresh_btn = ToolButton(FIF.SYNC)
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setToolTip(self.tr("刷新"))
        refresh_btn.installEventFilter(
            ToolTipFilter(refresh_btn, 0, ToolTipPosition.TOP)
        )
        header_layout.addWidget(refresh_btn)

        toggle_btn = PushButton(self.tr("收起"))
        toggle_btn.setFixedWidth(72)
        header_layout.addWidget(toggle_btn)
        container_layout.addWidget(header)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        def _render_content() -> None:
            self._clear_layout_widgets(content_layout)

            path = self._extract_node_path(node)
            mode = self._extract_node_mode(node)
            if path:
                try:
                    source_text, resolved_path = self._load_source_text(path)
                    viewer = self._create_content_viewer(source_text, resolved_path, mode)
                    content_layout.addWidget(viewer)
                except Exception as exc:
                    logger.warning("加载 show 节点失败: key=%s, error=%s", self.key, exc)
                    error_label = BodyLabel(self.tr("Failed to load show content"))
                    error_label.setStyleSheet("color: #d9534f;")
                    content_layout.addWidget(error_label)

            child_nodes = node.get("shows") if isinstance(node.get("shows"), list) else []
            for idx, child in enumerate(child_nodes):
                if not isinstance(child, dict):
                    continue
                child_normalized = self._normalize_show_node(child, fallback_name=f"Item {idx + 1}")
                child_widget = self._create_show_node_widget(child_normalized, depth=depth + 1)
                content_layout.addWidget(child_widget)

        _render_content()

        container_layout.addWidget(content)

        def _toggle():
            visible = content.isVisible()
            content.setVisible(not visible)
            toggle_btn.setText(self.tr("展开") if visible else self.tr("收起"))

        def _refresh_current_node():
            _render_content()

        toggle_btn.clicked.connect(_toggle)
        refresh_btn.clicked.connect(_refresh_current_node)
        return container

    def _clear_layout_widgets(self, layout: QVBoxLayout) -> None:
        while layout.count() > 0:
            item = layout.takeAt(0)
            if not item:
                continue
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif child_layout is not None:
                while child_layout.count() > 0:
                    sub_item = child_layout.takeAt(0)
                    if sub_item and sub_item.widget():
                        sub_widget = sub_item.widget()
                        if sub_widget:
                            sub_widget.setParent(None)
                            sub_widget.deleteLater()
                child_layout.deleteLater()

    def _resolve_show_path(self, file_path: str) -> Path:
        if not file_path:
            raise ValueError("shows.path 为空")

        manager = get_interface_manager()
        base_dir = Path(getattr(manager, "_interface_dir", Path.cwd())).resolve()

        target = Path(file_path)
        if not target.is_absolute():
            target = (base_dir / target).resolve()
        else:
            target = target.resolve()

        if not target.is_relative_to(base_dir):
            raise ValueError("shows.path 超出 bundle 目录")
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(str(target))

        return target

    def _load_source_text(self, source: str) -> tuple[str, Optional[Path]]:
        """加载数据来源文本：优先按文件路径读取，失败则按内联文本处理。"""
        text = (source or "").strip()
        if not text:
            raise ValueError("空数据来源")

        # 占位语法：{key1.key2}，从当前任务选项中提取对应值
        if text.startswith("{") and text.endswith("}") and "/" not in text and "\\" not in text:
            resolved_placeholder = self._resolve_placeholder_value(text)
            if resolved_placeholder is not None:
                if isinstance(resolved_placeholder, (dict, list)):
                    return json.dumps(resolved_placeholder, ensure_ascii=False, indent=2), None
                return str(resolved_placeholder), None
            return text, None

        try:
            resolved = self._resolve_show_path(text)
            return resolved.read_text(encoding="utf-8"), resolved
        except Exception:
            return text, None

    def _resolve_placeholder_value(self, placeholder: str) -> Any:
        """解析 {a.b.c} 占位路径，从当前任务选项中取值。"""
        key_path = placeholder.strip()[1:-1].strip()
        if not key_path:
            return None

        options = self._get_current_task_options()
        if not isinstance(options, dict):
            return None

        current: Any = options
        for seg in key_path.split("."):
            seg = seg.strip()
            if not seg:
                return None
            if isinstance(current, dict) and seg in current:
                current = current.get(seg)
                continue
            return None
        return current

    def _get_current_task_options(self) -> Dict[str, Any]:
        """从父级 OptionWidget 中获取当前任务选项。"""
        widget = self.parentWidget()
        while widget is not None:
            service = getattr(widget, "service_coordinator", None)
            if service is not None:
                option_service = getattr(service, "option", None) or getattr(
                    service, "option_service", None
                )
                if option_service and hasattr(option_service, "get_options"):
                    try:
                        options = option_service.get_options()
                        if isinstance(options, dict):
                            return options
                    except Exception:
                        return {}
                return {}
            widget = widget.parentWidget()
        return {}

    def _detect_mode(self, path: Path, mode: str) -> str:
        if mode in {"md", "markdown", "json"}:
            return "md" if mode in {"md", "markdown"} else "json"

        suffix = path.suffix.lower()
        if suffix == ".md":
            return "md"
        if suffix in {".json", ".jsonc"}:
            return "json"
        return ""

    def _detect_mode_from_text(self, text: str, mode: str) -> str:
        if mode in {"md", "markdown", "json"}:
            return "md" if mode in {"md", "markdown"} else "json"
        stripped = (text or "").strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                jsonc.loads(stripped)
                return "json"
            except Exception:
                return "md"
        return "md"

    def _create_content_viewer(self, text: str, source_path: Optional[Path], mode: str) -> QWidget:
        if source_path is not None:
            detected = self._detect_mode(source_path, mode)
        else:
            detected = self._detect_mode_from_text(text, mode)

        if detected == "json":
            return self._create_json_viewer_from_text(text)
        return self._create_markdown_viewer_from_text(text, source_path.parent if source_path else None)

    def _create_markdown_viewer_from_text(self, content: str, base_path: Optional[Path]) -> QWidget:
        html = render_markdown(content, base_path=base_path)
        content_label = BodyLabel()
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.RichText)
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        content_label.setOpenExternalLinks(False)
        content_label.linkActivated.connect(self._on_link_activated)
        content_label.setText(html)
        return content_label

    def _create_json_viewer_from_text(self, raw: str) -> QWidget:
        try:
            data = jsonc.loads(raw)
        except Exception:
            fallback = BodyLabel(raw)
            fallback.setWordWrap(True)
            return fallback

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(6)

        if isinstance(data, dict):
            for key, value in data.items():
                root_layout.addWidget(self._create_json_item_widget(str(key), value, depth=0))
        elif isinstance(data, list):
            for idx, value in enumerate(data):
                root_layout.addWidget(self._create_json_item_widget(f"[{idx}]", value, depth=0))
        else:
            root_layout.addWidget(self._create_json_leaf_widget("value", data))

        return root

    def _create_json_item_widget(self, key: str, value: Any, depth: int) -> QWidget:
        card = SimpleCardWidget()
        card.setBorderRadius(8)
        layout = self._safe_get_card_layout(card)
        layout.setContentsMargins(10 + depth * 4, 8, 10, 8)
        layout.setSpacing(6)

        if isinstance(value, dict):
            header = BodyLabel(str(key))
            layout.addWidget(header)
            for child_key, child_value in value.items():
                layout.addWidget(self._create_json_item_widget(str(child_key), child_value, depth + 1))
            return card

        if isinstance(value, list):
            header = BodyLabel(str(key))
            layout.addWidget(header)
            for idx, child_value in enumerate(value):
                layout.addWidget(self._create_json_item_widget(f"[{idx}]", child_value, depth + 1))
            return card

        layout.addWidget(self._create_json_leaf_widget(key, value))
        return card

    def _create_json_leaf_widget(self, key: str, value: Any) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        key_label = BodyLabel(str(key))
        key_label.setMinimumWidth(120)
        row_layout.addWidget(key_label, 0)

        value_text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        value_label = BodyLabel(value_text)
        value_label.setWordWrap(True)
        row_layout.addWidget(value_label, 1)
        return row

    def _on_link_activated(self, link_or_url: str | QUrl):
        if isinstance(link_or_url, QUrl):
            link = link_or_url.toString()
        else:
            link = str(link_or_url)

        if link.startswith("image:"):
            image_path = link[6:]
            dialog = ImagePreviewDialog(image_path, self)
            dialog.exec()
            return

        QDesktopServices.openUrl(QUrl(link))

    def init_config(self):
        self.current_value = None

    def set_value(self, value: Any, skip_animation: bool = True):
        self.current_value = None

    def get_option(self) -> Dict[str, Any]:
        return {}

    def get_simple_option(self) -> Any:
        return None


__all__ = ["ShowOptionItem"]
