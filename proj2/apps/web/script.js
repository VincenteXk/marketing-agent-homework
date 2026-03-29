/**
 * Proj2 前端：参数表单 + 只读分阶段展示区。
 * Agent 接入后请实现 startPromotionRun（或改为 SSE 回调里调用 updateRunStage）。
 */

const STAGE_DEFS = [
  { key: "strategy", title: "推广策略与核心信息" },
  { key: "copy", title: "Slogan 与广告文案" },
  { key: "visual_plan", title: "主视觉创意说明" },
  { key: "visual_assets", title: "主视觉图" },
];

const STATUS_LABEL = {
  pending: "待输出",
  active: "进行中…",
  done: "已完成",
  error: "失败",
};

/** @type {Map<string, HTMLElement>} */
const stageRoots = new Map();

/** 供「导出」使用：在 SSE 过程中写入 */
const exportState = {
  slogan: "",
  copy: "",
  /** @type {string[]} */
  imageUrls: [],
};

function resetExportState() {
  exportState.slogan = "";
  exportState.copy = "";
  exportState.imageUrls = [];
}

function exportReady() {
  return (
    Boolean(exportState.slogan) &&
    Boolean(exportState.copy) &&
    exportState.imageUrls.length >= 2
  );
}

function setExportUiVisible(visible) {
  const wrap = document.getElementById("export_wrap");
  if (!wrap) {
    return;
  }
  wrap.classList.toggle("hidden", !visible);
  wrap.setAttribute("aria-hidden", visible ? "false" : "true");
}

/**
 * @param {Blob} blob
 * @param {string} filename
 */
function triggerBlobDownload(blob, filename) {
  const a = document.createElement("a");
  const u = URL.createObjectURL(blob);
  a.href = u;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.setTimeout(() => URL.revokeObjectURL(u), 3000);
}

function buildExportTextBlob() {
  const text =
    "【推广 Slogan】\n" +
    exportState.slogan +
    "\n\n【广告文案】\n" +
    exportState.copy +
    "\n";
  return new Blob(["\uFEFF" + text], { type: "text/plain;charset=utf-8" });
}

async function exportViaDirectoryPicker() {
  const dir = await window.showDirectoryPicker();
  const textBlob = buildExportTextBlob();
  const txtHandle = await dir.getFileHandle("推广slogan和文案.txt", { create: true });
  const txtWritable = await txtHandle.createWritable();
  await txtWritable.write(textBlob);
  await txtWritable.close();

  const names = ["推广图1.png", "推广图2.png"];
  for (let i = 0; i < 2; i++) {
    const res = await fetch(exportState.imageUrls[i]);
    if (!res.ok) {
      throw new Error(`拉取图片 ${i + 1} 失败：${res.status}`);
    }
    const blob = await res.blob();
    const imgHandle = await dir.getFileHandle(names[i], { create: true });
    const imgW = await imgHandle.createWritable();
    await imgW.write(blob);
    await imgW.close();
  }
}

async function exportViaSequentialDownloads() {
  triggerBlobDownload(buildExportTextBlob(), "推广slogan和文案.txt");
  await new Promise((r) => window.setTimeout(r, 450));
  for (let i = 0; i < 2; i++) {
    const res = await fetch(exportState.imageUrls[i]);
    if (!res.ok) {
      throw new Error(`拉取图片 ${i + 1} 失败：${res.status}`);
    }
    const blob = await res.blob();
    triggerBlobDownload(blob, i === 0 ? "推广图1.png" : "推广图2.png");
    await new Promise((r) => window.setTimeout(r, 450));
  }
}

async function onExportClick() {
  if (!exportReady()) {
    window.alert("请等待全流程跑完并生成两张图后再导出。");
    return;
  }

  try {
    if (typeof window.showDirectoryPicker === "function") {
      await exportViaDirectoryPicker();
      window.alert("已在所选文件夹中保存 3 个文件。");
    } else {
      await exportViaSequentialDownloads();
      window.alert("已触发 3 次下载；若被浏览器拦截，请允许本站下载多个文件。");
    }
  } catch (e) {
    const err = /** @type {Error & { name?: string }} */ (e);
    if (err.name === "AbortError") {
      return;
    }
    console.error(e);
    window.alert("导出失败：" + (err.message || String(e)));
  }
}

function getRunParams() {
  return {
    product: document.getElementById("param_product").value.trim(),
    goal: document.getElementById("param_goal").value.trim(),
    budget: document.getElementById("param_budget").value.trim(),
    channels: document.getElementById("param_channels").value.trim(),
  };
}

function validateParams(params) {
  if (!params.product) {
    return "请填写「产品描述」。";
  }
  if (!params.goal) {
    return "请填写「推广目标」。";
  }
  return null;
}

function clearRunFeed() {
  const feed = document.getElementById("run_feed");
  feed.innerHTML = "";
  stageRoots.clear();
}

function mountStageSkeletons() {
  const feed = document.getElementById("run_feed");
  for (const def of STAGE_DEFS) {
    const block = document.createElement("section");
    block.className = "stage-block";
    block.dataset.stage = def.key;

    const head = document.createElement("div");
    head.className = "stage-head";

    const title = document.createElement("span");
    title.className = "stage-title";
    title.textContent = def.title;

    const status = document.createElement("span");
    status.className = "stage-status pending";
    status.textContent = STATUS_LABEL.pending;

    head.appendChild(title);
    head.appendChild(status);

    const body = document.createElement("div");
    body.className = "stage-body";

    if (def.key === "visual_assets") {
      const progress = document.createElement("p");
      progress.className = "stage-asset-progress small muted";
      progress.textContent = "";
      body.appendChild(progress);
      const imgs = document.createElement("div");
      imgs.className = "stage-images";
      const slot = document.createElement("div");
      slot.className = "stage-image-slot";
      slot.textContent = "两张推广图生成后将显示于此";
      imgs.appendChild(slot);
      body.appendChild(imgs);
    }

    block.appendChild(head);
    block.appendChild(body);
    feed.appendChild(block);

    stageRoots.set(def.key, block);
  }
}

