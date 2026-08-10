// Shadow Gasp comic-pipeline Telegram bot.
//
// Thin by design: this Worker only receives Telegram webhook button taps and
// dispatches the `action.yml` GitHub Actions workflow, which does the actual
// work (Gumroad publish/delete via the CLI, or re-running the full pipeline
// for a page-count increase). No business logic is duplicated here.
//
// Telegram's callback_data has a hard 64-byte limit, and a case slug + a
// Gumroad product id together blow past that -- so callback_data only ever
// carries a short opaque token; the real context (case name, product id,
// chat/message id) lives in KV under that token, written by
// stage_and_deliver.py when the comic is first delivered for approval.

const GITHUB_REPO = "Universekianukal/shadow-gasp-comic-pipeline";
// Separate repo for the true-crime SHORTS video pipeline (script -> TTS ->
// FLUX stills -> CogVideoX hook -> render -> YouTube). Distinct from the
// comic-PDF pipeline above; dispatched with its own token (GITHUB_TOKEN_VIDEO)
// so this addition can't affect the comic flow's existing token/permissions.
const VIDEO_REPO = "Universekianukal/shadow-gasp-pipeline";

async function tg(env, method, params) {
  const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return r.json();
}

async function dispatchAction(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/action.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "shadow-gasp-bot",
      },
      body: JSON.stringify({ ref: "main", inputs }),
    }
  );
  if (!r.ok) {
    throw new Error(`GitHub dispatch failed: ${r.status} ${await r.text()}`);
  }
}

async function dispatchPipeline(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/pipeline.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "shadow-gasp-bot",
      },
      body: JSON.stringify({ ref: "main", inputs }),
    }
  );
  if (!r.ok) throw new Error(`GitHub dispatch failed: ${r.status} ${await r.text()}`);
}

async function dispatchGenCode(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/gen_code.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "shadow-gasp-bot",
      },
      body: JSON.stringify({ ref: "main", inputs }),
    }
  );
  if (!r.ok) throw new Error(`GitHub dispatch failed: ${r.status} ${await r.text()}`);
}

async function dispatchVideoPipeline(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${VIDEO_REPO}/actions/workflows/pipeline.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "shadow-gasp-bot",
      },
      body: JSON.stringify({ ref: "main", inputs }),
    }
  );
  if (!r.ok) throw new Error(`GitHub dispatch failed: ${r.status} ${await r.text()}`);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// A workflow_dispatch call returns 204 even when GitHub silently drops it --
