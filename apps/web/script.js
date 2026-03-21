const chatLog = document.getElementById("chat_log");
const sessionHint = document.getElementById("session_hint");
const timeline = document.getElementById("timeline");
const statusView = document.getElementById("status_view");
const resultView = document.getElementById("result_view");
const resultCards = document.getElementById("result_cards");
const nextQuestionBox = document.getElementById("next_question_box");
const nextQuestionText = document.getElementById("next_question_text");
const statusHuman = document.getElementById("status_human");
const resultTip = document.getElementById("result_tip");
const guessSuggestions = document.getElementById("guess_suggestions");
const knownInfo = document.getElementById("known_info");
const sendBtn = document.getElementById("send_btn");
const runBtn = document.getElementById("run_btn");
const chatInput = document.getElementById("chat_input");
const laneInput = document.getElementById("lane_input");
const researchBtn = document.getElementById("research_btn");
const queryPreview = document.getElementById("query_preview");
const researchStream = document.getElementById("research_stream");
const researchStructured = document.getElementById("research_structured");
const summaryStructured = document.getElementById("summary_structured");
const summaryLaneTitle = document.getElementById("summary_lane_title");
const citationList = document.getElementById("citation_list");
const tabButtons = Array.from(document.querySelectorAll(".tab-btn[data-tab]"));
const tabPanels = Array.from(document.querySelectorAll(".tab-content[data-tab-content]"));
const conceptChatLog = document.getElementById("concept_chat_log");
const conceptChatInput = document.getElementById("concept_chat_input");
const conceptSendBtn = document.getElementById("concept_send_btn");
const conceptConfirmedBox = document.getElementById("concept_confirmed_box");
const summaryConfirmedBox = document.getElementById("summary_confirmed_box");
const summaryPersonaNames = document.getElementById("summary_persona_names");
const exportMdBtn = document.getElementById("export_md_btn");
const restartBtn = document.getElementById("restart_btn");
const personaStatusHint = document.getElementById("persona_status_hint");
const personaProgressText = document.getElementById("persona_progress_text");
const personaStats = document.getElementById("persona_stats");
const personaChart = document.getElementById("persona_chart");
const personaCards = document.getElementById("persona_cards");
const personaGenerateBtn = document.getElementById("persona_generate_btn");
const conjointStatusHint = document.getElementById("conjoint_status_hint");
const conjointResult = document.getElementById("conjoint_result");
const conjointGenerateBtn = document.getElementById("conjoint_generate_btn");
const simulationStatusHint = document.getElementById("simulation_status_hint");
const simulationDataView = document.getElementById("simulation_data_view");
const simulationGenerateBtn = document.getElementById("simulation_generate_btn");
const analysisStatusHint = document.getElementById("analysis_status_hint");
const analysisResultView = document.getElementById("analysis_result_view");
const analysisGenerateBtn = document.getElementById("analysis_generate_btn");


const STEP_ORDER = [
  "market_exploration",
  "persona_generation",
  "conjoint_design",
  "simulation_data",
  "conjoint_analysis",
  "reflection",
];

const STEP_LABEL = {
  market_exploration: "市场探索",
  persona_generation: "消费者画像",
  conjoint_design: "联合分析设计",
  simulation_data: "消费者数据模拟",
  conjoint_analysis: "联合分析结果",
  reflection: "反思与建议",
};

let sessionId = null;
let pollTimer = null;
let resultAutoShown = false;
let readyToRun = false;
let researchStreamSegments = [];
let streamRenderScheduled = false;
let persistTimer = null;
let currentKnownInfo = {};
let currentMissingFields = [];
let currentGuesses = [];
let currentNextQuestion = "请先说说你想分析的业务场景。";
let currentNextQuestionReady = false;
let currentStructuredData = {};
let currentCitations = [];
let currentTimelineSteps = [];
let currentResultSteps = [];
let currentPersonaStep = null;
let currentConjointStep = null;
let currentSimulationDataStep = null;
let currentAnalysisStep = null;
let chatMessages = [];
let activeTab = "research";
let currentTargetLane = "";
let conceptChatMessages = [];
let currentResearchFullText = "";
let currentConfirmedConcept = "";
let conceptSending = false;
const WORKFLOW_STAGE_ORDER = ["research", "concept", "persona", "conjoint", "simulation", "analysis", "real-data"];
const WORKFLOW_STAGE_LEVEL = {
  research: 0,
  concept: 1,
  persona: 2,
  conjoint: 3,
  simulation: 4,
  analysis: 5,
  "real-data": 6,
};
const WORKFLOW_MAX_LEVEL = Math.max(...Object.values(WORKFLOW_STAGE_LEVEL));
let workflowCurrentStageId = WORKFLOW_STAGE_ORDER[0];
let workflowUnlockedStageIndex = 0;
let workflowCompletedStageMap = {};
let workflowSubmittedStageMap = {};
let workflowLockedStageMap = {};

const UI_STATE_KEY = "proj1.ui.state.v1";

function setPersonaProgress(text) {
  if (!personaProgressText) {
    return;
  }
  const content = String(text || "").trim() || "待开始";
  personaProgressText.textContent = `当前进度：${content}`;
}

function renderSummaryPersonaNames() {
  if (!summaryPersonaNames) {
    return;
  }
  const personas = Array.isArray(currentPersonaStep?.outputs?.personas) ? currentPersonaStep.outputs.personas : [];
  const names = personas
    .map((item) => String(item?.type || "").trim())
    .filter(Boolean)
    .slice(0, 3);
  if (!names.length) {
    summaryPersonaNames.textContent = "";
    summaryPersonaNames.classList.add("hidden");
    return;
  }
  summaryPersonaNames.innerHTML = `<strong>消费者画像：</strong>${names.map((item) => escapeHtml(item)).join("，")}`;
  summaryPersonaNames.classList.remove("hidden");
}

function buildEmptyWorkflowMap() {
  return WORKFLOW_STAGE_ORDER.reduce((acc, stageId) => {
    acc[stageId] = false;
    return acc;
  }, {});
}

function resetWorkflowState() {
  workflowCurrentStageId = WORKFLOW_STAGE_ORDER[0];
  workflowUnlockedStageIndex = 0;
  workflowCompletedStageMap = buildEmptyWorkflowMap();
  workflowSubmittedStageMap = buildEmptyWorkflowMap();
  workflowLockedStageMap = buildEmptyWorkflowMap();
}

function getStageLevel(stageId) {
  const level = WORKFLOW_STAGE_LEVEL[String(stageId || "")];
  return Number.isInteger(level) ? level : -1;
}

function getStageIdsByLevel(level) {
  return WORKFLOW_STAGE_ORDER.filter((stageId) => WORKFLOW_STAGE_LEVEL[stageId] === level);
}

function getDefaultStageByLevel(level) {
  return getStageIdsByLevel(level)[0] || WORKFLOW_STAGE_ORDER[0];
}

function isSummaryTab(tabId) {
  return String(tabId || "") === "summary";
}

function isStageUnlocked(stageId) {
  const level = getStageLevel(stageId);
  if (level < 0) {
    return false;
  }
  return level <= workflowUnlockedStageIndex;
}

function applyWorkflowLocksToUi() {
  tabButtons.forEach((button) => {
    const tabId = String(button.dataset.tab || "");
    if (isSummaryTab(tabId)) {
      button.disabled = false;
      button.classList.remove("tab-btn-locked");
      return;
    }
    const unlocked = isStageUnlocked(tabId);
    button.disabled = !unlocked;
    button.classList.toggle("tab-btn-locked", !unlocked);
  });

  tabPanels.forEach((panel) => {
    const tabId = String(panel.dataset.tabContent || "");
    if (isSummaryTab(tabId)) {
      panel.inert = false;
      panel.classList.remove("tab-content-stage-locked");
      return;
    }

    const editable = isStageUnlocked(tabId);
    panel.inert = !editable;
    panel.classList.toggle("tab-content-stage-locked", !editable);
  });
}

function moveWorkflowToNextStage(stageId) {
  const stageLevel = getStageLevel(stageId);
  if (stageLevel < 0) {
    return;
  }
  const nextIdx = Math.min(stageLevel + 1, WORKFLOW_MAX_LEVEL);
  if (nextIdx > workflowUnlockedStageIndex) {
    workflowUnlockedStageIndex = nextIdx;
  }
  const nextStageId = getDefaultStageByLevel(nextIdx);
  if (nextStageId && nextStageId !== stageId) {
    // 解锁下一阶段，但不自动切换标签页，保持用户当前浏览上下文
    workflowCurrentStageId = nextStageId;
  }
  applyWorkflowLocksToUi();
  schedulePersistUiState();
}

function markStageSubmitted(stageId) {
  const stageLevel = getStageLevel(stageId);
  if (stageLevel < 0) {
    return;
  }
  if (!workflowSubmittedStageMap[stageId]) {
    workflowSubmittedStageMap[stageId] = true;
    if (stageLevel > 0) {
      const prevLevelStageIds = getStageIdsByLevel(stageLevel - 1);
      prevLevelStageIds.forEach((prevStageId) => {
        workflowLockedStageMap[prevStageId] = true;
      });
    }
  }
  workflowCurrentStageId = stageId;
  applyWorkflowLocksToUi();
  schedulePersistUiState();
}

function markStageCompleted(stageId) {
  const stageLevel = getStageLevel(stageId);
  if (stageLevel < 0) {
    return;
  }
  workflowCompletedStageMap[stageId] = true;
  if (stageLevel < WORKFLOW_MAX_LEVEL) {
    moveWorkflowToNextStage(stageId);
  }
}

