"""
选项表单组件
从 form_structure 生成选项表单，包含多个选项项组件
"""
import warnings
from copy import deepcopy
from typing import Dict, Any, Optional, TYPE_CHECKING
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame
from qfluentwidgets import BodyLabel, SwitchButton
from app.utils.logger import logger
from app.core.utils.option_binding import (
    BINDING_ACTIVE_KEY,
    binding_value_key,
    get_active_target_entry,
    get_binding_active_map,
    iter_binding_sources,
    normalize_target_entries,
    option_payload_value,
    upsert_entry_by_value,
    ensure_entry_payload,
)
from app.view.task_interface.components.Option_Framework.items import (
    OptionItemBase,
    OptionItemRegistry,
)
from app.view.task_interface.components.Option_Framework.animations import HeightAnimator

if TYPE_CHECKING:
    from app.view.task_interface.components.Option_Framework.items import OptionItemBase


class _ClickableHeader(QWidget):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class OptionFormWidget(QWidget):
    """
    选项表单组件
    根据 form_structure 动态生成选项表单
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        初始化选项表单组件
        
        :param parent: 父组件
        """
        super().__init__(parent)
        self.option_items: Dict[str, "OptionItemBase"] = {}  # 选项项组件字典
        self.form_structure: Dict[str, Any] = {}  # 表单结构
        self.binding_global_switches: Dict[str, SwitchButton] = {}
        self._task_config_snapshot: Dict[str, Any] = {}
        self.binding_global_panel: Optional[QWidget] = None
        self._binding_global_content: Optional[QWidget] = None
        self._binding_global_header_arrow: Optional[BodyLabel] = None
        self._binding_global_animator: Optional[HeightAnimator] = None
        self._binding_global_expanded = False
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
    
    def build_from_structure(self, form_structure: Dict[str, Any], config: Optional[Dict[str, Any]] = None):
        """
        根据表单结构生成选项表单
        
        :param form_structure: 表单结构字典
        :param config: 可选的初始配置字典
        """
        self.form_structure = form_structure
        self._task_config_snapshot = deepcopy(config or {})
        
        # 清空现有的选项项
        self._clear_options()
        
        # 遍历表单结构，创建选项项
        for key, item_config in form_structure.items():
            # 跳过非选项字段（如 description）
            if key == "description" or not isinstance(item_config, dict):
                continue

            # 处理缺失的 type 字段（向后兼容）
            option_config = dict(item_config)
            if "type" not in option_config:
                option_config["type"] = "combobox"
                logger.debug(f"选项 {key} 缺失 type，默认作为 combobox 处理")

            # 使用注册器创建选项项组件
            option_item = OptionItemRegistry.create(key, option_config, self)
            
            # 预创建子选项（如果存在）
            if "children" in option_config:
                for option_value, child_config in option_config["children"].items():
                    option_item.add_child_option(option_value, child_config)
            
            # 保存选项项引用
            self.option_items[key] = option_item
            
            # 添加到布局
            self.main_layout.addWidget(option_item)

        self._build_binding_global_panel()
        self._sync_binding_global_switches(config or {})
        
        # 如果有初始配置，应用它
        if config:
            self.apply_config(config)
    
    def _clear_options(self):
        """清空所有选项项"""
        # 先断开所有信号连接，防止在清理过程中触发不必要的信号
        for option_item in list(self.option_items.values()):
            if option_item is None:
                continue
            signal = getattr(option_item, "option_changed", None)
            if signal is None:
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    signal.disconnect()
            except Exception:
                pass  # 如果没有连接或接收端已失效，忽略
        
        # 收集所有需要删除的控件
        widgets_to_delete = []
        layouts_to_delete = []
        
        # 移除所有选项项组件
        while self.main_layout.count() > 0:
            item = self.main_layout.takeAt(0)
            
            # 处理不同类型的布局项
            if item.widget():
                widget = item.widget()
                if widget:
                    widget.hide()
                    widget.setParent(None)
                widgets_to_delete.append(widget)
            elif item.layout():
                layout = item.layout()
                # 递归清理子布局中的控件
                while layout.count() > 0:
                    child_item = layout.takeAt(0)
                    if child_item.widget():
                        child_widget = child_item.widget()
                        if child_widget:
                            child_widget.hide()
                            child_widget.setParent(None)
                        widgets_to_delete.append(child_widget)
                    elif child_item.layout():
                        # 嵌套的子布局也要清理
                        child_layout = child_item.layout()
                        while child_layout.count() > 0:
                            nested_item = child_layout.takeAt(0)
                            if nested_item.widget():
                                nested_widget = nested_item.widget()
                                if nested_widget:
                                    nested_widget.hide()
                                    nested_widget.setParent(None)
                                widgets_to_delete.append(nested_widget)
                        layouts_to_delete.append(child_layout)
                layouts_to_delete.append(layout)
            # spacer 会被 takeAt 自动清理，不需要手动处理
        
        # 清空选项项字典
        self.option_items.clear()
        self.binding_global_switches.clear()
        self.binding_global_panel = None
        self._binding_global_content = None
        self._binding_global_header_arrow = None
        self._binding_global_animator = None
        self._binding_global_expanded = False
        
        # 删除所有布局
        for layout in layouts_to_delete:
            layout.deleteLater()
        
        # 删除所有控件
        for widget in widgets_to_delete:
            widget.deleteLater()
        
        # 确保布局完全清空（处理可能遗漏的项）
        remaining_count = 0
        max_iterations = 100  # 防止无限循环
        iteration = 0
        while self.main_layout.count() > 0 and iteration < max_iterations:
            item = self.main_layout.takeAt(0)
            # 删除剩余的项
            if item:
                if item.widget():
                    widget = item.widget()
                    if widget:
                        widget.hide()
                        widget.setParent(None)
                        widget.deleteLater()
                elif item.layout():
                    layout = item.layout()
                    layout.deleteLater()
            iteration += 1
            remaining_count = self.main_layout.count()
        
        # 如果还有剩余项，记录警告
        if remaining_count > 0:
            logger.warning(f"布局未完全清空，剩余 {remaining_count} 项")
        
        # 重置布局属性，确保下次添加时状态正确
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 强制更新布局和几何结构，确保界面刷新
        self.updateGeometry()
        self.update()
    
    def apply_config(self, config: Dict[str, Any]):
        """
        应用配置到表单
        
        :param config: 配置字典
        """
        self._task_config_snapshot = deepcopy(config or {})
        self._sync_binding_global_switches(config)
        config = self._prepare_config_for_binding(config)

        # 第一步：先隐藏所有子选项容器
        for option_item in self.option_items.values():
            if option_item.config_type in ["combobox", "switch", "checkbox"]:
                for child_widget in option_item.child_options.values():
                    child_widget.setVisible(False)
                option_item.children_wrapper.setVisible(False)
        
        # 第二步：应用配置并设置值
        for key, value in config.items():
            if key in self.option_items:
                option_item = self.option_items[key]
                self._apply_option_item_config(option_item, value)
        
        # 第三步：最后确保所有选项项的子选项可见性正确（只显示当前选中值对应的子选项）
        # 注意：由于 set_value 已经调用了 _update_children_visibility，这里只需要处理那些没有通过 set_value 设置的选项
        # 实际上，如果所有选项都通过 set_value 设置，这一步可能是多余的，但保留作为保险
        for option_item in self.option_items.values():
            if option_item.config_type in ["combobox", "switch"]:
                # 只在选项值已设置但子选项可见性可能不正确时才更新（跳过动画）
                # 由于 set_value 已经处理了可见性，这里主要是为了处理边缘情况
                if option_item.current_value is not None:
                    option_item._update_children_visibility(option_item.current_value, skip_animation=True)
            elif option_item.config_type == "checkbox":
                # checkbox 类型使用自己的子选项更新逻辑
                if option_item.current_value is not None:
                    option_item._update_children_for_checkbox(skip_animation=True)
    
    def _apply_single_child_config(self, option_item: "OptionItemBase", option_value: str, child_config: Any):
        """
        应用单个子选项的配置
        
        :param option_item: 选项项组件
        :param option_value: 子选项的值（当前选中值）
        :param child_config: 子选项配置
        """
        if option_value in option_item.config.get("children", {}):
            child_structure = option_item.config["children"][option_value]
            option_item.add_child_option(option_value, child_structure)

        if isinstance(child_config, list):
            for config_item in child_config:
                self._apply_single_child_config(option_item, option_value, config_item)
            return

        child_widget = option_item.find_child_widget(option_value, child_config)
        if child_widget:
            self._apply_child_widget_config(child_widget, child_config)

    def _apply_child_widget_config(self, child_widget: "OptionItemBase", child_config: Any):
        """将配置应用到已定位的子选项控件"""
        # 注意：不需要设置可见性，因为 set_value 已经通过 _update_children_visibility 处理了
        if isinstance(child_config, dict):
            # 如果是配置格式（包含 value 字段）
            if "value" in child_config:
                children_config = child_config.get("children", {})

                # 设置子选项的值（这会触发子选项的 _update_children_visibility）
                child_widget.set_value(child_config["value"])

                # 如果有子选项的子选项，递归应用（使用 _apply_children_config 以支持 hidden 字段）
                if children_config:
                    self._apply_children_config(child_widget, children_config)
            else:
                # 如果字典不包含 value 字段，可能是输入框的值（inputs 类型）
                if child_widget.config_type in ["lineedit", "input", "inputs"]:
                    child_widget.set_value(child_config)
                else:
                    logger.warning(f"子选项类型 {child_widget.config_type} 不应该接收字典值: {child_config}")
        else:
            child_widget.set_value(child_config)

    def _apply_option_item_config(
        self, option_item: "OptionItemBase", value: Any
    ) -> None:
        if isinstance(value, dict):
            if "value" in value:
                children_config = value.get("children", {})
                option_item.set_value(value["value"])
                if children_config:
                    self._apply_children_config(option_item, children_config)
            else:
                option_item.set_value(value)
        else:
            option_item.set_value(value)
    
    def _apply_children_config(self, option_item: "OptionItemBase", children_config: Dict[str, Any]):
        """
        应用子选项配置，兼容多种配置格式：
        1. config_key 是 option_value（如 "自行输入角色名"）
        2. config_key 是旧格式的内部 key（如 "选择A级角色_child_自行输入角色名_输入A级角色名_0"）
        3. config_key 是 child_name（如 "输入A级角色名"）
        会跳过标记为 hidden 的子选项。
        """
        if not children_config:
            return

        child_definitions = option_item.config.get("children", {})

        for config_key, child_cfg in children_config.items():
            # 跳过标记为 hidden 的子选项（hidden=True）
            if isinstance(child_cfg, dict) and child_cfg.get("hidden", False):
                logger.debug(f"跳过隐藏的子选项: option_key={option_item.key}, config_key={config_key}")
                continue
            
            option_value = None
            child_widget = None
            
            # 尝试方式1：config_key 是 option_value
            if config_key in child_definitions:
                option_value = config_key
            
            # 尝试方式2：config_key 是旧格式的内部 key
            if not option_value:
                option_value = option_item.get_option_value_for_child_key(config_key)
                if option_value:
                    child_widget = option_item.child_options.get(config_key)
            
            # 尝试方式3：config_key 是 child_name
            if not option_value:
                result = option_item.find_child_by_name(config_key)
                if result:
                    option_value, child_widget = result

            if option_value and child_cfg:
                # 如果 child_cfg 是字典且包含 hidden 字段（但 hidden=False），移除 hidden 字段后应用
                if isinstance(child_cfg, dict) and "hidden" in child_cfg:
                    # 移除 hidden 字段，保留其他配置
                    actual_cfg = {k: v for k, v in child_cfg.items() if k != "hidden"}
                    # 如果移除 hidden 后只剩下 value 字段，直接使用 value
                    if len(actual_cfg) == 1 and "value" in actual_cfg:
                        actual_cfg = actual_cfg["value"]
                    if child_widget:
                        self._apply_child_widget_config(child_widget, actual_cfg)
                    else:
                        self._apply_single_child_config(option_item, option_value, actual_cfg)
                else:
                    if child_widget:
                        self._apply_child_widget_config(child_widget, child_cfg)
                    else:
                        self._apply_single_child_config(option_item, option_value, child_cfg)
            else:
                logger.debug(
                    f"跳过无效的子选项配置: option_key={option_item.key}, config_key={config_key}"
                )
    
    def get_options(self) -> Dict[str, Any]:
        """
        获取当前所有选项的配置（递归获取子选项）
        
        :return: 选项配置字典
        """
        result = {}
        
        for key, option_item in self.option_items.items():
            if bool(option_item.config.get("non_persistent", False)):
                continue
            result[key] = option_item.get_option()

        result = self._apply_binding_to_options(result)
        self._task_config_snapshot.update(deepcopy(result))
        for source_key, _target_key in iter_binding_sources(
            self.form_structure, logger=logger
        ):
            if source_key not in result:
                self._task_config_snapshot.pop(source_key, None)
        
        return result
    
    def get_simple_options(self) -> Dict[str, Any]:
        """
        获取简单的选项值（不包含嵌套的 children 结构）
        
        :return: 选项值字典
        """
        result = {}
        
        for key, option_item in self.option_items.items():
            if bool(option_item.config.get("non_persistent", False)):
                continue
            result[key] = option_item.get_simple_option()
        
        return result

    def _build_binding_global_panel(self) -> None:
        binding_sources = list(iter_binding_sources(self.form_structure, logger=logger))
        if not binding_sources:
            return

        panel = QFrame(self)
        panel.setObjectName("BindingGlobalPanel")
        panel.setStyleSheet(
            """
            QFrame#BindingGlobalPanel {
                border: 1px solid rgba(128, 128, 128, 0.22);
                border-radius: 6px;
                margin-top: 6px;
            }
            """
        )
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 6, 8, 6)
        panel_layout.setSpacing(4)

        header = _ClickableHeader(panel)
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        arrow = BodyLabel(">")
        arrow.setFixedWidth(14)
        title = BodyLabel(self.tr("Global Settings"))
        count_label = BodyLabel(
            self.tr("{count} item(s)").format(count=len(binding_sources))
        )
        count_label.setStyleSheet("color: gray;")

        header_layout.addWidget(arrow)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(count_label)
        panel_layout.addWidget(header)

        content = QWidget(panel)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 4, 0, 0)
        content_layout.setSpacing(4)

        for source_key, _target_key in binding_sources:
            option_item = self.option_items.get(source_key)
            if option_item is None:
                continue
            self._add_binding_global_switch(source_key, option_item, content_layout)

        panel_layout.addWidget(content)

        self.binding_global_panel = panel
        self._binding_global_content = content
        self._binding_global_header_arrow = arrow
        self._binding_global_animator = HeightAnimator(content, duration=180, parent=self)
        self._binding_global_expanded = False
        content.setVisible(False)
        content.setMaximumHeight(0)
        header.clicked.connect(self._toggle_binding_global_panel)

        self.main_layout.addWidget(panel)

    def _add_binding_global_switch(
        self,
        source_key: str,
        option_item: "OptionItemBase",
        parent_layout: QVBoxLayout,
    ) -> None:
        switch_container = QWidget(self.binding_global_panel or self)
        switch_layout = QHBoxLayout(switch_container)
        switch_layout.setContentsMargins(0, 2, 0, 2)
        switch_layout.setSpacing(8)

        label_text = str(option_item.config.get("label") or source_key)
        label = BodyLabel(label_text)
        switch_layout.addWidget(label)
        switch_layout.addStretch()

        switch = SwitchButton(parent=switch_container)
        switch.setOnText(self.tr("On"))
        switch.setOffText(self.tr("Off"))
        switch_layout.addWidget(switch)

        switch.checkedChanged.connect(
            lambda _checked, key=source_key, item=option_item: item.option_changed.emit(
                key, item.current_value
            )
        )
        parent_layout.addWidget(switch_container)
        self.binding_global_switches[source_key] = switch

    def _toggle_binding_global_panel(self) -> None:
        content = self._binding_global_content
        animator = self._binding_global_animator
        if content is None or animator is None:
            return

        self._binding_global_expanded = not self._binding_global_expanded
        self._update_binding_global_header()

        if self._binding_global_expanded:
            animator.expand()
        else:
            animator.collapse()

    def _update_binding_global_header(self) -> None:
        if self._binding_global_header_arrow is not None:
            self._binding_global_header_arrow.setText(
                "v" if self._binding_global_expanded else ">"
            )

    def _sync_binding_global_switches(self, config: Dict[str, Any]) -> None:
        for source_key, switch in self.binding_global_switches.items():
            checked = self._is_binding_global_enabled(source_key, config)
            switch.blockSignals(True)
            try:
                switch.setChecked(checked)
            finally:
                switch.blockSignals(False)

    def _is_binding_global_enabled(
        self, source_key: str, config: Dict[str, Any]
    ) -> bool:
        if source_key in (config or {}):
            return True
        target_key = self._binding_target_for_source(source_key)
        if not target_key:
            return True
        active_entry = get_active_target_entry(config or {}, target_key)
        if isinstance(active_entry, dict) and source_key in active_entry:
            return False
        return True

    def _binding_target_for_source(self, source_key: str) -> Optional[str]:
        for current_source, target_key in iter_binding_sources(
            self.form_structure, logger=logger
        ):
            if current_source == source_key:
                return target_key
        return None

    def _prepare_config_for_binding(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        prepared = deepcopy(config or {})
        for source_key, target_key in iter_binding_sources(
            self.form_structure, logger=logger
        ):
            active_entry = get_active_target_entry(config or {}, target_key)
            if active_entry:
                prepared[target_key] = active_entry

            if not self._is_binding_global_enabled(source_key, config or {}):
                if isinstance(active_entry, dict) and source_key in active_entry:
                    prepared[source_key] = active_entry[source_key]
        return prepared

    def _apply_binding_to_options(
        self, raw_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = deepcopy(raw_options)
        active_map = get_binding_active_map(self._task_config_snapshot)

        for source_key, target_key in iter_binding_sources(
            self.form_structure, logger=logger
        ):
            if target_key not in raw_options:
                continue

            target_payload = raw_options.get(target_key)
            active_value = option_payload_value(target_payload)
            active_map[target_key] = active_value

            existing_payload = (
                result.get(target_key)
                if isinstance(result.get(target_key), list)
                else self._task_config_snapshot.get(target_key)
            )
            entries = normalize_target_entries(existing_payload)
            new_entry = ensure_entry_payload(target_payload)
            replace_keys: set[str] = set()

            if not self._is_binding_switch_global(source_key):
                source_payload = raw_options.get(source_key)
                if source_payload is not None:
                    new_entry[source_key] = source_payload
                    # The form returns a complete source snapshot. Replace its
                    # root so stale fields from older storage shapes cannot survive.
                    replace_keys.add(source_key)
                result.pop(source_key, None)

            result[target_key] = upsert_entry_by_value(
                entries,
                new_entry,
                replace_keys=replace_keys,
            )

        if active_map:
            result[BINDING_ACTIVE_KEY] = active_map

        return result

    def _is_binding_switch_global(self, source_key: str) -> bool:
        switch = self.binding_global_switches.get(source_key)
        return True if switch is None else bool(switch.isChecked())

    def prepare_binding_for_change(self, changed_key: str) -> None:
        """Refresh source controls when a bound target switches active value."""
        for source_key, target_key in iter_binding_sources(
            self.form_structure, logger=logger
        ):
            if changed_key != target_key or self._is_binding_switch_global(source_key):
                continue

            source_item = self.option_items.get(source_key)
            target_item = self.option_items.get(target_key)
            if source_item is None or target_item is None:
                continue

            target_payload = target_item.get_option()
            active_value = option_payload_value(target_payload)
            active_key = binding_value_key(active_value)

            for entry in normalize_target_entries(
                self._task_config_snapshot.get(target_key)
            ):
                if binding_value_key(entry.get("value")) != active_key:
                    continue
                if source_key in entry:
                    self._apply_option_item_config(source_item, entry[source_key])
                break