// this happens in practice right after a push to the same branch the
// workflow lives on (exactly the commitHookVideo -> dispatch sequence this
// bot does), because the ref hasn't finished propagating internally yet for
// scheduling purposes. A 204 alone is NOT proof the run was created, so this
// polls the workflow's own run list afterward and retries once if nothing
// shows up -- only then is it safe to tell the user "render running now".
async function dispatchWorkflowVerified(env, workflowFile, inputs) {
  const dispatchOnce = async () => {
    const beforeMs = Date.now();
    const r = await fetch(
      `https://api.github.com/repos/${VIDEO_REPO}/actions/workflows/${workflowFile}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`,
          Accept: "application/vnd.github+json",
          "User-Agent": "shadow-gasp-bot",
        },
        body: JSON.stringify({ ref: "main", inputs }),
      }
    );
    if (!r.ok) throw new Error(`GitHub dispatch failed: ${r.status} ${await r.text()}`);
    return beforeMs;
  };

  const runAppeared = async (afterMs) => {
    const r = await fetch(
      `https://api.github.com/repos/${VIDEO_REPO}/actions/workflows/${workflowFile}/runs?event=workflow_dispatch&per_page=5`,
      { headers: { Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`, "User-Agent": "shadow-gasp-bot" } }
    );
    if (!r.ok) return false;
    const data = await r.json();
    return (data.workflow_runs || []).some((run) => new Date(run.created_at).getTime() >= afterMs - 2000);
  };

  let beforeMs = await dispatchOnce();
  await sleep(4000);
  if (await runAppeared(beforeMs)) return;

  // Retry once -- the race is transient, a second attempt a few seconds
  // later almost always lands cleanly.
  beforeMs = await dispatchOnce();
  await sleep(4000);
  if (await runAppeared(beforeMs)) return;

  throw new Error("dispatched twice but no run appeared in Actions -- check the repo's Actions tab manually");
}

async function dispatchFinishBatchDay(env, inputs) {
  return dispatchWorkflowVerified(env, "finish_batch_day.yml", inputs);
}

async function dispatchBatchPregen(env, inputs) {
  return dispatchWorkflowVerified(env, "batch_pregen.yml", inputs);
}

function pregenKeyboard() {
  return {
    inline_keyboard: [
      [3, 5, 7].map((n) => ({ text: `${n} days`, callback_data: `pregen:${n}` })),
      [10].map((n) => ({ text: `${n} days`, callback_data: `pregen:${n}` })),
    ],
  };
}

async function ghRaw(env, path) {
  const r = await fetch(`https://raw.githubusercontent.com/${VIDEO_REPO}/main/${path}`, {
    headers: { "User-Agent": "shadow-gasp-bot" },
  });
  if (!r.ok) throw new Error(`${path} not found in repo (${r.status})`);
  return r;
}

// Commits the Telegram-downloaded hook video straight into the day's
// images/seq/01.mp4 via the Contents API (small binary payload, well under
// GitHub's 100MB API limit for a ~10s clip) so finish_batch_day.yml's render
// job has something to check out and render, with no local machine involved.
async function commitHookVideo(env, dayNum, videoBytes) {
  const path = `_pipeline/batch/day${String(dayNum).padStart(2, "0")}/images/seq/01.mp4`;
  let sha;
  const existing = await fetch(
    `https://api.github.com/repos/${VIDEO_REPO}/contents/${path}?ref=main`,
    { headers: { Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`, "User-Agent": "shadow-gasp-bot" } }
  );
  if (existing.ok) sha = (await existing.json()).sha;

  // btoa needs a binary string, not raw bytes -- build it in chunks to avoid
  // blowing the call stack on a multi-MB Uint8Array.
  let binary = "";
  const bytes = new Uint8Array(videoBytes);
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  const b64 = btoa(binary);

  const r = await fetch(`https://api.github.com/repos/${VIDEO_REPO}/contents/${path}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN_VIDEO}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "shadow-gasp-bot",
    },
    body: JSON.stringify({
      message: `batch: day ${String(dayNum).padStart(2, "0")} hook video (via Telegram)`,
      content: b64,
      branch: "main",
      ...(sha ? { sha } : {}),
    }),
  });
  if (!r.ok) throw new Error(`Commit failed: ${r.status} ${await r.text()}`);
}

// "HH:MM" is read as IST wall-clock, next occurrence (today if still ahead of
// now, otherwise tomorrow) -- matches how the user actually talks about times
// ("5:15", "18:30"), converted to the UTC RFC3339 YouTube's publishAt needs.
// Always the NEXT calendar day at 05:15 IST, regardless of current time --
// used by the 5h hook-video timeout fallback, which must never publish same-day.
function nextDayFiveFifteenIST() {
  const nowUtc = new Date();
  const nowIst = new Date(nowUtc.getTime() + 5.5 * 3600 * 1000);
  const target = new Date(Date.UTC(
    nowIst.getUTCFullYear(), nowIst.getUTCMonth(), nowIst.getUTCDate() + 1,
    5, 15, 0
  ));
  const publishAtUtc = new Date(target.getTime() - 5.5 * 3600 * 1000);
  return publishAtUtc.toISOString().replace(/\.\d{3}Z$/, "Z");
}

function istTimeToPublishAt(hhmm) {
  const m = hhmm.match(/^(\d{1,2}):(\d{2})$/);
  if (!m) return null;
  const [, hh, mm] = m;
  const nowUtc = new Date();
  const nowIst = new Date(nowUtc.getTime() + 5.5 * 3600 * 1000);
  let target = new Date(Date.UTC(
    nowIst.getUTCFullYear(), nowIst.getUTCMonth(), nowIst.getUTCDate(),
    Number(hh), Number(mm), 0
  ));
  if (target.getTime() <= nowIst.getTime()) {
    target = new Date(target.getTime() + 24 * 3600 * 1000);
  }
  const publishAtUtc = new Date(target.getTime() - 5.5 * 3600 * 1000);
  return publishAtUtc.toISOString().replace(/\.\d{3}Z$/, "Z");
}

function approvalKeyboard(token) {
  return {
    inline_keyboard: [[
      { text: "✅ Approve", callback_data: `approve:${token}` },
      { text: "❌ Reject", callback_data: `reject:${token}` },
      { text: "\u{1F4C4} Increase Pages", callback_data: `pages_menu:${token}` },
    ]],
  };
}

// Mirrors PAGE_PRICE_TIERS in pipeline_lib/stage_and_deliver.py -- keep both
// in sync if the tiers ever change.
const PAGE_PRICE_TIERS = { 20: "0", 25: "2.99", 35: "3.99", 50: "4.99", 75: "6.99", 100: "8.99" };

function priceLabel(n) {
  return PAGE_PRICE_TIERS[n] === "0" ? `${n}pp (FREE)` : `${n}pp ($${PAGE_PRICE_TIERS[n]})`;
}

// Used before a build starts (/make), so the page count -- and therefore the
// price -- is a deliberate choice, not a silent 25pp/$2.99 default.
function makePageCountKeyboard() {
  return {
    inline_keyboard: [[20, 25, 35, 50, 75, 100].map((n) => ({
      text: priceLabel(n),
      callback_data: `make_pages:${n}`,
    }))],
  };
}

function pageCountKeyboard(token) {
  return {
    inline_keyboard: [[20, 35, 50, 75, 100].map((n) => ({
      text: priceLabel(n),
      callback_data: `set_pages:${token}:${n}`,
    }))],
  };
}

function confirmPublishKeyboard(token) {
  return {
    inline_keyboard: [[
      { text: "✅ Confirm Publish (goes LIVE)", callback_data: `confirm_publish:${token}` },
      { text: "↩️ Cancel", callback_data: `cancel_publish:${token}` },
    ]],
  };
}

async function handleCallback(env, cq) {
  const data = cq.data || "";
  const [action, token, extra] = data.split(":");
  const chatId = cq.message.chat.id;
  const messageId = cq.message.message_id;

  if (action === "pregen") {
    const n = parseInt(token, 10);
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `Starting ${n} days...` });
    await tg(env, "editMessageText", {
      chat_id: chatId, message_id: messageId,
      text: `\u{1F3AC} Generating ${n} new batch day(s) (case + script + 16 stills, vision-QA checked). This is sequential, so budget ~${n * 20}-${n * 30} min. I'll message you here once this chunk finishes.`,
    });
    try {
      await dispatchBatchPregen(env, { days: String(n), notify_chat_id: String(chatId) });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't start pregen: ${e.message}` });
    }
    return;
  }

  if (action === "make_pages") {
    const pages = token; // callback_data is "make_pages:<n>" -- no approval token involved
    const caseName = await env.PENDING.get(`awaiting_make:${chatId}`);
    if (caseName === null) {
      await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "This /make request expired -- send /make again" });
      return;
    }
    await env.PENDING.delete(`awaiting_make:${chatId}`);
    const label = priceLabel(parseInt(pages, 10));
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `Building at ${label}...` });
    await tg(env, "editMessageText", {
      chat_id: chatId, message_id: messageId,
      text: `\u{1F3AC} Building ${caseName ? `"${caseName}"` : "the next auto-picked case"} at ${label}.\nThis takes a while (script → art → OCR check → PDF). You'll get the draft here with buttons when it's done.`,
    });
    try {
      await dispatchPipeline(env, { case: caseName, target_pages: pages, dry_run: "false" });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't start build: ${e.message}` });
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
      chat_id: chatId, message_id: messageId,
      text: `Ready to publish "${entry.case}" (Gumroad draft ${entry.product_id}).\nConfirm to go LIVE, or Cancel to back out.`,
      reply_markup: confirmPublishKeyboard(token),
    });
  } else if (action === "reject") {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Rejecting..." });
    await tg(env, "editMessageText", {
      chat_id: chatId, message_id: messageId,
      text: `❌ Rejecting "${entry.case}"... deleting Gumroad draft.`,
    });
    await dispatchAction(env, {
      action: "reject", product_id: entry.product_id,
      chat_id: String(chatId), message_id: String(messageId),
    });
  } else if (action === "pages_menu") {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id });
    await tg(env, "editMessageText", {
      chat_id: chatId, message_id: messageId,
      text: `How many pages should "${entry.case}" be expanded to?`,
      reply_markup: pageCountKeyboard(token),
    });
  } else if (action === "set_pages") {
    const label = priceLabel(parseInt(extra, 10));
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `Regenerating at ${label}...` });
    await tg(env, "editMessageText", {
      chat_id: chatId, message_id: messageId,
      text: `\u{1F504} Regenerating "${entry.case}" at ${label}. This takes a while (script + art + build) — you'll get a new message when it's ready.`,
    });
    await dispatchAction(env, {
      action: "regenerate", case: entry.case, target_pages: extra,
      chat_id: String(chatId), message_id: String(messageId),
    });
  } else if (action === "confirm_publish") {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Publishing..." });
    await tg(env, "editMessageText", {
      chat_id: chatId, message_id: messageId,
      text: `Publishing "${entry.case}"...`,
    });
    await dispatchAction(env, {
      action: "publish", product_id: entry.product_id, case: entry.case,
      chat_id: String(chatId), message_id: String(messageId),
    });
  } else if (action === "cancel_publish") {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Cancelled" });
    await tg(env, "editMessageText", {
      chat_id: chatId, message_id: messageId,
      text: `Publish cancelled for "${entry.case}". Draft left as-is on Gumroad. Re-approve when ready.`,
      reply_markup: approvalKeyboard(token),
    });
  } else {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Unknown action" });
  }
}