function hasResearchOutputFromDoneEvent(event) {
  const structured = event && typeof event === "object" ? event.structured || {} : {};
  const hasStructuredList =
    (Array.isArray(structured.industry_pain_points) && structured.industry_pain_points.length > 0) ||
    (Array.isArray(structured.product_gaps) && structured.product_gaps.length > 0) ||
    (Array.isArray(structured.opportunities) && structured.opportunities.length > 0);
  const fullText = String((event && event.full_text) || "").trim();
  const hasCitations = Array.isArray(event?.citations) && event.citations.length > 0;
  return Boolean(fullText || hasStructuredList || hasCitations);
}

function hasStructuredResearchData(structuredData) {
  const structured = structuredData && typeof structuredData === "object" ? structuredData : {};
  return (
    (Array.isArray(structured.industry_pain_points) && structured.industry_pain_points.length > 0) ||
    (Array.isArray(structured.product_gaps) && structured.product_gaps.length > 0) ||
    (Array.isArray(structured.opportunities) && structured.opportunities.length > 0)
  );
}

function hydrateWorkflowStateFromSnapshot(state) {
  const hasResearchOutput =
    Boolean(String(state.researchFullText || "").trim()) ||
    hasStructuredResearchData(state.structuredData || {}) ||
    (Array.isArray(state.citations) && state.citations.length > 0);
  if (hasResearchOutput) {
    workflowSubmittedStageMap.research = true;
    workflowCompletedStageMap.research = true;
    workflowUnlockedStageIndex = Math.max(workflowUnlockedStageIndex, 1);
    if (workflowCurrentStageId === "research") {
      workflowCurrentStageId = "concept";
    }
  }

  const hasConceptInput =
    Array.isArray(state.conceptChatMessages) &&
    state.conceptChatMessages.some((item) => item && item.role === "user" && String(item.text || "").trim());
  if (hasConceptInput) {
    workflowSubmittedStageMap.concept = true;
    workflowLockedStageMap.research = true;
    if (workflowCurrentStageId === "research") {
      workflowCurrentStageId = "concept";
    }
  }

  const hasPersonaOutput = Boolean(state.personaStep && Array.isArray(state.personaStep?.outputs?.personas) && state.personaStep.outputs.personas.length > 0);
  if (hasPersonaOutput) {
    workflowSubmittedStageMap.persona = true;
    workflowCompletedStageMap.persona = true;
    workflowLockedStageMap.concept = true;
    workflowUnlockedStageIndex = Math.max(workflowUnlockedStageIndex, 3);
    if (workflowCurrentStageId === "concept" || workflowCurrentStageId === "persona") {
      workflowCurrentStageId = "conjoint";
    }
  }
}

function showJson(target, obj) {
  target.textContent = JSON.stringify(obj, null, 2);
  schedulePersistUiState();
}

function setStatusHumanText(text) {
  statusHuman.textContent = text;
  schedulePersistUiState();
}

function setNextQuestion(text, isReady = false) {
  currentNextQuestion = text || "";
  currentNextQuestionReady = Boolean(isReady);
  nextQuestionText.textContent = text;
  nextQuestionBox.classList.remove("checklist-ok", "checklist-warning");
  nextQuestionBox.classList.add(isReady ? "checklist-ok" : "checklist-warning");
  schedulePersistUiState();
}

function setActionState() {
  if (readyToRun) {
    runBtn.disabled = false;
    runBtn.classList.add("primary");
    sendBtn.classList.remove("primary");
    sendBtn.textContent = "继续补充（可选）";
    return;
  }
  runBtn.disabled = true;
  runBtn.classList.remove("primary");
  sendBtn.classList.add("primary");
  sendBtn.textContent = "发送回答";
  schedulePersistUiState();
}

function renderGuessSuggestions(guesses = []) {
  currentGuesses = Array.isArray(guesses) ? guesses : [];
  guessSuggestions.innerHTML = "";
  if (!Array.isArray(guesses) || guesses.length === 0) {
    schedulePersistUiState();
    return;
  }
  guesses.forEach((guess) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "suggestion-chip";
    btn.textContent = guess;
    btn.addEventListener("click", () => {
      chatInput.value = guess;
      chatInput.focus();
    });
    guessSuggestions.appendChild(btn);
  });
  schedulePersistUiState();
}

function renderKnownInfo(info = {}, missingFields = []) {
  currentKnownInfo = info || {};
  currentMissingFields = Array.isArray(missingFields) ? missingFields : [];
  const missing = new Set(Array.isArray(missingFields) ? missingFields : []);
  const targetUsers = Array.isArray(info.target_users) && info.target_users.length > 0 ? info.target_users.join(" / ") : "";
  const rows = [
    { key: "domain", label: "赛道", value: info.domain || "" },
    { key: "goal", label: "目标", value: info.goal || "" },
    { key: "target_users", label: "目标用户", value: targetUsers },
    { key: "sample_size", label: "样本量", value: info.sample_size ? String(info.sample_size) : "" },
    { key: "deadline", label: "截止时间", value: info.deadline || "" },
  ];

  knownInfo.innerHTML = "";
  rows.forEach((row) => {
    const card = document.createElement("div");
    const isMissing = missing.has(row.key) || !row.value;
    card.className = `known-item ${isMissing ? "known-item-missing" : "known-item-ready"}`;

    const label = document.createElement("div");
    label.className = "known-label";
    label.textContent = row.label;

    const value = document.createElement("div");
    value.className = "known-value";
    value.textContent = row.value || "未填写";

    card.appendChild(label);
    card.appendChild(value);
    knownInfo.appendChild(card);
  });
  schedulePersistUiState();
}

function statusToText(status) {
  if (status === "running") {
    return "分析进行中，系统正在自动执行各步骤。";
  }
  if (status === "completed") {
    return "分析已完成，结论卡片已更新到下方。";
  }
  if (status === "failed") {
    return "分析失败，请先补充信息或查看错误提示后重试。";
  }
  return "还没开始分析。先按 Agent 的问题补充信息。";
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

function parseSseEvents(chunk, onEvent) {
  const blocks = chunk.split("\n\n");
  const remains = blocks.pop() || "";
  blocks.forEach((block) => {
    const lines = block.split("\n");
    lines.forEach((line) => {
      const text = line.trim();
      if (!text.startsWith("data:")) {
        return;
      }
      const payload = text.slice(5).trim();
      if (!payload) {
        return;
      }
      try {
        onEvent(JSON.parse(payload));
      } catch (error) {
        // ignore broken event fragments
      }
    });
  });
  return remains;
}

function collectUiState() {
  return {
    laneInput: laneInput.value || "",
    queryPreview: queryPreview.textContent || "",
    researchStreamSegments,
    structuredData: currentStructuredData,
    citations: currentCitations,
    sessionId,
    readyToRun,
    resultAutoShown,
    knownInfo: currentKnownInfo,
    missingFields: currentMissingFields,
    nextQuestion: currentNextQuestion,
    nextQuestionReady: currentNextQuestionReady,
    guesses: currentGuesses,
    statusHuman: statusHuman.textContent || "",
    statusJsonText: statusView.textContent || "",
    resultJsonText: resultView.textContent || "",
    resultTipText: resultTip.textContent || "",
    timelineSteps: currentTimelineSteps,
    resultSteps: currentResultSteps,
    personaStep: currentPersonaStep,
    personaProgressText: personaProgressText ? personaProgressText.textContent : "",
    conjointStep: currentConjointStep,
    simulationDataStep: currentSimulationDataStep,
    chatMessages,
    activeTab,
    targetLane: currentTargetLane,
    conceptChatMessages,
    researchFullText: currentResearchFullText,
    confirmedConcept: currentConfirmedConcept,
    workflowCurrentStageId,
    workflowUnlockedStageIndex,
    workflowCompletedStageMap,
    workflowSubmittedStageMap,
    workflowLockedStageMap,
  };
}

function saveUiState() {
  try {
    const payload = collectUiState();
    localStorage.setItem(UI_STATE_KEY, JSON.stringify(payload));
  } catch (error) {
    // ignore storage quota or privacy mode errors
  }
}

function schedulePersistUiState() {
  if (persistTimer) {
    clearTimeout(persistTimer);
  }
  persistTimer = setTimeout(() => {
    saveUiState();
    persistTimer = null;
  }, 180);
}

function loadUiState() {
  try {
    const raw = localStorage.getItem(UI_STATE_KEY);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw);
  } catch (error) {
    return null;
  }
}

function buildConceptGreetingText() {
  const lane = currentTargetLane || "该";
  return `你选定了${lane}赛道，现在我们来一起完善一下你的产品概念吧。`;
}

function renderConfirmedConcept() {
  const text = currentConfirmedConcept
    ? `<strong>产品概念已确认：</strong>${escapeHtml(currentConfirmedConcept)}`
    : "";
  [conceptConfirmedBox, summaryConfirmedBox].forEach((target) => {
    if (!target) {
      return;
    }
    target.innerHTML = text;
    target.classList.toggle("hidden", !text);
  });
  const locked = Boolean(currentConfirmedConcept);
  if (conceptChatInput) {
    conceptChatInput.disabled = locked;
    conceptChatInput.placeholder = locked ? "产品概念已确认，输入已锁定" : "请输入你的想法，例如：我们主打通勤场景下的轻量化方案";
  }
  if (conceptSendBtn) {
    conceptSendBtn.disabled = locked;
  }
  if (locked) {
    markStageCompleted("concept");
    if (personaStatusHint && !currentPersonaStep) {
      personaStatusHint.textContent = "产品概念已确认，可点击“基于已确认概念生成画像”。";
    }
    if (!currentPersonaStep) {
      setPersonaProgress("待生成（可点击按钮）");
    }
  } else {
    applyWorkflowLocksToUi();
    setPersonaProgress("等待概念确认");
  }
  renderSummaryPersonaNames();
  schedulePersistUiState();
}

