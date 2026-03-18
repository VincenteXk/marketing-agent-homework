# AI Marketing Lab (Proj Framework)

一个可复用到 `Proj1 / Proj2 / Proj3` 的本地项目骨架，支持通过前端表单与对话生成 `project spec`，并驱动后续 Agent 工作流。

## 当前实现（MVP）

- 前端单页：`apps/web`
  - 表单输入 Spec
  - 对话抽取 Spec
  - Diff 对比并回填
  - 冻结 Spec 与触发工作流
- 后端 API：`apps/api`
  - `POST /spec/extract`
  - `POST /spec/validate`
  - `POST /spec/freeze`
  - `POST /workflow/run`
  - `GET /artifacts`

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

当前 `extract` 与 `workflow` 已采用 DeepSeek 严格执行模式，不做规则降级或兜底。
任一步骤失败会直接报错并中止流程。

可使用 `GET /llm/ping` 快速验证 DeepSeek 连通性。
