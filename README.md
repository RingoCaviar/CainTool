# CainTool

## External Resource Manager (0.5.0)

The **外部资源管理器** scans file-backed Blender data, generic RNA file-path properties, and linked `.blend` libraries. It shows missing/packed/generated status and references, supports locating object references and selectively making linked data local, and copies resources into a typed `assets/` tree beside the saved project before changing paths to Blender-relative `//assets/...` paths.

Quick and full scans, hashing, copying, verification, and path updates run as cancellable incremental tasks. The manager reports the current stage and item, item/byte progress, throughput, elapsed time, ETA, errors, and a retained task log. Open the large manager dialog from `3D View > Sidebar > CainTool > 外部资源管理器`.

Safety defaults: source files are never moved or deleted, destination conflicts receive a content-hash suffix, copied files are verified before path changes, and unsaved projects cannot be packaged with relative paths.

Image resources expose a complete expandable reference chain through image nodes, nested node groups, materials or geometry-node modifiers, objects, collections, scenes, and view layers. Every row has its own locate action: materials activate the correct object slot, nodes open and select inside their node tree, and scene/object/collection rows switch to their corresponding Blender context.

The default reference view summarizes unique meaningful users instead of expanding every graph path. Materials are listed once with their object/slot hosts collapsed below them; worlds, lights, compositors, geometry-node modifiers, and unresolved node users have separate groups. Selecting a user shows one concise clickable breadcrumb path at a time, while the raw graph remains available as an advanced view.

The manager dialog uses a two-column inspector: the left side is the active resource browser and the right side always shows that resource's usage overview and an automatically selected visual flow. Packaging checkboxes are independent operator controls and do not set the active resource. Flow cards wrap three per row, show the incoming relationship and Blender data type, and can each navigate to that point in the chain.

Reference flows now always continue to the graph's real terminal node instead of stopping at the selected material, host, or first image node. Nested group instances and parent collections remain visible through the outermost node tree, object, collection hierarchy, scene, and view layer. The inspector renders this as a compact scrollable vertical pipeline; scan settings, task details, user switching, and the raw graph are collapsed by default.

CainTool 是一个面向 Blender 4.2+ 的模块化工具插件，入口位于 `3D View > Sidebar > CainTool`。它把一组高频但重复的工作流工具集中到同一个 N 面板里，重点解决常用命令执行、批量属性修改、关键帧过渡、父子层级隐藏、多场景渲染设置同步，以及 Cycles 场景参数统一调整这类问题。

这个仓库除了提供现成工具，也刻意保留了清晰的模块边界，方便后续继续扩展，而不是把所有逻辑重新堆回单个脚本。

## 适用场景

- 同一批对象需要统一设置某个 Blender 属性
- 需要一键删除选中物体关联的动画数据
- 需要快速给多个对象补一段“当前值 -> 目标值”的偏移关键帧
- 需要临时隐藏一整组父子层级，并在之后精确恢复原始状态
- 多场景项目中，希望把当前场景的渲染设置同步到其它场景
- 需要一键统一所有 Cycles 场景的采样参数

## 当前已启用功能

当前真正启用的模块由 `feature_registry.py` 控制。现在会出现在面板里的功能如下：

| 模块 | 作用 | 说明 |
| --- | --- | --- |
| 常用命令 | 放置高频的一键操作命令 | 当前包含“删除选中物体动画”，会清除选中物体、物体数据块和形态键上的动画数据，并刷新相关编辑器 |
| 批量设置属性 | 给选中对象统一写入同一个属性值 | 支持布尔、整数、浮点、字符串、枚举、向量、颜色等输入模式；支持从右键属性菜单快速带入属性名和值 |
| 渐入渐出 | 为选中对象按规则插入当前帧与偏移帧关键帧 | 可同时配置多条属性规则；支持从右键属性菜单快速添加当前属性 |
| 父子级隐藏 | 隐藏选中父级及其整棵子层级，并保存可见性快照 | 支持单独恢复或全部恢复，也可选是否同时影响渲染可见性和可选择状态 |
| 渲染设置同步 | 把当前场景的渲染设置同步到勾选的目标场景 | 支持手动同步和自动同步；不会覆盖输出路径 |
| 修改场景参数 | 批量修改所有 Cycles 场景的采样参数 | 统一设置最终采样、视口采样、自适应阈值；非 Cycles 场景会跳过 |

## 仓库内但当前未启用的模块

这些文件已经在仓库中，但当前没有加入 `feature_registry.py`，因此不会显示在插件 UI 中：

- `features/object_tools.py`
- `features/collection_tools.py`

另外，`features/template_feature.py` 是保留给后续新增功能时使用的模板模块。

## 安装

### 运行要求

