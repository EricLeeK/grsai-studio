# Grsai Studio

Grsai 生图 API 的 Web 管理界面，支持多模型、并行生成、实时监控。

## 快速启动

### 1. 配置 API Key

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 Grsai API Key
# GRSAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 2. 启动服务

```bash
# 前台启动（可看日志，Ctrl+C 停止）
bash start.sh

# 后台启动
bash start-bg.sh

# 停止
bash stop.sh

# 指定端口
bash start.sh 9000
```

启动后访问 http://127.0.0.1:8099

## 功能

- **模型选择**：nano-banana 全系列 + gpt-image-2 全系列
- **参数配置**：分辨率、比例、质量、数量、并行
- **参考图上传**：拖拽上传，支持多张
- **任务监控**：实时轮询、状态徽章、进度显示
- **图片查看**：Lightbox 全屏、键盘导航、下载
- **任务管理**：删除任务（自动清理文件）

## 项目结构

```
grsai-studio/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py             # 配置（自动加载 .env）
│   ├── database.py           # SQLite 数据库
│   ├── models.py             # 数据模型
│   ├── schemas.py            # Pydantic schemas
│   ├── routers/tasks.py      # API 路由
│   ├── services/
│   │   ├── grsai.py          # Grsai API 封装
│   │   └── executor.py       # 线程池执行器
│   ├── static/               # 前端静态文件
│   │   ├── css/style.css
│   │   └── js/app.js
│   └── templates/index.html
├── scripts/
│   └── generate.sh           # Grsai 生图脚本
├── tests/                    # 测试
├── .env.example              # 环境变量模板
├── data/                     # SQLite 数据库文件（gitignore）
├── output/                   # 生成的图片（gitignore）
├── requirements.txt
├── start.sh                  # 前台启动
├── start-bg.sh               # 后台启动
└── stop.sh                   # 停止
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/tasks | 创建任务 (JSON) |
| POST | /api/tasks/upload | 创建任务 (带参考图) |
| GET | /api/tasks | 列出所有任务 |
| GET | /api/tasks/{id} | 获取任务详情 |
| DELETE | /api/tasks/{id} | 删除任务 |
| GET | /api/health | 健康检查 |

## 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite
- **前端**：原生 HTML/CSS/JS（无构建工具）
- **执行器**：ThreadPoolExecutor（支持并行）
