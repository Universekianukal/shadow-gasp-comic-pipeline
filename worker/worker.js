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
async function handleMessage(env, msg) {
  const text = (msg.text || "").trim();
  const chatId = msg.chat.id;

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
        text: "Commands:\n/make <case name>  — build a comic (25 pages)\n/make <case name> | 50  — set page count\n/make  — auto-pick the next comic case\n\n/short  — auto-pick + build a true-crime short (test run, no upload)\n/short <case>  — build a specific case\n/short <case> | draft  — faster render for testing\n/short <case> | upload  — build and upload to YouTube",
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
