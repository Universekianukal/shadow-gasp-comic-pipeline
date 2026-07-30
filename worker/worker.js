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

async function dispatchFinishBatchDay(env, inputs) {
  const r = await fetch(
    `https://api.github.com/repos/${VIDEO_REPO}/actions/workflows/finish_batch_day.yml/dispatches`,
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

function pageCountKeyboard(token) {
  return {
    inline_keyboard: [[35, 50, 75, 100].map((n) => ({
      text: String(n),
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
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `Regenerating at ${extra} pages...` });
    await tg(env, "editMessageText", {
      chat_id: chatId, message_id: messageId,
      text: `\u{1F504} Regenerating "${entry.case}" at ${extra} pages. This takes a while (script + art + build) — you'll get a new message when it's ready.`,
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
//   /make <case name>            -> 25 pages (default)
//   /make <case name> | 50       -> explicit page count
//   /make                        -> let the pipeline auto-pick the next case
//
//   /short                       -> auto-pick case, high quality, no upload (test run)
//   /short <case name>           -> specific case, high quality, no upload
//   /short <case name> | draft   -> faster/cheaper render for a pipeline smoke-test
//   /short <case name> | upload  -> also upload the result to YouTube when done
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
    const dayNum = await env.PENDING.get(`awaiting_hook:${chatId}`);
    if (!dayNum) {
      await tg(env, "sendMessage", { chat_id: chatId, text: "Got a video, but no /day <N> is pending -- send /day <N> first so I know which day this belongs to." });
      return;
    }
    await tg(env, "sendMessage", { chat_id: chatId, text: `\u{1F4E5} Got it — committing as day ${dayNum}'s hook video and starting a render (no upload yet)...` });
    try {
      const fileInfo = await tg(env, "getFile", { file_id: videoObj.file_id });
      if (!fileInfo.ok) throw new Error(`getFile failed: ${JSON.stringify(fileInfo)}`);
      const fileUrl = `https://api.telegram.org/file/bot${env.TELEGRAM_BOT_TOKEN}/${fileInfo.result.file_path}`;
      const fileResp = await fetch(fileUrl);
      if (!fileResp.ok) throw new Error(`file download failed: ${fileResp.status}`);
      const videoBytes = await fileResp.arrayBuffer();

      await commitHookVideo(env, dayNum, videoBytes);
      await dispatchFinishBatchDay(env, { day: dayNum, upload: "false", publish_at: "" });
      await env.PENDING.delete(`awaiting_hook:${chatId}`);

      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: `✅ Day ${dayNum} hook video committed, render running now. Once you've confirmed it looks right, use /publish ${dayNum} (or /publish ${dayNum} at HH:MM to schedule).`,
      });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't process the video: ${e.message}` });
    }
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
      await dispatchFinishBatchDay(env, { day: String(dayNum), upload: "true", publish_at: publishAt });
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
    let caseName = rest;
    let quality = "high";
    let upload = "false";
    const bar = rest.lastIndexOf("|");
    if (bar !== -1) {
      caseName = rest.slice(0, bar).trim();
      const flag = rest.slice(bar + 1).trim().toLowerCase();
      if (flag === "draft" || flag === "standard" || flag === "high") quality = flag;
      else if (flag === "upload") upload = "true";
    }

    try {
      await dispatchVideoPipeline(env, { case: caseName, quality, upload });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't start short: ${e.message}` });
      return;
    }

    await tg(env, "sendMessage", {
      chat_id: chatId,
      text: `\u{1F3AC} Building short: ${caseName ? `"${caseName}"` : "next auto-picked case"} (${quality} quality${upload === "true" ? ", will upload to YouTube" : ", no upload"}).\nThis runs script -> TTS -> FLUX stills -> hook clip -> render on GitHub Actions, expect 30-60+ min. Check the Actions tab for progress.`,
    });
    return;
  }

  if (!text.startsWith("/make")) {
    if (text.startsWith("/")) {
      await tg(env, "sendMessage", {
        chat_id: chatId,
        text: "Commands:\n/make <case name>  — build a comic (25 pages)\n/make <case name> | 50  — set page count\n/make  — auto-pick the next comic case\n\n/short  — auto-pick + build a true-crime short (test run, no upload)\n/short <case>  — build a specific case\n/short <case> | draft  — faster render for testing\n/short <case> | upload  — build and upload to YouTube\n\n/day <N>  — get day N's hook still + Flow prompt from the 30-day batch\n(reply with the Flow video)  — commits it, renders (no upload yet)\n/publish <N>  — render + upload day N now\n/publish <N> at <HH:MM>  — same, scheduled for that IST time",
      });
    }
    return;
  }

  const rest = text.slice("/make".length).trim();
  let caseName = rest;
  let pages = "25";
  const bar = rest.lastIndexOf("|");
  if (bar !== -1) {
    caseName = rest.slice(0, bar).trim();
    const n = rest.slice(bar + 1).trim();
    if (/^\d+$/.test(n)) pages = n;
  }

  try {
    await dispatchPipeline(env, { case: caseName, target_pages: pages, dry_run: "false" });
  } catch (e) {
    await tg(env, "sendMessage", { chat_id: chatId, text: `❌ Couldn't start build: ${e.message}` });
    return;
  }

  await tg(env, "sendMessage", {
    chat_id: chatId,
    text: `\u{1F3AC} Building ${caseName ? `"${caseName}"` : "the next auto-picked case"} at ${pages} pages.\nThis takes a while (script → art → OCR check → PDF). You'll get the draft here with buttons when it's done.`,
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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

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
