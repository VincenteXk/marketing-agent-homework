# Proj2 · Agent 推广方案

顶部参数 + 只读分阶段输出（**生成过程区不限制高度、不内滚动**，便于整页长截图）。后端流水线：标语 5 选 1 → 正文 5 选 1 → **中文双图生图提示词 5 套选 1（每套图一+图二整体评分）** → 魔搭 **并行文生图 2 张**。LLM 走 **DeepSeek**（与 `proj1` 相同调用方式），生图走 **ModelScope**（`https://api-inference.modelscope.cn`，异步创建 + 轮询任务）。

## 环境变量

复制 `proj1/.env` 中的 `DEEPSEEK_*`，以及 DeepSpeak `server/.env` 中的 `MODELSCOPE_TOKEN`（或 `MODELSCOPE_API_KEY`）到 **`proj2/.env`**（勿提交仓库，见 `proj2/.gitignore`）。可参考 `proj2/.env.example`。

## 启动

在 **`proj2/`** 目录下：

```bash
pip install -r requirements.txt
uvicorn apps.api.main:app --reload --port 8010
```

打开 <http://127.0.0.1:8010> ，填参后点「生成推广文案」。

## 评分规则（三并行 LLM）

- **标语 / 正文**：各 5 候选；每候选由三个独立子维度各打 1–10 分，取算术均分最高者。
- **生图**：5 **套** 双图中文 prompt；每套按「图一+图二」**整体**接受三维度评分（产品双图契合、大陆渠道适配、创意与双图协调性），取均分最高的一套，再各生成一张图。

## 静态资源与 304

浏览器对已缓存的 `styles.css` / `script.js` 可能返回 **304 Not Modified**，属正常机制。本项目对 `/`、`/static/*` 响应加了 **`Cache-Control: no-store`**，一般刷新后会直接 **200**；若仍见 304，可用 **强制刷新（Ctrl+F5）** 或无痕窗口。

## API

- `POST /promotion/stream`：请求体 JSON 字段 `product`、`goal`、`budget`、`channels`；响应为 **SSE**（`data: {...}`，以 `data: [DONE]` 结束）。成图阶段 `done` 事件含 `image_urls` 数组（2 个 URL）。
- `GET /promotion/proxy-image?url=`：代理拉取魔搭返回的 HTTPS 图链（限制 modelscope / `.cn` / aliyuncs 域名）。

## 目录

- `apps/web`：静态页与 SSE 消费逻辑
- `apps/api/services/promotion_pipeline.py`：流水线与评分
- `apps/api/services/llm_service.py`：DeepSeek HTTP
- `apps/api/services/modelscope_image.py`：魔搭文生图