function ensureConceptGreeting() {
  const greetingText = buildConceptGreetingText();
  if (!Array.isArray(conceptChatMessages) || conceptChatMessages.length === 0) {
    conceptChatMessages = [{ role: "agent", text: greetingText }];
    renderConceptChatMessages();
    return;
  }
  const hasUserMessage = conceptChatMessages.some((item) => item.role === "user");
  if (!hasUserMessage && conceptChatMessages[0]?.role === "agent" && conceptChatMessages[0].text !== greetingText) {
    conceptChatMessages[0].text = greetingText;
    renderConceptChatMessages();
  }
}

function renderConceptChatMessages() {
  if (!conceptChatLog) {
    return;
  }
  conceptChatLog.innerHTML = "";
  conceptChatMessages.forEach((message) => {
    const row = document.createElement("div");
    row.className = `concept-chat-row ${message.role === "user" ? "concept-chat-row-user" : "concept-chat-row-agent"}`;
    const bubble = document.createElement("div");
    bubble.className = `concept-bubble ${message.role === "user" ? "concept-bubble-user" : "concept-bubble-agent"}`;
    bubble.textContent = String(message.text || "");
    row.appendChild(bubble);
    conceptChatLog.appendChild(row);
  });
  conceptChatLog.scrollTop = conceptChatLog.scrollHeight;
  schedulePersistUiState();
}

function addConceptMessage(role, text) {
  conceptChatMessages.push({ role: String(role || "agent"), text: String(text || "") });
  renderConceptChatMessages();
}

function getResearchContextForConcept() {
  if (currentResearchFullText) {
    return currentResearchFullText;
  }
  const answerText = researchStreamSegments
    .filter((item) => item && item.kind === "answer")
    .map((item) => String(item.text || ""))
    .join("")
    .trim();
  return answerText;
}

function extractAssistantReplyFromJsonStream(rawText) {
  const source = String(rawText || "");
  const keyIndex = source.indexOf("\"assistant_reply\"");
  if (keyIndex < 0) {
    return { started: false, complete: false, text: "" };
  }
  const colonIndex = source.indexOf(":", keyIndex);
  if (colonIndex < 0) {
    return { started: true, complete: false, text: "" };
  }
  let quoteIndex = -1;
  for (let i = colonIndex + 1; i < source.length; i += 1) {
    const ch = source[i];
    if (ch === " " || ch === "\n" || ch === "\r" || ch === "\t") {
      continue;
    }
    if (ch === "\"") {
      quoteIndex = i;
    }
    break;
  }
  if (quoteIndex < 0) {
    return { started: true, complete: false, text: "" };
  }

  let escaped = false;
  let complete = false;
  let out = "";
  for (let i = quoteIndex + 1; i < source.length; i += 1) {
    const ch = source[i];
    if (escaped) {
      if (ch === "n") {
        out += "\n";
      } else if (ch === "r") {
        out += "\r";
      } else if (ch === "t") {
        out += "\t";
      } else if (ch === "\"") {
        out += "\"";
      } else if (ch === "\\") {
        out += "\\";
      } else if (ch === "/") {
        out += "/";
      } else {
        out += ch;
      }
      escaped = false;
      continue;
    }
    if (ch === "\\") {
      escaped = true;
      continue;
    }
    if (ch === "\"") {
      complete = true;
      break;
    }
    out += ch;
  }
  return { started: true, complete, text: out };
}

async function submitConceptMessage() {
  if (!conceptChatInput) {
    return;
  }
  if (currentConfirmedConcept) {
    return;
  }
  if (conceptSending) {
    return;
  }
  const text = (conceptChatInput.value || "").trim();
  if (!text) {
    return;
  }
  markStageSubmitted("concept");
  addConceptMessage("user", text);
  conceptChatInput.value = "";
  const historyForRequest = conceptChatMessages.map((item) => ({
    role: item.role,
    text: item.text,
  }));
  const streamingIndex = conceptChatMessages.length;
  conceptChatMessages.push({ role: "agent", text: "..." });
  renderConceptChatMessages();
  conceptSending = true;
  if (conceptSendBtn) {
    conceptSendBtn.disabled = true;
  }
  conceptChatInput.disabled = true;
  try {
    const payload = {
      lane: currentTargetLane || (laneInput.value || "").trim(),
      research_context: getResearchContextForConcept(),
      opening_message: buildConceptGreetingText(),
      current_concept: currentConfirmedConcept,
      messages: historyForRequest,
    };
    const response = await fetch("/concept/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok || !response.body) {
      const textBody = await response.text();
      throw new Error(textBody || "产品概念流式请求失败");
    }

    let receivedFirstToken = false;
    let receivedDone = false;
    let streamError = "";
    let rawJsonBuffer = "";
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      buffer = parseSseEvents(buffer, (event) => {
        if (event.type === "delta") {
          const piece = String(event.content || "");
          if (!piece) {
            return;
          }
          rawJsonBuffer += piece;
          const replyState = extractAssistantReplyFromJsonStream(rawJsonBuffer);
          if (!replyState.started) {
            return;
          }
          conceptChatMessages[streamingIndex].text = replyState.text || "...";
          receivedFirstToken = receivedFirstToken || replyState.text.length > 0;
          renderConceptChatMessages();
          return;
        }
        if (event.type === "done") {
          const reply = String(event.assistant_reply || "").trim();
          const confirmed = Boolean(event.is_confirmed) && String(event.final_concept || "").trim();
          if (confirmed) {
            conceptChatMessages.splice(streamingIndex, 1);
            renderConceptChatMessages();
            currentConfirmedConcept = String(event.final_concept).trim();
            renderConfirmedConcept();
          } else if (!receivedFirstToken) {
            conceptChatMessages[streamingIndex].text = reply || "（未返回有效内容）";
            renderConceptChatMessages();
          }
          receivedDone = true;
          return;
        }
        if (event.type === "error") {
          streamError = String(event.message || "产品概念流式请求失败");
        }
      });
      if (streamError) {
        throw new Error(streamError);
      }
    }

    if (!receivedDone && !receivedFirstToken) {
      conceptChatMessages[streamingIndex].text = "请求结束，但未收到有效回复。";
      renderConceptChatMessages();
    }
  } catch (error) {
    conceptChatMessages[streamingIndex].text = `请求失败：${String(error)}`;
    renderConceptChatMessages();
  } finally {
    conceptSending = false;
    if (conceptSendBtn && !currentConfirmedConcept) {
      conceptSendBtn.disabled = false;
    }
    if (!currentConfirmedConcept) {
      conceptChatInput.disabled = false;
      conceptChatInput.focus();
    }
  }
}

function parseLaneFromFirstSentence(firstSentence) {
  const source = String(firstSentence || "").trim();
  if (!source) {
    return "";
  }
  const matched = source.match(/^分析(.+?)市场$/);
  if (matched && matched[1]) {
    return matched[1].trim();
  }
  return source.replace(/^分析/, "").replace(/市场$/, "").trim() || source;
}

function setSummaryLaneTitleByName(laneName) {
  currentTargetLane = String(laneName || "").trim();
  if (!summaryLaneTitle) {
    return;
  }
  summaryLaneTitle.textContent = `目标赛道：${currentTargetLane || "未生成"}`;
  ensureConceptGreeting();
  schedulePersistUiState();
}

function setSummaryLaneTitleByFirstSentence(firstSentence) {
  const laneName = parseLaneFromFirstSentence(firstSentence);
  setSummaryLaneTitleByName(laneName);
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttribute(text) {
  return String(text).replaceAll("\"", "&quot;").replaceAll("'", "&#39;");
}

function isSafeExternalUrl(url) {
  if (!url) {
    return false;
  }
  const value = String(url).trim();
  return /^https?:\/\//i.test(value);
}

function buildCitationReference(index) {
  if (!Number.isInteger(index) || index <= 0) {
    return null;
  }
  const item = currentCitations[index - 1];
  if (item && isSafeExternalUrl(item.link)) {
    return {
      href: String(item.link).trim(),
      external: true,
    };
  }
  return {
    href: `#citation-source-${index}`,
    external: false,
  };
}

function renderInlineMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  html = html.replace(/\[\[(\d+)\]\]/g, (match, rawIndex) => {
    const index = Number.parseInt(rawIndex, 10);
    const ref = buildCitationReference(index);
    if (!ref) {
      return match;
    }
    const label = `[${index}]`;
    if (ref.external) {
      return `<a class="citation-ref" href="${escapeAttribute(ref.href)}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    }
    return `<a class="citation-ref" href="${ref.href}">${label}</a>`;
  });
  return html;
}

function parseTableCells(line) {
  const trimmed = String(line || "").trim();
  const withoutEdgePipes = trimmed.replace(/^\|/, "").replace(/\|$/, "");
  return withoutEdgePipes.split("|").map((cell) => cell.trim());
}

function isTableSeparatorLine(line) {
  const cells = parseTableCells(line);
  if (!cells.length) {
    return false;
  }
  return cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function isPotentialTableRow(line) {
  const trimmed = String(line || "").trim();
  if (!trimmed.includes("|")) {
    return false;
  }
  const cells = parseTableCells(trimmed);
  return cells.length >= 2;
}

function markdownToHtml(markdown, inlineOnly = false) {
  const source = String(markdown || "").replace(/\r\n/g, "\n");
  if (!source.trim()) {
    return "";
  }
  if (inlineOnly) {
    return renderInlineMarkdown(source);
  }

  const lines = source.split("\n");
  const out = [];
  let inUl = false;
  let inOl = false;

  const closeLists = () => {
    if (inUl) {
      out.push("</ul>");
      inUl = false;
    }
    if (inOl) {
      out.push("</ol>");
      inOl = false;
    }
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const trimmed = line.trim();
    if (!trimmed) {
      closeLists();
      out.push("<br />");
      continue;
    }

    const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      closeLists();
      const level = Math.min(heading[1].length, 6);
      out.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }

    const hr = trimmed.match(/^(-{3,}|\*{3,}|_{3,})$/);
    if (hr) {
      closeLists();
      out.push("<hr />");
      continue;
    }

    const nextTrimmed = i + 1 < lines.length ? lines[i + 1].trim() : "";
    if (isPotentialTableRow(trimmed) && isTableSeparatorLine(nextTrimmed)) {
      closeLists();
      const headerCells = parseTableCells(trimmed);
      const colCount = headerCells.length;
      const bodyRows = [];
      i += 2;
      while (i < lines.length) {
        const row = lines[i].trim();
        if (!row || !isPotentialTableRow(row) || isTableSeparatorLine(row)) {
          i -= 1;
          break;
        }
        bodyRows.push(parseTableCells(row));
        i += 1;
      }

      const theadHtml = headerCells
        .map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`)
        .join("");
      const tbodyHtml = bodyRows
        .map((rowCells) => {
          const normalized = headerCells.map((_, idx) => rowCells[idx] || "");
          if (rowCells.length > colCount) {
            normalized.push(...rowCells.slice(colCount));
          }
          return `<tr>${normalized.map((cell) => `<td>${renderInlineMarkdown(cell)}</td>`).join("")}</tr>`;
        })
        .join("");
      out.push(`<table><thead><tr>${theadHtml}</tr></thead><tbody>${tbodyHtml}</tbody></table>`);
      continue;
    }

    const ulItem = trimmed.match(/^[-*]\s+(.+)$/);
    if (ulItem) {
      if (inOl) {
        out.push("</ol>");
        inOl = false;
      }
      if (!inUl) {
        out.push("<ul>");
        inUl = true;
      }
      out.push(`<li>${renderInlineMarkdown(ulItem[1])}</li>`);
      continue;
    }

    const olItem = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (olItem) {
      if (inUl) {
        out.push("</ul>");
        inUl = false;
      }
      if (!inOl) {
        out.push("<ol>");
        inOl = true;
      }
      out.push(`<li>${renderInlineMarkdown(olItem[1])}</li>`);
      continue;
    }

    closeLists();
    out.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
  }

  closeLists();
  return out.join("");
}

