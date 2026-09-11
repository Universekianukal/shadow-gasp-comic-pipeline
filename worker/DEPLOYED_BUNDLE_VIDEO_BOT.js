var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// DEPLOYED_BUNDLE.js
var __defProp2 = Object.defineProperty;
var __name2 = /* @__PURE__ */ __name((target, value) => __defProp2(target, "name", { value, configurable: true }), "__name");
var __defProp22 = Object.defineProperty;
var __name22 = /* @__PURE__ */ __name2((target, value) => __defProp22(target, "name", { value, configurable: true }), "__name");
var __defProp222 = Object.defineProperty;
var __name222 = /* @__PURE__ */ __name22((target, value) => __defProp222(target, "name", { value, configurable: true }), "__name");
var __defProp2222 = Object.defineProperty;
var __name2222 = /* @__PURE__ */ __name222((target, value) => __defProp2222(target, "name", { value, configurable: true }), "__name");
var __defProp22222 = Object.defineProperty;
var __name22222 = /* @__PURE__ */ __name2222((target, value) => __defProp22222(target, "name", { value, configurable: true }), "__name");
var __defProp222222 = Object.defineProperty;
var __name222222 = /* @__PURE__ */ __name22222((target, value) => __defProp222222(target, "name", { value, configurable: true }), "__name");
var GITHUB_REPO = "Universekianukal/shadow-gasp-comic-pipeline";
var VIDEO_REPO = "Universekianukal/shadow-gasp-pipeline";
var KAGGLE_SLOTS = [["IMAGE", "anuragmishra108"], ["VIDEO", "kianukal"], ["MAHADEVI", "mahadevi108"]];
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
    if (chatId && method === "sendMessage") {
      try {
        await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: chatId,
            text: `\u26A0\uFE0F A reply could not be delivered: ${body.description || body.error_code || "unknown"}`.slice(0, 300)
          })
        });
      } catch (e) {
      }
    }
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
__name2222(tg, "tg");
__name22222(tg, "tg");
__name222222(tg, "tg");
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
__name2222(dispatchAction, "dispatchAction");
__name22222(dispatchAction, "dispatchAction");
__name222222(dispatchAction, "dispatchAction");
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
__name2222(dispatchPipeline, "dispatchPipeline");
__name22222(dispatchPipeline, "dispatchPipeline");
__name222222(dispatchPipeline, "dispatchPipeline");
async function dispatchPostPromo(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/post_promo.yml/dispatches`,
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
__name(dispatchPostPromo, "dispatchPostPromo");
__name2(dispatchPostPromo, "dispatchPostPromo");
__name22(dispatchPostPromo, "dispatchPostPromo");
async function gumroadProducts(env) {
  const r = await fetch(
    `https://api.gumroad.com/v2/products?access_token=${encodeURIComponent(env.GUMROAD_ACCESS_TOKEN || "")}`,
    { headers: { "User-Agent": "shadow-gasp-bot" } }
  );
  if (!r.ok) throw new Error(`Gumroad list failed: ${r.status}`);
  const j = await r.json();
  return (j.products || []).filter((p) => p.published);
}
__name(gumroadProducts, "gumroadProducts");
__name2(gumroadProducts, "gumroadProducts");
__name22(gumroadProducts, "gumroadProducts");
async function promoPosted(env) {
  try {
    const r = await fetch(
      `https://api.github.com/repos/${GITHUB_REPO}/contents/promo?ref=main`,
      { headers: ghHeaders(env) }
    );
    if (!r.ok) return /* @__PURE__ */ new Set();
    const files = await r.json();
    return new Set((Array.isArray(files) ? files : []).filter((f) => f.name && f.name.endsWith(".json")).map((f) => f.name.replace(/\.json$/, "")));
  } catch (e) {
    return /* @__PURE__ */ new Set();
  }
}
__name(promoPosted, "promoPosted");
__name2(promoPosted, "promoPosted");
__name22(promoPosted, "promoPosted");
var REGISTRY_PATH = "issues.json";
var KAGGLE_ACCOUNTS_FALLBACK = "-:anuragmishra108,B:mahadevi108,C:kianukal";
function caseSlug(name) {
  return String(name || "").toLowerCase().replace(/ /g, "-").replace(/[^a-z0-9-]/g, "").slice(0, 40);
}
__name(caseSlug, "caseSlug");
__name2(caseSlug, "caseSlug");
__name22(caseSlug, "caseSlug");
function b64decode(s) {
  const bin = atob(String(s).replace(/\s/g, ""));
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
}
__name(b64decode, "b64decode");
__name2(b64decode, "b64decode");
__name22(b64decode, "b64decode");
function b64encode(text) {
  const bytes = new TextEncoder().encode(text);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}
