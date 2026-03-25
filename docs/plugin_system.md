# 插件系统说明（MFW-UI）

本文档说明当前 MFW-UI 前端插件系统的使用方式、开发规范和界面行为。

## 1. 目标与范围

- 插件为**前端扩展**，使用 Python OOP 编写。
- 插件用于扩展 UI 页面与交互，不直接修改后端耦合逻辑。
- 插件入口可导入/扫描，并在左侧导航栏显示。
- 当插件数量超过侧栏上限时，超出部分自动归入“插件集合”。

---

## 2. 目录与加载规则

### 2.1 插件目录

- 默认目录：`MAH-UI/plugins/`
- 扫描规则：仅加载目录下 `*.py` 文件，且忽略以下划线开头的文件。

### 2.2 导入规则

- 通过“实验性功能 -> Import plugin”导入 `.py` 文件。
- 导入后文件会复制到 `plugins/`。
- 若文件重名，自动重命名为 `xxx_1.py`、`xxx_2.py` ...

### 2.3 必须满足的导出约定

插件文件必须提供工厂函数：

```python
def create_plugin() -> PluginBase:
    return YourPlugin()
```

否则会被判定为加载失败。

---

## 3. 插件接口（OOP）

接口定义位于：`app/core/plugins/plugin_base.py`

### 3.1 元信息 `PluginMeta`

- `plugin_id: str`：插件唯一 ID（必须唯一）
- `name: str`：显示名称
- `version: str`：版本号
- `description: str = ""`：描述（用于集合页和管理页）
- `icon: str = "APPLICATION"`：图标名（支持 `MESSAGE` / `FOLDER` / `FIF.MESSAGE` 等）
- `entry_position: str = "top"`：保留字段（当前主要使用 top）
- `i18n: dict[str, dict[str, str]] | None = None`：插件内置翻译表（可选）

当 `name` / `description` 使用 `"$key"` 形式时，插件系统会根据当前 UI 语言从 `meta.i18n` 中自动解析：

```python
meta = PluginMeta(
    plugin_id="demo.plugin",
    name="$plugin_name",
    description="$plugin_desc",
    version="0.1.0",
    i18n={
        "zh_cn": {"plugin_name": "示例插件", "plugin_desc": "示例描述"},
        "en_us": {"plugin_name": "Demo Plugin", "plugin_desc": "Demo description"},
    },
)
```

### 3.2 生命周期 `PluginBase`

- `on_load(ctx)`：加载时调用
- `create_widget(parent=None)`：创建并返回插件页面 `QWidget`
- `on_unload()`：卸载时调用
- `on_enable_changed(enabled)`：启用状态变化回调

### 3.3 上下文 `PluginContext`

插件可用上下文：

- `logger`
- `signal_bus`
- `service_coordinator`
- `language_code`：当前 UI 语言代码（例如 `zh_cn` / `en_us` / `ja_jp`）
- `tr(value, i18n_map=None)`：解析 `"$key"` 文本的快捷函数

`ctx.tr()` 使用示例：

```python
title = QLabel(ctx.tr("$page_title", self.meta.i18n))
```

> 建议只使用前端能力，不要在插件中耦合后端关键流程。

---

## 4. 左侧导航显示规则

实现位置：`app/view/main_window/main_window.py`

### 4.1 常规显示

- 插件按 `order` 排序。
- 启用的插件进入导航候选列表。
- 页面 `objectName` 为空时，主窗口会自动补全，避免 `addSubInterface` 报错。

### 4.2 超限收纳

- 配置项：`plugin_sidebar_max_visible`（默认 3，范围 1~10）
- 启用插件数超过上限时：
  - 前 N 个直接显示在左侧导航
  - 超出项进入“插件集合”

### 4.3 插件集合页

- 显示超出插件的列表项。
- 每项包含：图标、插件名、描述。
- 点击后切换到对应插件页面。

---

## 5. 实验性功能入口

设置页位置：`Setting -> Experimental / Compatibility`

包含以下入口：

- `Import plugin`：导入插件文件
- `Scan plugins`：扫描并加载插件目录
- `Custom sidebar plugin display`：管理启用状态与侧栏优先级
- `Max sidebar plugins`：设置侧栏最大直显数量

---

## 6. 自定义显示与持久化

配置项（`Config`）：

- `plugin_sidebar_preferred`：侧栏优先列表（JSON 字符串）
- `plugin_sidebar_preferred`：插件排序顺序列表（JSON 字符串，来源于拖拽结果）
- `plugin_enabled_overrides`：启用覆盖状态（JSON 字符串）
- `plugin_sidebar_max_visible`：侧栏上限（RangeConfigItem）

行为说明：

1. 读取“自定义侧栏插件显示”里的拖拽顺序
2. 结合启用状态过滤出可显示插件
3. 截取前 N 个显示到侧栏
4. 剩余归入“插件集合”

---

## 7. 最小插件示例

```python
from app.core.plugins.plugin_base import PluginBase, PluginMeta, PluginContext
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class DemoPlugin(PluginBase):
    meta = PluginMeta(
        plugin_id="demo.plugin",
        name="Demo 插件",
        version="0.1.0",
        description="这是一个最小插件示例",
        icon="MESSAGE",
    )

    def __init__(self):
        self._ctx = None
        self._widget = None

    def on_load(self, ctx: PluginContext) -> None:
        self._ctx = ctx
        self._ctx.logger.info("DemoPlugin loaded")

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        if self._widget is not None:
            return self._widget
        root = QWidget(parent)
        layout = QVBoxLayout(root)
        layout.addWidget(QLabel("Hello Plugin"))
        self._widget = root
        return root

    def on_unload(self) -> None:
        self._ctx = None
        self._widget = None

    def on_enable_changed(self, enabled: bool) -> None:
        if self._ctx:
            self._ctx.logger.info("DemoPlugin enabled=%s", enabled)


def create_plugin() -> PluginBase:
    return DemoPlugin()
```

---

## 8. 常见问题

### Q1：插件未显示在侧栏？

- 检查是否已启用。
- 检查是否超过侧栏上限，被收纳到“插件集合”。
- 点击 `Scan plugins` 重新扫描。

### Q2：加载失败如何排查？

- 确认存在 `create_plugin()`。
- 确认返回对象是 `PluginBase` 子类实例。
- 检查 `plugin_id`、`name` 是否为空或重复。

### Q3：图标不生效？

- 请使用 qfluentwidgets 的有效图标名（如 `MESSAGE`）。
- 不识别时会回退到 `APPLICATION`。

---

## 9. 版本说明

本文档对应当前仓库插件系统实现（MFW-UI 前端）。后续如有字段或流程变更，请同步更新本文档。