// GitHub Actions (stage_and_deliver.py) can't write to this Worker's KV
// binding directly -- only code running inside the Worker can. So instead of
// a separate Cloudflare API token, the Action just POSTs the pending-approval
// details to this Worker's own public URL (protected by a shared secret it
// already has as a GitHub secret), and the Worker writes to its own KV and
// sends the Telegram message itself. Same pattern MindUnlocked uses: the
// Worker owns all state, GitHub Actions only does the heavy build work.
// Text commands, so a comic can be started from a phone without touching a
// terminal:
//   /make <case name>            -> asks how many pages (button picker, shows price)
//   /make <case name> | 50       -> explicit page count, skips the picker
//   /make                        -> let the pipeline auto-pick the next case
//
//   /short                       -> auto-pick case, generate script + stills, then wait for a Flow hook video (like /day)
//   /short <case name>           -> same, for a specific case
//
//   /day <N>                     -> sends day N's hook still + motion prompt, to feed into Google Flow
//   (reply with the Flow video)  -> commits it, renders (no upload yet)
//   /publish <N>                 -> render+upload day N to YouTube immediately
//   /publish <N> at <HH:MM>      -> same, but scheduled for that IST time (today or next occurrence)
async function handleMessage(env, msg) {
  const text = (msg.text || "").trim();
  const chatId = msg.chat.id;

  // A video (or a document that's actually a video, which Telegram uses for
  // files sent "as file" instead of compressed) arriving while a /day <N> is
  // pending is treated as that day's Flow hook clip -- no reply-threading
  // required, just "the most recent /day this chat asked about".
  const videoObj = msg.video || (msg.document && msg.document.mime_type?.startsWith("video/") ? msg.document : null);
  if (videoObj) {
    // A short-pipeline hook-wait (fresh auto-picked day, 5h deadline) takes
    // priority over a manual /day <N> pending in the same chat -- it's the
    // one with a hard timeout riding on it.
    let dayNum = null;
    let shortPending = false;
    const shortRaw = await env.PENDING.get(`awaiting_short_hook:${chatId}`);
    if (shortRaw) {
      dayNum = String(JSON.parse(shortRaw).day);
      shortPending = true;
    } else {
      dayNum = await env.PENDING.get(`awaiting_hook:${chatId}`);
    }
    if (!dayNum) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "Got a video, but no day is waiting on a hook clip -- send /day <N> first so I know which day this belongs to." });
      return;
    }
    await tg(env, "sendMessage", { chat_id: chatId, text: `\u{1F4E5} Got it — committing as day ${dayNum}'s hook video, then rendering + uploading to YouTube automatically. I'll confirm here once it's live.` });
    try {
      const fileInfo = await tg(env, "getFile", { file_id: videoObj.file_id });
      if (!fileInfo.ok) throw new Error(`getFile failed: ${JSON.stringify(fileInfo)}`);
      const fileUrl = `https://api.telegram.org/file/bot${env.TELEGRAM_BOT_TOKEN}/${fileInfo.result.file_path}`;
      const fileResp = await fetch(fileUrl);
      if (!fileResp.ok) throw new Error(`file download failed: ${fileResp.status}`);
      const videoBytes = await fileResp.arrayBuffer();

      await commitHookVideo(env, dayNum, videoBytes);
      // upload: "true" -- end to end, no /publish step needed. finish_batch_day.yml's
      // upload job POSTs back to this Worker's /batch/uploaded once it's actually
      // live on YouTube (see that endpoint below), which is what sends the real
      // confirmation -- this message just confirms the render/upload STARTED.
      await dispatchFinishBatchDay(env, { day: dayNum, upload: "true", publish_at: "", notify_chat_id: String(chatId) });
      await env.PENDING.delete(shortPending ? `awaiting_short_hook:${chatId}` : `awaiting_hook:${chatId}`);

      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `\u{1F680} Day ${dayNum} hook video committed. Rendering + uploading to YouTube now (~15-20 min) — I'll message you here the moment it's live.`,
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't process the video: ${e.message}` });
    }
    return;
  }

  if (text.startsWith("/freeclaims")) {
    const slug = text.slice("/freeclaims".length).trim();
    if (!slug) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "Usage: /freeclaims <slug>, e.g. /freeclaims norjak" });
      return;
    }
    const count = parseInt((await env.PENDING.get(`free_codes_count:${slug}`)) || "0", 10);
    await tg(env, "sendMessage", { chat_id: chatId, text: `\u{1F381} ${slug}: ${count} one-time code(s) issued so far.` });
    return;
  }

  if (text.startsWith("/gencode")) {
    const rest = text.slice("/gencode".length).trim();
    const [slug, capStr] = rest.split(/\s+/);
    if (!slug) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "Usage: /gencode <slug> [cap], e.g. /gencode norjak 50" });
      return;
    }
    const raw = await env.PENDING.get(`free_offer:${slug}`);
    if (!raw) {
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `No product registered for "${slug}" yet. Register it once with the product_id first (ask Claude), then /gencode will work from here on.`,
      });
      return;
    }
    const { product_id } = JSON.parse(raw);
    const cap = capStr && /^\d+$/.test(capStr) ? capStr : "50";
    try {
      await dispatchGenCode(env, { slug, product_id, cap, chat_id: String(chatId) });
      await tg(env, "sendMessage", { chat_id: chatId, text: `\u{1F504} Generating a one-time code for "${slug}" (cap ${cap}) — I'll DM it here shortly.` });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't start code generation: ${e.message}` });
    }
    return;
  }

  if (text.startsWith("/pregen")) {
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: "How many new batch days should I generate (case + script + 16 stills each, no hook video yet)? Each day takes ~15-30 min, sequentially.",
      reply_markup: pregenKeyboard(),
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
      const shot1Url = `https://raw.githubusercontent.com/${VIDEO_REPO}/main/_pipeline/batch/day${dd}/shot1.jpeg`;
      await env.PENDING.put(`awaiting_hook:${chatId}`, String(dayNum), { expirationTtl: 86400 });
      await tg(env, "sendPhoto", {
        chat_id: chatId,
        photo: shot1Url,
        caption: `Day ${dayNum}: "${meta.title_working}"\n\nMotion prompt for Google Flow:\n${meta.hook_motion_prompt}\n\nReply here with the finished Flow video when ready.`,
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't load day ${dayNum}: ${e.message}` });
    }
    return;
  }

  if (text.startsWith("/publish")) {
    const rest = text.slice("/publish".length).trim();
    const atMatch = rest.match(/^(\d+)\s+at\s+(\d{1,2}:\d{2})$/i);
    const dayNum = atMatch ? parseInt(atMatch[1], 10) : parseInt(rest, 10);
    if (!dayNum) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "Usage: /publish <N>  or  /publish <N> at <HH:MM> (IST)" });
      return;
    }
    let publishAt = "";
    if (atMatch) {
      publishAt = istTimeToPublishAt(atMatch[2]);
      if (!publishAt) {
        await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't parse time "${atMatch[2]}" — use HH:MM` });
        return;
      }
    }
    try {
      await dispatchFinishBatchDay(env, { day: String(dayNum), upload: "true", publish_at: publishAt, notify_chat_id: String(chatId) });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't start publish: ${e.message}` });
      return;
    }
    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: publishAt
        ? `\u{1F4C5} Rendering day ${dayNum} and scheduling for ${atMatch[2]} IST. Check Actions for progress.`
        : `\u{1F680} Rendering + publishing day ${dayNum} to YouTube now. Check Actions for progress.`,
    });
    return;
  }

  if (text.startsWith("/short")) {
    const rest = text.slice("/short".length).trim();
    const bar = rest.lastIndexOf("|");
    const caseName = bar !== -1 ? rest.slice(0, bar).trim() : rest;

    try {
      await dispatchVideoPipeline(env, { case: caseName });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't start short: ${e.message}` });
      return;
    }

    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: `\u{1F3AC} Building short: ${caseName ? `"${caseName}"` : "next auto-picked case"} (script -> FLUX stills on GitHub Actions, ~15-25 min). It'll land as a new batch day and I'll DM you the hook still + Flow motion prompt here, same as /day -- reply with the Flow video within 5h or it auto-falls-back to a static cut, scheduled for the next 05:15 IST slot.`,
    });
    return;
  }

  if (!text.startsWith("/make")) {
    if (text.startsWith("/")) {
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: "Commands:\n/make <case name>  — build a comic (asks how many pages first)\n/make <case name> | 50  — build now, explicit page count (skips the picker)\n/make  — auto-pick the next comic case (still asks pages)\n\n/gencode <slug> [cap]  — mint a ONE-TIME free code for a published comic, DM'd here (default cap 50). Send the code to one person only — it stops working after their first use.\n/freeclaims <slug>  — check how many one-time codes have been issued so far\n\n/short  — auto-pick + generate a new true-crime short's script+stills, then DM the hook still + Flow prompt (5h reply window, else auto-falls-back to a static cut scheduled for 05:15 IST)\n/short <case>  — same, for a specific case\n\n/day <N>  — get day N's hook still + Flow prompt from the batch\n(reply with the Flow video)  — commits it, renders + uploads to YouTube automatically\n/publish <N>  — render + upload day N now\n/publish <N> at <HH:MM>  — same, scheduled for that IST time",
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
    // Explicit "| N" still skips the picker -- you already made the choice.
    if (/^\d+$/.test(n)) {
      try {
        await dispatchPipeline(env, { case: caseName, target_pages: n, dry_run: "false" });
      } catch (e) {
        await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't start build: ${e.message}` });
        return;
      }
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `\u{1F3AC} Building ${caseName ? `"${caseName}"` : "the next auto-picked case"} at ${priceLabel(parseInt(n, 10))}.\nThis takes a while (script → art → OCR check → PDF). You'll get the draft here with buttons when it's done.`,
      });
      return;
    }
  }

  // No explicit page count -- ask instead of silently defaulting to 25pp/$2.99.
  await env.PENDING.put(`awaiting_make:${chatId}`, caseName, { expirationTtl: 3600 });
  await tg(env, "sendMessage", {
    chat_id: chatId,
    text: `How many pages should ${caseName ? `"${caseName}"` : "the next auto-picked case"} be?`,
    reply_markup: makePageCountKeyboard(),
  });
}