function appendResearchStreamSegment(kind, content) {
  const text = String(content || "");
  if (!text) {
    return;
  }
  const segmentKind = kind === "thinking" ? "thinking" : "answer";
  const last = researchStreamSegments.length ? researchStreamSegments[researchStreamSegments.length - 1] : null;
  if (last && last.kind === segmentKind) {
    last.text += text;
    return;
  }
  researchStreamSegments.push({ kind: segmentKind, text });
}

function renderResearchStreamSegments() {
  if (!researchStreamSegments.length) {
    researchStream.innerHTML = "";
    return;
  }
  researchStream.innerHTML = researchStreamSegments
    .map((segment) => {
      const html = markdownToHtml(segment.text);
      return `<div class="research-segment research-segment-${segment.kind} markdown-content">${html}</div>`;
    })
    .join("");
  schedulePersistUiState();
}

function scheduleResearchStreamRender() {
  if (streamRenderScheduled) {
    return;
  }
  streamRenderScheduled = true;
  requestAnimationFrame(() => {
    renderResearchStreamSegments();
    streamRenderScheduled = false;
  });
}

function renderStructuredResearch(data = {}) {
  currentStructuredData = data || {};
  const rows = [
    {
      label: "主要消费者痛点",
      value: Array.isArray(data.industry_pain_points) ? data.industry_pain_points : [],
    },
    {
      label: "现有产品不足",
      value: Array.isArray(data.product_gaps) ? data.product_gaps : [],
    },
    {
      label: "创新方向/机会点",
      value: Array.isArray(data.opportunities) ? data.opportunities : [],
    },
  ];
  const renderToTarget = (target) => {
    if (!target) {
      return;
    }
    target.innerHTML = "";
    rows.forEach((row) => {
      const card = document.createElement("div");
      const hasValue = Array.isArray(row.value) ? row.value.length > 0 : Boolean(row.value);
      card.className = `known-item research-structured-card ${hasValue ? "known-item-ready" : "known-item-missing"}`;
      const label = document.createElement("div");
      label.className = "known-label research-structured-title";
      label.textContent = row.label;
      const value = document.createElement("div");
      value.className = "known-value markdown-content research-structured-value";
      const markdownSource = Array.isArray(row.value)
        ? row.value.map((item) => String(item || "")).join("\n")
        : String(row.value || "");
      value.innerHTML = markdownToHtml(markdownSource) || "未解析到";
      card.appendChild(label);
      card.appendChild(value);
      target.appendChild(card);
    });
  };
  renderToTarget(researchStructured);
  renderToTarget(summaryStructured);
  schedulePersistUiState();
}

function renderCitations(citations = []) {
  currentCitations = Array.isArray(citations) ? citations : [];
  citationList.innerHTML = "";
  if (!Array.isArray(citations) || citations.length === 0) {
    schedulePersistUiState();
    return;
  }
  const title = document.createElement("div");
  title.className = "small muted";
  title.textContent = "引用来源（秘塔返回）";
  citationList.appendChild(title);

  citations.forEach((item, index) => {
    const a = document.createElement("a");
    const safeLink = isSafeExternalUrl(item.link) ? String(item.link).trim() : "";
    a.href = safeLink || `#citation-source-${index + 1}`;
    if (safeLink) {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    }
    a.id = `citation-source-${index + 1}`;
    a.textContent = `[${index + 1}] ${item.title || item.link || "来源"}`;
    a.className = "citation-item";
    citationList.appendChild(a);
  });
  schedulePersistUiState();
}

async function runMetasoResearch() {
  const lane = (laneInput.value || "").trim();
  if (!lane) {
    throw new Error("请先输入赛道");
  }
  researchBtn.disabled = true;
  queryPreview.textContent = "正在构造 query 并请求秘塔...";
  researchStreamSegments = [];
  researchStream.innerHTML = "";
  researchStructured.innerHTML = "";
  if (summaryStructured) {
    summaryStructured.innerHTML = "";
  }
  citationList.innerHTML = "";
  schedulePersistUiState();

  const response = await fetch("/research/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ domain: lane }),
  });
  if (!response.ok || !response.body) {
    const text = await response.text();
    throw new Error(text || "秘塔调研请求失败");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    buffer = parseSseEvents(buffer, (event) => {
      if (event.type === "meta") {
        queryPreview.textContent = event.first_sentence || "";
        setSummaryLaneTitleByFirstSentence(event.first_sentence || "");
        schedulePersistUiState();
      } else if (event.type === "delta") {
        appendResearchStreamSegment(event.delta_kind || "answer", event.content || "");
        scheduleResearchStreamRender();
      } else if (event.type === "citations") {
        renderCitations(event.citations || []);
      } else if (event.type === "done") {
        currentResearchFullText = String(event.full_text || "").trim();
        if (event.full_text && researchStreamSegments.length === 0) {
          appendResearchStreamSegment("answer", event.full_text);
          scheduleResearchStreamRender();
        }
        renderStructuredResearch(event.structured || {});
        if (!citationList.innerHTML) {
          renderCitations(event.citations || []);
        }
        if (hasResearchOutputFromDoneEvent(event)) {
          markStageCompleted("research");
        }
      } else if (event.type === "error") {
        throw new Error(event.message || "秘塔流式调研失败");
      }
    });
  }
  researchBtn.disabled = false;
  schedulePersistUiState();
}

function setActiveTab(tabId, shouldPersist = true) {
  const requestedTab = tabPanels.some((panel) => panel.dataset.tabContent === tabId) ? tabId : "research";
  let nextTab = requestedTab;
  if (!isSummaryTab(nextTab) && !isStageUnlocked(nextTab)) {
    nextTab = workflowCurrentStageId || WORKFLOW_STAGE_ORDER[0];
  }
  activeTab = nextTab;
  tabButtons.forEach((button) => {
    const isActive = button.dataset.tab === nextTab;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  tabPanels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.tabContent === nextTab);
  });
  applyWorkflowLocksToUi();
  if (shouldPersist) {
    schedulePersistUiState();
  }
}

function addChatMessage(role, text, record = true) {
  if (record) {
    chatMessages.push({ role: String(role || ""), text: String(text || "") });
  }
  const div = document.createElement("div");
  div.className = `chat-msg ${role === "user" ? "chat-msg-user" : "chat-msg-agent"}`;
  div.textContent = `${role === "user" ? "你" : "Agent"}：${text}`;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
  schedulePersistUiState();
}

function toMarkdownRoleLabel(role) {
  return String(role || "").toLowerCase() === "user" ? "用户" : "Agent";
}

function normalizeMarkdownText(text) {
  return String(text || "").replace(/\r\n/g, "\n").trim();
}

function buildMarkdownDialogue(messages = []) {
  const rows = Array.isArray(messages) ? messages : [];
  if (rows.length === 0) {
    return "_暂无对话记录_";
  }
  return rows
    .map((item) => {
      const roleLabel = toMarkdownRoleLabel(item.role);
      const content = normalizeMarkdownText(item.text);
      const body = content || "（空）";
      return `### ${roleLabel}\n\n${body}`;
    })
    .join("\n\n");
}

