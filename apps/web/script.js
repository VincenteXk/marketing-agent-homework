const diffView = document.getElementById("diff_view");
const resultView = document.getElementById("result_view");

let extractedSpec = null;
let frozenSpec = null;

function getFormSpec() {
  const targetUsers = document
    .getElementById("target_users")
    .value.split(",")
    .map((x) => x.trim())
    .filter(Boolean);

  return {
    project_id: document.getElementById("project_id").value || "proj1",
    version: "draft",
    domain: document.getElementById("domain").value.trim(),
    goal: document.getElementById("goal").value.trim(),
    target_users: targetUsers,
    constraints: {
      timeline: "",
      budget: "",
      sample_size: Number(document.getElementById("sample_size").value || 100),
      must_use_credamo: true,
    },
    deliverables: {
      format: ["ppt", "pdf", "excel", "chat_logs"],
      deadline: document.getElementById("deadline").value.trim(),
    },
    notes: document.getElementById("notes").value.trim(),
  };
}

function fillForm(spec) {
  document.getElementById("project_id").value = spec.project_id || "";
  document.getElementById("domain").value = spec.domain || "";
  document.getElementById("goal").value = spec.goal || "";
  document.getElementById("target_users").value = (spec.target_users || []).join(",");
  document.getElementById("sample_size").value = spec.constraints?.sample_size || 100;
  document.getElementById("deadline").value = spec.deliverables?.deadline || "";
  document.getElementById("notes").value = spec.notes || "";
}

function showJson(target, obj) {
  target.textContent = JSON.stringify(obj, null, 2);
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "request failed");
  }
  return data;
}

async function loadArtifacts() {
  const response = await fetch("/artifacts");
  const data = await response.json();
  showJson(resultView, data);
}

document.getElementById("extract_btn").addEventListener("click", async () => {
  try {
    const currentSpec = getFormSpec();
    const chat = document.getElementById("chat_input").value.trim();
    const messages = chat ? chat.split("\n").filter(Boolean) : [];

    const data = await postJson("/spec/extract", {
      chat_messages: messages,
      current_spec: currentSpec,
    });
    extractedSpec = data.data.spec;
    fillForm(extractedSpec);
    showJson(diffView, { from: currentSpec, to: extractedSpec });
  } catch (error) {
    showJson(resultView, { ok: false, message: String(error) });
  }
});

document.getElementById("validate_btn").addEventListener("click", async () => {
  try {
    const spec = extractedSpec || getFormSpec();
    const data = await postJson("/spec/validate", { spec });
    showJson(resultView, data);
  } catch (error) {
    showJson(resultView, { ok: false, message: String(error) });
  }
});

document.getElementById("freeze_btn").addEventListener("click", async () => {
  try {
    const spec = extractedSpec || getFormSpec();
    const data = await postJson("/spec/freeze", { spec });
    frozenSpec = { ...spec, version: data.data.version };
    showJson(resultView, { freeze: data, frozen_spec_preview: frozenSpec });
  } catch (error) {
    showJson(resultView, { ok: false, message: String(error) });
  }
});

document.getElementById("run_btn").addEventListener("click", async () => {
  try {
    const spec = frozenSpec || extractedSpec || getFormSpec();
    const data = await postJson("/workflow/run", { spec });
    showJson(resultView, data);
  } catch (error) {
    showJson(resultView, { ok: false, message: String(error) });
  }
});

document.getElementById("reload_artifacts_btn").addEventListener("click", loadArtifacts);

loadArtifacts();
