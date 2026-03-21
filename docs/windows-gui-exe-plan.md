# VideoWhisper Windows GUI EXE 开发计划（复审版）

更新时间：2026-03-15  
工作分支：`codex/win`

## 1. 核心判断

这件事值得做，但必须走对路。

本项目现状不是原生桌面应用，而是：

- Flask 后端
- Jinja 模板
- 大量前端 JavaScript 交互
- 本地文件上传、下载、剪贴板、`obsidian://` 协议调用

所以正确方案不是重写一套原生 GUI 页面，而是：

1. 使用 `PySide6 + Qt WebEngine` 提供真正的 Windows 窗口壳
2. 在进程内启动本地私有 HTTP 服务
3. 在窗口内嵌加载现有前端
4. 对“浏览器不可靠、但桌面需要稳定”的能力做桌面桥接

一句话概括：复用现有 Web UI，补齐桌面壳和 OS 集成层，做成真正的 GUI EXE。

## 2. 对上一版计划的复审结论

上一版方向大体正确，但有四个地方不够严谨。

### 2.1 过早锁死打包工具

之前把 `pyside6-deploy` 说得太满了，这不够实用。

真实情况是：

- GUI 技术栈可以确定为 `PySide6 + Qt WebEngine`
- 最终打包工具不应该在计划第一天就锁死
- 应先完成桌面壳和资源路径抽象，再做构建工具验证

修正后策略：

- 运行时框架固定：`PySide6 + Qt WebEngine`
- 发布构建优先尝试 `pyside6-deploy`（Qt 官方路线）
- 如果它在当前 Python 依赖组合下不稳定，则回退到 `PyInstaller onedir`
- 不在一开始承诺 `onefile`

这是“好品味”问题。先确定系统边界，再决定封装工具。反过来做，只会被工具拖着跑。

### 2.2 不能继续使用 Flask 开发服务器作为桌面内嵌服务

`app.run()` 适合源码开发，不适合桌面 GUI 进程内长期运行。

问题在于：

- 生命周期不可控
- 关闭窗口时不容易优雅停服
- 桌面应用里要避免把调试服务器当正式组件
- Windows GUI 进程中更需要确定性的启动和退出

修正后策略：

- 桌面模式内嵌服务改为 `waitress`
- 服务只监听 `127.0.0.1`
- 使用随机空闲端口
- GUI 层负责启动、健康检查、超时处理和关闭

这一步必须做，不然桌面版只是把一个临时开发服务器塞进壳里，属于糟糕设计。

参考：

