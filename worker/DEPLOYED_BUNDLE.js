var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// DEPLOYED_BUNDLE.js
var __defProp2 = Object.defineProperty;
var __name2 = /* @__PURE__ */ __name((target, value) => __defProp2(target, "name", { value, configurable: true }), "__name");
var __defProp22 = Object.defineProperty;
var __name22 = /* @__PURE__ */ __name2((target, value) => __defProp22(target, "name", { value, configurable: true }), "__name");
var __defProp222 = Object.defineProperty;
var __name222 = /* @__PURE__ */ __name22((target, value) => __defProp222(target, "name", { value, configurable: true }), "__name");
var GITHUB_REPO = "Universekianukal/shadow-gasp-comic-pipeline";
var VIDEO_REPO = "Universekianukal/shadow-gasp-pipeline";
async function tg(env, method, params) {
  const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params)
  });
  const body = await r.json();
  if (!body.ok) {
    console.log(`tg ${method} failed: ${body.error_code} ${body.description}`);
    const chatId = params && params.chat_id;
    if (chatId && method !== "sendMessage" && method !== "answerCallbackQuery") {
      await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text: `\u274C Telegram refused ${method}: ${body.description || body.error_code}`
        })
      });
    }
  }
  return body;
}
__name(tg, "tg");
__name2(tg, "tg");
__name22(tg, "tg");
__name222(tg, "tg");
async function dispatchAction(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/action.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "shadow-gasp-bot"
      },
      body: JSON.stringify({ ref: "main", inputs })
    }
  );
  if (!r.ok) {
    throw new Error(`GitHub dispatch failed: ${r.status} ${await r.text()}`);
  }
}
__name(dispatchAction, "dispatchAction");
__name2(dispatchAction, "dispatchAction");
__name22(dispatchAction, "dispatchAction");
__name222(dispatchAction, "dispatchAction");
async function dispatchPipeline(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/pipeline.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "shadow-gasp-bot"
      },
      body: JSON.stringify({ ref: "main", inputs })
    }
  );
  if (!r.ok) throw new Error(`GitHub dispatch failed: ${r.status} ${await r.text()}`);
}
__name(dispatchPipeline, "dispatchPipeline");
__name2(dispatchPipeline, "dispatchPipeline");
__name22(dispatchPipeline, "dispatchPipeline");
__name222(dispatchPipeline, "dispatchPipeline");
async function dispatchGenCode(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/gen_code.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "shadow-gasp-bot"
      },
      body: JSON.stringify({ ref: "main", inputs })
    }
  );
  if (!r.ok) throw new Error(`GitHub dispatch failed: ${r.status} ${await r.text()}`);
}
__name(dispatchGenCode, "dispatchGenCode");
__name2(dispatchGenCode, "dispatchGenCode");
__name22(dispatchGenCode, "dispatchGenCode");
__name222(dispatchGenCode, "dispatchGenCode");
async function dispatchVideoPipeline(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${VIDEO_REPO}/actions/workflows/pipeline.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "shadow-gasp-bot"
      },
      body: JSON.stringify({ ref: "main", inputs })
    }
  );
  if (!r.ok) throw new Error(`GitHub dispatch failed: ${r.status} ${await r.text()}`);
}
__name(dispatchVideoPipeline, "dispatchVideoPipeline");
__name2(dispatchVideoPipeline, "dispatchVideoPipeline");
__name22(dispatchVideoPipeline, "dispatchVideoPipeline");
__name222(dispatchVideoPipeline, "dispatchVideoPipeline");
var sleep = /* @__PURE__ */ __name222((ms) => new Promise((resolve) => setTimeout(resolve, ms)), "sleep");
async function dispatchWorkflowVerified(env, workflowFile, inputs) {
  const dispatchOnce = /* @__PURE__ */ __name222(async () => {
    const beforeMs2 = Date.now();
    const r = await fetch(
      `https://api.github.com/repos/${VIDEO_REPO}/actions/workflows/${workflowFile}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`,
          Accept: "application/vnd.github+json",
          "User-Agent": "shadow-gasp-bot"
        },
        body: JSON.stringify({ ref: "main", inputs })
      }
    );
    if (!r.ok) throw new Error(`GitHub dispatch failed: ${r.status} ${await r.text()}`);
    return beforeMs2;
  }, "dispatchOnce");
  const runAppeared = /* @__PURE__ */ __name222(async (afterMs) => {
    const r = await fetch(
      `https://api.github.com/repos/${VIDEO_REPO}/actions/workflows/${workflowFile}/runs?event=workflow_dispatch&per_page=5`,
      { headers: { Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`, "User-Agent": "shadow-gasp-bot" } }
    );
    if (!r.ok) return false;
    const data = await r.json();
    return (data.workflow_runs || []).some((run) => new Date(run.created_at).getTime() >= afterMs - 2e3);
  }, "runAppeared");
  let beforeMs = await dispatchOnce();
  await sleep(4e3);
  if (await runAppeared(beforeMs)) return;
  beforeMs = await dispatchOnce();
  await sleep(4e3);
  if (await runAppeared(beforeMs)) return;
  throw new Error("dispatched twice but no run appeared in Actions -- check the repo's Actions tab manually");
}
__name(dispatchWorkflowVerified, "dispatchWorkflowVerified");
__name2(dispatchWorkflowVerified, "dispatchWorkflowVerified");
__name22(dispatchWorkflowVerified, "dispatchWorkflowVerified");
__name222(dispatchWorkflowVerified, "dispatchWorkflowVerified");
async function dispatchFinishBatchDay(env, inputs) {
  return dispatchWorkflowVerified(env, "finish_batch_day.yml", inputs);
}
__name(dispatchFinishBatchDay, "dispatchFinishBatchDay");
__name2(dispatchFinishBatchDay, "dispatchFinishBatchDay");
__name22(dispatchFinishBatchDay, "dispatchFinishBatchDay");
__name222(dispatchFinishBatchDay, "dispatchFinishBatchDay");
async function dispatchBatchPregen(env, inputs) {
  return dispatchWorkflowVerified(env, "batch_pregen.yml", inputs);
}
__name(dispatchBatchPregen, "dispatchBatchPregen");
__name2(dispatchBatchPregen, "dispatchBatchPregen");
__name22(dispatchBatchPregen, "dispatchBatchPregen");
__name222(dispatchBatchPregen, "dispatchBatchPregen");
function pregenKeyboard() {
  return {
    inline_keyboard: [
      [3, 5, 7].map((n) => ({ text: `${n} days`, callback_data: `pregen:${n}` })),
      [10].map((n) => ({ text: `${n} days`, callback_data: `pregen:${n}` }))
    ]
  };
}
__name(pregenKeyboard, "pregenKeyboard");
__name2(pregenKeyboard, "pregenKeyboard");
__name22(pregenKeyboard, "pregenKeyboard");
__name222(pregenKeyboard, "pregenKeyboard");
async function ghRaw(env, path) {
  const r = await fetch(`https://raw.githubusercontent.com/${VIDEO_REPO}/main/${path}`, {
    headers: { "User-Agent": "shadow-gasp-bot" }
  });
  if (!r.ok) throw new Error(`${path} not found in repo (${r.status})`);
  return r;
}
__name(ghRaw, "ghRaw");
__name2(ghRaw, "ghRaw");
__name22(ghRaw, "ghRaw");
__name222(ghRaw, "ghRaw");
async function hookStillUrl(env, dd) {
  const candidates = [
    `_pipeline/batch/day${dd}/shot1.jpeg`,
    `_pipeline/batch/day${dd}/images/seq/01.jpeg`
  ];
  let lastErr = null;
  for (const path of candidates) {
    try {
      await ghRaw(env, path);
      return `https://raw.githubusercontent.com/${VIDEO_REPO}/main/${path}`;
    } catch (e) {
      lastErr = e;
    }
  }
  throw new Error(`no hook still for day ${dd} (${lastErr && lastErr.message})`);
}
__name(hookStillUrl, "hookStillUrl");
__name2(hookStillUrl, "hookStillUrl");
__name22(hookStillUrl, "hookStillUrl");
async function sendHookStill(env, chatId, imgUrl, caption) {
  const r = await fetch(imgUrl, { headers: { "User-Agent": "shadow-gasp-bot" } });
  if (!r.ok) throw new Error(`couldn't fetch the still: ${r.status}`);
  const bytes = await r.arrayBuffer();
  const form = new FormData();
  form.append("chat_id", String(chatId));
  form.append("caption", caption.length > 1024 ? caption.slice(0, 1021) + "..." : caption);
  form.append("photo", new Blob([bytes], { type: "image/jpeg" }), "shot1.jpeg");
  const resp = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendPhoto`, {
    method: "POST",
    body: form
  });
  const body = await resp.json();
  if (!body.ok) {
    throw new Error(`sendPhoto refused the upload: ${body.description || body.error_code}`);
  }
  return body;
}
__name(sendHookStill, "sendHookStill");
__name2(sendHookStill, "sendHookStill");
__name22(sendHookStill, "sendHookStill");
__name222(hookStillUrl, "hookStillUrl");
async function dispatchCrosspostDecision(env, inputs) {
  return dispatchWorkflowVerified(env, "crosspost_decision.yml", inputs);
}
__name(dispatchCrosspostDecision, "dispatchCrosspostDecision");
__name2(dispatchCrosspostDecision, "dispatchCrosspostDecision");
__name22(dispatchCrosspostDecision, "dispatchCrosspostDecision");
__name222(dispatchCrosspostDecision, "dispatchCrosspostDecision");
function fbIgDecisionKeyboard(day) {
  return {
    inline_keyboard: [
      [
        { text: "\u{1F4D8} FB: Approve", callback_data: `fbdec:${day}:approve` },
        { text: "\u274C FB: Reject", callback_data: `fbdec:${day}:reject` }
      ],
      [
        { text: "\u{1F4F7} IG: Approve", callback_data: `igdec:${day}:approve` },
        { text: "\u274C IG: Reject", callback_data: `igdec:${day}:reject` }
      ]
    ]
  };
}
__name(fbIgDecisionKeyboard, "fbIgDecisionKeyboard");
__name2(fbIgDecisionKeyboard, "fbIgDecisionKeyboard");
__name22(fbIgDecisionKeyboard, "fbIgDecisionKeyboard");
__name222(fbIgDecisionKeyboard, "fbIgDecisionKeyboard");
async function dispatchGenerateTitleVariant(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${VIDEO_REPO}/actions/workflows/generate_title_variant.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "shadow-gasp-bot"
      },
      body: JSON.stringify({ ref: "main", inputs })
    }
  );
  if (!r.ok) throw new Error(`GitHub dispatch failed: ${r.status} ${await r.text()}`);
}
__name(dispatchGenerateTitleVariant, "dispatchGenerateTitleVariant");
__name2(dispatchGenerateTitleVariant, "dispatchGenerateTitleVariant");
__name22(dispatchGenerateTitleVariant, "dispatchGenerateTitleVariant");
__name222(dispatchGenerateTitleVariant, "dispatchGenerateTitleVariant");
async function dispatchRetitlePublished(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${VIDEO_REPO}/actions/workflows/retitle_published.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "shadow-gasp-bot"
      },
      body: JSON.stringify({ ref: "main", inputs })
    }
  );
  if (!r.ok) throw new Error(`GitHub dispatch failed: ${r.status} ${await r.text()}`);
}
__name(dispatchRetitlePublished, "dispatchRetitlePublished");
__name2(dispatchRetitlePublished, "dispatchRetitlePublished");
__name22(dispatchRetitlePublished, "dispatchRetitlePublished");
__name222(dispatchRetitlePublished, "dispatchRetitlePublished");
function titleStyleKeyboard(day) {
  return {
    inline_keyboard: [
      [
        { text: "\u{1F631} Shock", callback_data: `titlestyle:${day}:shock` },
        { text: "\u2753 Curiosity", callback_data: `titlestyle:${day}:curiosity` }
      ],
      [
        { text: "\u{1F501} Open-loop", callback_data: `titlestyle:${day}:openloop` },
        { text: "\u{1F3AF} Direct", callback_data: `titlestyle:${day}:direct` }
      ]
    ]
  };
}
__name(titleStyleKeyboard, "titleStyleKeyboard");
__name2(titleStyleKeyboard, "titleStyleKeyboard");
__name22(titleStyleKeyboard, "titleStyleKeyboard");
__name222(titleStyleKeyboard, "titleStyleKeyboard");
function titleDraftKeyboard(day, style) {
  return {
    inline_keyboard: [
      [
        { text: "\u2705 Apply", callback_data: `title_apply:${day}` },
        { text: "\u274C Discard", callback_data: `title_discard:${day}` }
      ],
      [
        { text: "\u{1F504} Regenerate (same style)", callback_data: `title_regen:${day}:${style || ""}` },
        { text: "\u{1F3A8} Try another style", callback_data: `title_retry:${day}` }
      ]
    ]
  };
}
__name(titleDraftKeyboard, "titleDraftKeyboard");
__name2(titleDraftKeyboard, "titleDraftKeyboard");
__name22(titleDraftKeyboard, "titleDraftKeyboard");
__name222(titleDraftKeyboard, "titleDraftKeyboard");
async function getCurrentTitle(env, dayNum) {
  const dayDir = `_pipeline/batch/day${String(dayNum).padStart(2, "0")}`;
  const overrideR = await fetch(
    `https://api.github.com/repos/${VIDEO_REPO}/contents/${dayDir}/TITLE_OVERRIDE.json?ref=main`,
    { headers: { Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`, "User-Agent": "shadow-gasp-bot" } }
  );
  if (overrideR.ok) {
    const j = JSON.parse(atob((await overrideR.json()).content));
    return { title: j.title, source: "override already applied" };
  }
  const ytR = await fetch(
    `https://api.github.com/repos/${VIDEO_REPO}/contents/${dayDir}/youtube.json?ref=main`,
    { headers: { Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`, "User-Agent": "shadow-gasp-bot" } }
  );
  if (ytR.ok) {
    const j = JSON.parse(atob((await ytR.json()).content));
    return { title: j.title, source: "final render title" };
  }
  const metaR = await fetch(
    `https://api.github.com/repos/${VIDEO_REPO}/contents/${dayDir}/meta.json?ref=main`,
    { headers: { Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`, "User-Agent": "shadow-gasp-bot" } }
  );
  if (metaR.ok) {
    const j = JSON.parse(atob((await metaR.json()).content));
    if (j.title_working) return { title: j.title_working, source: "working title from script" };
  }
  return null;
}
__name(getCurrentTitle, "getCurrentTitle");
__name2(getCurrentTitle, "getCurrentTitle");
__name22(getCurrentTitle, "getCurrentTitle");
__name222(getCurrentTitle, "getCurrentTitle");
async function commitTitleOverride(env, dayNum, title, tags) {
  const path = `_pipeline/batch/day${String(dayNum).padStart(2, "0")}/TITLE_OVERRIDE.json`;
  let sha;
  const existing = await fetch(
    `https://api.github.com/repos/${VIDEO_REPO}/contents/${path}?ref=main`,
    { headers: { Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`, "User-Agent": "shadow-gasp-bot" } }
  );
  if (existing.ok) sha = (await existing.json()).sha;
  const content = JSON.stringify({ title, tags: tags || [] }, null, 2);
  const b64 = btoa(unescape(encodeURIComponent(content)));
  const r = await fetch(`https://api.github.com/repos/${VIDEO_REPO}/contents/${path}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "shadow-gasp-bot"
    },
    body: JSON.stringify({
      message: `batch: day ${String(dayNum).padStart(2, "0")} title override (via Telegram style-picker)`,
      content: b64,
      branch: "main",
      ...sha ? { sha } : {}
    })
  });
  if (!r.ok) throw new Error(`Commit failed: ${r.status} ${await r.text()}`);
}
__name(commitTitleOverride, "commitTitleOverride");
__name2(commitTitleOverride, "commitTitleOverride");
__name22(commitTitleOverride, "commitTitleOverride");
__name222(commitTitleOverride, "commitTitleOverride");
async function commitHookVideo(env, dayNum, videoBytes) {
  const path = `_pipeline/batch/day${String(dayNum).padStart(2, "0")}/images/seq/01.mp4`;
  let sha;
  const existing = await fetch(
    `https://api.github.com/repos/${VIDEO_REPO}/contents/${path}?ref=main`,
    { headers: { Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`, "User-Agent": "shadow-gasp-bot" } }
  );
  if (existing.ok) sha = (await existing.json()).sha;
  let binary = "";
  const bytes = new Uint8Array(videoBytes);
  const chunkSize = 32768;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  const b64 = btoa(binary);
  const r = await fetch(`https://api.github.com/repos/${VIDEO_REPO}/contents/${path}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "shadow-gasp-bot"
    },
    body: JSON.stringify({
      message: `batch: day ${String(dayNum).padStart(2, "0")} hook video (via Telegram)`,
      content: b64,
      branch: "main",
      ...sha ? { sha } : {}
    })
  });
  if (!r.ok) throw new Error(`Commit failed: ${r.status} ${await r.text()}`);
}
__name(commitHookVideo, "commitHookVideo");
__name2(commitHookVideo, "commitHookVideo");
__name22(commitHookVideo, "commitHookVideo");
__name222(commitHookVideo, "commitHookVideo");
async function queueDayForScheduledPublish(env, dayNum, chatId) {
  const path = "_pipeline/batch/queue.json";
  for (let attempt = 0; attempt < 2; attempt++) {
    const existing = await fetch(
      `https://api.github.com/repos/${VIDEO_REPO}/contents/${path}?ref=main`,
      { headers: { Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`, "User-Agent": "shadow-gasp-bot" } }
    );
    let sha, queue = {};
    if (existing.ok) {
      const data = await existing.json();
      sha = data.sha;
      queue = JSON.parse(atob(data.content.replace(/\n/g, "")));
    }
    queue[String(dayNum)] = {
      status: "pending_render",
      notify_chat_id: String(chatId),
      queued_at: (/* @__PURE__ */ new Date()).toISOString()
    };
    const r = await fetch(`https://api.github.com/repos/${VIDEO_REPO}/contents/${path}`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "shadow-gasp-bot"
      },
      body: JSON.stringify({
        message: `queue: day ${dayNum} queued for 04:30/05:15 IST`,
        content: btoa(JSON.stringify(queue, null, 2)),
        branch: "main",
        ...sha ? { sha } : {}
      })
    });
    if (r.ok) return;
    if (attempt === 1) throw new Error(`Queue commit failed: ${r.status} ${await r.text()}`);
  }
}
__name(queueDayForScheduledPublish, "queueDayForScheduledPublish");
__name2(queueDayForScheduledPublish, "queueDayForScheduledPublish");
__name22(queueDayForScheduledPublish, "queueDayForScheduledPublish");
__name222(queueDayForScheduledPublish, "queueDayForScheduledPublish");
function describeNextIST(hh, mm) {
  const nowUtc = /* @__PURE__ */ new Date();
  const nowIst = new Date(nowUtc.getTime() + 5.5 * 3600 * 1e3);
  let target = new Date(Date.UTC(
    nowIst.getUTCFullYear(),
    nowIst.getUTCMonth(),
    nowIst.getUTCDate(),
    hh,
    mm,
    0
  ));
  const when = target.getTime() > nowIst.getTime() ? "today" : "tomorrow";
  return `${when} ${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")} IST`;
}
__name(describeNextIST, "describeNextIST");
__name2(describeNextIST, "describeNextIST");
__name22(describeNextIST, "describeNextIST");
__name222(describeNextIST, "describeNextIST");
function nextDayFiveFifteenIST() {
  const nowUtc = /* @__PURE__ */ new Date();
  const nowIst = new Date(nowUtc.getTime() + 5.5 * 3600 * 1e3);
  const target = new Date(Date.UTC(
    nowIst.getUTCFullYear(),
    nowIst.getUTCMonth(),
    nowIst.getUTCDate() + 1,
    5,
    15,
    0
  ));
  const publishAtUtc = new Date(target.getTime() - 5.5 * 3600 * 1e3);
  return publishAtUtc.toISOString().replace(/\.\d{3}Z$/, "Z");
}
__name(nextDayFiveFifteenIST, "nextDayFiveFifteenIST");
__name2(nextDayFiveFifteenIST, "nextDayFiveFifteenIST");
__name22(nextDayFiveFifteenIST, "nextDayFiveFifteenIST");
__name222(nextDayFiveFifteenIST, "nextDayFiveFifteenIST");
function istTimeToPublishAt(hhmm) {
  const m = hhmm.match(/^(\d{1,2}):(\d{2})$/);
  if (!m) return null;
  const [, hh, mm] = m;
  const nowUtc = /* @__PURE__ */ new Date();
  const nowIst = new Date(nowUtc.getTime() + 5.5 * 3600 * 1e3);
  let target = new Date(Date.UTC(
    nowIst.getUTCFullYear(),
    nowIst.getUTCMonth(),
    nowIst.getUTCDate(),
    Number(hh),
    Number(mm),
    0
  ));
  if (target.getTime() <= nowIst.getTime()) {
    target = new Date(target.getTime() + 24 * 3600 * 1e3);
  }
  const publishAtUtc = new Date(target.getTime() - 5.5 * 3600 * 1e3);
  return publishAtUtc.toISOString().replace(/\.\d{3}Z$/, "Z");
}
__name(istTimeToPublishAt, "istTimeToPublishAt");
__name2(istTimeToPublishAt, "istTimeToPublishAt");
__name22(istTimeToPublishAt, "istTimeToPublishAt");
__name222(istTimeToPublishAt, "istTimeToPublishAt");
function istDateTimeToPublishAt(dd, mm, yyyy, hhmm) {
  const m = hhmm.match(/^(\d{1,2}):(\d{2})$/);
  if (!m) return { error: `Couldn't parse time "${hhmm}" \u2014 use HH:MM` };
  const [, hh, min] = m;
  const day = Number(dd), month = Number(mm), year = Number(yyyy);
  if (day < 1 || day > 31 || month < 1 || month > 12 || Number(hh) > 23 || Number(min) > 59) {
    return { error: `Couldn't parse "${dd}-${mm}-${yyyy} ${hhmm}" \u2014 use DD-MM-YYYY HH:MM` };
  }
  const target = new Date(Date.UTC(year, month - 1, day, Number(hh), Number(min), 0));
  if (target.getUTCMonth() !== month - 1 || target.getUTCDate() !== day) {
    return { error: `"${dd}-${mm}-${yyyy}" isn't a real date` };
  }
  const publishAtUtc = new Date(target.getTime() - 5.5 * 3600 * 1e3);
  const nowUtc = /* @__PURE__ */ new Date();
  if (publishAtUtc.getTime() <= nowUtc.getTime()) {
    return { error: `${dd}-${mm}-${yyyy} ${hhmm} IST is already in the past` };
  }
  return { publishAt: publishAtUtc.toISOString().replace(/\.\d{3}Z$/, "Z") };
}
__name(istDateTimeToPublishAt, "istDateTimeToPublishAt");
__name2(istDateTimeToPublishAt, "istDateTimeToPublishAt");
__name22(istDateTimeToPublishAt, "istDateTimeToPublishAt");
__name222(istDateTimeToPublishAt, "istDateTimeToPublishAt");
function hookGateKeyboard(runId) {
  return {
    inline_keyboard: [[
      { text: "\u{1F6D1} Stop", callback_data: `hk:stop:${runId}` },
      { text: "\u25B6\uFE0F Continue with static still", callback_data: `hk:go:${runId}` }
    ]]
  };
}
__name(hookGateKeyboard, "hookGateKeyboard");
__name2(hookGateKeyboard, "hookGateKeyboard");
__name22(hookGateKeyboard, "hookGateKeyboard");
__name222(hookGateKeyboard, "hookGateKeyboard");
function approvalKeyboard(token) {
  return {
    inline_keyboard: [[
      { text: "\u2705 Approve", callback_data: `approve:${token}` },
      { text: "\u274C Reject", callback_data: `reject:${token}` },
      { text: "\u{1F4C4} Increase Pages", callback_data: `pages_menu:${token}` }
    ]]
  };
}
__name(approvalKeyboard, "approvalKeyboard");
__name2(approvalKeyboard, "approvalKeyboard");
__name22(approvalKeyboard, "approvalKeyboard");
__name222(approvalKeyboard, "approvalKeyboard");
var PAGE_PRICE_TIERS = { 20: "0", 25: "2.99", 35: "3.99", 50: "4.99", 75: "6.99", 100: "8.99" };
function priceLabel(n) {
  return PAGE_PRICE_TIERS[n] === "0" ? `${n}pp (FREE)` : `${n}pp ($${PAGE_PRICE_TIERS[n]})`;
}
__name(priceLabel, "priceLabel");
__name2(priceLabel, "priceLabel");
__name22(priceLabel, "priceLabel");
__name222(priceLabel, "priceLabel");
function makePageCountKeyboard() {
  return {
    inline_keyboard: [[20, 25, 35, 50, 75, 100].map((n) => ({
      text: priceLabel(n),
      callback_data: `make_pages:${n}`
    }))]
  };
}
__name(makePageCountKeyboard, "makePageCountKeyboard");
__name2(makePageCountKeyboard, "makePageCountKeyboard");
__name22(makePageCountKeyboard, "makePageCountKeyboard");
__name222(makePageCountKeyboard, "makePageCountKeyboard");
var STYLE_BUTTONS = [
  ["cinematic", "\u{1F3AC}"],
  ["mosaic", "\u{1F9E9}"],
  ["classic", "\u{1F4D6}"],
  ["chamber", "\u{1F512}"],
  ["staccato", "\u26A1"],
  ["documentary", "\u{1F4C1}"]
];
function makeStyleKeyboard() {
  const btn = /* @__PURE__ */ __name2(([name, icon]) => ({ text: `${icon} ${name}`, callback_data: `make_style:${name}` }), "btn");
  return {
    inline_keyboard: [
      STYLE_BUTTONS.slice(0, 3).map(btn),
      STYLE_BUTTONS.slice(3).map(btn),
      [{ text: "\u{1F3B2} Auto (from case name)", callback_data: "make_style:auto" }]
    ]
  };
}
__name(makeStyleKeyboard, "makeStyleKeyboard");
__name2(makeStyleKeyboard, "makeStyleKeyboard");
__name22(makeStyleKeyboard, "makeStyleKeyboard");
__name222(makeStyleKeyboard, "makeStyleKeyboard");
function pageCountKeyboard(token) {
  return {
    inline_keyboard: [[20, 35, 50, 75, 100].map((n) => ({
      text: priceLabel(n),
      callback_data: `set_pages:${token}:${n}`
    }))]
  };
}
__name(pageCountKeyboard, "pageCountKeyboard");
__name2(pageCountKeyboard, "pageCountKeyboard");
__name22(pageCountKeyboard, "pageCountKeyboard");
__name222(pageCountKeyboard, "pageCountKeyboard");
function confirmPublishKeyboard(token) {
  return {
    inline_keyboard: [[
      { text: "\u2705 Confirm Publish (goes LIVE)", callback_data: `confirm_publish:${token}` },
      { text: "\u21A9\uFE0F Cancel", callback_data: `cancel_publish:${token}` }
    ]]
  };
}
__name(confirmPublishKeyboard, "confirmPublishKeyboard");
__name2(confirmPublishKeyboard, "confirmPublishKeyboard");
__name22(confirmPublishKeyboard, "confirmPublishKeyboard");
__name222(confirmPublishKeyboard, "confirmPublishKeyboard");
async function handleCallback(env, cq) {
  const data = cq.data || "";
  const [action, token, extra] = data.split(":");
  const chatId = cq.message.chat.id;
  const messageId = cq.message.message_id;
  if (action === "clip") {
    const chosen = token;
    const raw2 = await env.PENDING.get(`pendingclip:${chatId}`);
    if (!raw2) {
      await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "That clip has expired -- send it again." });
      return;
    }
    await env.PENDING.delete(`pendingclip:${chatId}`);
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `Committing as day ${chosen}.` });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `\u{1F4E5} Using this clip for day ${chosen}.`
    });
    await acceptHookClip(env, chatId, chosen, JSON.parse(raw2).file_id);
    return;
  }
  if (action === "hk") {
    const decision = token;
    const runId = extra;
    if (decision !== "stop" && decision !== "go" || !runId) return;
    await env.PENDING.put(`hookdecision:${runId}`, decision, { expirationTtl: 2 * 3600 });
    await tg(env, "answerCallbackQuery", {
      callback_query_id: cq.id,
      text: decision === "stop" ? "Stopping -- won't publish hookless." : "Continuing with a static still."
    });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: decision === "stop" ? "\u{1F6D1} Stopped \u2014 render will not publish hookless." : "\u25B6\uFE0F Continuing \u2014 will render and publish with a static Ken Burns still."
    });
    return;
  }
  if (action === "pregen") {
    const n = parseInt(token, 10);
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `Starting ${n} days...` });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `\u{1F3AC} Generating ${n} new batch day(s) (case + script + 16 stills, vision-QA checked). This is sequential, so budget ~${n * 20}-${n * 30} min. I'll message you here once this chunk finishes.`
    });
    try {
      await dispatchBatchPregen(env, { days: String(n), notify_chat_id: String(chatId) });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start pregen: ${e.message}` });
    }
    return;
  }
  if (action === "make_pages") {
    const pages = token;
    const caseName = await env.PENDING.get(`awaiting_make:${chatId}`);
    if (caseName === null) {
      await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "This /make request expired -- send /make again" });
      return;
    }
    await env.PENDING.delete(`awaiting_make:${chatId}`);
    const label = priceLabel(parseInt(pages, 10));
    await env.PENDING.put(
      `awaiting_style:${chatId}`,
      JSON.stringify({ case: caseName, pages, label }),
      { expirationTtl: 3600 }
    );
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `${label} -- now pick a style` });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `${caseName ? `"${caseName}"` : "Next auto-picked case"} at ${label}.

Which page style?
\u{1F3AC} cinematic -- widescreen, wide tiers, splashes used generously
\u{1F9E9} mosaic -- restless, tier structure changes every page
\u{1F4D6} classic -- house rhythm, wide establishing then tighter beats
\u{1F512} chamber -- close and claustrophobic, paired tall panels
\u26A1 staccato -- fast cutting, abrupt changes of size
\u{1F4C1} documentary -- dense evidential grid, splashes rare`,
      reply_markup: makeStyleKeyboard()
    });
    return;
  }
  if (action === "make_style") {
    const style = token;
    const raw2 = await env.PENDING.get(`awaiting_style:${chatId}`);
    if (raw2 === null) {
      await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "This /make request expired -- send /make again" });
      return;
    }
    await env.PENDING.delete(`awaiting_style:${chatId}`);
    const { case: caseName, pages, label } = JSON.parse(raw2);
    const profile = style === "auto" ? "" : style;
    const styleLabel = profile || "auto (from case name)";
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `Building ${styleLabel}...` });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `\u{1F3AC} Building ${caseName ? `"${caseName}"` : "the next auto-picked case"} at ${label}, ${styleLabel} layout.
This takes a while (script \u2192 art \u2192 OCR check \u2192 PDF). You'll get the draft here with buttons when it's done.`
    });
    try {
      await dispatchPipeline(env, { case: caseName, target_pages: pages, profile, dry_run: "false" });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start build: ${e.message}` });
    }
    return;
  }
  if (action === "titlestyle") {
    const day = token;
    const style = extra;
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `Drafting a ${style} title...` });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `\u270D\uFE0F Drafting a ${style} title for day ${day}...`
    });
    try {
      await dispatchGenerateTitleVariant(env, { day: String(day), style, notify_chat_id: String(chatId) });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start title draft: ${e.message}` });
    }
    return;
  }
  if (action === "title_retry") {
    const day = token;
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id });
    let currentLine = "";
    try {
      const cur = await getCurrentTitle(env, day);
      currentLine = cur ? `Current title (${cur.source}): "${cur.title}"

` : "";
    } catch (e) {
      currentLine = "";
    }
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `${currentLine}Pick a title style for day ${day}:`,
      reply_markup: titleStyleKeyboard(day)
    });
    return;
  }
  if (action === "title_regen") {
    const day = token;
    const style = extra || "direct";
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `Regenerating a ${style} title...` });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `\u{1F504} Regenerating a ${style} title for day ${day}...`
    });
    try {
      await dispatchGenerateTitleVariant(env, { day: String(day), style, notify_chat_id: String(chatId) });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't regenerate: ${e.message}` });
    }
    return;
  }
  if (action === "edittitle") {
    const day = token;
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id });
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: `Pick a title style for day ${day} (drafts only -- nothing is applied until you tap Apply). Only takes effect if this day hasn't uploaded to YouTube yet -- the upload token can't edit a live title.`,
      reply_markup: titleStyleKeyboard(day)
    });
    return;
  }
  if (action === "title_discard") {
    const day = token;
    await env.PENDING.delete(`titledraft:${day}`);
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Discarded" });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `Discarded draft for day ${day}. The normal AI-generated title stays in effect.`
    });
    return;
  }
  if (action === "title_apply") {
    const day = token;
    const draftRaw = await env.PENDING.get(`titledraft:${day}`);
    if (!draftRaw) {
      await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Draft expired or already applied" });
      return;
    }
    const draft = JSON.parse(draftRaw);
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Applying..." });
    try {
      await commitTitleOverride(env, day, draft.title, draft.tags);
      await env.PENDING.delete(`titledraft:${day}`);
      await tg(env, "editMessageText", {
        chat_id: chatId,
        message_id: messageId,
        text: `\u2705 Applied for day ${day}: "${draft.title}"
Saved as the pending title (used if this day hasn't uploaded yet). Checking whether it's already live on YouTube...`
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't apply title override: ${e.message}` });
      return;
    }
    try {
      await dispatchRetitlePublished(env, { day: String(day), new_title: draft.title, notify_chat_id: String(chatId) });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't check/apply the live retitle: ${e.message}` });
    }
    return;
  }
  if (action === "fbdec" || action === "igdec") {
    const day = token;
    const decision = extra;
    const platform = action === "fbdec" ? "fb" : "ig";
    const label = platform === "fb" ? "Facebook" : "Instagram";
    if (decision !== "approve" && decision !== "reject") return;
    await tg(env, "answerCallbackQuery", {
      callback_query_id: cq.id,
      text: decision === "approve" ? `Posting to ${label} now...` : `Rejecting ${label}...`
    });
    try {
      await dispatchCrosspostDecision(env, { day: String(day), platform, decision, notify_chat_id: String(chatId) });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't ${decision} ${label} for day ${day}: ${e.message}` });
    }
    return;
  }
  const raw = await env.PENDING.get(`pending:${token}`);
  if (!raw) {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Unknown or expired request" });
    return;
  }
  const entry = JSON.parse(raw);
  if (action === "approve") {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `Ready to publish "${entry.case}" (Gumroad draft ${entry.product_id}).
Confirm to go LIVE, or Cancel to back out.`,
      reply_markup: confirmPublishKeyboard(token)
    });
  } else if (action === "reject") {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Rejecting..." });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `\u274C Rejecting "${entry.case}"... deleting Gumroad draft.`
    });
    await dispatchAction(env, {
      action: "reject",
      product_id: entry.product_id,
      chat_id: String(chatId),
      message_id: String(messageId)
    });
  } else if (action === "pages_menu") {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `How many pages should "${entry.case}" be expanded to?`,
      reply_markup: pageCountKeyboard(token)
    });
  } else if (action === "set_pages") {
    const label = priceLabel(parseInt(extra, 10));
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `Regenerating at ${label}...` });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `\u{1F504} Regenerating "${entry.case}" at ${label}. This takes a while (script + art + build) \u2014 you'll get a new message when it's ready.`
    });
    await dispatchAction(env, {
      action: "regenerate",
      case: entry.case,
      target_pages: extra,
      chat_id: String(chatId),
      message_id: String(messageId)
    });
  } else if (action === "confirm_publish") {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Publishing..." });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `Publishing "${entry.case}"...`
    });
    await dispatchAction(env, {
      action: "publish",
      product_id: entry.product_id,
      case: entry.case,
      chat_id: String(chatId),
      message_id: String(messageId)
    });
  } else if (action === "cancel_publish") {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Cancelled" });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `Publish cancelled for "${entry.case}". Draft left as-is on Gumroad. Re-approve when ready.`,
      reply_markup: approvalKeyboard(token)
    });
  } else {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Unknown action" });
  }
}
__name(handleCallback, "handleCallback");
__name2(handleCallback, "handleCallback");
__name22(handleCallback, "handleCallback");
__name222(handleCallback, "handleCallback");
async function acceptHookClip(env, chatId, dayNum, fileId) {
  dayNum = String(dayNum);
  await tg(env, "sendMessage", { chat_id: chatId, text: `\u{1F4E5} Got it \u2014 committing as day ${dayNum}'s hook video, then queuing it for the scheduled 04:30/05:15 IST render+publish slot. I'll confirm here once it's live.` });
  try {
    const fileInfo = await tg(env, "getFile", { file_id: fileId });
    if (!fileInfo.ok) throw new Error(`getFile failed: ${JSON.stringify(fileInfo)}`);
    const fileUrl = `https://api.telegram.org/file/bot${env.TELEGRAM_BOT_TOKEN}/${fileInfo.result.file_path}`;
    const fileResp = await fetch(fileUrl);
    if (!fileResp.ok) throw new Error(`file download failed: ${fileResp.status}`);
    const videoBytes = await fileResp.arrayBuffer();
    await commitHookVideo(env, dayNum, videoBytes);
    await queueDayForScheduledPublish(env, dayNum, chatId);
    const shortRaw = await env.PENDING.get(`awaiting_short_hook:${chatId}`);
    if (shortRaw && String(JSON.parse(shortRaw).day) === dayNum) {
      await env.PENDING.delete(`awaiting_short_hook:${chatId}`);
    }
    if (await env.PENDING.get(`awaiting_hook:${chatId}`) === dayNum) {
      await env.PENDING.delete(`awaiting_hook:${chatId}`);
    }
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: `\u{1F550} Day ${dayNum} hook video committed and queued. Renders ${describeNextIST(4, 30)}, publishes to YouTube at ${describeNextIST(5, 15)} \u2014 I'll message you here the moment it's live, with Facebook/Instagram Approve/Reject buttons on that message. (Want it out sooner instead? Use /publish ${dayNum} to skip the queue and go now.)

Want a different title than the AI-generated one? Tap below -- only works before this renders/uploads.`,
      reply_markup: titleStyleKeyboard(dayNum)
    });
  } catch (e) {
    await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't process the video: ${e.message}` });
  }
}
__name(acceptHookClip, "acceptHookClip");
__name2(acceptHookClip, "acceptHookClip");
async function handleMessage(env, msg) {
  const text = (msg.text || "").trim();
  const chatId = msg.chat.id;
  const videoObj = msg.video || (msg.document && msg.document.mime_type?.startsWith("video/") ? msg.document : null);
  if (videoObj) {
    const repliedTo = msg.reply_to_message;
    const repliedText = repliedTo ? repliedTo.caption || repliedTo.text || "" : "";
    const replyMatch = repliedText.match(/^Day\s+0*(\d+)\s*:/);
    const shortRaw = await env.PENDING.get(`awaiting_short_hook:${chatId}`);
    const shortDay = shortRaw ? String(JSON.parse(shortRaw).day) : null;
    const manualDay = await env.PENDING.get(`awaiting_hook:${chatId}`);
    let dayNum = null;
    if (replyMatch) {
      dayNum = String(parseInt(replyMatch[1], 10));
    } else if (shortDay && manualDay && shortDay !== manualDay) {
      await env.PENDING.put(`pendingclip:${chatId}`, JSON.stringify({ file_id: videoObj.file_id }), { expirationTtl: 3600 });
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `\u2753 Two days are waiting on a hook clip: day ${shortDay} (today's automatic build) and day ${manualDay} (your /day ${manualDay}). Which one is this clip for?

Tip: replying directly to a day's hook-request message skips this question.`,
        reply_markup: { inline_keyboard: [[
          { text: `Day ${shortDay}`, callback_data: `clip:${shortDay}` },
          { text: `Day ${manualDay}`, callback_data: `clip:${manualDay}` }
        ]] }
      });
      return;
    } else {
      dayNum = shortDay || manualDay;
    }
    if (!dayNum) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "Got a video, but no day is waiting on a hook clip -- send /day <N> first so I know which day this belongs to." });
      return;
    }
    await acceptHookClip(env, chatId, dayNum, videoObj.file_id);
    return;
  }
  if (text.startsWith("/freeclaims")) {
    const slug = text.slice("/freeclaims".length).trim();
    if (!slug) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "Usage: /freeclaims <slug>, e.g. /freeclaims norjak" });
      return;
    }
    const count = parseInt(await env.PENDING.get(`free_codes_count:${slug}`) || "0", 10);
    await tg(env, "sendMessage", { chat_id: chatId, text: `\u{1F381} ${slug}: ${count} one-time code(s) issued so far.` });
    return;
  }
  if (text.startsWith("/gencode")) {
    const rest2 = text.slice("/gencode".length).trim();
    const [slug, capStr] = rest2.split(/\s+/);
    if (!slug) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "Usage: /gencode <slug> [cap], e.g. /gencode norjak 50" });
      return;
    }
    const raw = await env.PENDING.get(`free_offer:${slug}`);
    if (!raw) {
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `No product registered for "${slug}" yet. Register it once with the product_id first (ask Claude), then /gencode will work from here on.`
      });
      return;
    }
    const { product_id } = JSON.parse(raw);
    const cap = capStr && /^\d+$/.test(capStr) ? capStr : "50";
    try {
      await dispatchGenCode(env, { slug, product_id, cap, chat_id: String(chatId) });
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u{1F504} Generating a one-time code for "${slug}" (cap ${cap}) \u2014 I'll DM it here shortly.` });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start code generation: ${e.message}` });
    }
    return;
  }
  if (text.startsWith("/pregen")) {
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: "How many new batch days should I generate (case + script + 16 stills each, no hook video yet)? Each day takes ~15-30 min, sequentially.",
      reply_markup: pregenKeyboard()
    });
    return;
  }
  if (text.startsWith("/day")) {
    const dayNum = parseInt(text.slice("/day".length).trim(), 10);
    if (!dayNum) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "Usage: /day <N>, e.g. /day 1" });
      return;
    }
    const dd = String(dayNum).padStart(2, "0");
    try {
      const meta = await (await ghRaw(env, `_pipeline/batch/day${dd}/meta.json`)).json();
      const shot1Url = await hookStillUrl(env, dd);
      await env.PENDING.put(`awaiting_hook:${chatId}`, String(dayNum), { expirationTtl: 86400 });
      await sendHookStill(env, chatId, shot1Url, `Day ${dayNum}: "${meta.title_working}"

Motion prompt for Google Flow:
${meta.hook_motion_prompt}

Reply here with the finished Flow video when ready.`);
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't load day ${dayNum}: ${e.message}` });
    }
    return;
  }
  if (text.startsWith("/title")) {
    const dayNum = parseInt(text.slice("/title".length).trim(), 10);
    if (!dayNum) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "Usage: /title <N>, e.g. /title 12" });
      return;
    }
    let currentLine = "";
    try {
      const cur = await getCurrentTitle(env, dayNum);
      currentLine = cur ? `Current title (${cur.source}): "${cur.title}"

` : "";
    } catch (e) {
      currentLine = "";
    }
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: `${currentLine}Pick a title style for day ${dayNum} (drafts only -- nothing is applied until you tap Apply). Only takes effect if this day hasn't uploaded to YouTube yet -- the upload token can't edit a live title.`,
      reply_markup: titleStyleKeyboard(dayNum)
    });
    return;
  }
  if (text.startsWith("/publish")) {
    const rest2 = text.slice("/publish".length).trim();
    const atDateMatch = rest2.match(/^(\d+)\s+at\s+(\d{1,2})-(\d{1,2})-(\d{4})\s+(\d{1,2}:\d{2})$/i);
    const atTimeMatch = !atDateMatch ? rest2.match(/^(\d+)\s+at\s+(\d{1,2}:\d{2})$/i) : null;
    const dayNum = atDateMatch ? parseInt(atDateMatch[1], 10) : atTimeMatch ? parseInt(atTimeMatch[1], 10) : parseInt(rest2, 10);
    if (!dayNum) {
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: "Usage:\n/publish <N>\n/publish <N> at <HH:MM> (IST, next occurrence)\n/publish <N> at <DD-MM-YYYY> <HH:MM> (IST, exact date)"
      });
      return;
    }
    let publishAt = "";
    let whenLabel = "";
    if (atDateMatch) {
      const [, , dd, mm, yyyy, hhmm] = atDateMatch;
      const result = istDateTimeToPublishAt(dd, mm, yyyy, hhmm);
      if (result.error) {
        await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C ${result.error}` });
        return;
      }
      publishAt = result.publishAt;
      whenLabel = `${dd}-${mm}-${yyyy} ${hhmm} IST`;
    } else if (atTimeMatch) {
      publishAt = istTimeToPublishAt(atTimeMatch[2]);
      if (!publishAt) {
        await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't parse time "${atTimeMatch[2]}" \u2014 use HH:MM` });
        return;
      }
      whenLabel = `${atTimeMatch[2]} IST`;
    }
    try {
      await dispatchFinishBatchDay(env, { day: String(dayNum), upload: "true", publish_at: publishAt, notify_chat_id: String(chatId) });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start publish: ${e.message}` });
      return;
    }
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: publishAt ? `\u{1F4C5} Rendering day ${dayNum} and scheduling YouTube for ${whenLabel}. Facebook/Instagram are handled separately -- Approve/Reject buttons will show up on the "day is LIVE" message once it uploads.` : `\u{1F680} Rendering + publishing day ${dayNum} to YouTube now. Facebook/Instagram are handled separately -- Approve/Reject buttons will show up on the "day is LIVE" message once it uploads.`
    });
    return;
  }
  if (text.startsWith("/cancel")) {
    const rest3 = text.slice("/cancel".length).trim();
    const dayNum2 = parseInt(rest3, 10);
    if (!dayNum2) {
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: "Usage:\n/cancel <N>  \u2014 cancel an in-progress render/publish for day N.\nOnly matches runs dispatched after this command shipped (older runs aren't tagged with their day number)."
      });
      return;
    }
    try {
      const headers = { Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`, "User-Agent": "shadow-gasp-bot" };
      const [inProgR, queuedR] = await Promise.all([
        fetch(`https://api.github.com/repos/${VIDEO_REPO}/actions/workflows/finish_batch_day.yml/runs?status=in_progress&per_page=20`, { headers }),
        fetch(`https://api.github.com/repos/${VIDEO_REPO}/actions/workflows/finish_batch_day.yml/runs?status=queued&per_page=20`, { headers })
      ]);
      if (!inProgR.ok) throw new Error(`GitHub list failed: ${inProgR.status} ${await inProgR.text()}`);
      const inProgData = await inProgR.json();
      const queuedData = queuedR.ok ? await queuedR.json() : { workflow_runs: [] };
      const candidates = [...inProgData.workflow_runs || [], ...queuedData.workflow_runs || []];
      const dayToken = new RegExp(`^day ${dayNum2}(\\D|$)`, "i");
      const match = candidates.find((run) => dayToken.test(run.display_title || run.name || ""));
      if (!match) {
        const listing = candidates.length ? candidates.map((r2) => `#${r2.run_number} "${r2.display_title}" (${r2.status})`).join("\n") : "none";
        await tg(env, "sendMessage", {
          chat_id: chatId,
          text: `\u26A0\uFE0F No in-progress run tagged "day ${dayNum2}" found (older runs from before /cancel shipped aren't tagged). Currently active:
${listing}

Cancel manually from the Actions tab if one of these is it: https://github.com/${VIDEO_REPO}/actions`
        });
        return;
      }
      const cancelR = await fetch(`https://api.github.com/repos/${VIDEO_REPO}/actions/runs/${match.id}/cancel`, {
        method: "POST",
        headers: { ...headers, Accept: "application/vnd.github+json" }
      });
      if (!cancelR.ok && cancelR.status !== 202) throw new Error(`Cancel failed: ${cancelR.status} ${await cancelR.text()}`);
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `\u{1F6D1} Cancelling day ${dayNum2}'s run (#${match.run_number}, was ${match.status}). This only stops the render/upload job -- it does NOT touch or unpublish anything already live on YouTube/FB/IG.`
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't cancel: ${e.message}` });
    }
    return;
  }
  if (text.startsWith("/short")) {
    const rest2 = text.slice("/short".length).trim();
    const bar2 = rest2.lastIndexOf("|");
    const caseName2 = bar2 !== -1 ? rest2.slice(0, bar2).trim() : rest2;
    try {
      await dispatchVideoPipeline(env, { case: caseName2 });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start short: ${e.message}` });
      return;
    }
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: `\u{1F3AC} Building short: ${caseName2 ? `"${caseName2}"` : "next auto-picked case"} (script -> FLUX stills on GitHub Actions, ~15-25 min). It'll land as a new batch day and I'll DM you the hook still + Flow motion prompt here, same as /day -- reply with the Flow video within 5h or it auto-falls-back to a static cut, scheduled for the next 05:15 IST slot.`
    });
    return;
  }
  if (text.startsWith("/retention")) {
    try {
      await dispatchWorkflowVerified(env, "retention.yml", { chat_id: String(chatId) });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start the retention digest: ${e.message}` });
      return;
    }
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: "\u{1F4CA} Pulling retention analytics (last 21 days)\u2026 report in a minute or two."
    });
    return;
  }
  if (text.startsWith("/trending")) {
    try {
      await dispatchWorkflowVerified(env, "trending.yml", { chat_id: String(chatId) });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start the trending search: ${e.message}` });
      return;
    }
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: "\u{1F50E} Scanning for trending true-crime/horror stories (checked against what's already covered)\u2026 report in a couple minutes."
    });
    return;
  }
  if (!text.startsWith("/make")) {
    if (text.startsWith("/")) {
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: "Commands:\n/make <case name>  \u2014 build a comic (asks pages, then page style)\n/make <case name> | 50  \u2014 build now, explicit page count (skips both pickers, auto style)\n/make  \u2014 auto-pick the next comic case (still asks pages + style)\n\n/gencode <slug> [cap]  \u2014 mint a ONE-TIME free code for a published comic, DM'd here (default cap 50). Send the code to one person only \u2014 it stops working after their first use.\n/freeclaims <slug>  \u2014 check how many one-time codes have been issued so far\n\n/short  \u2014 auto-pick + generate a new true-crime short's script+stills, then DM the hook still + Flow prompt (5h reply window, else auto-falls-back to a static cut scheduled for 05:15 IST)\n/short <case>  \u2014 same, for a specific case\n\n/day <N>  \u2014 get day N's hook still + Flow prompt from the batch\n(reply with the Flow video)  \u2014 commits it, renders + uploads to YouTube automatically\n/publish <N>  \u2014 render + upload day N now\n/publish <N> at <HH:MM>  \u2014 same, scheduled for that IST time\n/cancel <N>  \u2014 cancel an in-progress render/publish for day N (only runs dispatched after this shipped)\n/title <N>  \u2014 draft an alt title in a style (Shock/Curiosity/Open-loop/Direct), tap Apply to use it -- only works before this day uploads to YouTube\n\n/trending  \u2014 report-only scan for trending true-crime/horror stories not yet covered (nothing auto-built)\n/retention  \u2014 report-only digest: last 21 days' views/retention/drop-off per video, ranked by retention AND reach separately"
      });
    }
    return;
  }
  const rest = text.slice("/make".length).trim();
  let caseName = rest;
  const bar = rest.lastIndexOf("|");
  if (bar !== -1) {
    caseName = rest.slice(0, bar).trim();
    const n = rest.slice(bar + 1).trim();
    if (/^\d+$/.test(n)) {
      try {
        await dispatchPipeline(env, { case: caseName, target_pages: n, dry_run: "false" });
      } catch (e) {
        await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start build: ${e.message}` });
        return;
      }
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `\u{1F3AC} Building ${caseName ? `"${caseName}"` : "the next auto-picked case"} at ${priceLabel(parseInt(n, 10))}.
This takes a while (script \u2192 art \u2192 OCR check \u2192 PDF). You'll get the draft here with buttons when it's done.`
      });
      return;
    }
  }
  await env.PENDING.put(`awaiting_make:${chatId}`, caseName, { expirationTtl: 3600 });
  await tg(env, "sendMessage", {
    chat_id: chatId,
    text: `How many pages should ${caseName ? `"${caseName}"` : "the next auto-picked case"} be?`,
    reply_markup: makePageCountKeyboard()
  });
}
__name(handleMessage, "handleMessage");
__name2(handleMessage, "handleMessage");
__name22(handleMessage, "handleMessage");
__name222(handleMessage, "handleMessage");
async function sendApprovalMessage(env, { token, caseName, productId, title }) {
  return tg(env, "sendMessage", {
    chat_id: env.TELEGRAM_CHAT_ID,
    text: `${title} \u2014 draft ready for review (Gumroad draft: ${productId})`,
    reply_markup: approvalKeyboard(token)
  });
}
__name(sendApprovalMessage, "sendApprovalMessage");
__name2(sendApprovalMessage, "sendApprovalMessage");
__name22(sendApprovalMessage, "sendApprovalMessage");
__name222(sendApprovalMessage, "sendApprovalMessage");
async function sweepExpiredHookWaits(env) {
  const list = await env.PENDING.list({ prefix: "awaiting_short_hook:" });
  for (const key of list.keys) {
    const raw = await env.PENDING.get(key.name);
    if (!raw) continue;
    let entry;
    try {
      entry = JSON.parse(raw);
    } catch {
      await env.PENDING.delete(key.name);
      continue;
    }
    if (Date.now() < entry.deadline) continue;
    const chatId = key.name.slice("awaiting_short_hook:".length);
    const day = entry.day;
    try {
      await dispatchFinishBatchDay(env, {
        day: String(day),
        upload: "true",
        publish_at: nextDayFiveFifteenIST(),
        notify_chat_id: chatId,
        use_cog_fallback: "false"
      });
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `\u23F0 No Flow hook video for day ${String(day).padStart(2, "0")} within 5 hours \u2014 falling back to a static cut, rendering now and scheduling it for tomorrow 05:15 IST.`
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Day ${day}'s hook-video deadline passed and the static-fallback dispatch failed: ${e.message}. Use /publish ${day} to retry manually.` });
    }
    await env.PENDING.delete(key.name);
  }
}
__name(sweepExpiredHookWaits, "sweepExpiredHookWaits");
__name2(sweepExpiredHookWaits, "sweepExpiredHookWaits");
__name22(sweepExpiredHookWaits, "sweepExpiredHookWaits");
__name222(sweepExpiredHookWaits, "sweepExpiredHookWaits");
var worker_default = {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "POST" && url.pathname === "/free-offer/set") {
      const auth = request.headers.get("X-Shared-Secret");
      if (auth !== env.WORKER_SHARED_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { slug, product_id, offer_code_id, code } = body;
      if (!slug || !product_id || !offer_code_id || !code) {
        return new Response("missing fields", { status: 400 });
      }
      await env.PENDING.put(`free_offer:${slug}`, JSON.stringify({ product_id, offer_code_id, code }));
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/free-codes/reserve") {
      const auth = request.headers.get("X-Shared-Secret");
      if (auth !== env.WORKER_SHARED_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { slug, cap } = body;
      if (!slug || !cap) {
        return new Response("missing fields", { status: 400 });
      }
      const key = `free_codes_count:${slug}`;
      const current = parseInt(await env.PENDING.get(key) || "0", 10);
      if (current >= cap) {
        return new Response(JSON.stringify({ error: "cap reached", count: current }), {
          status: 409,
          headers: { "Content-Type": "application/json" }
        });
      }
      const next = current + 1;
      await env.PENDING.put(key, String(next));
      return new Response(JSON.stringify({ ok: true, count: next }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }
    if (request.method === "GET" && url.pathname.startsWith("/free-claims/")) {
      const auth = request.headers.get("X-Shared-Secret");
      if (auth !== env.WORKER_SHARED_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const slug = url.pathname.slice("/free-claims/".length);
      const raw = await env.PENDING.get(`free_offer:${slug}`);
      if (!raw) {
        return new Response(JSON.stringify({ error: "no free offer configured for this slug" }), {
          status: 404,
          headers: { "Content-Type": "application/json" }
        });
      }
      const { product_id, offer_code_id, code } = JSON.parse(raw);
      const gr = await fetch(
        `https://api.gumroad.com/v2/products/${product_id}/offer_codes/${offer_code_id}?access_token=${env.GUMROAD_ACCESS_TOKEN}`
      );
      const grData = await gr.json();
      const oc = grData.offer_code || {};
      const cap = oc.max_purchase_count ?? 0;
      const claimed = oc.times_used ?? 0;
      return new Response(JSON.stringify({
        code,
        cap,
        claimed,
        remaining: Math.max(0, cap - claimed),
        sold_out: claimed >= cap
      }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (request.method === "POST" && url.pathname === "/register") {
      const auth = request.headers.get("X-Shared-Secret");
      if (auth !== env.WORKER_SHARED_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { token, case: caseName, product_id, title } = body;
      if (!token || !caseName || !product_id) {
        return new Response("missing fields", { status: 400 });
      }
      await env.PENDING.put(`pending:${token}`, JSON.stringify({ case: caseName, product_id }));
      await sendApprovalMessage(env, { token, caseName, productId: product_id, title: title || caseName });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/script-cache/save") {
      const auth = request.headers.get("X-Shared-Secret");
      if (auth !== env.WORKER_SHARED_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { key, script, panel_prompts } = body;
      if (!key || !script || !panel_prompts) {
        return new Response("missing fields", { status: 400 });
      }
      await env.PENDING.put(`script_cache:${key}`, JSON.stringify({ script, panel_prompts }), { expirationTtl: 604800 });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/script-cache/get") {
      const auth = request.headers.get("X-Shared-Secret");
      if (auth !== env.WORKER_SHARED_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const raw = body.key ? await env.PENDING.get(`script_cache:${body.key}`) : null;
      if (!raw) {
        return new Response("not found", { status: 404 });
      }
      return new Response(raw, { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (request.method === "POST" && url.pathname === "/batch/uploaded") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { day, case: caseName, video_id, drive_link, cloudinary_link, title, hashtags, fb_post_id, ig_media_id, chat_id } = body;
      if (!day || !video_id && !fb_post_id && !ig_media_id) {
        return new Response("missing fields", { status: 400 });
      }
      const lines = [];
      if (video_id) {
        lines.push(`\u2705 Day ${day} is LIVE on YouTube: https://youtu.be/${video_id}`);
      } else {
        lines.push(`\u2705 Day ${day} crossposted (YouTube upload skipped this run):`);
      }
      if (title) lines.push(`"${title}"`);
      else if (caseName) lines.push(`"${caseName}"`);
      if (fb_post_id) lines.push(`\u{1F4D8} Facebook: https://facebook.com/${fb_post_id}`);
      if (ig_media_id) lines.push(`\u{1F4F7} Instagram media_id: ${ig_media_id}`);
      if (cloudinary_link) lines.push(`\u2B07\uFE0F Download: ${cloudinary_link}`);
      else if (drive_link) lines.push(`\u{1F4F9} Video file: ${drive_link}`);
      if (hashtags) lines.push(hashtags);
      const needsCrosspostDecision = !!video_id && !fb_post_id && !ig_media_id;
      if (needsCrosspostDecision) {
        lines.push("", "\u{1F4E4} Facebook and Instagram are NOT posted yet -- approve or reject each below:");
      }
      await tg(env, "sendMessage", {
        chat_id: chat_id || env.TELEGRAM_CHAT_ID,
        text: lines.join("\n"),
        ...needsCrosspostDecision ? { reply_markup: fbIgDecisionKeyboard(day) } : {}
      });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/batch/crosspost-decided") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { day, platform, decision, ref_id, chat_id } = body;
      if (!day || !platform || !decision) {
        return new Response("missing fields", { status: 400 });
      }
      const label = platform === "fb" ? "Facebook" : "Instagram";
      let text;
      if (decision === "approve") {
        text = ref_id ? `\u2705 Day ${day} posted to ${label}: ${platform === "fb" ? `https://facebook.com/${ref_id}` : `media_id ${ref_id}`}` : `\u26A0\uFE0F Day ${day} ${label} approve ran but no post id came back -- check the Actions log.`;
      } else {
        text = `\u{1F6AB} Day ${day} ${label}: rejected, not posted.`;
      }
      await tg(env, "sendMessage", { chat_id: chat_id || env.TELEGRAM_CHAT_ID, text });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/batch/title-variant") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { day, style, title, tags, chat_id } = body;
      if (!day || !title) {
        return new Response("missing fields", { status: 400 });
      }
      const targetChatId = chat_id || env.TELEGRAM_CHAT_ID;
      await env.PENDING.put(`titledraft:${day}`, JSON.stringify({ title, tags: tags || [], style: style || "" }), { expirationTtl: 86400 });
      const hashtags = (tags || []).map((t) => `#${String(t).replace(/\s+/g, "")}`).join(" ");
      await tg(env, "sendMessage", {
        chat_id: targetChatId,
        text: `\u{1F4DD} ${style || ""} title draft for day ${day}:
"${title}"
${hashtags}

Apply, regenerate, try another style, or discard?`,
        reply_markup: titleDraftKeyboard(day, style)
      });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/batch/notify-raw") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { chat_id, text } = body;
      if (!text) {
        return new Response("missing fields", { status: 400 });
      }
      await tg(env, "sendMessage", { chat_id: chat_id || env.TELEGRAM_CHAT_ID, text });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/retention/report") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { report, chat_id } = body;
      if (!report) {
        return new Response("missing fields", { status: 400 });
      }
      await tg(env, "sendMessage", { chat_id: chat_id || env.TELEGRAM_CHAT_ID, text: report });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/trending/report") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { report, chat_id } = body;
      if (!report) {
        return new Response("missing fields", { status: 400 });
      }
      await tg(env, "sendMessage", {
        chat_id: chat_id || env.TELEGRAM_CHAT_ID,
        text: `\u{1F52D} Trending story scan:

${report}`
      });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/batch/hookmissing") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { day, run_id, run_url, reason, chat_id } = body;
      if (!day || !run_id) {
        return new Response("missing fields", { status: 400 });
      }
      await env.PENDING.put(`hookdecision:${run_id}`, "pending", { expirationTtl: 2 * 3600 });
      await tg(env, "sendMessage", {
        chat_id: chat_id || env.TELEGRAM_CHAT_ID,
        text: `\u26A0\uFE0F Day ${day} has no hook video (${reason}). Publish hookless with a static still, or stop the run?
${run_url}

No answer in 15 min defaults to STOP.`,
        reply_markup: hookGateKeyboard(run_id)
      });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "GET" && url.pathname === "/batch/hookdecision") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const runId = url.searchParams.get("run_id");
      const decision = runId && await env.PENDING.get(`hookdecision:${runId}`) || "pending";
      return new Response(JSON.stringify({ decision }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }
    if (request.method === "POST" && url.pathname === "/batch/failed") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { day, job, step, run_url, chat_id } = body;
      if (!day || !job) {
        return new Response("missing fields", { status: 400 });
      }
      await tg(env, "sendMessage", {
        chat_id: chat_id || env.TELEGRAM_CHAT_ID,
        text: `\u274C Day ${day}'s "${job}" job failed at step "${step || "unknown"}".
${run_url || ""}`
      });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/batch/pregen_done") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { new_days_done, through_day, batch_complete, chat_id } = body;
      const text = batch_complete ? `\u{1F389} All 30 days generated! Batch pregen is fully complete through day ${through_day}. Use /day <N> to pull a still + prompt for Google Flow whenever you're ready.` : `\u{1F4E6} Pregen chunk done: ${new_days_done} new day(s) generated, through day ${through_day}. Next chunk auto-starting -- I'll message you again once that finishes. Use /day <N> anytime to pull a still + prompt for Google Flow.`;
      await tg(env, "sendMessage", { chat_id: chat_id || env.TELEGRAM_CHAT_ID, text });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/short/ready") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { day, case: caseName } = body;
      if (!day) {
        return new Response("missing fields", { status: 400 });
      }
      const chatId = env.TELEGRAM_CHAT_ID;
      const dd = String(day).padStart(2, "0");
      try {
        const meta = await (await ghRaw(env, `_pipeline/batch/day${dd}/meta.json`)).json();
        const shot1Url = await hookStillUrl(env, dd);
        const deadline = Date.now() + 5 * 3600 * 1e3;
        await env.PENDING.put(`awaiting_short_hook:${chatId}`, JSON.stringify({ day: String(day), deadline }), { expirationTtl: 8 * 3600 });
        await sendHookStill(env, chatId, shot1Url, `Day ${dd}: "${meta.title_working}"${caseName ? ` (${caseName})` : ""}

Motion prompt for Google Flow:
${meta.hook_motion_prompt}

Reply here with the finished Flow video within 5 hours, or I'll fall back to a static cut and schedule it for tomorrow 05:15 IST.`);
      } catch (e) {
        await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Day ${dd} generated but I couldn't send the hook-video request: ${e.message}. Use /day ${day} to retry manually.` });
      }
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/short/sweep") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      await sweepExpiredHookWaits(env);
      return new Response("ok", { status: 200 });
    }
    if (request.method !== "POST") {
      return new Response("Shadow Gasp comic-pipeline bot is running.", { status: 200 });
    }
    let update;
    try {
      update = await request.json();
    } catch {
      return new Response("bad request", { status: 400 });
    }
    if (update.message) {
      try {
        await handleMessage(env, update.message);
      } catch (e) {
        console.error(e);
      }
    }
    if (update.callback_query) {
      try {
        await handleCallback(env, update.callback_query);
      } catch (e) {
        console.error(e);
      }
    }
    return new Response("ok", { status: 200 });
  }
};
export {
  worker_default as default
};
//# sourceMappingURL=DEPLOYED_BUNDLE.js.map