__name(b64encode, "b64encode");
__name2(b64encode, "b64encode");
__name22(b64encode, "b64encode");
function ghHeaders(env) {
  return {
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    Accept: "application/vnd.github+json",
    "Content-Type": "application/json",
    "User-Agent": "shadow-gasp-bot"
  };
}
__name(ghHeaders, "ghHeaders");
__name2(ghHeaders, "ghHeaders");
__name22(ghHeaders, "ghHeaders");
function parseKaggleAccounts(s) {
  return String(s || "").split(",").map((p) => p.split(":")).filter((p) => p.length === 2 && p[0].trim() && p[1].trim()).map((p) => ({ slot: p[0].trim(), handle: p[1].trim() }));
}
__name(parseKaggleAccounts, "parseKaggleAccounts");
__name2(parseKaggleAccounts, "parseKaggleAccounts");
__name22(parseKaggleAccounts, "parseKaggleAccounts");
async function kaggleAccounts(env) {
  try {
    const r = await fetch(
      `https://api.github.com/repos/${GITHUB_REPO}/actions/variables/KAGGLE_ACCOUNTS`,
      { headers: ghHeaders(env) }
    );
    if (r.ok) {
      const j = await r.json();
      const parsed = parseKaggleAccounts(j && j.value);
      if (parsed.length) return parsed;
    }
  } catch (e) {
    console.log(`kaggleAccounts: ${e.message}`);
  }
  return parseKaggleAccounts(KAGGLE_ACCOUNTS_FALLBACK);
}
__name(kaggleAccounts, "kaggleAccounts");
__name2(kaggleAccounts, "kaggleAccounts");
__name22(kaggleAccounts, "kaggleAccounts");
async function readRegistry(env) {
  const r = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/contents/${REGISTRY_PATH}?ref=main`,
    { headers: ghHeaders(env) }
  );
  if (!r.ok) return null;
  const j = await r.json();
  let data;
  try {
    data = JSON.parse(b64decode(j.content));
  } catch (e) {
    return null;
  }
  if (!data || typeof data !== "object") return null;
  data.issues = data.issues || {};
  data.kaggle = data.kaggle || {};
  return { data, sha: j.sha };
}
__name(readRegistry, "readRegistry");
__name2(readRegistry, "readRegistry");
__name22(readRegistry, "readRegistry");
async function peekCase(env, caseName) {
  const cur = await readRegistry(env);
  if (!cur) return null;
  const slug = caseSlug(caseName);
  return {
    slug,
    issue: cur.data.issues[slug],
    slot: cur.data.kaggle[slug]
  };
}
__name(peekCase, "peekCase");
__name2(peekCase, "peekCase");
__name22(peekCase, "peekCase");
async function reserveCase(env, caseName, wantSlot) {
  const slug = caseSlug(caseName);
  for (let attempt = 0; attempt < 3; attempt++) {
    const cur = await readRegistry(env);
    if (!cur) return { error: "could not read issues.json" };
    const issues = cur.data.issues;
    const kaggle = cur.data.kaggle;
    const haveIssue = Object.prototype.hasOwnProperty.call(issues, slug);
    const havePin = Object.prototype.hasOwnProperty.call(kaggle, slug);
    const slot = havePin ? kaggle[slug] : wantSlot || "-";
    const nums = Object.values(issues).filter((n) => typeof n === "number");
    const issue = haveIssue ? issues[slug] : (nums.length ? Math.max.apply(null, nums) : 0) + 1;
    if (haveIssue && havePin) return { issue, slot, pinned: true };
    issues[slug] = issue;
    kaggle[slug] = slot;
    const out = {};
    for (const k of Object.keys(cur.data).sort()) out[k] = cur.data[k];
    const si = {};
    for (const k of Object.keys(issues).sort()) si[k] = issues[k];
    const sk = {};
    for (const k of Object.keys(kaggle).sort()) sk[k] = kaggle[k];
    out.issues = si;
    out.kaggle = sk;
    const put = await fetch(
      `https://api.github.com/repos/${GITHUB_REPO}/contents/${REGISTRY_PATH}`,
      {
        method: "PUT",
        headers: ghHeaders(env),
        body: JSON.stringify({
          message: `reserve #${String(issue).padStart(2, "0")} for ${slug} (kaggle ${slot})`,
          content: b64encode(JSON.stringify(out, null, 2)),
          sha: cur.sha,
          branch: "main"
        })
      }
    );
    if (put.ok) return { issue, slot, pinned: havePin };
    if (put.status !== 409 && put.status !== 422) {
      return { error: `${put.status} ${(await put.text()).slice(0, 120)}` };
    }
  }
  return { error: "issues.json kept changing underneath the reservation" };
}
__name(reserveCase, "reserveCase");
__name2(reserveCase, "reserveCase");
__name22(reserveCase, "reserveCase");
async function dispatchFunnelComicLink(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${VIDEO_REPO}/actions/workflows/funnel_comic_link.yml/dispatches`,
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
__name(dispatchFunnelComicLink, "dispatchFunnelComicLink");
__name2(dispatchFunnelComicLink, "dispatchFunnelComicLink");
__name22(dispatchFunnelComicLink, "dispatchFunnelComicLink");
__name222(dispatchFunnelComicLink, "dispatchFunnelComicLink");
__name2222(dispatchFunnelComicLink, "dispatchFunnelComicLink");
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
__name2222(dispatchGenCode, "dispatchGenCode");
__name22222(dispatchGenCode, "dispatchGenCode");
__name222222(dispatchGenCode, "dispatchGenCode");
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
__name2222(dispatchVideoPipeline, "dispatchVideoPipeline");
__name22222(dispatchVideoPipeline, "dispatchVideoPipeline");
__name222222(dispatchVideoPipeline, "dispatchVideoPipeline");
var sleep = /* @__PURE__ */ __name222222((ms) => new Promise((resolve) => setTimeout(resolve, ms)), "sleep");
async function dispatchWorkflowVerified(env, workflowFile, inputs) {
  const dispatchOnce = /* @__PURE__ */ __name222222(async () => {
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
  const runAppeared = /* @__PURE__ */ __name222222(async (afterMs) => {
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
__name2222(dispatchWorkflowVerified, "dispatchWorkflowVerified");
__name22222(dispatchWorkflowVerified, "dispatchWorkflowVerified");
__name222222(dispatchWorkflowVerified, "dispatchWorkflowVerified");
async function dispatchFinishBatchDay(env, inputs) {
  return dispatchWorkflowVerified(env, "finish_batch_day.yml", inputs);
}
__name(dispatchFinishBatchDay, "dispatchFinishBatchDay");
__name2(dispatchFinishBatchDay, "dispatchFinishBatchDay");
__name22(dispatchFinishBatchDay, "dispatchFinishBatchDay");
__name222(dispatchFinishBatchDay, "dispatchFinishBatchDay");
__name2222(dispatchFinishBatchDay, "dispatchFinishBatchDay");
__name22222(dispatchFinishBatchDay, "dispatchFinishBatchDay");
__name222222(dispatchFinishBatchDay, "dispatchFinishBatchDay");
async function dispatchBatchPregen(env, inputs) {
  return dispatchWorkflowVerified(env, "batch_pregen.yml", inputs);
}
__name(dispatchBatchPregen, "dispatchBatchPregen");
__name2(dispatchBatchPregen, "dispatchBatchPregen");
__name22(dispatchBatchPregen, "dispatchBatchPregen");
__name222(dispatchBatchPregen, "dispatchBatchPregen");
__name2222(dispatchBatchPregen, "dispatchBatchPregen");
__name22222(dispatchBatchPregen, "dispatchBatchPregen");
__name222222(dispatchBatchPregen, "dispatchBatchPregen");
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
__name2222(pregenKeyboard, "pregenKeyboard");
__name22222(pregenKeyboard, "pregenKeyboard");
__name222222(pregenKeyboard, "pregenKeyboard");
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
__name2222(ghRaw, "ghRaw");
__name22222(ghRaw, "ghRaw");
__name222222(ghRaw, "ghRaw");
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
__name222(hookStillUrl, "hookStillUrl");
__name2222(hookStillUrl, "hookStillUrl");
__name22222(hookStillUrl, "hookStillUrl");
async function dayPublishState(env, dayNum) {
  let entry = null;
  try {
    const st = await (await ghRaw(env, "_pipeline/batch/state.json")).json();
    entry = st && st.days && st.days[String(dayNum)] || null;
  } catch (err) {
    return null;
  }
  if (!entry) return null;
  let queueStatus = null;
  try {
    const q = await (await ghRaw(env, "_pipeline/batch/queue.json")).json();
    const qe = q && q[String(dayNum)];
    queueStatus = qe && qe.status || null;
  } catch (err) {
    queueStatus = null;
  }
  if (queueStatus && queueStatus !== "published") return null;
  if (queueStatus === "published") return { ...entry, queueStatus };
  try {
    const led = await (await ghRaw(env, "_pipeline/cases_used.json")).json();
    const hit = (led.cases || []).find((c) => c && c.case === entry.case && c.videoId);
    if (hit) return { ...entry, videoId: hit.videoId, publishedAt: hit.publishedAt, queueStatus };
  } catch (err) {
  }
  return null;
}
__name(dayPublishState, "dayPublishState");
__name2(dayPublishState, "dayPublishState");
__name22(dayPublishState, "dayPublishState");
__name222(dayPublishState, "dayPublishState");
__name2222(dayPublishState, "dayPublishState");
__name22222(dayPublishState, "dayPublishState");
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
__name222(sendHookStill, "sendHookStill");
__name2222(sendHookStill, "sendHookStill");
__name22222(sendHookStill, "sendHookStill");
__name222222(hookStillUrl, "hookStillUrl");
async function dispatchCrosspostDecision(env, inputs) {
  return dispatchWorkflowVerified(env, "crosspost_decision.yml", inputs);
}
__name(dispatchCrosspostDecision, "dispatchCrosspostDecision");
__name2(dispatchCrosspostDecision, "dispatchCrosspostDecision");
__name22(dispatchCrosspostDecision, "dispatchCrosspostDecision");
__name222(dispatchCrosspostDecision, "dispatchCrosspostDecision");
__name2222(dispatchCrosspostDecision, "dispatchCrosspostDecision");
__name22222(dispatchCrosspostDecision, "dispatchCrosspostDecision");
__name222222(dispatchCrosspostDecision, "dispatchCrosspostDecision");
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
      ],
      [
        { text: "⏰ FB: Schedule", callback_data: `fbsch:${day}` },
        { text: "⏰ IG: Schedule", callback_data: `igsch:${day}` }
      ]
    ]
  };
}
__name(fbIgDecisionKeyboard, "fbIgDecisionKeyboard");
__name2(fbIgDecisionKeyboard, "fbIgDecisionKeyboard");
__name22(fbIgDecisionKeyboard, "fbIgDecisionKeyboard");
__name222(fbIgDecisionKeyboard, "fbIgDecisionKeyboard");
__name2222(fbIgDecisionKeyboard, "fbIgDecisionKeyboard");
__name22222(fbIgDecisionKeyboard, "fbIgDecisionKeyboard");
__name222222(fbIgDecisionKeyboard, "fbIgDecisionKeyboard");
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
__name2222(dispatchGenerateTitleVariant, "dispatchGenerateTitleVariant");
__name22222(dispatchGenerateTitleVariant, "dispatchGenerateTitleVariant");
__name222222(dispatchGenerateTitleVariant, "dispatchGenerateTitleVariant");
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
__name2222(dispatchRetitlePublished, "dispatchRetitlePublished");
__name22222(dispatchRetitlePublished, "dispatchRetitlePublished");
__name222222(dispatchRetitlePublished, "dispatchRetitlePublished");
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
__name2222(titleStyleKeyboard, "titleStyleKeyboard");
__name22222(titleStyleKeyboard, "titleStyleKeyboard");
__name222222(titleStyleKeyboard, "titleStyleKeyboard");
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
__name2222(titleDraftKeyboard, "titleDraftKeyboard");
__name22222(titleDraftKeyboard, "titleDraftKeyboard");
__name222222(titleDraftKeyboard, "titleDraftKeyboard");
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
__name2222(getCurrentTitle, "getCurrentTitle");
__name22222(getCurrentTitle, "getCurrentTitle");
__name222222(getCurrentTitle, "getCurrentTitle");
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
__name2222(commitTitleOverride, "commitTitleOverride");
__name22222(commitTitleOverride, "commitTitleOverride");
__name222222(commitTitleOverride, "commitTitleOverride");
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
__name2222(commitHookVideo, "commitHookVideo");
__name22222(commitHookVideo, "commitHookVideo");
__name222222(commitHookVideo, "commitHookVideo");
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
__name2222(queueDayForScheduledPublish, "queueDayForScheduledPublish");
__name22222(queueDayForScheduledPublish, "queueDayForScheduledPublish");
__name222222(queueDayForScheduledPublish, "queueDayForScheduledPublish");
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
__name2222(describeNextIST, "describeNextIST");
__name22222(describeNextIST, "describeNextIST");
__name222222(describeNextIST, "describeNextIST");
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
__name2222(nextDayFiveFifteenIST, "nextDayFiveFifteenIST");
__name22222(nextDayFiveFifteenIST, "nextDayFiveFifteenIST");
__name222222(nextDayFiveFifteenIST, "nextDayFiveFifteenIST");
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
__name2222(istTimeToPublishAt, "istTimeToPublishAt");
__name22222(istTimeToPublishAt, "istTimeToPublishAt");
__name222222(istTimeToPublishAt, "istTimeToPublishAt");
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
__name2222(istDateTimeToPublishAt, "istDateTimeToPublishAt");
__name22222(istDateTimeToPublishAt, "istDateTimeToPublishAt");
__name222222(istDateTimeToPublishAt, "istDateTimeToPublishAt");
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
__name2222(hookGateKeyboard, "hookGateKeyboard");
__name22222(hookGateKeyboard, "hookGateKeyboard");
__name222222(hookGateKeyboard, "hookGateKeyboard");
function approvalKeyboard(token, videoId) {
  const rows = [[
    { text: "\u2705 Approve", callback_data: `approve:${token}` },
    { text: "\u274C Reject", callback_data: `reject:${token}` },
    { text: "\u{1F4C4} Increase Pages", callback_data: `pages_menu:${token}` }
  ]];
  if (videoId) {
    rows.push([{ text: "\u{1F517} Funnel to YouTube", callback_data: `funnel:${token}` }]);
  }
  return { inline_keyboard: rows };
}
__name(approvalKeyboard, "approvalKeyboard");
__name2(approvalKeyboard, "approvalKeyboard");
__name22(approvalKeyboard, "approvalKeyboard");
__name222(approvalKeyboard, "approvalKeyboard");
__name2222(approvalKeyboard, "approvalKeyboard");
__name22222(approvalKeyboard, "approvalKeyboard");
__name222222(approvalKeyboard, "approvalKeyboard");
var PAGE_PRICE_TIERS = { 20: "0", 25: "19", 35: "24", 50: "29", 75: "39", 100: "49" };
function priceLabel(n) {
  return PAGE_PRICE_TIERS[n] === "0" ? `${n}pp (FREE)` : `${n}pp ($${PAGE_PRICE_TIERS[n]})`;
}
__name(priceLabel, "priceLabel");
__name2(priceLabel, "priceLabel");
__name22(priceLabel, "priceLabel");
__name222(priceLabel, "priceLabel");
__name2222(priceLabel, "priceLabel");
__name22222(priceLabel, "priceLabel");
__name222222(priceLabel, "priceLabel");
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
__name2222(makePageCountKeyboard, "makePageCountKeyboard");
__name22222(makePageCountKeyboard, "makePageCountKeyboard");
__name222222(makePageCountKeyboard, "makePageCountKeyboard");
var STYLE_BUTTONS = [
  ["cinematic", "\u{1F3AC}"],
  ["mosaic", "\u{1F9E9}"],
  ["classic", "\u{1F4D6}"],
  ["chamber", "\u{1F512}"],
  ["staccato", "\u26A1"],
  ["documentary", "\u{1F4C1}"]
];
function makeStyleKeyboard() {
  const btn = /* @__PURE__ */ __name2222(([name, icon]) => ({ text: `${icon} ${name}`, callback_data: `make_style:${name}` }), "btn");
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
__name2222(makeStyleKeyboard, "makeStyleKeyboard");
__name22222(makeStyleKeyboard, "makeStyleKeyboard");
__name222222(makeStyleKeyboard, "makeStyleKeyboard");
var PAGE_QUESTION = `How many pages?

25 \u2014 ~41pp delivered, $${PAGE_PRICE_TIERS[35]} tier
35 \u2014 ~50-55pp, $${PAGE_PRICE_TIERS[50]} tier (the usual choice)
50 \u2014 bigger book, roughly double the art time, $${PAGE_PRICE_TIERS[75]} tier
75 \u2014 the largest that has built cleanly, $${PAGE_PRICE_TIERS[100]} tier`;
function pagesKeyboard(token, idx, slot) {
  return { inline_keyboard: [[25, 35, 50, 75].map((n) => ({
    text: String(n),
    callback_data: `tpag:${token}:${idx}|${slot}|${n}`
  }))] };
}
__name(pagesKeyboard, "pagesKeyboard");
__name2(pagesKeyboard, "pagesKeyboard");
__name22(pagesKeyboard, "pagesKeyboard");
function topicStyleKeyboard(token, idx, slot, pages) {
  const btn = /* @__PURE__ */ __name22(([name, icon]) => ({
    text: `${icon} ${name}`,
    callback_data: `topicgo:${token}:${idx}|${slot}|${pages}|${name}`
  }), "btn");
  return {
    inline_keyboard: [
      STYLE_BUTTONS.slice(0, 3).map(btn),
      STYLE_BUTTONS.slice(3).map(btn),
      [{ text: "\u{1F3B2} Auto (from case name)", callback_data: `topicgo:${token}:${idx}|${slot}|${pages}|auto` }]
    ]
  };
}
__name(topicStyleKeyboard, "topicStyleKeyboard");
__name2(topicStyleKeyboard, "topicStyleKeyboard");
__name22(topicStyleKeyboard, "topicStyleKeyboard");
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
__name2222(pageCountKeyboard, "pageCountKeyboard");
__name22222(pageCountKeyboard, "pageCountKeyboard");
__name222222(pageCountKeyboard, "pageCountKeyboard");
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
__name2222(confirmPublishKeyboard, "confirmPublishKeyboard");
__name22222(confirmPublishKeyboard, "confirmPublishKeyboard");
__name222222(confirmPublishKeyboard, "confirmPublishKeyboard");
var RAW_COMIC = "https://raw.githubusercontent.com/Universekianukal/shadow-gasp-comic-pipeline/main";
var RAW_VIDEO = "https://raw.githubusercontent.com/Universekianukal/shadow-gasp-pipeline/main";
var TOPICS_PER_PAGE = 8;
function normCase(s) {
  return (s || "").normalize("NFKD").replace(/[^\p{L}\p{N}]+/gu, " ").trim().toLowerCase();
}
__name(normCase, "normCase");
__name2(normCase, "normCase");
__name22(normCase, "normCase");
async function loadTopics(env) {
  const [comicR, videoR, stR] = await Promise.all([
    fetch(`${RAW_COMIC}/cases_used.json`, { headers: { "User-Agent": "shadow-gasp-bot" } }),
    fetch(`${RAW_VIDEO}/_pipeline/cases_used.json`, { headers: { "User-Agent": "shadow-gasp-bot" } }),
    fetch(`${RAW_VIDEO}/_pipeline/batch/state.json`, { headers: { "User-Agent": "shadow-gasp-bot" } })
  ]);
  if (!videoR.ok) throw new Error(`video ledger fetch ${videoR.status}`);
  const cases = (await videoR.json()).cases || [];
  let drawn = /* @__PURE__ */ new Set();
  if (comicR.ok) {
    const comicCases = (await comicR.json()).cases || [];
    drawn = new Set(comicCases.filter((c) => c.comicAt).map((c) => normCase(c.case)));
  }
  const doneRecords = [];
  try {
    const recs = await env.PENDING.list({ prefix: "comic:" });
    for (const k of recs.keys) {
      const raw = await env.PENDING.get(k.name);
      if (!raw) continue;
      const rec = JSON.parse(raw);
      doneRecords.push(rec);
      if (rec.case) drawn.add(normCase(rec.case));
    }
  } catch (e) {
  }
  const published = new Set(cases.filter((c) => c.videoId).map((c) => normCase(c.case)));
  const upcoming = [];
  if (stR.ok) {
    const days = (await stR.json()).days || {};
    const nums = Object.keys(days).map(Number).sort((a, b) => a - b);
    let frontier = 0;
    for (const n of nums) if (published.has(normCase(days[String(n)].case))) frontier = n;
    for (const n of nums) {
      const d = days[String(n)];
      const k = normCase(d.case);
      if (!d.done || published.has(k) || drawn.has(k) || n <= frontier) continue;
      upcoming.push({ label: `day ${n}`, case: d.case });
    }
  }
  let carried = "";
  const sortKey = /* @__PURE__ */ new Map();
  for (const c of cases) {
    if (c.publishedAt) carried = c.publishedAt;
    sortKey.set(c, c.publishedAt || carried);
  }
  const backlog = cases.filter((c) => c.videoId && !drawn.has(normCase(c.case))).sort((a, b) => (sortKey.get(b) || "").localeCompare(sortKey.get(a) || "")).map((c) => ({
    label: c.publishedAt ? c.publishedAt.slice(0, 10) : sortKey.get(c) ? `~${sortKey.get(c).slice(0, 10)}` : "undated",
    case: c.case
  }));
  const done = doneRecords.filter((c) => c.linked_at).map((c) => ({
    label: c.issue ? `#${c.issue}` : "linked",
    case: `${c.title || c.case} \u2192 youtu.be/${c.video_id || "?"}`
  }));
  return { upcoming, backlog, done };
}
__name(loadTopics, "loadTopics");
__name2(loadTopics, "loadTopics");
__name22(loadTopics, "loadTopics");
async function sendTopicsPage(env, chatId, kind, page, messageId) {
  let lists;
  try {
    lists = await loadTopics(env);
  } catch (e) {
    await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't load the topic lists: ${e.message}` });
    return;
  }
  const items = kind === "up" ? lists.upcoming : kind === "dn" ? lists.done : lists.backlog;
  if (!items.length) {
    const blank = kind === "up" ? "No upcoming days are waiting for a comic." : kind === "dn" ? "No comic is linked to its short yet." : "Every published short already has a comic.";
    await tg(env, "sendMessage", { chat_id: chatId, text: blank });
    return;
  }
  const pages = Math.ceil(items.length / TOPICS_PER_PAGE);
  page = Math.max(0, Math.min(page, pages - 1));
  const slice = items.slice(page * TOPICS_PER_PAGE, (page + 1) * TOPICS_PER_PAGE);
  const token = Math.random().toString(36).slice(2, 10);
  await env.PENDING.put(`topics:${token}`, JSON.stringify(slice.map((x) => x.case)), { expirationTtl: 86400 });
  const rows = kind === "dn" ? [] : slice.map((x, i) => [{
    text: `${i + 1}. ${x.label} \xB7 ${x.case.length > 38 ? x.case.slice(0, 37) + "\u2026" : x.case}`,
    callback_data: `topic:${token}:${i}`
  }]);
  const pageNav = [];
  if (page > 0) pageNav.push({ text: `\u2039 page ${page}`, callback_data: `topicpg:${kind}:${page - 1}` });
  if (page < pages - 1) pageNav.push({ text: `page ${page + 2} \u203A`, callback_data: `topicpg:${kind}:${page + 1}` });
  const listNav = [];
  for (const nk of [
    ["up", "upcoming", lists.upcoming.length],
    ["bk", "backlog", lists.backlog.length],
    ["dn", "completed", lists.done.length]
  ]) {
    if (nk[0] !== kind) listNav.push({ text: `${nk[1]} (${nk[2]})`, callback_data: `topicpg:${nk[0]}:0` });
  }
  if (pageNav.length) rows.push(pageNav);
  if (listNav.length) rows.push(listNav);
  const head = kind === "up" ? `\u{1F680} UPCOMING shorts \u2014 not published yet, so the comic lands with the launch. ${items.length} waiting.` : kind === "dn" ? `\u2705 COMPLETED \u2014 comic built AND linked into its short's description. ${items.length} done.` : `\u{1F4DA} BACKLOG \u2014 published shorts with no comic yet. ${items.length} waiting, newest first.`;
  const listing = "\n\n" + slice.map((x, i) => `${kind === "dn" ? "" : `${i + 1}. `}${x.label} \xB7 ${x.case}`).join("\n");
  const body = `${head}
Page ${page + 1}/${pages}.` + (kind === "dn" ? " Nothing to do here \u2014 these are already earning." : " Tap one to choose its page count.") + listing;
  const params = { chat_id: chatId, text: body, reply_markup: { inline_keyboard: rows } };
  if (messageId) await tg(env, "editMessageText", { ...params, message_id: messageId });
  else await tg(env, "sendMessage", params);
}
__name(sendTopicsPage, "sendTopicsPage");
__name2(sendTopicsPage, "sendTopicsPage");
__name22(sendTopicsPage, "sendTopicsPage");
var RAW_VIDEO_LEDGER = "https://raw.githubusercontent.com/Universekianukal/shadow-gasp-pipeline/main/_pipeline/cases_used.json";
function caseHead(name) {
  let head = (name || "").split("/")[0].replace(/\(.*?\)/g, "");
  return head.replace(/\s+/g, " ").trim().toLowerCase();
}
__name(caseHead, "caseHead");
__name2(caseHead, "caseHead");
__name22(caseHead, "caseHead");
var _ledgerCache = null;
async function ledgerCases() {
  if (_ledgerCache) return _ledgerCache;
  const r = await fetch(RAW_VIDEO_LEDGER, { headers: { "User-Agent": "shadow-gasp-bot" } });
  if (!r.ok) throw new Error(`ledger fetch ${r.status}`);
  _ledgerCache = (await r.json()).cases || [];
  return _ledgerCache;
}
__name(ledgerCases, "ledgerCases");
__name2(ledgerCases, "ledgerCases");
__name22(ledgerCases, "ledgerCases");
async function resolveShort(rec) {
  if (rec && rec.video_id) return rec.video_id;
  const name = rec && (rec.case || rec.title) || "";
  if (!name) return "";
  try {
    const cases = await ledgerCases();
    const want = caseHead(name);
    const hits = cases.filter((c) => c.videoId && ((c.case || "").trim().toLowerCase() === name.trim().toLowerCase() || caseHead(c.case) === want));
    if (!hits.length) return "";
    hits.sort((a, b) => (b.publishedAt || "").localeCompare(a.publishedAt || ""));
    return hits[0].videoId || "";
  } catch (e) {
    return "";
  }
}
__name(resolveShort, "resolveShort");
__name2(resolveShort, "resolveShort");
__name22(resolveShort, "resolveShort");
async function caseOfVideo(videoId) {
  try {
    const cases = await ledgerCases();
    const hit = cases.find((c) => c.videoId === videoId);
    return hit ? hit.case : "";
  } catch (e) {
    return "";
  }
}
__name(caseOfVideo, "caseOfVideo");
__name2(caseOfVideo, "caseOfVideo");
__name22(caseOfVideo, "caseOfVideo");
async function funnelComic(env, chatId, caseId, videoIdOverride) {
  const raw = await env.PENDING.get("comic:" + caseId);
  if (!raw) {
    await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C I have no record for that comic any more." });
    return;
  }
  const c = JSON.parse(raw);
  const videoId = videoIdOverride || c.video_id || await resolveShort(c);
  if (!videoId) {
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: `\u274C No short found for "${c.title || c.case}" \u2014 its video is not published yet.`
    });
    return;
  }
  if (!c.product_url) {
    await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C No Gumroad URL recorded for that book." });
    return;
  }
  try {
    await dispatchFunnelComicLink(env, {
      video_id: videoId,
      product_url: c.product_url,
      product_name: c.title || c.case,
      pages: String(c.pages || ""),
      hook: c.hook || "",
      position: "top",
      notify_chat_id: String(chatId)
    });
  } catch (e) {
    await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start the funnel job: ${e.message}` });
    return;
  }
  await tg(env, "sendMessage", {
    chat_id: chatId,
    text: `\u{1F517} Linking ${c.title || c.case}
  \u2192 https://youtu.be/${videoId}
  ${c.product_url}
Result follows here.`
  });
}
__name(funnelComic, "funnelComic");
__name2(funnelComic, "funnelComic");
__name22(funnelComic, "funnelComic");
async function autoFunnelForCase(env, caseName, videoId, chatId) {
  if (!caseName || !videoId) return;
  try {
    const list = await env.PENDING.list({ prefix: "comic:" });
    const want = caseHead(caseName);
    for (const k of list.keys) {
      const raw = await env.PENDING.get(k.name);
      if (!raw) continue;
      const c = JSON.parse(raw);
      const name = c.case || c.title || "";
      if (!c.product_url || caseHead(name) !== want) continue;
      if (c.linked_at && c.video_id === videoId) return;
      await dispatchFunnelComicLink(env, {
        video_id: videoId,
        product_url: c.product_url,
        product_name: c.title || c.case,
        pages: String(c.pages || ""),
        hook: c.hook || "",
        position: "top",
        notify_chat_id: chatId ? String(chatId) : ""
      });
      return;
    }
  } catch (e) {
    console.log("autoFunnel failed (non-fatal): " + e.message);
  }
}
__name(autoFunnelForCase, "autoFunnelForCase");
__name2(autoFunnelForCase, "autoFunnelForCase");
__name22(autoFunnelForCase, "autoFunnelForCase");
var VIDEO_COMMANDS = ["/day", "/publish", "/short", "/title", "/cancel", "/pregen", "/retention", "/trending"];
var COMIC_COMMANDS = ["/make", "/regen", "/topics", "/gencode", "/freeclaims", "/links", "/promo", "/funnel"];
var VIDEO_ACTIONS = ["clip", "hk", "edittitle", "titlestyle", "title_apply", "title_discard", "title_regen", "title_retry", "fbdec", "igdec", "pregen", "fbsch", "igsch"];
var COMIC_ACTIONS = ["approve", "reject", "confirm_publish", "cancel_publish", "pages_menu", "set_pages", "make_pages", "make_style", "topic", "topicgo", "topicpg", "tpag", "promo", "promogo", "promono", "promopv", "funnel", "funnelc", "retry"];
function commandSurface(text) {
  const cmd = text.split(/[\s@]/)[0].toLowerCase();
  if (VIDEO_COMMANDS.includes(cmd)) return "video";
  if (COMIC_COMMANDS.includes(cmd)) return "comics";
  return "shared";
}
__name(commandSurface, "commandSurface");
function actionSurface(action) {
  if (VIDEO_ACTIONS.includes(action)) return "video";
  if (COMIC_ACTIONS.includes(action)) return "comics";
  return "shared";
}
__name(actionSurface, "actionSurface");
function botModeAllows(env, surface) {
  const mode = (env.BOT_MODE || "all").toLowerCase();
  if (mode === "all" || surface === "shared") return true;
  return mode === surface;
}
__name(botModeAllows, "botModeAllows");
function otherBotHint(env) {
  const mode = (env.BOT_MODE || "all").toLowerCase();
  return mode === "comics" ? "\u{1F4DA} This is the COMICS bot \u2014 it handles /make, /regen, /topics, /gencode, /freeclaims, /links, /promo, /funnel (plus shared /quota).\n\nVideo commands (/day, /publish, /short, /title\u2026) and hook clips go to the original Shadow Gasp bot." : "\u{1F3AC} This is the VIDEO bot \u2014 comic commands moved to the Shadow Gasp Comics bot.\n\nSend /make, /regen, /topics, /gencode, /freeclaims, /links, /promo or /funnel there instead.";
}
__name(otherBotHint, "otherBotHint");
async function handleCallback(env, cq) {
  const data = cq.data || "";
  const [action, token, extra] = data.split(":");
  const chatId = cq.message.chat.id;
  const messageId = cq.message.message_id;
  if (!botModeAllows(env, actionSurface(action))) {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Wrong bot for this button." });
    await tg(env, "sendMessage", { chat_id: chatId, text: otherBotHint(env) });
    return;
  }
  if (await schedHandleCallback(env, cq, action, token, extra)) return;
  if (action === "kag") {
    const day = token;
    const slot = extra;
    const handle = (KAGGLE_SLOTS.find((r) => r[0] === slot) || [slot, slot])[1];
    try {
      await dispatchWorkflowVerified(env, "backfill_stills.yml", { day: String(day), kaggle_account: slot });
      await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `Retrying day ${day} on ${handle}` });
      await tg(env, "editMessageReplyMarkup", { chat_id: chatId, message_id: messageId, reply_markup: { inline_keyboard: [] } });
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `\u{1F504} Day ${day}'s stills are being regenerated on ${handle} (slot ${slot}). ~25-35 min.`
      });
    } catch (e) {
      await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Dispatch failed" });
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Could not retry day ${day} on ${handle}: ${e.message}` });
    }
    return;
  }
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
  if (action === "funnelc") {
    await funnelComic(env, chatId, token, extra || "");
    return;
  }
  if (action === "promo" || action === "promogo") {
    const rawP = await env.PENDING.get(`promo:${token}`);
    if (!rawP) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C That promo list has expired \u2014 run /promo again." });
      return;
    }
    const item = JSON.parse(rawP)[parseInt(extra, 10)];
    if (!item) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C Couldn't resolve that comic \u2014 run /promo again." });
      return;
    }
    if (action === "promo") {
      await tg(env, "answerCallbackQuery", { callback_query_id: cq.id });
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `\u{1F4E2} ${item.n}
$${Math.round((item.pr || 0) / 100)}
${item.u}

Post where?`,
        reply_markup: { inline_keyboard: [[
          { text: "\u{1F4D8} Facebook", callback_data: `promopv:${token}:${extra}|fb` },
          { text: "\u{1F4F8} Instagram", callback_data: `promopv:${token}:${extra}|ig` }
        ]] }
      });
      return;
    }
    const [idxG, platG] = String(extra).split("|");
    const itemG = JSON.parse(rawP)[parseInt(idxG, 10)];
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Publishing..." });
    try {
      await dispatchPostPromo(env, {
        case: itemG && (itemG.c || itemG.n) || item.c || item.n,
        platform: platG === "ig" ? "ig" : "fb",
        mode: "post",
        force: "false"
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start the post: ${e.message}` });
      return;
    }
    await tg(env, "editMessageCaption", {
      chat_id: chatId,
      message_id: messageId,
      caption: `\u{1F4E2} Publishing to ${platG === "ig" ? "Instagram" : "Facebook"}\u2026
I'll confirm here when it lands.`
    });
    return;
  }
  if (action === "promopv") {
    const [idxV, platV] = String(extra).split("|");
    const rawV = await env.PENDING.get(`promo:${token}`);
    if (!rawV) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C That promo list has expired \u2014 run /promo again." });
      return;
    }
    const itemV = JSON.parse(rawV)[parseInt(idxV, 10)];
    if (!itemV) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C Couldn't resolve that comic \u2014 run /promo again." });
      return;
    }
    await env.PENDING.put(`promodraft:${token}`, JSON.stringify({ token, idx: idxV }), { expirationTtl: 86400 });
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Building the draft\u2026" });
    try {
      await dispatchPostPromo(env, {
        case: itemV.c || itemV.n,
        platform: platV === "ig" ? "ig" : "fb",
        mode: "preview",
        force: "false"
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't build the draft: ${e.message}` });
      return;
    }
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `\u{1F5BC} Building the ${platV === "ig" ? "Instagram" : "Facebook"} draft for "${itemV.n}" \u2014 the image and caption land here in about a minute.`
    });
    return;
  }
  if (action === "promono") {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Cancelled" });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: "\u2716 Cancelled \u2014 nothing was posted."
    });
    return;
  }
  if (action === "topicpg") {
    await sendTopicsPage(env, chatId, token, parseInt(extra, 10) || 0, cq.message && cq.message.message_id);
    return;
  }
  if (action === "topic") {
    const raw2 = await env.PENDING.get(`topics:${token}`);
    if (!raw2) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C That topic list has expired \u2014 run /topics again." });
      return;
    }
    const picked = JSON.parse(raw2)[parseInt(extra, 10)];
    if (!picked) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C Couldn't resolve that topic \u2014 run /topics again." });
      return;
    }
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id });
    const known = await peekCase(env, picked);
    if (known && known.slot) {
      const accts2 = await kaggleAccounts(env);
      const hit = accts2.find((a) => a.slot === known.slot);
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `\u{1F4D6} ${picked}

\u{1F512} Kaggle: ${hit ? hit.handle : known.slot} \u2014 fixed, this book's art is already there` + (known.issue ? `
\u{1F516} Issue #${String(known.issue).padStart(2, "0")}` : "") + `

${PAGE_QUESTION}`,
        reply_markup: pagesKeyboard(token, extra, known.slot)
      });
      return;
    }
    const accts = await kaggleAccounts(env);
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: `\u{1F4D6} ${picked}

Which Kaggle account should build it?

Each build spends ~2h of that account's 30h weekly GPU quota.
\u26A0\uFE0F This is a one-time choice: the panels are stored on whichever account renders them, so every later rebuild of this book stays here too.`,
      reply_markup: { inline_keyboard: accts.map((a) => [{
        text: a.slot === "-" ? `${a.handle} (default)` : a.handle,
        callback_data: `tkag:${token}:${extra}|${a.slot}`
      }]) }
    });
    return;
  }
  if (action === "tkag") {
    const [idxK, slotK] = String(extra).split("|");
    const rawK = await env.PENDING.get(`topics:${token}`);
    if (!rawK) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C That topic list has expired \u2014 run /topics again." });
      return;
    }
    const pickedK = JSON.parse(rawK)[parseInt(idxK, 10)];
    if (!pickedK) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C Couldn't resolve that topic \u2014 run /topics again." });
      return;
    }
    const acctsK = await kaggleAccounts(env);
    const hitK = acctsK.find((a) => a.slot === slotK);
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: hitK ? hitK.handle : slotK });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `\u{1F4D6} ${pickedK}

\u{1F5A5}\uFE0F Kaggle: ${hitK ? hitK.handle : slotK}

${PAGE_QUESTION}`,
      reply_markup: pagesKeyboard(token, idxK, slotK)
    });
    return;
  }
  if (action === "tpag") {
    const [idxP, slotP, pagesP] = String(extra).split("|");
    const rawP = await env.PENDING.get(`topics:${token}`);
    if (!rawP) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C That topic list has expired \u2014 run /topics again." });
      return;
    }
    const pickedP = JSON.parse(rawP)[parseInt(idxP, 10)];
    if (!pickedP) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C Couldn't resolve that topic \u2014 run /topics again." });
      return;
    }
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `${pagesP} pages` });
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: `\u{1F4D6} ${pickedP}

${pagesP} pages

Which page style?
\u{1F3AC} cinematic \u2014 widescreen, wide tiers, splashes used generously
\u{1F9E9} mosaic \u2014 restless, tier structure changes every page
\u{1F4D6} classic \u2014 house rhythm, wide establishing then tighter beats
\u{1F512} chamber \u2014 close and claustrophobic, paired tall panels
\u26A1 staccato \u2014 fast cutting, abrupt changes of size
\u{1F4C1} documentary \u2014 dense evidential grid, splashes rare`,
      reply_markup: topicStyleKeyboard(token, idxP, slotP, pagesP)
    });
    return;
  }
  if (action === "topicgo") {
    const raw2 = await env.PENDING.get(`topics:${token}`);
    if (!raw2) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C That topic list has expired \u2014 run /topics again." });
      return;
    }
    const [idxStr, slotStr, pagesStr, styleStr] = String(extra).split("|");
    const picked2 = JSON.parse(raw2)[parseInt(idxStr, 10)];
    const pages2 = String(parseInt(pagesStr, 10) || 35);
    const profile2 = !styleStr || styleStr === "auto" ? "" : styleStr;
    if (!picked2) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C Couldn't resolve that topic \u2014 run /topics again." });
      return;
    }
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Reserving the issue number..." });
    const res = await reserveCase(env, picked2, slotStr || "-");
    const accts2 = await kaggleAccounts(env);
    const slotFinal = res.error ? slotStr || "-" : res.slot;
    const hit2 = accts2.find((a) => a.slot === slotFinal);
    const acctLabel = hit2 ? hit2.handle : slotFinal;
    try {
      await dispatchPipeline(env, {
        case: picked2,
        target_pages: pages2,
        profile: profile2,
        // A registry the Worker could not write must not block the book -- "auto" is exactly
        // what the build did before any of this existed.
        issue_no: res.error ? "auto" : String(res.issue).padStart(2, "0"),
        kaggle_account: slotFinal === "-" ? "" : slotFinal,
        dry_run: "false"
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start the build: ${e.message}` });
      return;
    }
    let note = "";
    if (res.error) {
      note = `

\u26A0\uFE0F Couldn't reserve the issue number (${res.error}) \u2014 the build will pick one itself, so don't start a second build until this one finishes.`;
    } else if (res.pinned && slotStr && slotStr !== res.slot) {
      note = `

\u{1F512} Ignored the account you picked: this book's art is already on ${acctLabel}, and building elsewhere would re-render every panel.`;
    }
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: `\u{1F4D6} Building "${picked2}"
` + (res.error ? "" : `\u{1F516} Issue #${String(res.issue).padStart(2, "0")}
`) + `\u{1F4C4} ${pages2} pages \xB7 ${profile2 || "auto"} layout
\u{1F5A5}\uFE0F Kaggle: ${acctLabel}

The draft lands here when it's done.${note}`
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
  if (action === "retry") {
    const raw2 = await env.PENDING.get("retry:" + token);
    if (!raw2) {
      await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "This retry has expired -- use /make" });
      return;
    }
    const b = JSON.parse(raw2);
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Retrying..." });
    try {
      await dispatchPipeline(env, {
        case: b.case || "",
        target_pages: String(b.target_pages || "25"),
        profile: b.profile || "",
        dry_run: "false"
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C Couldn't restart the build: " + e.message });
      return;
    }
    await tg(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text: '\u{1F501} Retrying "' + (b.case || "auto-picked case") + '" after the failure at ' + b.step + ".\nCached script, recovered art \u2014 only what broke is redone."
    });
    return;
  }
  if (action === "funnel") {
    const raw2 = await env.PENDING.get(`pending:${token}`);
    if (!raw2) {
      await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "This draft has expired -- rebuild it with /make" });
      return;
    }
    const rec = JSON.parse(raw2);
    if (!rec.video_id) {
      await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "No published short is linked to this case" });
      return;
    }
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Adding the comic link to YouTube..." });
    try {
      await dispatchFunnelComicLink(env, {
        video_id: rec.video_id,
        product_url: rec.product_url,
        product_name: rec.title || rec.case,
        pages: String(rec.pages || ""),
        hook: rec.hook || "",
        position: "top",
        notify_chat_id: String(chatId)
      });
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `\u{1F517} Adding "${rec.title || rec.case}" to https://youtu.be/${rec.video_id}'s description.
The job refuses if the Gumroad product is still a draft -- tap Approve first so the link isn't a 404 for viewers. I'll report back here.`
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start the funnel job: ${e.message}` });
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
__name2222(handleCallback, "handleCallback");
__name22222(handleCallback, "handleCallback");
__name222222(handleCallback, "handleCallback");
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
__name22(acceptHookClip, "acceptHookClip");
__name222(acceptHookClip, "acceptHookClip");
__name2222(acceptHookClip, "acceptHookClip");
var COMMAND_LIST = [
  "\u{1F4D6} SHADOW GASP BOT \u2014 all commands",
  "",
  "\u{1F4DA} COMICS",
  "/make  \u2014 auto-pick the next case that already has a published short, then ask pages + style",
  "/make <case>  \u2014 same, for a specific case",
  "/make <case> | 50  \u2014 build straight away at 50pp, skipping both pickers",
  "/regen p05_3 p06_1  \u2014 re-roll specific panels on the MOST RECENT book, after checking the OCR contact sheets. Panel names are the gold labels on those sheets. Everything else is reused, so it takes minutes not an hour.",
  "/regen <token> p05_3  \u2014 same, but for an older book (the token is in that book's sheet captions)",
  "/topics  - browse buildable cases: upcoming shorts first, then the published backlog. Full case names are listed under the buttons; tap one, pick the Kaggle account, the page count and the layout style.",
  "/promo  - promote a PUBLISHED comic on Facebook: cover + opening lines + the Gumroad link, in the post rather than the comments. Shows the post for confirmation first, and refuses a comic that has already gone out.",
  "/topics backlog  - jump straight to the published-but-no-comic list",
  "/links  - every comic with its Gumroad URL, the short it came from, and the command to link them",
  "/funnel  - put the most recent comic's link into the description of the short it was made from (published products only)",
  "/funnel <videoId>  - same, naming the video explicitly",
  "/gencode <slug> [cap]  \u2014 mint a ONE-TIME free download code for a published comic (default cap 50)",
  "/freeclaims <slug>  \u2014 how many one-time codes have been issued",
  "",
  "\u{1F3AC} SHORTS / VIDEO",
  "/short  \u2014 auto-pick a case, generate script + stills, DM the hook still and Flow prompt",
  "/short <case>  \u2014 same, for a specific case",
  "/day <N>  \u2014 hook still + Flow prompt for batch day N (add ' force' to override a published day)",
  "(reply to that with the Flow video)  \u2014 commits it, renders and uploads automatically",
  "/publish <N>  \u2014 render + upload day N now",
  "/publish <N> at <HH:MM>  \u2014 same, scheduled for that IST time",
  "/cancel <N>  \u2014 cancel an in-progress render/publish for day N",
  "/title <N>  \u2014 draft an alt title (Shock/Curiosity/Open-loop/Direct), tap Apply to use it",
  "",
  "⏰ SCHEDULED POSTS",
  "/scheduled  — FB/IG posts waiting for their time, each with a Cancel button",
  "(send any photo, with a caption)  — Post / Reject / Schedule it to Facebook or Instagram",
  "",
  "\u{1F4CA} REPORTS (nothing is built)",
  "/quota  \u2014 remaining weekly Kaggle GPU on all three accounts, before you spend any of it",
  "/trending  \u2014 trending true-crime stories not yet covered",
  "/retention  \u2014 last 21 days views/retention/drop-off, ranked by retention and by reach",
  "",
  "/help  \u2014 this list"
].join("\n");
async function handleMessage(env, msg) {
  const text = (msg.text || "").trim();
  const chatId = msg.chat.id;
  if (text.startsWith("/") && !botModeAllows(env, commandSurface(text))) {
    await tg(env, "sendMessage", { chat_id: chatId, text: otherBotHint(env) });
    return;
  }
  const videoObj = msg.video || (msg.document && msg.document.mime_type?.startsWith("video/") ? msg.document : null);
  if (videoObj && !botModeAllows(env, "video")) {
    await tg(env, "sendMessage", { chat_id: chatId, text: otherBotHint(env) });
    return;
  }
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
  if (await schedHandleMessage(env, msg, text)) return;
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
    const dayArg = text.slice("/day".length).trim();
    const dayNum = parseInt(dayArg, 10);
    const forced = /\bforce\b/i.test(dayArg);
    if (!dayNum) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "Usage: /day <N>, e.g. /day 1" });
      return;
    }
    const dd = String(dayNum).padStart(2, "0");
    if (!forced) {
      const st = await dayPublishState(env, dayNum);
      if (st) {
        await tg(env, "sendMessage", {
          chat_id: chatId,
          text: `\u2705 Day ${dayNum} is already published${st.case ? ` \u2014 "${st.case}"` : ""}${st.videoId ? `
https://youtu.be/${st.videoId}${st.publishedAt ? ` (${st.publishedAt})` : ""}` : ""}.

I haven't armed a hook wait, so replying with a clip here can't re-render or re-upload it. If you really do want to replace its hook video, send \`/day ${dayNum} force\`.`
        });
        return;
      }
    }
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
    const rawRest = text.slice("/publish".length).trim();
    const publishForced = /\bforce\b/i.test(rawRest);
    const rest2 = rawRest.replace(/\s*\bforce\b\s*/i, " ").trim();
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
    if (!publishForced) {
      const pst = await dayPublishState(env, dayNum);
      if (pst) {
        await tg(env, "sendMessage", {
          chat_id: chatId,
          text: `\u2705 Day ${dayNum} is already published${pst.case ? ` \u2014 "${pst.case}"` : ""}${pst.videoId ? `
https://youtu.be/${pst.videoId}${pst.publishedAt ? ` (${pst.publishedAt})` : ""}` : ""}.

Publishing again would render it and upload a SECOND copy to YouTube. Nothing has been dispatched. If that's genuinely what you want, send \`/publish ${dayNum} force\` (the \`at <time>\` forms still work alongside it).`
        });
        return;
      }
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
  if (text.startsWith("/help") || text.startsWith("/commands") || text.trim() === "/") {
    await tg(env, "sendMessage", { chat_id: chatId, text: COMMAND_LIST });
    return;
  }
  if (text.startsWith("/topics")) {
    const rest2 = text.slice("/topics".length).trim().toLowerCase();
    const kind = rest2.startsWith("back") ? "bk" : rest2.startsWith("done") || rest2.startsWith("comp") || rest2.startsWith("link") ? "dn" : "up";
    await sendTopicsPage(env, chatId, kind, 0, null);
    return;
  }
  if (text.startsWith("/promo")) {
    let products, posted;
    try {
      [products, posted] = await Promise.all([gumroadProducts(env), promoPosted(env)]);
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't read the storefront: ${e.message}` });
      return;
    }
    if (!products.length) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "No PUBLISHED comics to promote. Drafts are skipped \u2014 a link to a draft is a 404." });
      return;
    }
    products.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    const token = Math.random().toString(36).slice(2, 10);
    await env.PENDING.put(
      `promo:${token}`,
      JSON.stringify(products.map((p) => ({ n: p.name, u: p.short_url, c: p.custom_permalink, pr: p.price }))),
      { expirationTtl: 86400 }
    );
    const lines = [];
    const buttons = [];
    products.forEach((p, i) => {
      const done = posted.has(p.custom_permalink || "");
      lines.push(`${i + 1}. ${p.name}  \u2014 $${Math.round((p.price || 0) / 100)}${done ? "  \u2705 posted" : ""}`);
      if (!done) buttons.push({ text: String(i + 1), callback_data: `promo:${token}:${i}` });
    });
    const rows = [];
    for (let i = 0; i < buttons.length; i += 4) rows.push(buttons.slice(i, i + 4));
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: "\u{1F4E2} PROMOTE A COMIC ON FACEBOOK\n\n" + lines.join("\n") + `

Tap a number to see the exact post before anything goes out. The page has ~1,336 followers and the link goes IN the post.` + (rows.length ? "" : "\n\n\u2705 Every published comic has already been posted."),
      reply_markup: rows.length ? { inline_keyboard: rows } : void 0
    });
    return;
  }
  if (text.startsWith("/links")) {
    const list = await env.PENDING.list({ prefix: "comic:" });
    if (!list.keys.length) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "No comics indexed yet. They are recorded as they are built." });
      return;
    }
    const rows = [];
    const buttons = [];
    for (const k of list.keys) {
      const raw = await env.PENDING.get(k.name);
      if (!raw) continue;
      const c = JSON.parse(raw);
      if (!c.video_id) c.video_id = await resolveShort(c);
      const state = c.linked_at ? "  \u2705 linked " + c.linked_at + "  (re-check: /funnel " + c.video_id + ")" : "  \u{1F517} not linked yet \u2014 " + (c.video_id ? "/funnel " + c.video_id : "/funnel <videoId>");
      rows.push(
        (c.issue ? "#" + c.issue + " " : "") + (c.title || c.case) + "\n  store: " + (c.product_url || "(not staged)") + "\n  short: " + (c.video_id ? "https://youtu.be/" + c.video_id : "(none recorded)") + "\n" + state
      );
      if (!c.linked_at && c.video_id) {
        buttons.push([{
          text: `\u{1F517} Funnel ${c.issue ? "#" + c.issue : (c.title || c.case).slice(0, 24)}`,
          callback_data: `funnelc:${k.name.slice("comic:".length)}`
        }]);
      }
    }
    const LIMIT = 3500;
    const footer = "\n\nTap a button to link one \u2014 it pins that exact book. Typing /funnel <videoId> uses whichever comic is NEWEST, which is rarely what you mean when more than one is in flight.";
    const pages = [];
    let cur = "";
    for (const row of rows) {
      const candidate = cur ? cur + "\n\n" + row : row;
      if (candidate.length > LIMIT && cur) {
        pages.push(cur);
        cur = row;
      } else {
        cur = candidate;
      }
    }
    if (cur) pages.push(cur);
    for (let i = 0; i < pages.length; i++) {
      const head = pages.length > 1 ? `\u{1F4DA} COMICS (${i + 1}/${pages.length})

` : "\u{1F4DA} COMICS\n\n";
      const last = i === pages.length - 1;
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: head + pages[i] + (last ? footer : ""),
        // Buttons ride on the final page so one keyboard covers the whole list.
        reply_markup: last && buttons.length ? { inline_keyboard: buttons } : void 0
      });
    }
    return;
  }
  if (text.startsWith("/funnel")) {
    const args = text.trim().split(/\s+/).slice(1);
    let token = null, vid = null;
    if (args.length === 1) vid = args[0];
    else if (args.length >= 2) {
      token = args[0];
      vid = args[1];
    }
    if (!token) token = await env.PENDING.get("latest_pending");
    const raw = token ? await env.PENDING.get("pending:" + token) : null;
    if (!raw) {
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: "Usage: /funnel [videoId]\n\nLinks the most recent comic into its short's description. Pass a video id if the book has none recorded:\n/funnel ula5Affft-w"
      });
      return;
    }
    const rec = JSON.parse(raw);
    const videoId = vid || rec.video_id || await resolveShort(rec);
    if (vid && videoId) {
      const owner = await caseOfVideo(videoId);
      const book = rec.case || rec.title || "";
      if (owner && book && caseHead(owner) !== caseHead(book)) {
        await tg(env, "sendMessage", {
          chat_id: chatId,
          text: `\u26A0\uFE0F That pairing looks wrong, so nothing was dispatched.

https://youtu.be/${videoId} is "${owner}"
but the newest comic is "${book}".

Use /links and tap the button for the comic you mean \u2014 that pins the book. To force this pairing anyway: /funnel ${token} ${videoId}`
        });
        return;
      }
    }
    if (!videoId) {
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: '\u274C No short found for "' + (rec.title || rec.case) + '" \u2014 not in the record and not in the ledger either.\nPass the video id: /funnel <videoId>'
      });
      return;
    }
    if (!rec.product_url) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C No Gumroad URL recorded for that book." });
      return;
    }
    try {
      await dispatchFunnelComicLink(env, {
        video_id: videoId,
        product_url: rec.product_url,
        product_name: rec.title || rec.case,
        pages: String(rec.pages || ""),
        // Without the hook the description falls back to generic copy that sells the comic as
        // the same material the viewer just watched for free.
        hook: rec.hook || "",
        position: "top",
        notify_chat_id: String(chatId)
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C Couldn't start the funnel job: " + e.message });
      return;
    }
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: '\u{1F50E} Checking "' + (rec.title || rec.case) + '" against https://youtu.be/' + videoId + "\nIf the link is already there it changes nothing and says so; otherwise it adds it. Refuses while the product is a draft, since a draft URL 404s for viewers. Result follows in under a minute."
    });
    return;
  }
  if (text.startsWith("/regen")) {
    const parts = text.trim().split(/\s+/).slice(1);
    let token = null;
    if (parts.length && !/^p\d+[_-]/i.test(parts[0])) token = parts.shift();
    if (!token) token = await env.PENDING.get("latest_pending");
    const panels = parts.map((p) => p.endsWith(".jpg") ? p : p + ".jpg");
    if (!panels.length) {
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: "Usage: /regen p05_3 p06_1\n\nPanel names are the gold labels on the OCR contact sheets. This re-rolls on the most recent book; to target an older one, add the token from its sheet caption:\n/regen <token> p05_3"
      });
      return;
    }
    if (!token) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C No recent book to re-roll. Build one with /make first." });
      return;
    }
    const raw = await env.PENDING.get(`pending:${token}`);
    if (!raw) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C That token has expired or is not a book I know about." });
      return;
    }
    const rec = JSON.parse(raw);
    const known = new Set(rec.flagged || []);
    const unknown = known.size ? panels.filter((p) => !known.has(p)) : [];
    try {
      await dispatchPipeline(env, {
        case: rec.case,
        target_pages: String(rec.pages || "35"),
        regen_panels: panels.join(" "),
        dry_run: "false"
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u274C Couldn't start the re-roll: ${e.message}` });
      return;
    }
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: `\u{1F3A8} Re-rolling ${panels.length} panel(s) on a fresh seed: ${panels.join(", ")}` + (unknown.length ? `
\u26A0\uFE0F not in this book's flagged list, will be ignored: ${unknown.join(", ")}` : "") + `
Everything else is recovered, so only these are rendered. You'll get the rebuilt PDF here.`
    });
    return;
  }
  if (text.startsWith("/quota")) {
    try {
      await dispatchWorkflowVerified(env, "kaggle_quota.yml", {});
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: "\u{1F4CA} Checking Kaggle GPU quota on all three accounts \u2014 the table lands here in about 30s."
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "\u274C Could not start the quota check: " + e.message });
    }
    return;
  }
  if (!text.startsWith("/make")) {
    if (text.startsWith("/")) {
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: COMMAND_LIST
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
__name2222(handleMessage, "handleMessage");
__name22222(handleMessage, "handleMessage");
__name222222(handleMessage, "handleMessage");
function b_case_id(b) {
  return b.case_id || (b.case || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40);
}
__name(b_case_id, "b_case_id");
__name2(b_case_id, "b_case_id");
__name22(b_case_id, "b_case_id");
__name222(b_case_id, "b_case_id");
async function sendApprovalMessage(env, { token, caseName, productId, title, videoId }) {
  const funnelLine = videoId ? `
\u{1F517} From published short: https://youtu.be/${videoId}` : "";
  return tg(env, "sendMessage", {
    chat_id: env.TELEGRAM_CHAT_ID,
    text: `${title} \u2014 draft ready for review (Gumroad draft: ${productId})${funnelLine}`,
    reply_markup: approvalKeyboard(token, videoId)
  });
}
__name(sendApprovalMessage, "sendApprovalMessage");
__name2(sendApprovalMessage, "sendApprovalMessage");
__name22(sendApprovalMessage, "sendApprovalMessage");
__name222(sendApprovalMessage, "sendApprovalMessage");
__name2222(sendApprovalMessage, "sendApprovalMessage");
__name22222(sendApprovalMessage, "sendApprovalMessage");
__name222222(sendApprovalMessage, "sendApprovalMessage");
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
__name2222(sweepExpiredHookWaits, "sweepExpiredHookWaits");
__name22222(sweepExpiredHookWaits, "sweepExpiredHookWaits");
__name222222(sweepExpiredHookWaits, "sweepExpiredHookWaits");
// ---------------------------------------------------------------- SCHEDULED + PHOTO POSTS
//
// Added 2026-09-12. ADDITIVE ONLY: the existing fbdec/igdec/promogo/promono buttons keep their
// exact callback_data and handlers, and every existing workflow is dispatched unchanged.
//
// * "Schedule" parks a job in KV (`sched:jobs:<BOT_MODE>`, one list per bot so the two bots
//   sharing this KV namespace never race on the same key). /sched/tick fires the due ones by
//   dispatching the SAME workflow the Post/Approve button would have. This Cloudflare account is
//   at its cron cap, so the tick comes from mindunlocked-bot's existing */10 cron through a
//   service binding -- scheduled posts go out within ~10 min of the chosen time.
// * Photo posts (a day's thumbnail still, or any photo sent to the bot) go through the new
//   post_image.yml in the video repo. The photo bytes stay in KV and the workflow fetches them
//   back from /photo/get, so the bot token never leaves the Worker.
// * Every new button is refused outside TELEGRAM_CHAT_ID -- they post to public pages.
var SCHED_SLOTS = [["h1", "+1 hour"], ["h3", "+3 hours"], ["t19", "Today 7 PM"], ["n9", "Tomorrow 9 AM"], ["n19", "Tomorrow 7 PM"]];
// Video bot only (user, 2026-09-12): the comics bot does not get scheduling, so there is no
// comic-promo schedule here.
var SCHED_ACTIONS = ["fbsch", "igsch", "pqs", "pqc", "pqx", "ipg", "ipn", "ips"];
var SCHED_MAX_PER_TICK = 2;
var IST_OFFSET_MS = 330 * 60 * 1e3;
var POST_TTL = 30 * 86400;
function istParts(ms) {
  const d = new Date(ms + IST_OFFSET_MS);
  return { y: d.getUTCFullYear(), m: d.getUTCMonth() + 1, d: d.getUTCDate(), H: d.getUTCHours(), M: d.getUTCMinutes() };
}
function istToMs(y, m, d, H, M) {
  return Date.UTC(y, m - 1, d, H, M) - IST_OFFSET_MS;
}
function fmtIstMs(ms) {
  const p = istParts(ms), z = (n) => String(n).padStart(2, "0");
  return `${p.y}-${z(p.m)}-${z(p.d)} ${z(p.H)}:${z(p.M)} IST`;
}
function schedSlotMs(slot, now = Date.now()) {
  const t = istParts(now);
  const at = (addDays, H) => istToMs(t.y, t.m, t.d + addDays, H, 0);
  switch (slot) {
    case "h1": return now + 3600e3;
    case "h3": return now + 3 * 3600e3;
    case "t19": { const x = at(0, 19); return x > now + 60e3 ? x : at(1, 19); }
    case "n9": return at(1, 9);
    case "n19": return at(1, 19);
    default: return null;
  }
}
// "YYYY-MM-DD HH:MM" or just "HH:MM" (next occurrence), Indian time. null = not a time at all;
// NaN = looks like a time but is invalid, so the caller can say so instead of ignoring it.
function parseIstInput(text, now = Date.now()) {
  const s = String(text || "").trim();
  let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2})[:.](\d{2})$/);
  if (m) {
    const [y, mo, d, H, M] = m.slice(1).map(Number);
    if (mo < 1 || mo > 12 || d < 1 || d > 31 || H > 23 || M > 59) return NaN;
    return istToMs(y, mo, d, H, M);
  }
  m = s.match(/^(\d{1,2})[:.](\d{2})$/);
  if (m) {
    const H = +m[1], M = +m[2];
    if (H > 23 || M > 59) return NaN;
    const t = istParts(now);
    let x = istToMs(t.y, t.m, t.d, H, M);
    if (x <= now) x += 86400e3;
    return x;
  }
  return null;
}
function schedMode(env) {
  return (env.BOT_MODE || "all").toLowerCase();
}
function schedKey(env) {
  return `sched:jobs:${schedMode(env)}`;
}
async function schedLoad(env) {
  try {
    return JSON.parse(await env.PENDING.get(schedKey(env)) || "[]");
  } catch {
    return [];
  }
}
async function schedSave(env, jobs) {
  await env.PENDING.put(schedKey(env), JSON.stringify(jobs));
}
function schedIsOwner(env, chatId) {
  return !!env.TELEGRAM_CHAT_ID && String(chatId) === String(env.TELEGRAM_CHAT_ID);
}
function schedId() {
  return Math.random().toString(36).slice(2, 10);
}
function platName(p) {
  return p === "ig" ? "Instagram" : "Facebook";
}
function schedLabel(t) {
  if (t.kind === "video") return `Day ${t.day} video → ${platName(t.platform)}`;
  if (t.kind === "promo") return `Comic promo "${t.name || t.case}" → ${platName(t.platform)}`;
  return `${t.what || "Photo"} → ${platName(t.platform)}`;
}
async function schedOfferSlots(env, chatId, target) {
  const tok = schedId();
  await env.PENDING.put(`schtgt:${tok}`, JSON.stringify(target), { expirationTtl: 7 * 86400 });
  const b = SCHED_SLOTS.map(([code, label]) => ({ text: label, callback_data: `pqs:${tok}:${code}` }));
  await tg(env, "sendMessage", {
    chat_id: chatId,
    text: `⏰ When should this go out?
${schedLabel(target)}

Times are Indian time (IST). It posts within ~10 min of the chosen time.`,
    reply_markup: { inline_keyboard: [b.slice(0, 2), b.slice(2, 3), b.slice(3, 5), [{ text: "✏️ Custom time…", callback_data: `pqc:${tok}` }]] }
  });
}
async function schedAdd(env, chatId, target, runAt) {
  const jobs = await schedLoad(env);
  const job = { id: schedId(), run_at: runAt, chat_id: String(chatId), target };
  jobs.push(job);
  await schedSave(env, jobs);
  await tg(env, "sendMessage", {
    chat_id: chatId,
    text: `✅ Scheduled: ${schedLabel(target)}
\u{1F552} ${fmtIstMs(runAt)}

Nothing is posted until then. /scheduled lists everything waiting.`,
    reply_markup: { inline_keyboard: [[{ text: "✖ Cancel this schedule", callback_data: `pqx:${job.id}` }]] }
  });
}
function imgKeyboard(tok) {
  return { inline_keyboard: [
    [
      { text: "\u{1F4D8} FB: ✅ Post", callback_data: `ipg:${tok}:fb` },
      { text: "❌ Reject", callback_data: `ipn:${tok}:fb` },
      { text: "⏰ Schedule", callback_data: `ips:${tok}:fb` }
    ],
    [
      { text: "\u{1F4F7} IG: ✅ Post", callback_data: `ipg:${tok}:ig` },
      { text: "❌ Reject", callback_data: `ipn:${tok}:ig` },
      { text: "⏰ Schedule", callback_data: `ips:${tok}:ig` }
    ]
  ] };
}
async function imgDispatch(env, tok, platform, chatId) {
  const raw = await env.PENDING.get(`imgp:${tok}`);
  if (!raw) throw new Error("that post has expired (kept 30 days) — send the photo again");
  const item = JSON.parse(raw);
  if (item[platform] === "sent") throw new Error(`already sent to ${platName(platform)} — not posting a duplicate`);
  await dispatchWorkflowVerified(env, "post_image.yml", {
    platform,
    source: item.src,
    day: String(item.day || ""),
    photo_token: item.src === "photo" ? tok : "",
    caption: item.caption || "",
    bot: schedMode(env) === "comics" ? "comics" : "video",
    notify_chat_id: String(chatId),
    label: item.what || "Photo post"
  });
  item[platform] = "sent";
  await env.PENDING.put(`imgp:${tok}`, JSON.stringify(item), { expirationTtl: POST_TTL });
}
async function sendPhotoWithButtons(env, chatId, bytes, caption, replyMarkup) {
  const form = new FormData();
  form.append("chat_id", String(chatId));
  form.append("caption", caption.length > 1024 ? caption.slice(0, 1021) + "..." : caption);
  form.append("reply_markup", JSON.stringify(replyMarkup));
  form.append("photo", new Blob([bytes], { type: "image/jpeg" }), "photo.jpeg");
  const resp = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendPhoto`, { method: "POST", body: form });
  const body = await resp.json();
  if (!body.ok) throw new Error(`sendPhoto: ${body.description || body.error_code}`);
}
// The extra "post the thumbnail as a photo" offer under a freshly LIVE day. Sent as its own
// message AFTER the existing LIVE message, and the caller wraps it in try/catch, so nothing about
// the existing message or its Approve/Reject buttons can be affected by a failure here.
async function imgOfferDay(env, day, chatId, title) {
  const tok = schedId();
  const item = { src: "day", day: String(day), caption: "", what: `Day ${day} thumbnail photo` };
  await env.PENDING.put(`imgp:${tok}`, JSON.stringify(item), { expirationTtl: POST_TTL });
  const cap = `\u{1F5BC} Also post day ${day}'s thumbnail as a PHOTO post?${title ? `
"${title}"` : ""}

Caption = the video's own title, description and hashtags. Nothing is posted until you tap.`;
  try {
    const url = await hookStillUrl(env, String(day).padStart(2, "0"));
    const r = await fetch(url, { headers: { "User-Agent": "shadow-gasp-bot" } });
    if (!r.ok) throw new Error(`still ${r.status}`);
    await sendPhotoWithButtons(env, chatId, await r.arrayBuffer(), cap, imgKeyboard(tok));
  } catch (e) {
    await tg(env, "sendMessage", { chat_id: chatId, text: cap, reply_markup: imgKeyboard(tok) });
  }
}
async function imgIntakePhoto(env, msg, fileObj) {
  const chatId = msg.chat.id;
  const info = await tg(env, "getFile", { file_id: fileObj.file_id });
  if (!info.ok) throw new Error(`Telegram wouldn't hand over the file: ${info.description || info.error_code}`);
  const f = await fetch(`https://api.telegram.org/file/bot${env.TELEGRAM_BOT_TOKEN}/${info.result.file_path}`);
  if (!f.ok) throw new Error(`photo download failed: ${f.status}`);
  const tok = schedId();
  await env.PENDING.put(`photo:${tok}`, await f.arrayBuffer(), { expirationTtl: POST_TTL });
  const caption = (msg.caption || "").trim();
  await env.PENDING.put(`imgp:${tok}`, JSON.stringify({ src: "photo", caption, what: "Your photo" }), { expirationTtl: POST_TTL });
  await tg(env, "sendMessage", {
    chat_id: chatId,
    reply_to_message_id: msg.message_id,
    text: `\u{1F5BC} Post this photo to the Shadow Gasp page?

Caption: ${caption ? caption.slice(0, 600) : "(none — send the photo WITH a caption to add one)"}

Nothing is posted until you tap.`,
    reply_markup: imgKeyboard(tok)
  });
}
async function schedFire(env, job) {
  const t = job.target;
  if (t.kind === "video") {
    await dispatchCrosspostDecision(env, { day: String(t.day), platform: t.platform, decision: "approve", notify_chat_id: job.chat_id });
  } else if (t.kind === "image") {
    await imgDispatch(env, t.item, t.platform, job.chat_id);
  } else {
    throw new Error(`unknown job kind ${t.kind}`);
  }
}
async function schedRunDue(env) {
  const jobs = await schedLoad(env);
  const now = Date.now();
  const due = jobs.filter((j) => j.run_at <= now).sort((a, b) => a.run_at - b.run_at).slice(0, SCHED_MAX_PER_TICK);
  if (!due.length) return { fired: 0, waiting: jobs.length };
  const ids = new Set(due.map((j) => j.id));
  // Remove BEFORE dispatching: if the Worker dies mid-dispatch, the next tick must not post twice.
  await schedSave(env, jobs.filter((j) => !ids.has(j.id)));
  let fired = 0;
  for (const j of due) {
    // mindunlocked-bot's cron fires TWICE per 10 min (~8 s apart), so two ticks can race for the
    // same job before the list removal above is visible to the second. A per-job lock, written
    // before dispatch, makes the second tick skip it.
    if (await env.PENDING.get(`sched_fired:${j.id}`)) continue;
    await env.PENDING.put(`sched_fired:${j.id}`, "1", { expirationTtl: 86400 });
    fired++;
    const lateMin = Math.round((now - j.run_at) / 6e4);
    try {
      await schedFire(env, j);
      await tg(env, "sendMessage", {
        chat_id: j.chat_id,
        text: `⏰ Scheduled post going out now: ${schedLabel(j.target)}${lateMin > 20 ? ` (${lateMin} min late)` : ""}
I'll confirm here when it lands.`
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: j.chat_id, text: `❌ Scheduled post could NOT start: ${schedLabel(j.target)}
${e.message}` });
    }
  }
  return { fired, waiting: jobs.length - due.length };
}
async function schedListMessage(env, chatId) {
  const jobs = (await schedLoad(env)).sort((a, b) => a.run_at - b.run_at);
  if (!jobs.length) {
    await tg(env, "sendMessage", { chat_id: chatId, text: "⏰ Nothing scheduled. Tap ⏰ Schedule on any post to add one." });
    return;
  }
  const shown = jobs.slice(0, 30);
  await tg(env, "sendMessage", {
    chat_id: chatId,
    text: "⏰ SCHEDULED POSTS\n\n" + shown.map((j, i) => `${i + 1}. ${fmtIstMs(j.run_at)}\n   ${schedLabel(j.target)}`).join("\n") + (jobs.length > shown.length ? `\n…and ${jobs.length - shown.length} more` : "") + "\n\nTap a number to cancel that one.",
    reply_markup: { inline_keyboard: shown.map((j, i) => [{ text: `✖ Cancel ${i + 1}`, callback_data: `pqx:${j.id}` }]) }
  });
}
// Returns true when the button was one of the new ones (and has been handled).
async function schedHandleCallback(env, cq, action, token, extra) {
  if (!SCHED_ACTIONS.includes(action)) return false;
  const chatId = cq.message.chat.id;
  const messageId = cq.message.message_id;
  if (!schedIsOwner(env, chatId)) {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Not allowed." });
    return true;
  }
  await tg(env, "answerCallbackQuery", { callback_query_id: cq.id });
  try {
    if (action === "fbsch" || action === "igsch") {
      await schedOfferSlots(env, chatId, { kind: "video", day: String(token), platform: action === "fbsch" ? "fb" : "ig" });
    } else if (action === "pqs") {
      const raw = await env.PENDING.get(`schtgt:${token}`);
      if (!raw) throw new Error("that time picker has expired — tap ⏰ Schedule again");
      const runAt = schedSlotMs(extra);
      if (!runAt) throw new Error("unknown time slot");
      await env.PENDING.delete(`schtgt:${token}`);
      await tg(env, "editMessageReplyMarkup", { chat_id: chatId, message_id: messageId, reply_markup: { inline_keyboard: [] } });
      await schedAdd(env, chatId, JSON.parse(raw), runAt);
    } else if (action === "pqc") {
      if (!await env.PENDING.get(`schtgt:${token}`)) throw new Error("that time picker has expired — tap ⏰ Schedule again");
      await env.PENDING.put(`awaiting_sched_custom:${chatId}`, String(token), { expirationTtl: 3600 });
      await tg(env, "sendMessage", { chat_id: chatId, text: "✏️ Reply with the time in Indian time (IST):\n• 2026-09-20 18:30  (date + time)\n• 18:30  (next time it's 18:30)" });
    } else if (action === "pqx") {
      const jobs = await schedLoad(env);
      const job = jobs.find((j) => j.id === token);
      if (!job) {
        await tg(env, "sendMessage", { chat_id: chatId, text: "That one is no longer waiting — it was already sent or cancelled." });
      } else {
        await schedSave(env, jobs.filter((j) => j.id !== token));
        await tg(env, "sendMessage", { chat_id: chatId, text: `✖ Cancelled: ${schedLabel(job.target)} (${fmtIstMs(job.run_at)}). Nothing will be posted.` });
      }
    } else if (action === "ipg") {
      await imgDispatch(env, token, extra, chatId);
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u{1F4E4} Posting to ${platName(extra)} now… I'll confirm here when it lands.` });
    } else if (action === "ipn") {
      const raw = await env.PENDING.get(`imgp:${token}`);
      if (raw) {
        const item = JSON.parse(raw);
        if (item[extra] !== "sent") item[extra] = "rejected";
        await env.PENDING.put(`imgp:${token}`, JSON.stringify(item), { expirationTtl: POST_TTL });
      }
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u{1F6AB} ${platName(extra)}: rejected, not posted.` });
    } else if (action === "ips") {
      const raw = await env.PENDING.get(`imgp:${token}`);
      if (!raw) throw new Error("that post has expired (kept 30 days) — send the photo again");
      const item = JSON.parse(raw);
      await schedOfferSlots(env, chatId, { kind: "image", item: token, platform: extra === "ig" ? "ig" : "fb", what: item.what });
    }
  } catch (e) {
    await tg(env, "sendMessage", { chat_id: chatId, text: `❌ ${e.message}` });
  }
  return true;
}
// Returns true when the message was one of the new kinds (and has been handled). Photos used to be
// ignored entirely by this bot, and plain non-command text too, so neither path had a behaviour
// to preserve; a custom-time reply is only consumed when a Custom picker is actually waiting.
async function schedHandleMessage(env, msg, text) {
  const chatId = msg.chat.id;
  if (!schedIsOwner(env, chatId)) return false;
  const photo = msg.photo && msg.photo.length ? msg.photo[msg.photo.length - 1] : msg.document && (msg.document.mime_type || "").startsWith("image/") ? msg.document : null;
  if (photo) {
    try {
      await imgIntakePhoto(env, msg, photo);
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't take that photo: ${e.message}` });
    }
    return true;
  }
  if (/^\/scheduled(@\S+)?$/i.test(text)) {
    await schedListMessage(env, chatId);
    return true;
  }
  if (text && !text.startsWith("/")) {
    const tok = await env.PENDING.get(`awaiting_sched_custom:${chatId}`);
    if (!tok) return false;
    const runAt = parseIstInput(text);
    if (runAt === null) return false;
    if (Number.isNaN(runAt) || runAt <= Date.now()) {
      await tg(env, "sendMessage", { chat_id: chatId, text: Number.isNaN(runAt) ? "❌ That isn't a valid time. Try e.g. 2026-09-20 18:30 or 18:30." : "❌ That time has already passed. Send a future time." });
      return true;
    }
    const raw = await env.PENDING.get(`schtgt:${tok}`);
    await env.PENDING.delete(`awaiting_sched_custom:${chatId}`);
    if (!raw) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "❌ That time picker has expired — tap ⏰ Schedule again." });
      return true;
    }
    await env.PENDING.delete(`schtgt:${tok}`);
    await schedAdd(env, chatId, JSON.parse(raw), runAt);
    return true;
  }
  return false;
}
function schedAuthOk(request, env) {
  const a = request.headers.get("X-Batch-Notify-Secret");
  const b = request.headers.get("X-Shared-Secret");
  return !!env.BATCH_NOTIFY_SECRET && a === env.BATCH_NOTIFY_SECRET || !!env.WORKER_SHARED_SECRET && b === env.WORKER_SHARED_SECRET;
}
// New routes only; returns null for every path it doesn't own so the existing router runs as before.
async function schedRoutes(request, env, url, ctx) {
  if (request.method !== "POST") return null;
  if (url.pathname === "/sched/tick") {
    if (!env.SCHED_TICK_SECRET || request.headers.get("X-Sched-Secret") !== env.SCHED_TICK_SECRET) {
      return new Response("forbidden", { status: 403 });
    }
    // Answer at once and do the work in THIS Worker's waitUntil: the caller's cron invocation can
    // end -- cancelling this request -- before a dispatch (with its verify sleeps) finishes. Seen
    // 2026-09-11: the first of each pair of ticks was cancelled at ~6 s.
    if (ctx && ctx.waitUntil) {
      ctx.waitUntil(schedRunDue(env).catch((e) => console.log(`sched tick: ${e.message}`)));
      return new Response(JSON.stringify({ accepted: true }), { status: 202, headers: { "Content-Type": "application/json" } });
    }
    const r = await schedRunDue(env);
    return new Response(JSON.stringify(r), { status: 200, headers: { "Content-Type": "application/json" } });
  }
  if (url.pathname === "/photo/get") {
    if (!schedAuthOk(request, env)) return new Response("forbidden", { status: 403 });
    const { token } = await request.json();
    const bytes = token && await env.PENDING.get(`photo:${token}`, "arrayBuffer");
    if (!bytes) return new Response("not found", { status: 404 });
    return new Response(bytes, { status: 200, headers: { "Content-Type": "image/jpeg" } });
  }
  if (url.pathname === "/post/decided") {
    if (!schedAuthOk(request, env)) return new Response("forbidden", { status: 403 });
    const b = await request.json();
    const where = platName(b.platform);
    const text = b.ok ? `✅ ${b.label || "Photo post"} is LIVE on ${where}${b.ref_id ? (b.platform === "fb" ? `: https://facebook.com/${b.ref_id}` : ` (media_id ${b.ref_id})`) : ""}` : `❌ ${b.label || "Photo post"} → ${where} FAILED: ${b.error || "unknown error"}${b.run_url ? `
${b.run_url}` : ""}`;
    await tg(env, "sendMessage", { chat_id: b.chat_id || env.TELEGRAM_CHAT_ID, text });
    return new Response("ok", { status: 200 });
  }
  return null;
}
var worker_default = {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const schedResp = await schedRoutes(request, env, url, ctx);
    if (schedResp) return schedResp;
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
    if (request.method === "POST" && url.pathname === "/build-failed") {
      const auth = request.headers.get("X-Shared-Secret");
      if (auth !== env.WORKER_SHARED_SECRET) return new Response("forbidden", { status: 403 });
      const b = await request.json();
      const token = "r" + Math.random().toString(36).slice(2, 10);
      await env.PENDING.put("retry:" + token, JSON.stringify(b), { expirationTtl: 604800 });
      await tg(env, "sendMessage", {
        chat_id: env.TELEGRAM_CHAT_ID,
        text: "\u274C Build FAILED at: " + b.step + "\n\nCase: " + (b.case || "(auto-picked)") + "\nPages: " + (b.target_pages || "default") + (b.profile ? " \xB7 style " + b.profile : "") + "\nLog: " + b.run_url + "\n\nRetrying skips what already succeeded \u2014 the script is cached and the art is recovered from the Kaggle kernel, so it picks up at the step that broke.",
        reply_markup: { inline_keyboard: [[
          { text: "\u{1F501} Retry from here", callback_data: "retry:" + token }
        ]] }
      });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/register") {
      const auth = request.headers.get("X-Shared-Secret");
      if (auth !== env.WORKER_SHARED_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { token, case: caseName, product_id, title, video_id, product_url, pages } = body;
      if (!token || !caseName || !product_id) {
        return new Response("missing fields", { status: 400 });
      }
      await env.PENDING.put("latest_pending", token);
      if (b_case_id(body)) {
        await env.PENDING.put("comic:" + b_case_id(body), JSON.stringify({
          title: body.title || body.case,
          case: body.case,
          product_url: body.product_url || "",
          video_id: body.video_id || "",
          issue: body.issue_no || "",
          pages: body.pages || "",
          hook: body.hook || ""
        }));
      }
      await env.PENDING.put(`pending:${token}`, JSON.stringify({
        case: caseName,
        product_id,
        video_id: video_id || "",
        product_url: product_url || "",
        pages: pages || "",
        title: title || caseName
      }));
      await sendApprovalMessage(env, {
        token,
        caseName,
        productId: product_id,
        title: title || caseName,
        videoId: video_id || ""
      });
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
      await env.PENDING.put(`script_cache:${key}`, JSON.stringify({ script, panel_prompts }));
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
      await autoFunnelForCase(env, caseName, video_id, chat_id);
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
      if (needsCrosspostDecision) {
        try {
          await imgOfferDay(env, day, chat_id || env.TELEGRAM_CHAT_ID, title);
        } catch (e) {
          console.log(`thumbnail photo offer failed: ${e.message}`);
        }
      }
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
    if (request.method === "POST" && url.pathname === "/notify-raw") {
      const auth2 = request.headers.get("X-Shared-Secret");
      if (auth2 !== env.WORKER_SHARED_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body2 = await request.json();
      if (!body2.text) {
        return new Response("missing fields", { status: 400 });
      }
      await tg(env, "sendMessage", { chat_id: body2.chat_id || env.TELEGRAM_CHAT_ID, text: body2.text });
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
      const { day, job, step, run_url, chat_id, account, reason } = body;
      if (!day || !job) {
        return new Response("missing fields", { status: 400 });
      }
      let markup = void 0;
      let extraText = "";
      if (reason === "stills" && /^\d+$/.test(String(day))) {
        const others = KAGGLE_SLOTS.filter((r) => r[0] !== account);
        if (others.length) {
          markup = { inline_keyboard: [others.map((r) => ({ text: `\u{1F504} Retry on ${r[1]}`, callback_data: `kag:${day}:${r[0]}` }))] };
          const ranOn = (KAGGLE_SLOTS.find((r) => r[0] === account) || [account, account])[1];
          extraText = `

It ran on ${ranOn}. Out of GPU quota Kaggle queues instead of failing, so this can simply be the weekly limit. /quota shows all three.`;
        }
      }
      await tg(env, "sendMessage", {
        chat_id: chat_id || env.TELEGRAM_CHAT_ID,
        text: `\u274C Day ${day}'s "${job}" job failed at step "${step || "unknown"}".
${run_url || ""}` + extraText,
        reply_markup: markup
      });
      return new Response("ok", { status: 200 });
    }
    if (request.method === "POST" && url.pathname === "/comic/sweep") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const list = await env.PENDING.list({ prefix: "comic:" });
      const sent = [], skipped = [];
      for (const k of list.keys) {
        const raw = await env.PENDING.get(k.name);
        if (!raw) continue;
        const c = JSON.parse(raw);
        const name = c.title || c.case || k.name;
        if (c.linked_at) continue;
        if (!c.product_url) {
          skipped.push(`${name}: not staged`);
          continue;
        }
        const videoId = c.video_id || await resolveShort(c);
        if (!videoId) {
          skipped.push(`${name}: short not published`);
          continue;
        }
        let live = false;
        try {
          const r = await fetch(c.product_url, { method: "GET", headers: { "User-Agent": "shadow-gasp-bot" } });
          live = r.ok;
        } catch (e) {
          live = false;
        }
        if (!live) {
          skipped.push(`${name}: still a draft`);
          continue;
        }
        try {
          await dispatchFunnelComicLink(env, {
            video_id: videoId,
            product_url: c.product_url,
            product_name: name,
            pages: String(c.pages || ""),
            hook: c.hook || "",
            position: "top",
            notify_chat_id: String(env.TELEGRAM_CHAT_ID || "")
          });
          sent.push(`${name} -> ${videoId}`);
        } catch (e) {
          skipped.push(`${name}: dispatch failed (${e.message})`);
        }
      }
      if (sent.length) {
        await tg(env, "sendMessage", {
          chat_id: env.TELEGRAM_CHAT_ID,
          text: `\u{1F517} Link sweep: funnelling ${sent.length} comic(s) whose short was already live.
` + sent.join("\n")
        });
      }
      return new Response(JSON.stringify({ sent, skipped }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }
    if (request.method === "POST" && url.pathname === "/promo/preview") {
      const auth = request.headers.get("X-Shared-Secret");
      if (auth !== env.WORKER_SHARED_SECRET) return new Response("forbidden", { status: 403 });
      const p = await request.json();
      if (p.outcome !== "success" || !p.image) {
        await tg(env, "sendMessage", {
          chat_id: env.TELEGRAM_CHAT_ID,
          text: `\u274C Couldn't build the promo draft for "${p.case || "?"}".
${p.run_url || ""}`
        });
        return new Response("ok");
      }
      const plat = p.platform === "ig" ? "Instagram" : "Facebook";
      const token = Math.random().toString(36).slice(2, 10);
      await env.PENDING.put(
        `promo:${token}`,
        JSON.stringify([{ n: p.case, u: p.url, c: p.permalink, pr: (p.price || 0) * 100 }]),
        { expirationTtl: 86400 }
      );
      const warn = p.already ? "\n\n\u26A0\uFE0F This comic has ALREADY been posted here. Accepting will publish a SECOND copy \u2014 a duplicate is what cost this page its reach in August." : "";
      await tg(env, "sendPhoto", {
        chat_id: env.TELEGRAM_CHAT_ID,
        photo: p.image,
        caption: `\u{1F5BC} ${plat} DRAFT \u2014 nothing is published yet

${(p.caption || "").slice(0, 800)}${warn}`,
        reply_markup: { inline_keyboard: [[
          { text: `\u2705 Post to ${plat}`, callback_data: `promogo:${token}:0|${p.platform === "ig" ? "ig" : "fb"}` },
          { text: "\u2716 Reject", callback_data: `promono:${token}:0` }
        ]] }
      });
      return new Response("ok");
    }
    if (request.method === "POST" && url.pathname === "/promo/posted") {
      const auth = request.headers.get("X-Shared-Secret");
      if (auth !== env.WORKER_SHARED_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const b = await request.json();
      const ok = b.result === "success";
      const dry = String(b.dry_run) === "true";
      await tg(env, "sendMessage", {
        chat_id: env.TELEGRAM_CHAT_ID,
        text: dry ? `\u{1F9EA} Promo DRY RUN for "${b.case}" \u2014 ${ok ? "token and product check out; nothing posted." : "failed."}
${b.run_url || ""}` : ok ? `\u2705 Posted "${b.case}" to Facebook.` : `\u274C Facebook post FAILED for "${b.case}".
${b.run_url || ""}`
      });
      return new Response("ok");
    }
    if (request.method === "POST" && url.pathname === "/comic/linked") {
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { product_url, video_id, linked_at } = body;
      if (!product_url) return new Response("product_url required", { status: 400 });
      const list = await env.PENDING.list({ prefix: "comic:" });
      let hits = 0;
      for (const k of list.keys) {
        const raw = await env.PENDING.get(k.name);
        if (!raw) continue;
        const c = JSON.parse(raw);
        if ((c.product_url || "") !== product_url) continue;
        c.linked_at = linked_at || (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
        if (video_id && !c.video_id) c.video_id = video_id;
        await env.PENDING.put(k.name, JSON.stringify(c));
        hits++;
      }
      return new Response(`ok ${hits}`, { status: 200 });
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