- [Waitress 文档](https://docs.pylonsproject.org/projects/waitress/en/stable/)

### 2.3 之前低估了“浏览器行为”和“桌面行为”的差异

当前前端默认跑在系统浏览器里，很多行为在嵌入式 WebView 中不能想当然：

- 页面样式和脚本依赖外部 CDN
- 下载既有 `send_file` 触发的附件下载，也有 `fetch + Blob + a.download` 的前端下载
- `navigator.clipboard` 依赖浏览器权限模型
- `window.open("obsidian://...")` 在嵌入式环境里不可靠

这些都不是理论问题，是确定会踩的坑。

修正后策略：

1. 先把所有前端依赖本地化，不允许桌面版依赖公网 CDN
2. 用 `QWebEngineProfile` 统一处理下载、Cookie、存储目录
3. 对 `obsidian://`、打开目录、未来可能增加的系统调用，统一改为桌面桥接
4. 对 Blob 下载单独验收；如果行为不稳定，桌面模式改走原生下载流程

参考：

- [Qt `QWebEngineProfile` 文档](https://doc.qt.io/qt-6/qwebengineprofile.html)

### 2.4 之前对构建产物体积和复杂度仍然过于乐观

这不是一个小 exe。

桌面版至少会包含：

- Python 运行时
- Qt WebEngine 相关组件
- Flask 应用代码
- 前端模板和静态资源
- 可能内置的 `ffmpeg.exe` / `ffprobe.exe`

因此第一阶段必须接受：

- 先做 `standalone/onedir`
- 优先追求稳定和可调试
- 不把“单文件”当第一目标

如果一开始就追 `onefile`，那是在把调试、签名、杀软误报和启动性能问题一起请进门。

## 3. 目标架构

目标架构如下：

```text
VideoWhisper.exe
├─ Qt GUI 壳（PySide6）
│  ├─ 主窗口
│  ├─ QWebEngineView
│  ├─ 下载处理
│  ├─ 桌面桥接（打开 URI / 打开目录 / 未来扩展）
│  └─ 生命周期管理
├─ 内嵌本地服务（Waitress + Flask app）
│  ├─ 仅监听 127.0.0.1:随机端口
│  ├─ 加载现有 app/ 与 web/
│  └─ 保留现有 API 形态，避免破坏前端
├─ 只读资源
│  ├─ web/templates
│  ├─ web/static
│  ├─ 默认配置模板
│  └─ 应用图标等资源
└─ 可写运行数据（%LOCALAPPDATA%\VideoWhisper）
   ├─ logs
   ├─ temp
   ├─ output
   ├─ tasks.json
   ├─ .secret_key
   ├─ 用户配置副本
   └─ 桌面 WebEngine 持久化数据
```

## 4. 明确范围

### 4.1 本次要做

- 真正的 Windows GUI 窗口应用
- 不打开系统浏览器
- 复用现有 Web UI
- 支持本地上传、任务处理、下载结果、设置保存
- 支持桌面可分发 EXE

### 4.2 本次不做

- 重写原生 Qt 表单界面
- 同时支持 macOS 桌面包
- 一开始就追求单文件发行
- 一开始就做自动更新器

## 5. 详细实施计划

## 阶段 P0：设计收口

### 目标

把会影响全局结构的决策一次定清楚，避免做到一半返工。

### 任务

1. 固定 GUI 路线为 `PySide6 + Qt WebEngine`
2. 固定内嵌服务路线为 `Waitress + Flask`
3. 定义“桌面模式”和“现有 Web 部署模式”并行共存
4. 确定桌面模式的可写目录标准
5. 确定桌面桥接边界

### 输出物

- `desktop/` 目录结构草案
- 运行时路径规范
- 桌面模式配置优先级规范

### 验收

- 能明确回答每份数据放哪里
- 能明确回答谁负责启动和关闭服务
- 能明确回答哪些能力由 JS 做，哪些能力由桌面层做

## 阶段 P1：运行时路径与模式抽象

### 目标

把“源码模式”和“桌面打包模式”从路径层彻底分开。

### 必做项

1. 新增统一运行时路径模块，例如：
   - `app/utils/runtime_paths.py`
   - 或 `desktop/runtime_paths.py`
2. 抽象以下目录：
   - 应用资源根目录
   - 用户数据目录
   - 日志目录
   - temp 目录
   - output 目录
   - 配置文件目录
   - WebEngine 持久化目录
3. 调整以下模块对路径的获取方式：
   - `app/config/settings.py`
   - `app/__init__.py`
   - `app/services/video_processor.py`
   - `app/services/file_manager.py`
   - `app/services/file_uploader.py`
4. 保证源码模式行为不回归

### 风险点

- 当前逻辑广泛依赖项目根目录推导路径
- `logs/`、`config/.secret_key`、`output/tasks.json` 都是隐式写项目目录

### 验收

- 源码模式继续正常运行
- 桌面模式下所有可写文件都落在 `%LOCALAPPDATA%\VideoWhisper`
- 安装目录可设为只读也不崩

## 阶段 P2：桌面壳骨架

### 目标

做出真正的 Windows GUI 窗口，能在窗口内显示现有首页。

### 必做项

1. 新增桌面入口：
   - `desktop/main.py`
2. 新增服务管理器：
   - 负责启动 Waitress
   - 分配随机空闲端口
   - 做 `/api/health` 轮询
   - 负责超时和退出
3. 新增 Qt 主窗口：
   - `QMainWindow`
   - `QWebEngineView`
   - 基础窗口标题、图标、尺寸
4. 加载 URL：
   - `http://127.0.0.1:<port>/`
5. 关闭窗口时触发服务回收

### 关键修正

这里不能再沿用 `run.py` 直接启动逻辑。

原因：

- `run.py` 现在默认读取 Web 配置并考虑 HTTP/HTTPS 双模式
- 桌面应用不需要对外服务
- 桌面应用只需要本地私有服务

### 验收

- 双击入口能看到桌面窗口
- 页面加载成功
- 不会弹系统浏览器
- 关闭窗口后后台服务退出

## 阶段 P3：前端桌面兼容化

### 目标

把当前“默认浏览器环境”修正为“可嵌入桌面环境”。

### 必做项

1. 移除模板中全部外部 CDN 依赖
2. 把以下资源落地到本地静态目录：
   - Bootstrap CSS
   - Bootstrap JS bundle
   - Font Awesome
   - Bootstrap Icons
3. 删除模板里为公网加载失败设计的 fallback loader
4. 验证以下功能在 Qt WebEngine 中稳定：
   - 文件上传按钮
   - 拖拽上传
   - 普通结果下载
   - 批量下载
   - `fetch + Blob` 下载
   - `localStorage`
   - `navigator.clipboard`

### 特别注意

当前前端下载有两种形态：

1. 直接访问后端附件下载 URL
2. 前端 `fetch()` 后转成 Blob，再触发浏览器下载

第二种在嵌入式 WebView 中最容易出鬼问题，必须单独验证。

如果 Blob 下载不稳定，修正原则是：

- 桌面模式优先走更笨但更稳定的下载方式
- 不为了一点“网页端体验一致性”坚持脆弱实现

### 验收

- 离线环境下页面样式完整
- 上传、下载、设置持久化都正常
- 没有公网依赖

## 阶段 P4：桌面桥接层

### 目标

把网页里不适合继续依赖浏览器技巧的能力，上移到桌面层。

### 必做项

1. 设计桌面桥接接口，例如通过 `QWebChannel`
2. 第一批桥接能力建议包括：
   - 打开 `obsidian://` URI
   - 打开输出目录
   - 未来如需“另存为”可扩展到桌面层
3. 改造前端中以下高风险行为：
   - `window.open(uri, "_blank")`
   - `iframe` 方式尝试唤起本地协议
   - 依赖浏览器权限模型的剪贴板写入

### 原则

桌面应用不该继续靠网页黑魔法去调系统协议。

如果 JS 代码里需要通过 `iframe`、隐藏链接、`window.open` 三连击来“碰碰运气”，那就说明这一层该搬走了。

### 验收

- Obsidian 导出在桌面版稳定工作
- 不再依赖浏览器兼容性赌博
- 失败时有明确错误提示和回退路径

## 阶段 P5：FFmpeg 与第三方运行依赖内置

### 目标

让桌面版具备可分发性，不要求用户先手工装 `ffmpeg`。

### 必做项

1. 明确内置 `ffmpeg.exe` / `ffprobe.exe` 的目录结构
2. 改造 `VideoDownloader._get_ffmpeg_path()` 查找顺序：
   - 桌面包内置路径优先
   - 系统 PATH 次之
   - 现有固定路径作为兼容兜底
3. 验证：
   - 视频下载
   - 音频提取
   - 长音频分段

### 风险点

- 包体积增大
- 杀软误报概率上升
- 需要明确许可证和来源管理

### 验收

- 干净 Windows 机器上不额外安装 ffmpeg 也能工作

## 阶段 P6：桌面构建与发布

### 目标

把桌面壳、内嵌服务、前端资源和 ffmpeg 组装成可运行发行物。

### 构建策略

第一选择：

- `pyside6-deploy`

备选方案：

- `PyInstaller onedir`

选择原则：

- 谁能更稳定打包 `Qt WebEngine + Flask + 资源文件 + ffmpeg`
- 谁就先用谁

而不是先在纸面上争论“哪个更优雅”。

### 必做项

1. 新增桌面依赖清单：
   - `requirements-desktop.txt`
   - 必要时 `requirements-desktop-build.txt`
2. 新增构建脚本：
   - `build-win-gui.ps1`
3. 显式声明资源打包：
   - `web/templates`
   - `web/static`
   - 默认配置模板
   - 图标
   - ffmpeg 二进制
4. 产出目录版发布物
5. 最后再评估是否值得做 `onefile`

### 验收

- 在未安装 Python 的 Windows 环境中可直接运行
- 主窗口正常打开
- 核心流程可用
- 退出无残留孤儿进程

## 阶段 P7：安装器与发布验证

### 目标

把“能跑”升级为“能发”。

### 必做项

1. 选择安装器：
   - Inno Setup
   - 或 NSIS
2. 加入：
   - 开始菜单快捷方式
   - 桌面快捷方式
   - 卸载入口
   - 图标和版本信息
3. 做发布前验证清单

### 验收清单

- 双击桌面图标启动
- 首次启动能创建用户数据目录
- 上传本地文件成功
- 下载结果成功
- Obsidian 导出成功或有明确回退
- 重启后历史任务仍在
- 卸载不会误删用户输出目录

## 6. 拟修改文件清单

### 新增文件

- `desktop/main.py`
- `desktop/server_manager.py`
- `desktop/webview_window.py`
- `desktop/bridge.py`
- `desktop/runtime_paths.py`
- `build-win-gui.ps1`
- `requirements-desktop.txt`
- `requirements-desktop-build.txt`（如需要）

### 高概率修改文件

- `app/__init__.py`
- `app/config/settings.py`
- `app/services/video_downloader.py`
- `app/services/video_processor.py`
- `app/services/file_manager.py`
- `app/services/file_uploader.py`
- `run.py`
- `web/templates/index.html`
- `web/templates/files.html`
- `web/templates/settings.html`
- `web/static/js/app.js`
- `web/static/js/files.js`
- `web/static/js/settings.js`

## 7. 关键风险与对应策略

### 风险 1：Qt WebEngine 下载行为和浏览器不完全一致

策略：

- 优先用 `QWebEngineProfile` 接管下载
- 单独验证 Blob 下载
- 必要时让桌面模式走不同下载路径

### 风险 2：Obsidian URI 在嵌入式环境不稳定

策略：

- 改为桌面桥接调用
- 不再依赖前端 `window.open`

### 风险 3：安装目录不可写导致崩溃

策略：

- 所有可写目录统一迁移到用户目录
- 安装目录只做只读资源区

### 风险 4：打包工具对复杂依赖兼容性不稳定

策略：

- 不预先神化某个工具
- 保留 `pyside6-deploy` / `PyInstaller` 双路径

### 风险 5：桌面模式改动反噬现有 Web 部署模式

策略：

- 明确分离桌面入口
- 保持现有 `run.py` 与桌面模式并行
- 先做路径抽象，再做 GUI 壳

## 8. 最终交付标准

满足以下条件，才算这件事做完：

1. 交付物是 Windows GUI EXE，而不是自动打开浏览器的启动器
2. 桌面版不依赖公网 CDN
3. 桌面版可以离线显示完整界面
4. 核心处理流程可用
5. 结果下载可用
6. 设置持久化可用
7. Obsidian 导出有稳定路径
8. 桌面版关闭时无孤儿服务进程
9. 现有源码运行模式不被破坏

## 9. 建议的开发顺序

按下面顺序做，返工最少：

1. 路径抽象
2. Waitress 内嵌服务
3. Qt 主窗口 + WebEngine 壳
4. 前端资源本地化
5. 下载与桌面桥接
6. ffmpeg 内置
7. 构建脚本
8. 安装器

## 10. 参考资料

- [Qt for Python 部署文档](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html)
- [Qt `QWebEngineProfile` 文档](https://doc.qt.io/qt-6/qwebengineprofile.html)
- [Waitress 文档](https://docs.pylonsproject.org/projects/waitress/en/stable/)
- [pywebview Web Engine 文档](https://pywebview.flowrl.com/guide/web_engine.html)

## 11. 最后的结论

这个方案本质上是“桌面壳 + 本地私有服务 + 现有 Web UI 复用”。

真正需要控制的是三件事：

1. 路径
2. 生命周期
3. 桌面集成边界

这三件事做对了，Windows GUI EXE 是工程问题。  
这三件事做错了，最后只会得到一个披着桌面壳的脆弱浏览器玩具。