function buildMarkdownResearchSection() {
  const lane = String(currentTargetLane || laneInput.value || "").trim();
  const queryText = String(queryPreview.textContent || "").trim();
  const parts = [];
  if (lane) {
    parts.push(`- 赛道：${lane}`);
  }
  if (queryText) {
    parts.push(`- Query：${queryText}`);
  }
  researchStreamSegments.forEach((segment) => {
    if (!segment || !String(segment.text || "").trim()) {
      return;
    }
    const label = segment.kind === "thinking" ? "Agent（思考流）" : "Agent（回答流）";
    parts.push(`### ${label}\n\n${normalizeMarkdownText(segment.text)}`);
  });
  if (parts.length === 0) {
    return "_暂无调研对话数据_";
  }
  return parts.join("\n\n");
}

function buildAgentConversationMarkdown() {
  const exportedAt = new Date();
  const sections = [
    "# Agent 对话导出",
    "",
    `- 导出时间：${exportedAt.toLocaleString()}`,
    `- 会话ID：${sessionId || "未创建"}`,
    "",
    "## 赛道初步调研",
    "",
    buildMarkdownResearchSection(),
    "",
    "## 产品概念对话",
    "",
    buildMarkdownDialogue(conceptChatMessages),
    "",
    "## 汇总页 Agent 对话",
    "",
    buildMarkdownDialogue(chatMessages),
    "",
  ];
  return sections.join("\n");
}

function buildExportFileName() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const datePart = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  const lane = String(currentTargetLane || laneInput.value || "")
    .trim()
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, "_");
  const lanePart = lane ? `_${lane}` : "";
  return `agent_conversation${lanePart}_${datePart}.md`;
}

