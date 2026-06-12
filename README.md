# Grsai Studio

Grsai Studio 是一个面向 Grsai 生图 API 的本地 Web 工作台。它把图片生成、参考图管理、任务历史、漫画分镜候选、微信公众号草稿发布这些流程放在同一个 FastAPI 应用里，适合个人创作、内容运营和批量出图调试。

启动后默认访问：

- 图片工作台：http://127.0.0.1:8099/
- 功能中心：http://127.0.0.1:8099/apps
- 漫画工作台：http://127.0.0.1:8099/comic
- 微信公众号发布器：http://127.0.0.1:8099/publisher

## 功能概览

- **图片工作台：** 输入 Prompt，选择模型、比例、分辨率、质量、数量，支持串行或并行生成。
- **参考图管理：** 支持临时上传、粘贴上传、长期保存参考图，并在后续任务中复用。
- **任务历史：** 实时轮询任务状态，查看耗时、错误、生成结果；支持复用任务参数和删除失败任务。
- **Lightbox 查看器：** 全屏查看生成图，支持键盘切换、下载、压缩当前图片。
- **漫画工作台：** 以项目为单位管理论文解读漫画，按页面生成候选图，选择最终候选，维护常驻 Prompt 和 IP 参考图。
- **微信公众号发布器：** 将 Markdown 转为微信图文 HTML，生成或上传封面，并创建微信公众号草稿。
- **命令行生图脚本：** `scripts/generate.sh` 可独立调用 Grsai API，支持参考图、异步轮询和国内/海外节点兜底。

## 环境要求

- Python 3.10 或更高版本。
- Git。
- Grsai API Key。
- macOS/Linux 推荐使用 Bash 启动脚本。
- Windows 推荐使用 PowerShell；也可以用 Git Bash 或 WSL 运行 Bash 脚本。

如果要使用微信公众号发布器，还需要：

- 微信公众号 `AppID` 和 `AppSecret`。
- Gemini API Key，用于 Markdown 到微信 HTML 的转换。

## 获取项目

```bash
git clone https://github.com/EricLeeK/grsai-studio.git
cd grsai-studio
```

如果已经下载了 zip 包，请解压后在终端进入项目目录。

## 配置环境变量

先复制环境变量模板：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`：

```env
GRSAI_API_KEY=your_api_key_here

WECHAT_APPID=your_wechat_appid_here
WECHAT_SECRET=your_wechat_secret_here

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
GEMINI_MODEL=gemini-2.5-flash

# 可选：默认使用国内节点。海外网络也可以改为 https://grsaiapi.com
# GRSAI_BASE_URL=https://grsai.dakka.com.cn

# 可选：命令行脚本默认输出目录
# GRSAI_OUTPUT_DIR=./output
```

只使用图片工作台时，必须配置 `GRSAI_API_KEY`。微信公众号发布器需要额外配置 `WECHAT_APPID`、`WECHAT_SECRET` 和 `GEMINI_API_KEY`。

## macOS 使用指南

### 方式一：一键启动

项目自带启动脚本，会自动创建 `.venv` 并安装依赖。

```bash
bash start.sh
```

指定端口：

```bash
bash start.sh 9000
```

后台启动：

```bash
bash start-bg.sh
```

停止后台服务：

```bash
bash stop.sh
```

启动成功后访问 http://127.0.0.1:8099。

### 方式二：手动启动

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8099
```

## Windows 使用指南

### PowerShell 启动