/**
 * @param {string} key
 * @param {{ status?: 'pending'|'active'|'done'|'error', bodyText?: string, appendText?: string, imageUrls?: string[] }} patch
 */
function updateRunStage(key, patch) {
  const block = stageRoots.get(key);
  if (!block) {
    return;
  }
  const statusEl = block.querySelector(".stage-status");
  const bodyEl = block.querySelector(".stage-body");

  if (patch.status && statusEl) {
    statusEl.className = "stage-status " + patch.status;
    statusEl.textContent = STATUS_LABEL[patch.status] || patch.status;
  }

  if (key === "visual_assets") {
    if (patch.imageUrls && patch.imageUrls.length > 0) {
      let imgs = bodyEl.querySelector(".stage-images");
      if (!imgs) {
        imgs = document.createElement("div");
        imgs.className = "stage-images";
        bodyEl.appendChild(imgs);
      }
      imgs.innerHTML = "";
      patch.imageUrls.forEach((url, idx) => {
        const slot = document.createElement("div");
        slot.className = "stage-image-slot";
        const img = document.createElement("img");
        img.src = url;
        img.alt = idx === 0 ? "推广图一" : "推广图二";
        slot.appendChild(img);
        imgs.appendChild(slot);
      });
      return;
    }
  }

  if (patch.bodyText != null && bodyEl) {
    if (key === "visual_assets") {
      const prog = bodyEl.querySelector(".stage-asset-progress");
      if (prog) {
        prog.textContent = patch.bodyText;
      }
    } else {
      bodyEl.textContent = patch.bodyText;
    }
  } else if (patch.appendText && bodyEl && key !== "visual_assets") {
    bodyEl.textContent += patch.appendText;
  }
}

/**
 * @param {Record<string, unknown>} ev
 */
function handlePromotionEvent(ev) {
  if (ev.event === "error") {
    window.alert(/** @type {string} */ (ev.message || "运行出错"));
    return;
  }
  if (ev.event === "done") {
    const data = ev.data;
    if (data && typeof data === "object") {
      if (data.slogan != null) {
        exportState.slogan = String(data.slogan);
      }
      if (data.copy != null) {
        exportState.copy = String(data.copy);
      }
    }
    return;
  }
  if (ev.event !== "stage" || !ev.stage) {
    return;
  }
  const stage = /** @type {string} */ (ev.stage);
  const status = ev.status;
  const text = ev.text != null ? String(ev.text) : null;
  const singleUrl = ev.image_url != null ? String(ev.image_url) : null;
  const multiUrls = Array.isArray(ev.image_urls)
    ? ev.image_urls.map((u) => String(u)).filter(Boolean)
    : [];

  if (status === "active") {
    updateRunStage(stage, { status: "active" });
  } else if (status === "update" && text != null) {
    updateRunStage(stage, { status: "active", bodyText: text });
  } else if (status === "done") {
    const rawList = multiUrls.length > 0 ? multiUrls : singleUrl ? [singleUrl] : [];
    if (rawList.length > 0) {
      const proxied = rawList.map(
        (u) => `/promotion/proxy-image?url=${encodeURIComponent(u)}`,
      );
      if (stage === "visual_assets") {
        exportState.imageUrls = proxied;
      }
      updateRunStage(stage, { status: "done", imageUrls: proxied });
    } else if (text != null) {
      updateRunStage(stage, { status: "done", bodyText: text });
    } else {
      updateRunStage(stage, { status: "done" });
    }
  }
}

/**
 * @param {ReadableStream<Uint8Array> | null} stream
 */
async function consumeSseStream(stream) {
  if (!stream) {
    throw new Error("响应无正文流");
  }
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data:")) {
          continue;
        }
        const raw = line.slice(5).trim();
        if (raw === "[DONE]") {
          continue;
        }
        try {
          handlePromotionEvent(JSON.parse(raw));
        } catch (e) {
          console.warn("SSE 解析跳过", raw, e);
        }
      }
    }
  }
}

/**
 * @param {ReturnType<typeof getRunParams>} params
 * @returns {Promise<void>}
 */
async function startPromotionRun(params) {
  const res = await fetch("/promotion/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  await consumeSseStream(res.body);
}

async function onGenerateClick() {
  const params = getRunParams();
  const err = validateParams(params);
  if (err) {
    window.alert(err);
    return;
  }

  const btn = document.getElementById("btn_generate");
  btn.disabled = true;
  resetExportState();
  setExportUiVisible(false);
  clearRunFeed();
  mountStageSkeletons();

  try {
    await startPromotionRun(params);
    if (exportReady()) {
      setExportUiVisible(true);
    }
  } catch (e) {
    console.error(e);
    const first = stageRoots.get("strategy");
    if (first) {
      const statusEl = first.querySelector(".stage-status");
      if (statusEl) {
        statusEl.className = "stage-status error";
        statusEl.textContent = STATUS_LABEL.error;
      }
    }
    window.alert("运行失败，请稍后重试或查看控制台。");
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("btn_generate").addEventListener("click", () => {
  void onGenerateClick();
});

document.getElementById("btn_export").addEventListener("click", () => {
  void onExportClick();
});

window.proj2Feed = {
  getRunParams,
  updateRunStage,
  startPromotionRun,
  handlePromotionEvent,
  STAGE_DEFS,
  exportState,
};