function exportAgentConversationAsMarkdown() {
  const markdown = buildAgentConversationMarkdown();
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = buildExportFileName();
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function renderTimeline(steps = []) {
  currentTimelineSteps = Array.isArray(steps) ? steps : [];
  const map = {};
  steps.forEach((item) => {
    map[item.name] = item;
  });
  timeline.innerHTML = "";
  STEP_ORDER.forEach((name) => {
    const item = map[name] || { name, status: "pending", summary: "" };
    const node = document.createElement("div");
    node.className = `timeline-item timeline-item-${item.status}`;
    node.textContent = `${STEP_LABEL[name]}：${item.status}${item.summary ? ` ｜ ${item.summary}` : ""}`;
    timeline.appendChild(node);
  });
  schedulePersistUiState();
}

function renderResultCards(steps = []) {
  currentResultSteps = Array.isArray(steps) ? steps : [];
  resultCards.innerHTML = "";
  steps.forEach((step) => {
    const card = document.createElement("div");
    card.className = "result-card";

    const title = document.createElement("h3");
    title.textContent = STEP_LABEL[step.step] || step.step;

    const lead = document.createElement("p");
    lead.className = "result-lead";
    lead.innerHTML = markdownToHtml(pickLead(step), true);

    card.appendChild(title);
    card.appendChild(lead);
    renderStepDetails(card, step);
    resultCards.appendChild(card);
  });
  schedulePersistUiState();
}

function renderPersonaWorkspace(step = null) {
  if (!personaStatusHint || !personaStats || !personaChart || !personaCards) {
    return;
  }
  const personaStep = step && typeof step === "object" ? step : null;
  const personas = Array.isArray(personaStep?.outputs?.personas) ? personaStep.outputs.personas : [];
  if (!personaStep || personas.length === 0) {
    personaStatusHint.textContent = currentConfirmedConcept
      ? "产品概念已确认，可点击“基于已确认概念生成画像”。"
      : "请先完成“产品概念设计”并确认概念。";
    personaStats.innerHTML = "";
    personaChart.innerHTML = "";
    personaCards.innerHTML = "";
    setPersonaProgress(currentConfirmedConcept ? "待生成（可点击按钮）" : "等待概念确认");
    renderSummaryPersonaNames();
    return;
  }

  const validShares = personas.map((item) => Number(item.share) || 0).filter((num) => Number.isFinite(num) && num > 0);
  const shareSum = validShares.reduce((acc, num) => acc + num, 0);
  const avgPriceSensitivity =
    personas.reduce((acc, item) => acc + (Number(item.price_sensitivity) || 0), 0) / Math.max(personas.length, 1);
  personaStatusHint.textContent = "已基于最新分析结果生成画像，可用于后续联合分析与策略模拟。";

  const statsRows = [
    { label: "画像数量", value: `${personas.length}` },
    { label: "占比合计", value: `${shareSum.toFixed(1)}%` },
    { label: "平均价格敏感度", value: `${avgPriceSensitivity.toFixed(2)} / 5` },
  ];
  personaStats.innerHTML = "";
  statsRows.forEach((row) => {
    const card = document.createElement("div");
    card.className = "known-item known-item-ready";
    const label = document.createElement("div");
    label.className = "known-label";
    label.textContent = row.label;
    const value = document.createElement("div");
    value.className = "known-value";
    value.textContent = row.value;
    card.appendChild(label);
    card.appendChild(value);
    personaStats.appendChild(card);
  });

  personaChart.innerHTML = "";
  personas.forEach((item) => {
    const row = document.createElement("div");
    row.className = "persona-bar-row";
    const label = document.createElement("div");
    label.className = "persona-bar-label";
    label.textContent = item.type || "未命名画像";
    const barWrap = document.createElement("div");
    barWrap.className = "persona-bar-wrap";
    const bar = document.createElement("div");
    bar.className = "persona-bar-fill";
    const share = Math.max(0, Math.min(100, Number(item.share) || 0));
    bar.style.width = `${share}%`;
    bar.textContent = `${share.toFixed(1)}%`;
    barWrap.appendChild(bar);
    row.appendChild(label);
    row.appendChild(barWrap);
    personaChart.appendChild(row);
  });

  personaCards.innerHTML = "";
  personas.forEach((item) => {
    const card = document.createElement("div");
    card.className = "result-card persona-detail-card";
    const title = document.createElement("h3");
    title.textContent = `${item.type || "未命名画像"}（${(Number(item.share) || 0).toFixed(1)}%）`;
    card.appendChild(title);

    const demographics = item.demographics && typeof item.demographics === "object"
      ? item.demographics
      : { age: "待补充", occupation: "待补充", city_tier: "待补充" };
    const demographicsList = Object.entries(demographics)
      .map(([k, v]) => `${k}：${String(v || "待补充")}`)
      .slice(0, 5);

    appendPersonaSection(card, "demographics", "人口特征", demographicsList);
    appendPersonaSection(card, "needs", "需求", Array.isArray(item.needs) ? item.needs : []);
    appendPersonaSection(card, "motivation", "动机", Array.isArray(item.motivation) ? item.motivation : []);
    appendPersonaSection(card, "pain_points", "痛点", Array.isArray(item.pain_points) ? item.pain_points : []);
    appendPersonaSection(card, "behaviors", "行为特征", Array.isArray(item.behaviors) ? item.behaviors : []);
    appendPersonaSection(card, "price_sensitivity", "价格敏感度（1-5）", [String(item.price_sensitivity || "待补充")]);
    personaCards.appendChild(card);
  });
  setPersonaProgress("已完成（画像已生成）");
  renderSummaryPersonaNames();
  schedulePersistUiState();
}

function appendPersonaSection(card, sectionKey, title, rawItems) {
  const section = document.createElement("div");
  section.className = `result-section persona-section persona-section-${String(sectionKey || "")}`;

  const heading = document.createElement("div");
  heading.className = "result-section-title";
  heading.textContent = title;
  section.appendChild(heading);

  const list = document.createElement("ul");
  list.className = "result-bullets";
  const items = Array.isArray(rawItems) ? rawItems.map((item) => String(item || "").trim()).filter(Boolean) : [];
  const finalItems = items.length > 0 ? items.slice(0, 5) : ["暂无"];
  finalItems.forEach((item) => {
    const li = document.createElement("li");
    li.innerHTML = markdownToHtml(item, true);
    list.appendChild(li);
  });
  section.appendChild(list);
  card.appendChild(section);
}

async function generatePersonaFromConcept() {
  setPersonaProgress("校验输入");
  if (!currentConfirmedConcept) {
    throw new Error("请先在“产品概念设计”中确认最终概念");
  }
  const lane = String(currentTargetLane || laneInput.value || "").trim();
  if (!lane) {
    throw new Error("请先完成赛道调研并确定赛道名称");
  }
  if (personaGenerateBtn) {
    personaGenerateBtn.disabled = true;
  }
  personaStatusHint.textContent = "正在根据已确认概念生成模拟画像，请稍候…";
  setPersonaProgress("请求后端生成");
  markStageSubmitted("persona");

  const response = await postJson("/persona/generate", {
    lane,
    research_context: getResearchContextForConcept(),
    research_structured: currentStructuredData || {},
    confirmed_concept: currentConfirmedConcept,
    target_users: [],
    sample_size: 120,
  });
  const step = response?.data?.step;
  setPersonaProgress("解析结果");
  if (!step || !Array.isArray(step?.outputs?.personas) || step.outputs.personas.length === 0) {
    throw new Error("画像生成成功但未返回有效结果");
  }
  currentPersonaStep = step;
  renderPersonaWorkspace(currentPersonaStep);
  markStageCompleted("persona");
}

async function generateConjointDesign() {
  // 自动兜底，而不是阻断
if (!currentConfirmedConcept) {
  console.warn("未确认概念，使用默认");
  currentConfirmedConcept = "默认AI产品概念";
}

if (!currentPersonaStep) {
  console.warn("未生成persona，使用mock数据");
  currentPersonaStep = {
    outputs: {
      personas: [
        {
          type: "大众用户",
          share: 100,
          price_sensitivity: 3
        }
      ]
    }
  };
}

  if (conjointGenerateBtn) {
    conjointGenerateBtn.disabled = true;
  }
  if (conjointStatusHint) {
    conjointStatusHint.textContent = "正在生成联合分析框架，请稍候…";
  }

  markStageSubmitted("conjoint");

  const response = await postJson("/conjoint/design", {
    lane: String(currentTargetLane || laneInput.value || "").trim(),
    research_context: currentResearchFullText,
    research_structured: currentStructuredData || {},
    confirmed_concept: currentConfirmedConcept,
    personas: currentPersonaStep?.outputs?.personas || [],
  });

  const step = response?.data?.step;
  if (!step || !Array.isArray(step?.outputs?.attributes) || step.outputs.attributes.length === 0) {
    throw new Error("联合分析框架生成成功，但未返回有效属性设计");
  }

  currentConjointStep = step;
  renderConjointWorkspace(currentConjointStep);
  markStageCompleted("conjoint");
}

async function generateSimulationData() {
  console.log("generateSimulationData started");

  if (!currentConjointStep) {
    throw new Error("请先完成联合分析设计");
  }

  if (simulationGenerateBtn) {
    simulationGenerateBtn.disabled = true;
  }
  if (simulationStatusHint) {
    simulationStatusHint.textContent = "正在生成模拟消费者数据，请稍候…";
  }

  markStageSubmitted("simulation");

  const response = await postJson("/simulation/generate", {
    lane: String(currentTargetLane || laneInput.value || "").trim(),
    confirmed_concept: currentConfirmedConcept || "默认AI产品概念",
    conjoint_design: currentConjointStep?.outputs || {},
    personas: currentPersonaStep?.outputs?.personas || [
      { type: "默认用户", share: 100, price_sensitivity: 3 }
    ],
    sample_size: 100
  });

  console.log("simulation response:", response);

  const step = response?.data?.step;
  if (!step || !step.outputs) {
    throw new Error("模拟数据生成成功，但未返回有效结果");
  }

  currentSimulationDataStep = step;
  renderSimulationDataWorkspace(currentSimulationDataStep);
  markStageCompleted("simulation");
  // 强制刷新按钮状态
  applyWorkflowLocksToUi();
  // 可选：启用 analysis 按钮
  if (analysisGenerateBtn) {
    analysisGenerateBtn.disabled = false;
}
}
if (analysisGenerateBtn) {
  analysisGenerateBtn.addEventListener("click", async () => {
    try {
      await generateConjointAnalysis();
    } catch (error) {
      if (analysisStatusHint) {
        analysisStatusHint.textContent = `生成失败：${String(error)}`;
      }
    } finally {
      if (analysisGenerateBtn) {
        analysisGenerateBtn.disabled = false;
      }
    }
  });
}

function renderConjointWorkspace(step = null) {
  if (!conjointStatusHint || !conjointResult) {
    return;
  }

  const conjointStep = step && typeof step === "object" ? step : null;
  const attributes = Array.isArray(conjointStep?.outputs?.attributes)
    ? conjointStep.outputs.attributes
    : [];

  // ❌ 没数据
  if (!conjointStep || attributes.length === 0) {
    conjointStatusHint.textContent = "暂无联合分析设计，请点击按钮生成。";
    conjointResult.innerHTML = "";
    return;
  }

  // ✅ 有数据
  conjointStatusHint.textContent = "已生成联合分析设计";

  conjointResult.innerHTML = "";

  attributes.forEach((attr) => {
    const card = document.createElement("div");
    card.className = "result-card";

    // 属性名
    const title = document.createElement("h3");
    title.textContent = attr.name || "未命名属性";

    // levels（取值）
    const levels = document.createElement("div");
    levels.className = "result-section";
    levels.innerHTML = `
      <div class="result-section-title">属性取值</div>
      <ul class="result-bullets">
        ${(attr.levels || []).map(l => `<li>${l}</li>`).join("")}
      </ul>
    `;

    // 解释
    const reason = document.createElement("div");
    reason.className = "result-section";
    reason.innerHTML = `
      <div class="result-section-title">设计理由</div>
      <div class="result-text">${attr.reason || "暂无说明"}</div>
    `;

    card.appendChild(title);
    card.appendChild(levels);
    card.appendChild(reason);

    conjointResult.appendChild(card);
  });

  // 可选：整体说明
  if (conjointStep.outputs?.design_notes) {
    const note = document.createElement("div");
    note.className = "result-card";
    note.innerHTML = `
      <h3>设计说明</h3>
      <div class="result-text">${conjointStep.outputs.design_notes}</div>
    `;
    conjointResult.appendChild(note);
  }

  schedulePersistUiState();
}

function renderSimulationDataWorkspace(step = null) {
  if (!simulationStatusHint || !simulationDataView) {
    return;
  }

  const simulationStep = step && typeof step === "object" ? step : null;
  const outputs = simulationStep?.outputs || {};
  const respondents = Array.isArray(outputs.respondents) ? outputs.respondents : [];
  const profiles = Array.isArray(outputs.profiles) ? outputs.profiles : [];
  const choices = Array.isArray(outputs.choices) ? outputs.choices : [];
  const profileSummary = Array.isArray(outputs.profile_summary) ? outputs.profile_summary : [];
  const segmentSummary = Array.isArray(outputs.segment_summary) ? outputs.segment_summary : [];
  const logicNotes = Array.isArray(outputs.logic_notes) ? outputs.logic_notes : [];
  


  if (!simulationStep || (!respondents.length && !choices.length)) {
    simulationStatusHint.textContent = "暂无模拟数据，请点击按钮生成。";
    simulationDataView.innerHTML = "";
    return;
  }

  simulationStatusHint.textContent = "已生成模拟消费者数据，可用于后续策略分析。";

  simulationDataView.innerHTML = `
    <div class="result-card">
      <h3>样本概览</h3>
      <div class="result-text">模拟消费者数量：${respondents.length}</div>
      <div class="result-text">模拟选择记录数量：${choices.length}</div>
    </div>
    <div class="result-card">
      <h3>前 5 条消费者样本</h3>
      <pre class="output">${escapeHtml(JSON.stringify(respondents.slice(0, 5), null, 2))}</pre>
    </div>
    <div class="result-card">
      <h3>前 5 条选择记录</h3>
      <pre class="output">${escapeHtml(JSON.stringify(choices.slice(0, 5), null, 2))}</pre>
    </div>
  `;


    const profileSummaryWithDetails = profileSummary.map((row) => {
      const matchedProfile = profiles.find((p) => p.profile_id === row.profile_id) || {};
      return {
        ...row,
        ...matchedProfile
    };
  });

  if (profileSummaryWithDetails.length) {
    simulationDataView.appendChild(
      buildSimpleTable("方案汇总", profileSummaryWithDetails)
    );
  }

  if (segmentSummary.length) {
    simulationDataView.appendChild(
      buildSimpleTable("分画像汇总", segmentSummary)
    );
  }

  if (logicNotes.length) {
    simulationDataView.appendChild(
      buildBulletCard("模拟逻辑说明", logicNotes)
    );
}
  schedulePersistUiState();
}

function pickLead(step) {
  const outputs = step.outputs || {};
  if (step.step === "market_exploration" && outputs.conclusion) {
    return outputs.conclusion;
  }
  if (step.step === "reflection" && outputs.improvement_suggestions) {
    return String(outputs.improvement_suggestions).split("。")[0] || step.summary || "已完成分析。";
  }
  return step.summary || "已完成分析。";
}

function addSection(card, title, value) {
  if (!value) {
    return;
  }
  const section = document.createElement("div");
  section.className = "result-section";

  const heading = document.createElement("div");
  heading.className = "result-section-title";
  heading.textContent = title;
  section.appendChild(heading);

  if (Array.isArray(value)) {
    const ul = document.createElement("ul");
    ul.className = "result-bullets";
    value.forEach((item) => {
      const li = document.createElement("li");
      li.innerHTML = markdownToHtml(String(item), true);
      ul.appendChild(li);
    });
    section.appendChild(ul);
  } else if (typeof value === "object") {
    const grid = document.createElement("div");
    grid.className = "kv-grid";
    Object.entries(value).forEach(([k, v]) => {
      const row = document.createElement("div");
      row.className = "kv-item";
      const key = document.createElement("div");
      key.className = "kv-key";
      key.textContent = k;
      const val = document.createElement("div");
      val.className = "kv-value markdown-content";
      if (Array.isArray(v)) {
        const markdownSource = v.map((item) => `- ${String(item)}`).join("\n");
        val.innerHTML = markdownToHtml(markdownSource);
      } else if (v && typeof v === "object") {
        val.innerHTML = markdownToHtml(JSON.stringify(v));
      } else {
        val.innerHTML = markdownToHtml(String(v), true);
      }
      row.appendChild(key);
      row.appendChild(val);
      grid.appendChild(row);
    });
    section.appendChild(grid);
  } else {
    const p = document.createElement("div");
    p.className = "result-text markdown-content";
    p.innerHTML = markdownToHtml(String(value));
    section.appendChild(p);
  }

  card.appendChild(section);
}

function renderStepDetails(card, step) {
  const outputs = step.outputs || {};
  if (step.step === "market_exploration") {
    addSection(card, "行业痛点", (outputs.industry_pain_points || []).slice(0, 4));
    addSection(card, "现有产品不足", (outputs.product_gaps || []).slice(0, 4));
    addSection(card, "机会点", (outputs.opportunities || []).slice(0, 4));
    addSection(card, "结论", outputs.conclusion || "");
    return;
  }

  if (step.step === "persona_generation") {
    const personas = Array.isArray(outputs.personas) ? outputs.personas : [];
    personas.forEach((persona) => {
      const features = Array.isArray(persona.key_features) ? persona.key_features.slice(0, 4) : [];
      addSection(card, `画像：${persona.type || "未命名"}`, features);
    });
    return;
  }

  if (step.step === "conjoint_design") {
    const attrs = Array.isArray(outputs.attributes) ? outputs.attributes : [];
    attrs.forEach((attr) => {
      addSection(card, `${attr.name || "属性"}（${(attr.levels || []).join(" / ")}）`, attr.reason || "");
    });
    addSection(card, "设计说明", outputs.design_notes || "");
    return;
  }

  if (step.step === "simulation_data") {
    const sample = outputs.simulated_sample_structure || {};
    addSection(card, "模拟样本结构", {
      sample_size: sample.sample_size || "",
      user_segments: Array.isArray(sample.user_segments) ? sample.user_segments.map((x) => `${x.segment} ${x.percentage}%`) : [],
      data_collection_methods: sample.data_collection_methods || [],
    });
    addSection(card, "策略建议", outputs.strategy_recommendations || {});
    return;
  }

  if (step.step === "reflection") {
    addSection(card, "可靠性评估", outputs.reliability || "");
    addSection(card, "成本收益", outputs.cost_benefit || "");
    addSection(card, "潜在损失", outputs.potential_losses || "");
    addSection(card, "改进建议", outputs.improvement_suggestions || "");
    return;
  }

  addSection(card, "详细内容", outputs);
}

function setSessionHint() {
  sessionHint.textContent = sessionId ? `会话：${sessionId}` : "会话：未创建";
  schedulePersistUiState();
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function fetchStatus() {
  if (!sessionId) {
    throw new Error("请先保存业务需求，创建会话");
  }
  const response = await fetch(`/session/status?session_id=${encodeURIComponent(sessionId)}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "status request failed");
  }
  showJson(statusView, data);
  renderTimeline(data.data.steps || []);
  setStatusHumanText(statusToText(data.data.status));
  if (data.data.status === "completed" || data.data.status === "failed") {
    stopPolling();
  }
  if (data.data.status === "completed" && !resultAutoShown) {
    resultAutoShown = true;
    await fetchResult(true);
  }
  return data;
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      await fetchStatus();
    } catch (error) {
      stopPolling();
      showJson(statusView, { ok: false, message: String(error) });
    }
  }, 2000);
}

async function fetchResult(scrollToResult = false) {
  if (!sessionId) {
    throw new Error("请先保存业务需求");
  }
  const response = await fetch(`/session/result?session_id=${encodeURIComponent(sessionId)}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "result request failed");
  }
  showJson(resultView, data);
  renderResultCards(data.data.steps || []);
  resultTip.textContent = "已展示可读结论，原始 JSON 仅供核对和导出使用。";
  if (scrollToResult) {
    resultCards.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  schedulePersistUiState();
}

async function generateConjointAnalysis() {

  if (analysisGenerateBtn) {
    analysisGenerateBtn.disabled = true;
  }
  if (analysisStatusHint) {
    analysisStatusHint.textContent = "正在生成联合分析结果，请稍候…";
  }

  markStageSubmitted("analysis");

  try {
    const response = await postJson("/analysis/generate", {
      lane: String(currentTargetLane || laneInput.value || "").trim(),
      confirmed_concept: currentConfirmedConcept || "默认AI产品概念",
      conjoint_design: currentConjointStep?.outputs || {},
      simulation_data: currentSimulationDataStep?.outputs || {},
      personas: currentPersonaStep?.outputs?.personas || [],
    });

    const step = response?.data?.step;
    if (!step || !step.outputs) {
      throw new Error("联合分析结果生成成功，但未返回有效结果");
    }

    currentAnalysisStep = step;
    renderAnalysisWorkspace(currentAnalysisStep);
    markStageCompleted("analysis");
  } finally {
    if (analysisGenerateBtn) {
      analysisGenerateBtn.disabled = false;
    }
    schedulePersistUiState();
  }
}

function buildSimpleTable(title, rows) {
  const wrapper = document.createElement("div");
  wrapper.className = "result-card";

  const heading = document.createElement("h3");
  heading.textContent = title;
  wrapper.appendChild(heading);

  if (!Array.isArray(rows) || rows.length === 0) {
    const empty = document.createElement("div");
    empty.className = "result-text";
    empty.textContent = "暂无数据";
    wrapper.appendChild(empty);
    return wrapper;
  }

  const table = document.createElement("table");
  table.className = "result-table";

  const columns = Object.keys(rows[0]);

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach((col) => {
      const td = document.createElement("td");
      td.textContent = row[col] == null ? "" : String(row[col]);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  wrapper.appendChild(table);
  return wrapper;
}

function renderAnalysisWorkspace(step = null) {
  if (!analysisStatusHint || !analysisResultView) {
    return;
  }

  const analysisStep = step && typeof step === "object" ? step : null;
  const outputs = analysisStep?.outputs || {};
  const attributeImportance = Array.isArray(outputs.attribute_importance) ? outputs.attribute_importance : [];
  const partworthSummary = Array.isArray(outputs.partworth_summary) ? outputs.partworth_summary : [];
  const recommendedProduct = outputs.recommended_product || null;
  const strategySuggestions = Array.isArray(outputs.strategy_suggestions) ? outputs.strategy_suggestions : [];

  // 新增这两行
  const personaPreferenceSummary = Array.isArray(outputs.persona_preference_summary)
    ? outputs.persona_preference_summary
    : [];
  const profileChoiceSummary = Array.isArray(outputs.profile_choice_summary)
    ? outputs.profile_choice_summary
    : [];

  if (!analysisStep || (!attributeImportance.length && !partworthSummary.length && !recommendedProduct)) {
    analysisStatusHint.textContent = "暂无联合分析结果，请点击按钮生成。";
    analysisResultView.innerHTML = "";
    return;
  }

  analysisStatusHint.textContent = "已生成联合分析结果与产品策略。";
  analysisResultView.innerHTML = "";

  if (attributeImportance.length) {
    analysisResultView.appendChild(buildSimpleTable("属性重要性", attributeImportance));
  }

  if (partworthSummary.length) {
    analysisResultView.appendChild(buildSimpleTable("偏好总结", partworthSummary));
  }

  if (recommendedProduct) {
    const card = document.createElement("div");
    card.className = "result-card";
    card.innerHTML = `
      <h3>推荐产品方案</h3>
      <div class="result-text">${escapeHtml(JSON.stringify(recommendedProduct, null, 2))}</div>
    `;
    analysisResultView.appendChild(card);
  }

  if (strategySuggestions.length) {
    const card = document.createElement("div");
    card.className = "result-card";
    const title = document.createElement("h3");
    title.textContent = "产品策略建议";
    card.appendChild(title);
  if (profileChoiceSummary.length) {
    analysisResultView.appendChild(buildSimpleTable("方案胜出情况", profileChoiceSummary));
  }

  if (personaPreferenceSummary.length) {
    analysisResultView.appendChild(buildSimpleTable("分画像偏好总结", personaPreferenceSummary));
  }
    const ul = document.createElement("ul");
    ul.className = "result-bullets";
    strategySuggestions.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      ul.appendChild(li);
    });
    card.appendChild(ul);
    analysisResultView.appendChild(card);
  }

  schedulePersistUiState();
}

document.getElementById("send_btn").addEventListener("click", async () => {
  try {
    const chat = chatInput.value.trim();
    if (!chat) {
      throw new Error("请输入你的业务需求");
    }
    addChatMessage("user", chat);
    chatInput.value = "";

    const data = await postJson("/session/message", {
      session_id: sessionId,
      message: chat,
    });
    sessionId = data.data.session_id;
    if (data.data.assistant_message) {
      addChatMessage("agent", data.data.assistant_message);
    }
    readyToRun = Boolean(data.data.ready_to_run);
    setSessionHint();
    renderKnownInfo(data.data.known_info || {}, data.data.missing_fields || []);
    setNextQuestion(
      readyToRun ? data.data.next_question || "已可开始分析，如有补充可继续输入。" : data.data.next_question || "请继续补充关键信息。",
      readyToRun,
    );
    renderGuessSuggestions(data.data.answer_guesses || []);
    setActionState();
    setStatusHumanText(readyToRun ? "信息已足够，可以直接开始分析。" : "信息收集中，Agent 正在引导你补全。");
    showJson(statusView, data);
  } catch (error) {
    showJson(statusView, { ok: false, message: String(error) });
    setStatusHumanText("发送失败，请根据提示重试。");
  }
});

runBtn.addEventListener("click", async () => {
  try {
    if (!sessionId) {
      throw new Error("请先发送回答，让 Agent 建立会话");
    }
    if (!readyToRun) {
      throw new Error("信息还不完整，请先回答 Agent 的下一问");
    }
    const data = await postJson("/session/run", { session_id: sessionId });
    resultAutoShown = false;
    resultTip.textContent = "分析中，完成后会自动展示结论卡片。";
    setStatusHumanText("分析已启动，正在自动执行步骤。");
    showJson(statusView, data);
    startPolling();
  } catch (error) {
    showJson(statusView, { ok: false, message: String(error) });
    setStatusHumanText("无法开始分析，请先补齐必要信息。");
  }
});

document.getElementById("result_btn").addEventListener("click", async () => {
  try {
    await fetchResult(false);
  } catch (error) {
    showJson(resultView, { ok: false, message: String(error) });
    resultTip.textContent = "暂时还没有可展示的结果，请先完成分析。";
  }
});

researchBtn.addEventListener("click", async () => {
  try {
    markStageSubmitted("research");
    await runMetasoResearch();
  } catch (error) {
    researchStream.innerHTML = markdownToHtml(`请求失败：${String(error)}`);
    queryPreview.textContent = "请检查 METASO_API_KEY 或网络后重试。";
  } finally {
    researchBtn.disabled = false;
  }
});

laneInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") {
    return;
  }
  event.preventDefault();
  researchBtn.click();
});