- Blender `4.2.0` 或更高版本
- 插件 ID: `caintool`
- 许可证: `GPL-3.0-or-later`

### 推荐安装方式

1. 克隆或下载本仓库。
2. 在仓库根目录使用 Blender 的扩展打包命令生成安装包：

```bash
blender --command extension build --source-dir /path/to/CainTool
```

3. 在 Blender 中安装生成的扩展 zip。
4. 启用插件后，进入 `3D View > Sidebar > CainTool` 即可使用。

## 快速使用

### 1. 常用命令

- 在 `Object Mode` 下选中一个或多个对象。
- 点击“删除选中物体动画”。
- 插件会删除选中物体关联的动画数据，包括 Object、Object Data 和 Shape Keys 上的 action、drivers 和 NLA 数据。
- 删除成功后会主动刷新当前视图层、时间线、大纲、属性面板、Dope Sheet、Graph Editor 和 NLA Editor。

说明：

- 灯光亮度、相机焦距等动画通常保存在物体数据块上，也会一起清除。
- 如果多个物体共享同一个数据块，Blender 会把这份共享数据块动画一并清除。
- 如果没有找到可删除的动画数据，命令会提示并保持当前场景不变。

### 2. 批量设置属性

- 在 `Object Mode` 下选中一个或多个对象。
- 填写直接属性名，例如 `hide_render`、`location`、`energy`。
- 选择目标值类型并设置目标值。
- 执行后，插件会优先修改真正存在该属性的对象或对象数据块。

提示：

- 这里只支持“直接属性名”，不支持复杂路径表达式。
- 可以在 Blender 属性上右键，把当前属性和值快速带入到 CainTool 面板。

### 3. 渐入渐出

- 为一个或多个属性添加规则。
- 设置 `frame_offset`，插件会在当前帧和偏移帧之间插入一组过渡关键帧。
- 规则既可以手动填写，也可以通过右键属性菜单直接导入。

适合做：

- `hide_render` 开关切换
- 灯光能量变化
- 位置、颜色等属性的短过渡

### 4. 父子级隐藏

- 选中父级对象后执行隐藏。
- 插件会自动收集整个层级，并记录原始可见性状态。
- 之后可以按根对象单独恢复，也可以一键恢复全部。

适合做：

- 临时收起某一整组绑定层级
- 切换制作状态时保留原始可见性

### 5. 渲染设置同步

- 在目标场景上勾选“作为同步目标”。
- 在主控场景中执行“立即同步”，或开启自动同步。
- 当前场景的渲染设置会同步到被勾选的其它场景。

说明：

- 输出路径不会被覆盖。
- 自动同步带有简单防抖，避免连续修改时频繁触发。

### 6. 修改场景参数

- 设置 `Cycles` 最终采样、视口采样和自适应阈值。
- 点击应用后，所有 `Cycles` 场景会统一更新。
- 非 `Cycles` 场景会被跳过。

## 开发与测试

### 项目结构

```text
CainTool/
|- __init__.py
|- blender_manifest.toml
|- feature_registry.py
|- properties.py
|- registration.py
|- features/
|- services/
|- tests/
|- ui/
`- ARCHITECTURE.md
```

分层约定：

- `ui/`: 面板布局与绘制
- `features/`: Blender Operator、功能入口、每个模块的 UI
- `services/`: 可复用业务逻辑，尽量放可测试代码
- `tests/`: 不依赖 Blender 运行时的服务层测试

### 运行测试

当前仓库已经包含服务层单元测试，可以直接在仓库根目录运行：

```bash
python -m unittest discover -s tests -p "test_*.py"
```

### 代码级检查

```bash
python -m py_compile __init__.py registration.py properties.py feature_registry.py ui/panels.py features/common_command_tools.py services/common_command_service.py
```

### Blender 扩展校验

```bash
blender --command extension validate /path/to/caintool.zip
```

## 新增功能的推荐流程

1. 复制 `features/template_feature.py` 作为新模块起点。
2. 在新模块中添加 Operator 和 `draw_feature(layout, context)`。
3. 把可复用逻辑放进 `services/`，尽量保持可测试。
4. 在 `feature_registry.py` 中注册新模块。
5. 如果需要新的设置项，在 `properties.py` 中增加对应属性。

更详细的架构说明可以查看 [ARCHITECTURE.md](./ARCHITECTURE.md)。

## 当前测试覆盖的服务

- `batch_property_service`
- `common_command_service`
- `keyframe_transition_service`
- `parent_child_hide_service`
- `render_sync_service`
- `scene_render_service`
- `value_input_service`

这些测试主要验证业务逻辑，不覆盖 Blender UI 注册、面板绘制和真实 `bpy` 运行时行为。

## 许可证

本项目使用 `GPL-3.0-or-later`。
