from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QApplication,
)
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SimpleCardWidget,
    SubtitleLabel,
)

from app.core.plugins.plugin_base import PluginBase, PluginContext, PluginMeta


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class IndexEntry:
    __slots__ = (
        "source_file",
        "entry_id",
        "display_name",
        "copy_key",
        "rarity",
        "element",
        "weapon",
        "effect_keys",
        "tags",
        "jp_name",
        "rel_path",
        "image_path",
    )

    def __init__(
        self,
        source_file: str,
        entry_id: str,
        display_name: str,
        copy_key: str,
        rarity: int | None,
        element: str,
        weapon: str,
        effect_keys: list[str],
        tags: list[str],
        jp_name: str,
        rel_path: str,
        image_path: Path | None,
    ) -> None:
        self.source_file = source_file
        self.entry_id = entry_id
        self.display_name = display_name
        self.copy_key = copy_key
        self.rarity = rarity
        self.element = element
        self.weapon = weapon
        self.effect_keys = effect_keys
        self.tags = tags
        self.jp_name = jp_name
        self.rel_path = rel_path
        self.image_path = image_path


class ImageEntryCard(QFrame):
    clicked = Signal(str)

    def __init__(self, entry: IndexEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entry = entry
        self._selected = False
        self.setObjectName("imageEntryCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(196, 248)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(6)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedHeight(170)
        self.image_label.setStyleSheet("background: transparent;")

        self.name_label = QLabel(entry.display_name, self)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("font-size: 13px; font-weight: 600;")

        meta_parts: list[str] = []
        if entry.rarity is not None:
            meta_parts.append(f"{entry.rarity}★")
        if entry.element:
            meta_parts.append(entry.element)
        if entry.weapon:
            meta_parts.append(entry.weapon)

        self.meta_label = QLabel(" | ".join(meta_parts), self)
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meta_label.setWordWrap(True)
        self.meta_label.setStyleSheet("font-size: 12px; color: rgba(120, 120, 120, 1);")

        root_layout.addWidget(self.image_label)
        root_layout.addWidget(self.name_label)
        root_layout.addWidget(self.meta_label)

        self._set_pixmap(entry.image_path)
        self.set_selected(False)

    def _set_pixmap(self, image_path: Path | None) -> None:
        if image_path is None or not image_path.is_file():
            self.image_label.setText("无图片")
            self.image_label.setStyleSheet("color: rgba(140, 140, 140, 1);")
            return

        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self.image_label.setText("图片损坏")
            self.image_label.setStyleSheet("color: rgba(140, 140, 140, 1);")
            return

        scaled = pixmap.scaled(
            170,
            170,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        if self._selected:
            self.setStyleSheet(
                "QFrame#imageEntryCard {"
                "border: 2px solid rgba(255, 132, 132, 1);"
                "border-radius: 10px;"
                "background: rgba(255, 239, 239, 0.65);"
                "}"
            )
        else:
            self.setStyleSheet(
                "QFrame#imageEntryCard {"
                "border: 1px solid rgba(0, 0, 0, 0.1);"
                "border-radius: 10px;"
                "background: rgba(255, 255, 255, 0.25);"
                "}"
            )

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.entry.entry_id)
        super().mousePressEvent(event)


class IndexImagePickerPlugin(PluginBase):
    meta = PluginMeta(
        plugin_id="mah.index_image_picker",
        name="资源索引选图器",
        version="1.0.0",
        description="按 index 条件筛选并选中图片，复制对应 key",
        icon="LIBRARY",
    )

    def __init__(self) -> None:
        self._ctx: PluginContext | None = None
        self._widget: QWidget | None = None
        self._enabled = True

        self._index_dir: Path | None = None
        self._image_roots: list[Path] = []
        self._entries_by_file: dict[str, list[IndexEntry]] = {}

        self._cards: dict[str, ImageEntryCard] = {}
        self._selected_entry_id: str | None = None

    def on_load(self, ctx: PluginContext) -> None:
        self._ctx = ctx
        self._index_dir = self._discover_index_dir()
        self._image_roots = self._discover_image_roots()
        self._load_all_entries()

        if self._ctx is not None:
            self._ctx.logger.info(
                "IndexImagePickerPlugin 已加载，index_dir=%s, image_roots=%s",
                self._index_dir,
                self._image_roots,
            )

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        if self._widget is not None:
            return self._widget

        root = QWidget(parent)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(14)

        left_card = SimpleCardWidget(root)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)

        right_card = SimpleCardWidget(root)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)

        root_layout.addWidget(left_card, 4)
        root_layout.addWidget(right_card, 6)

        left_layout.addWidget(SubtitleLabel("索引筛选", left_card))

        self.file_combo = ComboBox(left_card)
        self.file_combo.addItems(self._available_files())
        self.file_combo.currentTextChanged.connect(self._on_file_changed)
        left_layout.addWidget(BodyLabel("索引文件", left_card))
        left_layout.addWidget(self.file_combo)

        self.filter_stack = QStackedWidget(left_card)
        left_layout.addWidget(self.filter_stack)

        self.character_filter_widget = self._build_character_filter_widget(left_card)
        self.ar_filter_widget = self._build_ar_filter_widget(left_card)
        self.filter_stack.addWidget(self.character_filter_widget)
        self.filter_stack.addWidget(self.ar_filter_widget)

        button_row = QHBoxLayout()
        self.search_button = PrimaryPushButton("查找", left_card)
        self.search_button.clicked.connect(self._on_search_clicked)
        self.copy_button = PushButton("复制名称", left_card)
        self.copy_button.clicked.connect(self._on_copy_clicked)
        button_row.addWidget(self.search_button)
        button_row.addWidget(self.copy_button)
        left_layout.addLayout(button_row)

        self.selected_label = BodyLabel("未选择", left_card)
        self.result_label = BodyLabel("结果数：0", left_card)
        self.status_label = BodyLabel("", left_card)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: rgba(120, 120, 120, 1);")
        left_layout.addWidget(self.selected_label)
        left_layout.addWidget(self.result_label)
        left_layout.addWidget(self.status_label)
        left_layout.addStretch(1)

        right_layout.addWidget(SubtitleLabel("筛选结果", right_card))
        self.gallery_scroll = QScrollArea(right_card)
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.gallery_container = QWidget(self.gallery_scroll)
        self.gallery_grid = QGridLayout(self.gallery_container)
        self.gallery_grid.setContentsMargins(0, 0, 0, 0)
        self.gallery_grid.setSpacing(10)
        self.gallery_scroll.setWidget(self.gallery_container)
        right_layout.addWidget(self.gallery_scroll)

        self._widget = root
        self._on_file_changed(self.file_combo.currentText())
        return root

    def on_unload(self) -> None:
        self._ctx = None
        self._widget = None
        self._cards.clear()
        self._selected_entry_id = None

    def on_enable_changed(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if self._ctx is not None:
            self._ctx.logger.info("IndexImagePickerPlugin enabled=%s", self._enabled)

    def _build_character_filter_widget(self, parent: QWidget) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(BodyLabel("星级", widget))
        self.character_rarity_combo = ComboBox(widget)
        layout.addWidget(self.character_rarity_combo)

        layout.addWidget(BodyLabel("属性", widget))
        self.character_element_combo = ComboBox(widget)
        layout.addWidget(self.character_element_combo)

        layout.addWidget(BodyLabel("武器", widget))
        self.character_weapon_combo = ComboBox(widget)
        layout.addWidget(self.character_weapon_combo)

        return widget

    def _build_ar_filter_widget(self, parent: QWidget) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(BodyLabel("星级", widget))
        self.ar_rarity_combo = ComboBox(widget)
        layout.addWidget(self.ar_rarity_combo)

        layout.addWidget(BodyLabel("效果", widget))
        self.ar_effect_combo = ComboBox(widget)
        layout.addWidget(self.ar_effect_combo)

        layout.addWidget(BodyLabel("Tag（空格分隔）", widget))
        self.ar_tag_edit = LineEdit(widget)
        self.ar_tag_edit.setPlaceholderText("例如: 7thAnniversary exchange")
        layout.addWidget(self.ar_tag_edit)

        layout.addWidget(BodyLabel("日文名包含", widget))
        self.ar_jp_edit = LineEdit(widget)
        self.ar_jp_edit.setPlaceholderText("可选")
        layout.addWidget(self.ar_jp_edit)

        return widget

    def _discover_index_dir(self) -> Path | None:
        cwd = Path.cwd()
        candidates = [
            cwd / "resource" / "index",
            cwd / "assets" / "index",
            cwd.parent / "mah_res" / "index",
            cwd.parent / "MAH" / "assets" / "index",
        ]

        for candidate in candidates:
            if (candidate / "characters.json").is_file() or (candidate / "ar.json").is_file():
                return candidate

        return None

    def _discover_image_roots(self) -> list[Path]:
        cwd = Path.cwd()
        candidates = [
            cwd / "resource" / "base" / "image",
            cwd / "assets" / "resource" / "base" / "image",
            cwd.parent / "mah_res" / "image",
            cwd.parent / "MAH" / "assets" / "resource" / "base" / "image",
        ]
        return [p for p in candidates if p.is_dir()]

    def _available_files(self) -> list[str]:
        if self._index_dir is None:
            return ["characters.json", "ar.json"]

        preferred = ["characters.json", "ar.json"]
        available = [name for name in preferred if (self._index_dir / name).is_file()]
        return available or preferred

    def _load_all_entries(self) -> None:
        self._entries_by_file.clear()
        for file_name in ("characters.json", "ar.json"):
            self._entries_by_file[file_name] = self._load_entries_for(file_name)

    def _load_entries_for(self, file_name: str) -> list[IndexEntry]:
        if self._index_dir is None:
            return []

        file_path = self._index_dir / file_name
        if not file_path.is_file():
            return []

        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._emit_info("error", f"读取 {file_name} 失败: {exc}")
            if self._ctx is not None:
                self._ctx.logger.error("读取 %s 失败: %s", file_name, exc)
            return []

        entries: list[IndexEntry] = []
        if file_name == "characters.json":
            for char_key, forms in raw.items():
                if not isinstance(forms, dict):
                    continue
                for form_key, payload in forms.items():
                    if not isinstance(payload, dict):
                        continue
                    rel_path = str(payload.get("path", "")).strip()
                    entry = IndexEntry(
                        source_file=file_name,
                        entry_id=f"character::{char_key}::{form_key}",
                        display_name=f"{char_key} / {form_key}",
                        copy_key=str(char_key),
                        rarity=self._to_int(payload.get("rarity")),
                        element=str(payload.get("element", "")).strip(),
                        weapon=str(payload.get("weapon", "")).strip(),
                        effect_keys=[],
                        tags=[],
                        jp_name="",
                        rel_path=rel_path,
                        image_path=self._resolve_image_path(rel_path),
                    )
                    entries.append(entry)

        elif file_name == "ar.json":
            for ar_key, payload in raw.items():
                if not isinstance(payload, dict):
                    continue
                effect = payload.get("effect")
                effect_keys: list[str] = []
                if isinstance(effect, dict):
                    effect_keys = [str(k).strip() for k in effect.keys() if str(k).strip()]

                tags = payload.get("tag")
                tag_list: list[str] = []
                if isinstance(tags, list):
                    tag_list = [str(item).strip() for item in tags if str(item).strip()]

                rel_path = str(payload.get("path", "")).strip()
                entry = IndexEntry(
                    source_file=file_name,
                    entry_id=f"ar::{ar_key}",
                    display_name=str(ar_key),
                    copy_key=str(ar_key),
                    rarity=self._to_int(payload.get("rarity")),
                    element="",
                    weapon="",
                    effect_keys=effect_keys,
                    tags=tag_list,
                    jp_name=str(payload.get("jp_rawname", "")).strip(),
                    rel_path=rel_path,
                    image_path=self._resolve_image_path(rel_path),
                )
                entries.append(entry)

        return entries

    def _resolve_image_path(self, rel_path: str) -> Path | None:
        normalized = str(rel_path or "").strip().replace("\\", "/")
        if not normalized:
            return None

        for root in self._image_roots:
            candidate = (root / normalized).resolve()

            # 形如 ar/xxx.png
            if candidate.is_file() and candidate.suffix.lower() in IMAGE_SUFFIXES:
                return candidate

            # 形如 character/aegir/02/default/*.png
            if candidate.is_dir():
                default_dir = candidate / "default"
                from_default = self._first_image_in(default_dir)
                if from_default is not None:
                    return from_default

                direct = self._first_image_in(candidate)
                if direct is not None:
                    return direct

        return None

    def _first_image_in(self, folder: Path) -> Path | None:
        if not folder.is_dir():
            return None
        for path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                return path
        return None

    def _on_file_changed(self, file_name: str) -> None:
        file_name = str(file_name or "").strip()
        entries = self._entries_by_file.get(file_name, [])

        if file_name == "ar.json":
            self.filter_stack.setCurrentWidget(self.ar_filter_widget)
            self._reload_ar_filter_options(entries)
        else:
            self.filter_stack.setCurrentWidget(self.character_filter_widget)
            self._reload_character_filter_options(entries)

        self._status_text_for_source(file_name)
        self._show_empty_content("无内容")

    def _reload_character_filter_options(self, entries: list[IndexEntry]) -> None:
        rarity_values = sorted({str(item.rarity) for item in entries if item.rarity is not None}, key=lambda x: int(x))
        element_values = sorted({item.element for item in entries if item.element})
        weapon_values = sorted({item.weapon for item in entries if item.weapon})

        self._set_combo_items(self.character_rarity_combo, ["全部", *rarity_values])
        self._set_combo_items(self.character_element_combo, ["全部", *element_values])
        self._set_combo_items(self.character_weapon_combo, ["全部", *weapon_values])

    def _reload_ar_filter_options(self, entries: list[IndexEntry]) -> None:
        rarity_values = sorted({str(item.rarity) for item in entries if item.rarity is not None}, key=lambda x: int(x))
        effect_values = sorted({effect for item in entries for effect in item.effect_keys if effect})

        self._set_combo_items(self.ar_rarity_combo, ["全部", *rarity_values])
        self._set_combo_items(self.ar_effect_combo, ["全部", *effect_values])

    def _set_combo_items(self, combo: ComboBox, values: list[str]) -> None:
        combo.clear()
        combo.addItems(values)
        combo.setCurrentIndex(0)

    def _on_search_clicked(self) -> None:
        file_name = str(self.file_combo.currentText() or "").strip()
        entries = self._entries_by_file.get(file_name, [])
        filtered = self._apply_filters(file_name, entries)
        self._render_entries(filtered)

    def _apply_filters(self, file_name: str, entries: list[IndexEntry]) -> list[IndexEntry]:
        if file_name == "ar.json":
            rarity_text = str(self.ar_rarity_combo.currentText() or "全部")
            effect_text = str(self.ar_effect_combo.currentText() or "全部")
            jp_contains = self.ar_jp_edit.text().strip().lower()
            tag_tokens = [token for token in self.ar_tag_edit.text().strip().lower().split() if token]

            result: list[IndexEntry] = []
            for entry in entries:
                if rarity_text != "全部" and str(entry.rarity) != rarity_text:
                    continue
                if effect_text != "全部" and effect_text not in entry.effect_keys:
                    continue
                if jp_contains and jp_contains not in entry.jp_name.lower():
                    continue
                if tag_tokens:
                    entry_tags = [tag.lower() for tag in entry.tags if tag]
                    if not all(any(token in tag for tag in entry_tags) for token in tag_tokens):
                        continue
                result.append(entry)
            return result

        rarity_text = str(self.character_rarity_combo.currentText() or "全部")
        element_text = str(self.character_element_combo.currentText() or "全部")
        weapon_text = str(self.character_weapon_combo.currentText() or "全部")

        result = []
        for entry in entries:
            if rarity_text != "全部" and str(entry.rarity) != rarity_text:
                continue
            if element_text != "全部" and entry.element != element_text:
                continue
            if weapon_text != "全部" and entry.weapon != weapon_text:
                continue
            result.append(entry)
        return result

    def _render_entries(self, entries: list[IndexEntry]) -> None:
        self._clear_gallery()
        self.result_label.setText(f"结果数：{len(entries)}")

        if not entries:
            self._show_empty_content("无内容")
            return

        columns = 3
        for index, entry in enumerate(entries):
            row = index // columns
            col = index % columns
            card = ImageEntryCard(entry, self.gallery_container)
            card.clicked.connect(self._on_entry_card_clicked)
            self.gallery_grid.addWidget(card, row, col)
            self._cards[entry.entry_id] = card

        self.gallery_grid.setRowStretch((len(entries) // columns) + 1, 1)

        # 保留仍可见的已选项
        if self._selected_entry_id and self._selected_entry_id in self._cards:
            self._select_card(self._selected_entry_id)
        else:
            self._selected_entry_id = None
            self.selected_label.setText("未选择")

    def _clear_gallery(self) -> None:
        self._cards.clear()
        while self.gallery_grid.count() > 0:
            item = self.gallery_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_empty_content(self, text: str) -> None:
        self._clear_gallery()
        self.result_label.setText("结果数：0")
        self.selected_label.setText("未选择")
        self._selected_entry_id = None
        empty_label = QLabel(text, self.gallery_container)
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gallery_grid.addWidget(empty_label, 0, 0)

    def _on_entry_card_clicked(self, entry_id: str) -> None:
        self._select_card(entry_id)

    def _select_card(self, entry_id: str) -> None:
        if entry_id not in self._cards:
            return

        for card_id, card in self._cards.items():
            card.set_selected(card_id == entry_id)

        self._selected_entry_id = entry_id
        selected = self._cards[entry_id].entry
        self.selected_label.setText(
            f"已选择：{selected.display_name}  → 复制值：{selected.copy_key}"
        )

    def _on_copy_clicked(self) -> None:
        if self._selected_entry_id is None or self._selected_entry_id not in self._cards:
            self._emit_info("warning", "请先点击右侧图片进行选择")
            return

        selected = self._cards[self._selected_entry_id].entry
        clipboard = QApplication.clipboard()
        clipboard.setText(selected.copy_key)
        self._emit_info("success", f"已复制：{selected.copy_key}")

    def _status_text_for_source(self, file_name: str) -> None:
        index_text = str(self._index_dir) if self._index_dir is not None else "未找到 index 目录"
        image_text = "\n".join(str(path) for path in self._image_roots) if self._image_roots else "未找到图片目录"
        self.status_label.setText(
            f"当前文件：{file_name}\n索引目录：{index_text}\n图片目录：{image_text}"
        )

    def _emit_info(self, level: str, text: str) -> None:
        if self._ctx is None:
            return
        self._ctx.signal_bus.info_bar_requested.emit(level, text)

    @staticmethod
    def _to_int(value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


def create_plugin() -> PluginBase:
    return IndexImagePickerPlugin()