laneInput.addEventListener("input", () => {
  schedulePersistUiState();
});

tabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setActiveTab(button.dataset.tab || "research");
  });
});

if (conceptSendBtn) {
  conceptSendBtn.addEventListener("click", () => {
    void submitConceptMessage();
  });
}

if (conceptChatInput) {
  conceptChatInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") {
      return;
    }
    if (event.isComposing) {
      return;
    }
    event.preventDefault();
    void submitConceptMessage();
  });
}

if (personaGenerateBtn) {
  personaGenerateBtn.addEventListener("click", async () => {
    try {
      await generatePersonaFromConcept();
    } catch (error) {
      if (personaStatusHint) {
        personaStatusHint.textContent = `生成失败：${String(error)}`;
      }
      setPersonaProgress(`失败：${String(error)}`);
    } finally {
      if (personaGenerateBtn) {
        personaGenerateBtn.disabled = false;
      }
    }
  });
}

if (conjointGenerateBtn) {
  conjointGenerateBtn.addEventListener("click", async () => {
    try {
      await generateConjointDesign();
    } catch (error) {
      if (conjointStatusHint) {
        conjointStatusHint.textContent = `生成失败：${String(error)}`;
      }
    } finally {
      if (conjointGenerateBtn) {
        conjointGenerateBtn.disabled = false;
      }
    }
  });
}