async function sendApprovalMessage(env, { token, caseName, productId, title }) {
  // The Action already sent the PDF itself as a plain document (it has the
  // bytes locally right after building it) -- this Worker follows up with a
  // separate buttoned text message referencing that same draft, since the
  // Action has no way to attach Telegram buttons to its own upload without
  // first registering the token/product mapping here.
  return tg(env, "sendMessage", {
    chat_id: env.TELEGRAM_CHAT_ID,
    text: `${title} — draft ready for review (Gumroad draft: ${productId})`,
    reply_markup: approvalKeyboard(token),
  });
}

// Cron-triggered sweep (see wrangler.toml's [triggers]) for /short/ready
// hook-video requests whose 5h deadline has passed with no reply. Falls
// back to a static (no Flow, no CogVideoX) render, scheduled for the next
// 05:15 IST slot rather than publishing hookless immediately.
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
        use_cog_fallback: "false",
      });
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `\u{23F0} No Flow hook video for day ${String(day).padStart(2, "0")} within 5 hours — falling back to a static cut, rendering now and scheduling it for tomorrow 05:15 IST.`,
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Day ${day}'s hook-video deadline passed and the static-fallback dispatch failed: ${e.message}. Use /publish ${day} to retry manually.` });
    }
    await env.PENDING.delete(key.name);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Records which Gumroad product a case slug maps to (product_id), so
    // /gencode doesn't need it typed in by hand every time. The `code`/
    // `offer_code_id` fields here are leftover from an earlier one-shared-
    // code design that was replaced by per-requester single-use codes (see
    // /free-codes/reserve + gen_code.yml below) -- kept only for the
    // product_id lookup, safe to ignore otherwise.
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

    // Reserve one slot out of the overall "first N free" cap BEFORE a new
    // single-use code is created (gen_code.yml calls this first). Each
    // individual Gumroad code only caps at 1 use -- Gumroad has no concept of
    // an aggregate cap across many separate codes -- so this counter, not
    // Gumroad, is what actually enforces the total N. KV increments aren't
    // perfectly atomic under concurrent requests, but this is a manual,
    // one-person, one-at-a-time DM flow -- a worst-case off-by-one here isn't
    // worth the complexity of a Durable Object.
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
      const current = parseInt((await env.PENDING.get(key)) || "0", 10);
      if (current >= cap) {
        return new Response(JSON.stringify({ error: "cap reached", count: current }), {
          status: 409, headers: { "Content-Type": "application/json" },
        });
      }
      const next = current + 1;
      await env.PENDING.put(key, String(next));
      return new Response(JSON.stringify({ ok: true, count: next }), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    }

    // Auth-gated, NOT a public landing-page widget: the free code is being
    // handed out manually (user DMs it to whoever messages them on Facebook,
    // up to the cap), so this must never be reachable by anyone who doesn't
    // already have the shared secret -- an unauthenticated version of this
    // would leak the code to anyone who found the URL, bypassing the entire
    // point of gating it behind a DM. Private "how many have I given out"
    // check only.
    if (request.method === "GET" && url.pathname.startsWith("/free-claims/")) {
      const auth = request.headers.get("X-Shared-Secret");
      if (auth !== env.WORKER_SHARED_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const slug = url.pathname.slice("/free-claims/".length);
      const raw = await env.PENDING.get(`free_offer:${slug}`);
      if (!raw) {
        return new Response(JSON.stringify({ error: "no free offer configured for this slug" }), {
          status: 404, headers: { "Content-Type": "application/json" },
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
        code, cap, claimed, remaining: Math.max(0, cap - claimed), sold_out: claimed >= cap,
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

    // Script-generation cache: cases/ (script, art, PDF) is deliberately
    // NEVER committed to this public repo -- it's wiped by `rm -rf cases/`
    // at the end of every run, success or failure, so a paid comic can't be
    // downloaded free straight from git history. That's correct for art/PDF,
    // but it meant a retry after a LATER step failed (Kaggle auth, OCR, Gumroad)
    // silently re-billed the Anthropic API for a script that already generated
    // fine. The Worker's KV is private (not browsable/downloadable the way repo
    // content is), so it's a safe place to cache just the script+prompts JSON
    // across retries of the SAME case+page-count, same trust boundary as the
    // existing /register endpoint. Key includes target_pages because a 25pp
    // and a 75pp script for the same case are different content.
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
      // 7 days is plenty for a retry cycle without letting stale scripts
      // (e.g. after a manual case-content edit) live in KV forever.
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
      // finish_batch_day.yml's upload job calls this once a batch day is
      // actually live on YouTube and/or crossposted to Facebook/Instagram --
      // separate secret from /register's WORKER_SHARED_SECRET (that one
      // belongs to the comic pipeline; this is scoped to the video
      // pipeline's own GitHub repo secrets).
      //
      // video_id, fb_post_id and ig_media_id are all optional individually
      // (a youtube_upload=false crosspost-only re-run has no video_id at
      // all) but at least one must be present, otherwise nothing actually
      // went live and there's nothing to confirm. Before this, the workflow
      // itself skipped calling this endpoint entirely whenever video_id was
      // empty -- so a crosspost-only run (e.g. re-grading day7 and posting
      // to FB/IG without re-uploading to YouTube) finished successfully with
      // no Telegram confirmation at all, silently.
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { day, case: caseName, video_id, drive_link, fb_post_id, ig_media_id, chat_id } = body;
      if (!day || (!video_id && !fb_post_id && !ig_media_id)) {
        return new Response("missing fields", { status: 400 });
      }
      const lines = [];
      if (video_id) {
        lines.push(`✅ Day ${day} is LIVE on YouTube: https://youtu.be/${video_id}`);
      } else {
        lines.push(`✅ Day ${day} crossposted (YouTube upload skipped this run):`);
      }
      if (caseName) lines.push(`"${caseName}"`);
      if (fb_post_id) lines.push(`\u{1F4D8} Facebook: https://facebook.com/${fb_post_id}`);
      if (ig_media_id) lines.push(`\u{1F4F7} Instagram media_id: ${ig_media_id}`);
      if (drive_link) lines.push(`\u{1F4F9} Video file: ${drive_link}`);
      await tg(env, "sendMessage", {
        chat_id: chat_id || env.TELEGRAM_CHAT_ID,
        text: lines.join("\n"),
      });
      return new Response("ok", { status: 200 });
    }

    if (request.method === "POST" && url.pathname === "/batch/pregen_done") {
      // _batch_pregen.py calls this once its chunk finishes, so /pregen's
      // "I'll message you here" promise is real instead of silent.
      const auth = request.headers.get("X-Batch-Notify-Secret");
      if (auth !== env.BATCH_NOTIFY_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const { new_days_done, through_day, batch_complete, chat_id } = body;
      const text = batch_complete
        ? `\u{1F389} All 30 days generated! Batch pregen is fully complete through day ${through_day}. Use /day <N> to pull a still + prompt for Google Flow whenever you're ready.`
        : `\u{1F4E6} Pregen chunk done: ${new_days_done} new day(s) generated, through day ${through_day}. Next chunk auto-starting -- I'll message you again once that finishes. Use /day <N> anytime to pull a still + prompt for Google Flow.`;
      await tg(env, "sendMessage", { chat_id: chat_id || env.TELEGRAM_CHAT_ID, text });
      return new Response("ok", { status: 200 });
    }

    if (request.method === "POST" && url.pathname === "/short/ready") {
      // pipeline.yml's daily/auto-picked run calls this once script+stills
      // are committed as a new batch day, so it gets the exact same
      // hook-video request treatment as manual /day <N> -- except with a 5h
      // deadline: env.PENDING.list() below is swept by the cron trigger
      // (see `scheduled` export), and if nothing arrives in time it falls
      // back to a static render, scheduled for the next 05:15 IST slot,
      // instead of publishing hookless same-day.
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
        const shot1Url = `https://raw.githubusercontent.com/${VIDEO_REPO}/main/_pipeline/batch/day${dd}/shot1.jpeg`;
        const deadline = Date.now() + 5 * 3600 * 1000;
        // TTL well past the 5h deadline so the cron sweep (runs every 15 min)
        // is always the thing that expires this, not KV eviction racing it.
        await env.PENDING.put(`awaiting_short_hook:${chatId}`, JSON.stringify({ day: String(day), deadline }), { expirationTtl: 8 * 3600 });
        await tg(env, "sendPhoto", {
          chat_id: chatId,
          photo: shot1Url,
          caption: `Day ${dd}: "${meta.title_working}"${caseName ? ` (${caseName})` : ""}\n\nMotion prompt for Google Flow:\n${meta.hook_motion_prompt}\n\nReply here with the finished Flow video within 5 hours, or I'll fall back to a static cut and schedule it for tomorrow 05:15 IST.`,
        });
      } catch (e) {
        await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Day ${dd} generated but I couldn't send the hook-video request: ${e.message}. Use /day ${day} to retry manually.` });
      }
      return new Response("ok", { status: 200 });
    }

    if (request.method === "POST" && url.pathname === "/short/sweep") {
      // Driven by a GitHub Actions cron (sweep_hook_waits.yml, every 15 min),
      // not a Cloudflare Cron Trigger -- this account is already at the
      // Workers Free plan's 5-cron-trigger cap from other pipelines, so a
      // native `scheduled` trigger can't be added here without a plan
      // upgrade. Same effect, driven externally instead.
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
  },
};
