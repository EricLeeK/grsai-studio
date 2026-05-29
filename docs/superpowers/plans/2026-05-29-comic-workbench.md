# 论文漫画工作台实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 新增功能中心、favicon，以及可按漫画项目组织页面候选图的论文讲解漫画工作台。

**架构：** 保持 `/` 为现有生图工作台，新增 `/apps` 与 `/comic` 页面。后端新增漫画项目与候选图模型/API，普通任务继续复用现有生成执行器，并在任务参数带漫画元数据时把生成图登记为漫画候选。前端漫画工作台使用独立 `comic.js/css`，复用现有任务 API 与参考图 API。

**技术栈：** FastAPI、SQLAlchemy、SQLite、原生 HTML/CSS/JS、pytest、浏览器快检。

---

### 任务 1：后端漫画数据模型与 API

**文件：**
- 修改：`app/models.py`
- 修改：`app/schemas.py`
- 创建：`app/routers/comic.py`
- 修改：`app/main.py`
- 测试：`tests/test_comic.py`

- [ ] 编写失败测试：创建默认漫画项目、列出项目、创建任务后登记漫画候选、单候选自动选定。
- [ ] 实现 `ComicProject` 和 `ComicCandidate` 模型。
- [ ] 实现 `/api/comic/projects`、`/api/comic/projects/current`、`/api/comic/projects/{id}/candidates`、`/api/comic/candidates/{id}/select`。
- [ ] 在执行器保存图片后，如果任务参数存在 `comic_project_id`，创建漫画候选。
- [ ] 运行 `pytest tests/test_comic.py -q`。

### 任务 2：功能中心与 favicon

**文件：**
- 创建：`app/templates/apps.html`
- 创建：`app/static/img/favicon.svg`
- 修改：`app/main.py`
- 修改：`app/templates/index.html`

- [ ] `/` 保持现有生图工作台。
- [ ] 新增 `/apps` 功能中心，链接到 `/`、`/comic`、`/publisher`。
- [ ] 在页面 `<head>` 引入 favicon。
- [ ] Header 增加功能中心入口。
- [ ] 浏览器快检 `/` 与 `/apps` 均可打开。

### 任务 3：漫画工作台页面与提交

**文件：**
- 创建：`app/templates/comic.html`
- 创建：`app/static/css/comic.css`
- 创建：`app/static/js/comic.js`
- 修改：`app/main.py`

- [ ] 左侧实现漫画版配置：项目、页类型、数字页页码、IP 模式、prompt、模型、尺寸、质量、数量、并行、临时参考、图库参考、生成按钮。
- [ ] 页码为数字页时校验 1-20。
- [ ] 开启 IP 模式时自动附加 IP 图。
- [ ] 提交任务时把漫画元数据写进任务 `params`。
- [ ] 支持粘贴临时图。

### 任务 4：漫画提示词与 IP 库

**文件：**
- 修改：`app/static/js/comic.js`
- 修改：`app/static/css/comic.css`

- [ ] 实现漫画提示词库，按封面/数字页/尾页分组，保存在 `sessionStorage`。
- [ ] 每条提示词支持复制、使用、删除、自动追加开关。
- [ ] 自动追加开关在不刷新页面时保持，刷新后重置。
- [ ] 实现 IP 参考图上传/选择，使用现有参考图 API 并在漫画侧以 IP 图集合保存选中 ID。

### 任务 5：漫画预览与生成列表切换

**文件：**
- 修改：`app/static/js/comic.js`
- 修改：`app/static/css/comic.css`

- [ ] 右侧实现“漫画预览 / 生成列表”切换，切换不影响左侧配置。
- [ ] 漫画预览只渲染有候选的页面。
- [ ] 中心显示当前页大图，左右显示已有相邻页的暗色小预览。
- [ ] 点击左右预览或底部导航可切页。
- [ ] 上下按钮切换当前页候选。
- [ ] “选定此图为本页”调用后端接口。
- [ ] 生成列表复用主页面任务列表字段和筛选。

### 任务 6：漫画版一键同款

**文件：**
- 修改：`app/static/js/comic.js`

- [ ] 在生成列表任务卡片上提供复刻按钮。
- [ ] 回填 prompt、模型参数、参考图、漫画项目、页类型、页码、IP 模式。
- [ ] 用户再次点击生成即可同款生成。

### 任务 7：完整验证与提交

**文件：**
- 全部相关文件

- [ ] 运行 `node --check app/static/js/comic.js`。
- [ ] 运行 `node --check app/static/js/app.js`。
- [ ] 运行 `.venv/bin/pytest -q`。
- [ ] 启动本地服务并用浏览器快检 `/`、`/apps`、`/comic`。
- [ ] 提交实现。