if (simulationGenerateBtn) {
  simulationGenerateBtn.addEventListener("click", async () => {
    try {
      await generateSimulationData();
    } catch (error) {
      if (simulationStatusHint) {
        simulationStatusHint.textContent = `生成失败：${String(error)}`;
      }
    } finally {
      if (simulationGenerateBtn) {
        simulationGenerateBtn.disabled = false;
      }
    }
  });
}

if (restartBtn) {
  restartBtn.addEventListener("click", () => {
    const ok = window.confirm("确认重新开始吗？这会清空当前所有输入和结果。");
    if (!ok) {
      return;
    }
    stopPolling();
    try {
      localStorage.removeItem(UI_STATE_KEY);
    } catch (error) {
      // ignore storage access errors
    }
    applyDefaultUiState();
    laneInput.focus();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

if (exportMdBtn) {
  exportMdBtn.addEventListener("click", () => {
    exportAgentConversationAsMarkdown();
  });
}

chatInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") {
    return;
  }
  if (event.shiftKey) {
    return;
  }
  if (event.isComposing) {
    return;
  }
  event.preventDefault();
  sendBtn.click();
});

function applyDefaultUiState() {
  resetWorkflowState();
  sessionId = null;
  readyToRun = false;
  resultAutoShown = false;
  researchStreamSegments = [];
  chatMessages = [];
  currentResearchFullText = "";
  currentConfirmedConcept = "";
  currentPersonaStep = null;
  renderSummaryPersonaNames();
  queryPreview.textContent = "";
  laneInput.value = "";
  chatInput.value = "";
  if (conceptChatInput) {
    conceptChatInput.value = "";
  }
  setSummaryLaneTitleByName("");
  conceptChatMessages = [];
  ensureConceptGreeting();
  renderConfirmedConcept();
  researchStream.innerHTML = "";
  researchStructured.innerHTML = "";
  if (summaryStructured) {
    summaryStructured.innerHTML = "";
  }
  if (personaStats) {
    personaStats.innerHTML = "";
  }
  if (personaChart) {
    personaChart.innerHTML = "";
  }
  if (personaCards) {
    personaCards.innerHTML = "";
  }
  if (personaStatusHint) {
    personaStatusHint.textContent = "请先完成“产品概念设计”并确认概念。";
  }
  currentConjointStep = null;
  if (conjointResult) {
    conjointResult.innerHTML = "";
  }
  if (conjointStatusHint) {
    conjointStatusHint.textContent = "请先完成前面的产品概念与画像生成。";
  }
  // ---- simulation reset（加在这里）----
  currentSimulationDataStep = null;
  if (simulationDataView) {
    simulationDataView.innerHTML = "";
  }
  if (simulationStatusHint) {
    simulationStatusHint.textContent = "请先完成联合分析设计。";
  }

  currentAnalysisStep = null;
  if (analysisResultView) {
    analysisResultView.innerHTML = "";
  }
  if (analysisStatusHint) {
    analysisStatusHint.textContent = "请先完成消费者数据模拟。";
  }

  setPersonaProgress("待开始");
  citationList.innerHTML = "";
  chatLog.innerHTML = "";
  setSessionHint();
  renderTimeline([]);
  setActionState();
  renderKnownInfo({}, ["domain", "goal", "target_users", "sample_size"]);
  setNextQuestion("请先说说你想分析的业务场景。", false);
  renderGuessSuggestions([]);
  setStatusHumanText("还没开始分析。先按 Agent 的问题补充信息。");
  resultTip.textContent = "分析完成后会自动展示结论卡片。";
  showJson(statusView, { hint: "这里显示运行状态的技术详情（JSON）" });
  showJson(resultView, { hint: "这里显示分析结果的技术详情（JSON）" });
  setActiveTab("research", false);
  applyWorkflowLocksToUi();
}

function restoreUiState(state) {
  resetWorkflowState();
  sessionId = state.sessionId || null;
  readyToRun = Boolean(state.readyToRun);
  resultAutoShown = Boolean(state.resultAutoShown);
  researchStreamSegments = Array.isArray(state.researchStreamSegments) ? state.researchStreamSegments : [];
  laneInput.value = state.laneInput || "";
  queryPreview.textContent = state.queryPreview || "";
  if (state.targetLane) {
    setSummaryLaneTitleByName(state.targetLane);
  } else {
    setSummaryLaneTitleByFirstSentence(state.queryPreview || "");
  }
  conceptChatMessages = Array.isArray(state.conceptChatMessages) ? state.conceptChatMessages : [];
  currentResearchFullText = String(state.researchFullText || "");
  currentConfirmedConcept = String(state.confirmedConcept || "");
  workflowCurrentStageId = WORKFLOW_STAGE_ORDER.includes(state.workflowCurrentStageId) ? state.workflowCurrentStageId : WORKFLOW_STAGE_ORDER[0];
  workflowUnlockedStageIndex = Number.isInteger(state.workflowUnlockedStageIndex)
    ? Math.max(0, Math.min(state.workflowUnlockedStageIndex, WORKFLOW_MAX_LEVEL))
    : 0;
  workflowCompletedStageMap = { ...buildEmptyWorkflowMap(), ...(state.workflowCompletedStageMap || {}) };
  workflowSubmittedStageMap = { ...buildEmptyWorkflowMap(), ...(state.workflowSubmittedStageMap || {}) };
  workflowLockedStageMap = { ...buildEmptyWorkflowMap(), ...(state.workflowLockedStageMap || {}) };
  hydrateWorkflowStateFromSnapshot(state);
  if (!isStageUnlocked(workflowCurrentStageId)) {
    workflowCurrentStageId = getDefaultStageByLevel(workflowUnlockedStageIndex);
  }
  ensureConceptGreeting();
  renderConceptChatMessages();
  renderConfirmedConcept();
  renderResearchStreamSegments();
  renderStructuredResearch(state.structuredData || {});
  renderCitations(state.citations || []);

  chatMessages = Array.isArray(state.chatMessages) ? state.chatMessages : [];
  chatLog.innerHTML = "";
  chatMessages.forEach((item) => addChatMessage(item.role, item.text, false));

  renderKnownInfo(state.knownInfo || {}, state.missingFields || []);
  setNextQuestion(state.nextQuestion || "请先说说你想分析的业务场景。", Boolean(state.nextQuestionReady));
  renderGuessSuggestions(state.guesses || []);
  setActionState();
  setSessionHint();

  if (Array.isArray(state.timelineSteps) && state.timelineSteps.length > 0) {
    renderTimeline(state.timelineSteps);
  } else {
    renderTimeline([]);
  }
  if (Array.isArray(state.resultSteps) && state.resultSteps.length > 0) {
    renderResultCards(state.resultSteps);
  } else {
    resultCards.innerHTML = "";
  }
  currentPersonaStep = state.personaStep && typeof state.personaStep === "object" ? state.personaStep : null;
  if (state.personaProgressText && personaProgressText) {
    personaProgressText.textContent = state.personaProgressText;
  }
  renderPersonaWorkspace(currentPersonaStep);
  currentConjointStep = state.conjointStep && typeof state.conjointStep === "object" ? state.conjointStep : null;
  renderConjointWorkspace(currentConjointStep);

  currentSimulationDataStep = state.simulationDataStep && typeof state.simulationDataStep === "object" ? state.simulationDataStep : null;
  renderSimulationDataWorkspace(currentSimulationDataStep);
  statusHuman.textContent = state.statusHuman || "还没开始分析。先按 Agent 的问题补充信息。";
  statusView.textContent = state.statusJsonText || JSON.stringify({ hint: "这里显示运行状态的技术详情（JSON）" }, null, 2);
  resultView.textContent = state.resultJsonText || JSON.stringify({ hint: "这里显示分析结果的技术详情（JSON）" }, null, 2);
  resultTip.textContent = state.resultTipText || "分析完成后会自动展示结论卡片。";
  setActiveTab(state.activeTab || "research", false);
  applyWorkflowLocksToUi();
}

async function bootstrapUiState() {
  const restored = loadUiState();
  if (restored) {
    restoreUiState(restored);
  } else {
    applyDefaultUiState();
  }
  if (!sessionId) {
    return;
  }
  try {
    const status = await fetchStatus();
    const serverStatus = status?.data?.status;
    if (serverStatus === "running") {
      startPolling();
    } else if (serverStatus === "completed") {
      await fetchResult(false);
    }
  } catch (error) {
    // keep local snapshot when backend session is unavailable
  }
}

bootstrapUiState();