在项目目录打开 PowerShell：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8099
```

如果系统不认识 `py`，可以改用：

```powershell
python -m venv .venv
```

如果 PowerShell 禁止激活虚拟环境，可以在当前窗口临时放宽策略：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

启动成功后访问 http://127.0.0.1:8099。

### Git Bash 或 WSL 启动

如果你安装了 Git Bash 或 WSL，也可以使用和 macOS 类似的命令：

```bash
bash start.sh
```

注意：`start.sh` 会用 `lsof` 清理占用端口的旧进程。部分 Windows Git Bash 环境可能没有 `lsof`，这时请改用 PowerShell 手动启动。

## 首次使用流程

1. 打开 http://127.0.0.1:8099。
2. 在左侧输入 Prompt。
3. 选择模型，例如 `gpt-image-2-vip` 或 `nano-banana-pro-vip`。
4. 选择尺寸、质量和数量。
5. 如果需要参考图，可以拖拽、点击上传或直接粘贴图片。
6. 点击生成按钮。
7. 在右侧任务列表查看进度和结果。
8. 点击图片进入 Lightbox，可下载、切换图片或压缩图片。
9. 点击任务上的复用按钮，可以恢复 Prompt、模型、尺寸、质量和参考图配置。

## 图片工作台

图片工作台是默认首页，适合普通生图和参考图生图。

支持的模型包括：

- `nano-banana`
- `nano-banana-fast`
- `nano-banana-2`
- `nano-banana-2-cl`
- `nano-banana-2-4k-cl`
- `nano-banana-pro`
- `nano-banana-pro-cl`
- `nano-banana-pro-vip`
- `nano-banana-pro-4k-vip`
- `gpt-image-2`
- `gpt-image-2-vip`

`nano-banana` 系列使用比例和 `1K`、`2K`、`4K` 这类分辨率选项。`gpt-image-2` 系列使用像 `2048x2048`、`2048x1152` 这样的像素尺寸。

参考图分为两类：

- **临时参考图：** 只随当前任务上传，保存在 `data/task_references/`。
- **保存的参考图：** 上传到参考图库，保存在 `data/reference_images/`，后续任务可以重复选择。

## 漫画工作台

访问 http://127.0.0.1:8099/comic。

漫画工作台适合把论文、产品说明或长内容拆成多页视觉候选。它以项目为单位保存状态：

- 自动创建或加载最近的漫画项目。
- 每一页可以生成多个候选图。
- 可以在候选图之间切换并选择最终版本。
- 常驻 Prompt 保存在数据库中，不依赖浏览器本地缓存。
- IP 参考图和项目绑定，适合保持角色、画风或视觉资产一致。
- 可以从任务历史中点击「同款」复用完整参数。

推荐流程：

1. 先在参考图库上传角色、品牌或画风参考图。
2. 进入 `/comic`，确认当前项目。
3. 配置封面、正文页或其他页面类型的 Prompt。
4. 开启 IP 参考模式，选择项目长期参考图。
5. 逐页生成候选图。
6. 在预览区选择每页最终候选。

## 微信公众号发布器

访问 http://127.0.0.1:8099/publisher。

发布器用于把 Markdown 文章整理为微信公众号草稿：

- 粘贴或上传 `.md` 文件。
- 选择「简洁」「商务」「科技」样式。
- 调用 Gemini 将 Markdown 转成微信友好的内联 HTML。
- 上传封面图，或输入封面 Prompt 生成封面。
- 将封面上传到微信素材接口，获取 `media_id`。
- 填写标题、作者和摘要。
- 创建微信公众号草稿。

使用前请确认 `.env` 中已配置：

```env
WECHAT_APPID=your_wechat_appid_here
WECHAT_SECRET=your_wechat_secret_here
GEMINI_API_KEY=your_gemini_api_key_here
```

创建草稿后，请到 [微信公众平台](https://mp.weixin.qq.com/) 检查草稿内容，再决定是否发布。

## 命令行生图

除了 Web 界面，也可以直接使用脚本：

```bash
bash scripts/generate.sh "a cute cat, digital art"
```

指定模型、比例和分辨率：

```bash
bash scripts/generate.sh \
  --model nano-banana-pro-4k-vip \
  --ratio 16:9 \
  --size 4K \
  "landscape at sunset"
```

使用 `gpt-image-2-vip` 像素尺寸：

```bash
bash scripts/generate.sh \
  --model gpt-image-2-vip \
  --size 2048x2048 \
  --quality high \
  "abstract geometric art"
```

使用参考图：

```bash
bash scripts/generate.sh \
  --ref /path/to/reference.jpg \
  "same character in a different pose"
