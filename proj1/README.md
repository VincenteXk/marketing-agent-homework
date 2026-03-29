# AI Marketing Lab

课程仓库根目录为 `Projects/`，本作业代码在 `proj1/`。下文的「项目根目录」均指 `proj1/`（安装依赖、放置 `.env`、启动 `uvicorn` 时请先 `cd` 到该目录）。

一个可落地使用的营销分析工具。系统通过“赛道调研 -> 概念设计 -> 模拟画像 -> 汇总”流程，帮助从机会洞察快速推进到可执行的分析结论。

## 项目能力

- 前端单页应用：`apps/web`
  - 赛道初步调研（基于秘塔搜索）
  - 产品概念多轮对话
  - 一键生成模拟消费者画像
  - 汇总页查看结构化结果
- 后端 API：`apps/api`
  - 提供调研/概念/画像/会话工作流接口
  - 提供静态资源托管（`/` 直接访问前端）

## 快速启动

1. 安装依赖
   - `pip install -r requirements.txt`
2. 在项目根目录创建 `.env`（或 `.env.local`）
3. 启动服务
   - `uvicorn apps.api.main:app --reload --port 8000`
4. 打开页面
   - `http://127.0.0.1:8000`

## 环境变量

最少需要配置如下变量（按你实际账号填写）：

```env
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

METASO_API_KEY=your_metaso_key
METASO_BASE_URL=https://metaso.cn/api
METASO_MODEL=ds-r1
```

说明：
- 系统会自动读取根目录下的 `.env` 和 `.env.local`
- 如果同名变量已在系统环境中存在，则优先使用系统环境值

## API 概览

### 基础接口

- `GET /health`：服务健康检查
- `GET /llm/ping`：测试 DeepSeek 连通性

### 调研与概念

- `POST /research/stream`：赛道调研流式输出（SSE）
- `POST /concept/chat`：概念对话（非流式）
- `POST /concept/stream`：概念对话流式输出（SSE）
- `POST /persona/generate`：根据概念生成模拟画像

### Spec / Workflow（底层能力）

- `POST /spec/extract`
- `POST /spec/validate`
- `POST /spec/freeze`
- `POST /workflow/run`
- `GET /artifacts`

### Session 会话工作流

- `POST /session/message`
- `POST /session/run`
- `GET /session/status`
- `GET /session/result`
- `GET /session/export`

## 目录结构

- `apps/api`：FastAPI 服务与业务流程
- `apps/web`：前端静态页面（`index.html` / `script.js` / `styles.css`）
- `projects`：冻结后的 spec 快照
- `artifacts`：流程运行产物
- `runs`：运行日志与过程数据

## 产品说明

- 当前前端主流程覆盖“调研、概念、画像、汇总”四个核心分析阶段
- `conjoint / simulation / real-data` 分区为预留区，目前仅展示占位内容
- 依赖外部模型与搜索服务，不做本地兜底；调用失败会在接口层直接返回错误
