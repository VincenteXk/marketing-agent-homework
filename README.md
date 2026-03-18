# AI Marketing Lab (Proj Framework)

一个可复用到 `Proj1 / Proj2 / Proj3` 的本地项目骨架，支持通过前端表单与对话生成 `project spec`，并驱动后续 Agent 工作流。

## 当前实现（MVP）

- 前端单页：`apps/web`
  - 业务对话输入
  - 分析进度时间线
  - 结果卡片与原始结果查看
- 后端 API：`apps/api`
  - `POST /session/message`
  - `POST /session/run`
  - `GET /session/status`
  - `GET /session/result`
  - `GET /session/export`
  - 保留底层 `spec/workflow` API 作为内部能力

## 启动

1. 安装依赖
   - `pip install -r requirements.txt`
2. 配置密钥（项目根目录 `.env`）
   - `DEEPSEEK_API_KEY=...`
   - `DEEPSEEK_BASE_URL=https://api.deepseek.com`
   - `DEEPSEEK_MODEL=deepseek-chat`
3. 启动服务
   - `uvicorn apps.api.main:app --reload --port 8000`
4. 访问页面
   - `http://127.0.0.1:8000`

## 目录

- `apps/api`：API 与工作流入口
- `apps/web`：前端静态页面
- `projects`：冻结后的 Spec 版本
- `artifacts`：运行结果导出
- `runs`：运行日志

## 说明

当前产品默认通过“会话接口”执行，`spec` 由后端内部维护，前端不暴露配置细节。
`extract` 与 `workflow` 采用 DeepSeek 严格执行模式，不做规则降级或兜底，任一步骤失败会直接中止。

可使用 `GET /llm/ping` 快速验证 DeepSeek 连通性。