```

查看完整参数：

```bash
bash scripts/generate.sh --help
```

脚本会读取项目根目录的 `.env`。如果配置了 `GRSAI_BASE_URL`，会优先使用该节点；连接失败时会尝试内置的国内和海外节点。

## 数据和文件目录

运行过程中会生成以下本地文件：

```text
grsai-studio/
├── data/
│   ├── grsai.db             # SQLite 数据库
│   ├── reference_images/    # 保存的参考图库
│   └── task_references/     # 任务临时参考图
├── output/                  # 生成图片和发布器封面
├── logs/
│   └── server.log           # 后台启动日志
└── .server.pid              # 后台服务 PID
```

这些运行时数据默认不提交到 Git。备份项目时，如果要保留历史任务、参考图库和生成图片，请同时备份 `data/` 和 `output/`。

## API 简表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/tasks` | 创建 JSON 生图任务 |
| POST | `/api/tasks/upload` | 创建带上传参考图的生图任务 |
| GET | `/api/tasks?limit=50&offset=0` | 分页查询任务 |
| GET | `/api/tasks/{task_id}` | 查询单个任务 |
| DELETE | `/api/tasks/{task_id}` | 删除任务和对应文件 |
| DELETE | `/api/tasks/failed` | 删除失败任务 |
| POST | `/api/tasks/images/{image_id}/compress` | 压缩生成图片 |
| GET | `/api/reference-images` | 查询参考图库 |
| POST | `/api/reference-images` | 上传参考图到图库 |
| DELETE | `/api/reference-images/{image_id}` | 删除参考图 |
| GET | `/api/comic/projects/current` | 获取或创建当前漫画项目 |
| GET | `/api/comic/projects/{project_id}/candidates` | 查询漫画候选图 |
| GET | `/api/comic/projects/{project_id}/prompts` | 查询项目 Prompt |
| POST | `/api/comic/projects/{project_id}/prompts` | 新增项目 Prompt |
| PATCH | `/api/comic/prompts/{prompt_id}` | 修改项目 Prompt |
| DELETE | `/api/comic/prompts/{prompt_id}` | 删除项目 Prompt |
| GET | `/api/comic/projects/{project_id}/ip-references` | 查询项目 IP 参考图 |
| PUT | `/api/comic/projects/{project_id}/ip-references` | 更新项目 IP 参考图 |
| POST | `/api/comic/candidates/{candidate_id}/select` | 选择漫画候选图 |
| POST | `/api/publisher/convert` | Markdown 转微信 HTML |
| POST | `/api/publisher/upload-cover` | 上传或生成封面并上传微信 |
| POST | `/api/publisher/generate-cover-task` | 创建封面生成任务 |
| POST | `/api/publisher/upload-cover-from-task` | 从已完成任务上传封面 |
| POST | `/api/publisher/draft` | 创建微信公众号草稿 |

## 本地开发

安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

启动开发服务器：

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8099
```

运行测试：

```bash
python -m pytest -q
```

## 常见问题

### 启动后打不开网页

先确认终端中是否显示：

```text
Uvicorn running on http://127.0.0.1:8099
```

如果端口被占用，可以换端口：

```bash
bash start.sh 9000
```

或者手动启动：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 9000
```

### 提示 `GRSAI_API_KEY is not configured`

说明 `.env` 没有配置 `GRSAI_API_KEY`，或者当前终端没有在项目根目录启动服务。请确认 `.env` 位于项目根目录，并且包含：

```env
GRSAI_API_KEY=你的实际 Key
```

### Windows 无法激活虚拟环境

在当前 PowerShell 窗口执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

这个命令只影响当前窗口。

### 生成任务一直失败

可以先检查：

- `.env` 中的 `GRSAI_API_KEY` 是否正确。
- 网络是否能访问 `GRSAI_BASE_URL`。
- 参考图文件是否过大或格式不支持。
- 模型、尺寸、比例是否匹配。

也可以用命令行脚本单独测试：

```bash
bash scripts/generate.sh "simple test image"
```

### 微信草稿创建失败

请检查：

- `WECHAT_APPID` 和 `WECHAT_SECRET` 是否正确。
- 公众号接口权限是否可用。
- 封面是否已经上传并拿到 `media_id`。
- `GEMINI_API_KEY` 是否可用于 Markdown 转换。

## 技术栈

- **后端：** FastAPI、SQLAlchemy、SQLite。
- **前端：** 原生 HTML、CSS、JavaScript，无构建工具。
- **任务执行：** `ThreadPoolExecutor` 后台执行生图任务。
- **外部服务：** Grsai API、Gemini API、微信公众号接口。

## 项目结构

```text
grsai-studio/
├── app/
│   ├── main.py                  # FastAPI 入口和页面路由
│   ├── config.py                # 环境变量和目录配置
│   ├── database.py              # SQLite 连接和初始化
│   ├── models.py                # SQLAlchemy 模型
│   ├── schemas.py               # Pydantic schema
│   ├── routers/
│   │   ├── tasks.py             # 生图任务 API
│   │   ├── reference_images.py  # 参考图库 API
│   │   ├── comic.py             # 漫画项目 API
│   │   └── publisher.py         # 微信发布器页面和 API
│   ├── services/
│   │   ├── grsai.py             # Grsai API 封装
│   │   ├── executor.py          # 后台任务执行器
│   │   ├── image_compression.py # 图片压缩
│   │   ├── converter.py         # Markdown 转微信 HTML
│   │   └── wechat.py            # 微信公众号接口
│   ├── static/                  # CSS、JS、图标
│   └── templates/               # 页面模板
├── scripts/
│   └── generate.sh              # 命令行生图脚本
├── tests/                       # 自动化测试
├── data/                        # SQLite 和参考图，本地生成
├── output/                      # 生图输出，本地生成
├── logs/                        # 后台服务日志，本地生成
├── requirements.txt
├── start.sh
├── start-bg.sh
└── stop.sh
```
