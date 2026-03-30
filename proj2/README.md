# Proj2 · Agent 推广方案

顶部参数 + 只读分阶段输出（**生成过程区不限制高度、不内滚动**，便于整页长截图）。后端流水线：标语 5 选 1 → 正文 5 选 1 → **中文双图生图提示词 5 套选 1（每套图一+图二整体评分）** → **主视觉迭代**：每 **版**先展示「主视觉图（第 N 版）」再展示「主视觉画面验收」；**每一版都同时验收图一与图二**，若仅一侧未通过则下一版**只重绘未通过侧**，已通过侧**沿用且不重复送 VLM**；整段最多 **5 版**（首版 + **4** 轮迭代）。生图模型说明见仓库内 **`生图.md`**（Z-Image-Turbo 强调中英文文字渲染能力）；魔搭 HTTP 请求默认带 **`1024x1024`**，并可通过环境变量传入 `steps` / `guidance`（与官方 diffusers 示例一致时需以魔搭接口实际支持为准）。LLM 走 **DeepSeek**，生图走 **ModelScope**，验收走 **Volc Ark 视觉模型**。

## 环境变量

复制 `proj1/.env` 中的 `DEEPSEEK_*`，以及 DeepSpeak `server/.env` 中的 `MODELSCOPE_TOKEN`（或 `MODELSCOPE_API_KEY`）、**仅与 VLM 相关的** `VLM_ARK_API_KEY`（可选 `VLM_MODEL`）到 **`proj2/.env`**（勿提交仓库，见 `proj2/.gitignore`）。可选：`MODELSCOPE_IMAGE_SIZE`（默认 `1024x1024`）、`MODELSCOPE_IMAGE_STEPS`、`MODELSCOPE_IMAGE_GUIDANCE`。可参考 `proj2/.env.example`。VLM 走字节方舟 `https://ark.cn-beijing.volces.com/api/v3/responses`，与 DeepSpeak `server/routes/vlmProxy.ts` 一致。

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

- `POST /promotion/stream`：请求体 JSON 字段 `product`、`goal`、`budget`、`channels`；响应为 **SSE**（`data: {...}`，以 `data: [DONE]` 结束）。主视觉阶段为 **`stage: visual_iterate`**：`round_images`（`round`、`image_urls`、`kept`）与 `round_qa`（`round`、`results[]`）成对出现；结束时 `done.data.image_urls` 为当前采用的 2 个 URL。
- `GET /promotion/proxy-image?url=`：代理拉取魔搭返回的 HTTPS 图链（限制 modelscope / `.cn` / aliyuncs 域名）。

## 目录

- `apps/web`：静态页与 SSE 消费逻辑
- `apps/api/services/promotion_pipeline.py`：流水线与评分
- `apps/api/services/llm_service.py`：DeepSeek HTTP
- `apps/api/services/modelscope_image.py`：魔搭文生图
