/* =========================================================================
   LAMPLIGHT — Hindu Scriptures chat controller
   Vanilla JS. Three-pane editorial shell with motion. Talks to the real
   /api/* backend (query, agent stream, voices, auth). Multi-session history
   lives in localStorage; the active conversation also syncs to the server
   for signed-in users.
   ========================================================================= */
(function () {
  "use strict";

  if (!document.getElementById("app")) return;

  /* ------------------------------------------------------------ api base */
  var RAG_PREFIX = (document.body.getAttribute("data-api-base") || "").replace(/\/$/, "");
  function ragApiUrl(path) {
    return RAG_PREFIX + path;
  }
  function csrfHeaders() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    var token = meta ? meta.getAttribute("content") : "";
    var h = { "Content-Type": "application/json" };
    if (token) h["X-CSRFToken"] = token;
    return h;
  }

  var prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ------------------------------------------------------------ dom refs */
  var app           = document.getElementById("app");
  var mainEl        = document.getElementById("main");
  var rail          = document.getElementById("rail");
  var railToggle    = document.getElementById("railToggle");
  var sessionsList  = document.getElementById("sessions");
  var newRailBtn    = document.getElementById("newRail");
  var newChatBtn    = document.getElementById("newChat");
  var scrollArea    = document.getElementById("scroll");
  var thread        = document.getElementById("thread");
  var welcome       = document.getElementById("welcome");
  var headerName    = document.getElementById("headerName");
  var input         = document.getElementById("input");
  var sendBtn       = document.getElementById("send");
  var themeToggle   = document.getElementById("themeToggle");
  var scrim         = document.getElementById("scrim");
  var corpusBadge   = document.getElementById("corpusBadge");
  var promptsEl     = document.getElementById("prompts");

  var citationsBtn   = document.getElementById("citationsBtn");
  var citationsCount = document.getElementById("citationsCount");
  var citationsClose = document.getElementById("citationsClose");
  var citationsList  = document.getElementById("citationsList");
  var pill           = document.getElementById("pill");
  var pillCount      = document.getElementById("pillCount");

  var verseLeaf    = document.getElementById("verseLeaf");
  var verseRef     = document.getElementById("verseRef");
  var verseDev     = document.getElementById("verseDev");
  var verseIast    = document.getElementById("verseIast");
  var verseEng     = document.getElementById("verseEng");
  var verseExplain = document.getElementById("verseExplain");
  var verseApply   = document.getElementById("verseApply");

  var drawerOverlay   = document.getElementById("drawerOverlay");
  var drawerClose     = document.getElementById("drawerClose");
  var settingsBtn     = document.getElementById("settingsBtn");
  var voiceList       = document.getElementById("voiceList");
  var clearHistoryBtn = document.getElementById("clearHistoryBtn");

  var authUserLabel = document.getElementById("authUserLabel");
  var guestHint     = document.getElementById("guestHint");
  var loginBtn      = document.getElementById("loginBtn");
  var signupBtn     = document.getElementById("signupBtn");
  var logoutBtn     = document.getElementById("logoutBtn");
  var acctAvatar    = document.getElementById("acctAvatar");

  /* ------------------------------------------------------------ state */
  var isStreaming = false;
  var abortController = null;
  var useServerChat = false;
  var currentVoice = localStorage.getItem("hs-voice") || "elder";

  var unread = 0;
  var stickToBottom = true;
  var lastMobile = false;

  var store = null;          /* { activeId, sessions: [...] } */
  var currentSources = [];   /* sources of the latest reply, for the panel */

  var SESSIONS_KEY = "hs-sessions-v1";
  var MAX_STORED = 50;       /* messages kept per session */
  var MAX_SESSIONS = 30;
  var REQUEST_TIMEOUT_MS = 75000;

  var SEND_ICON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">' +
    '<line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
  var STOP_ICON =
    '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"></rect></svg>';

  var PROMPTS = [
    { topic: "Gītā",       label: "Overcoming anxiety & fear",      q: "What does the Bhagavad Gita say about overcoming anxiety and fear?" },
    { topic: "Upaniṣads",       label: "Brahman in the Upaniṣads",  q: "Explain the concept of Brahman in the Upanishads with key verses" },
    { topic: "Mahābhārata", label: "The meaning of dharma",         q: "What is the meaning of dharma according to the Mahabharata?" },
    { topic: "Comparison",           label: "Bhakti — Gītā vs Rāmcaritmānas", q: "Compare the teachings on devotion in the Gita versus the Ramcharitmanas" },
    { topic: "All schools",          label: "BG 2.47 across schools",         q: "What do different schools of philosophy say about Bhagavad Gita verse 2.47?" },
    { topic: "Rigveda",              label: "Hymns of creation",              q: "What does the Rigveda say about creation?" }
  ];

  /* ====================================================================
     Legacy PWA cleanup — retire the old offline shell
     ==================================================================== */
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.getRegistrations().then(function (regs) {
      regs.forEach(function (reg) {
        var worker = reg.active || reg.waiting || reg.installing;
        if (!worker || !worker.scriptURL) return;
        try {
          if (new URL(worker.scriptURL).pathname.indexOf("/static/sw.js") !== -1) reg.unregister();
        } catch (e) { /* ignore */ }
      });
    }).catch(function () {});
  }
  if ("caches" in window) {
    caches.keys().then(function (keys) {
      keys.forEach(function (key) { if (/^hs-rag-/.test(key)) caches.delete(key); });
    }).catch(function () {});
  }

  /* ====================================================================
     Theme
     ==================================================================== */
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("hs-theme", theme); } catch (e) { /* ignore */ }
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = theme === "dark" ? "#0e0a06" : "#faf4e6";
  }
  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }
  function toggleTheme() {
    var next = currentTheme() === "dark" ? "light" : "dark";
    if (document.startViewTransition && !prefersReducedMotion) {
      document.startViewTransition(function () { applyTheme(next); });
    } else {
      applyTheme(next);
    }
  }

  /* ====================================================================
     Session store (localStorage multi-session)
     ==================================================================== */
  function uid() {
    return "s_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }
  function newSession() {
    var now = Date.now();
    return { id: uid(), title: "", createdAt: now, updatedAt: now, messages: [] };
  }
  function deriveTitle(messages) {
    for (var i = 0; i < messages.length; i++) {
      if (messages[i] && messages[i].role === "user" && messages[i].content) {
        var t = String(messages[i].content).trim().replace(/\s+/g, " ");
        return t.length > 56 ? t.slice(0, 56) + "…" : t;
      }
    }
    return "";
  }
  function tryMigrateLegacy() {
    var keys = ["hs-conversations"];
    for (var i = 0; i < keys.length; i++) {
      try {
        var raw = localStorage.getItem(keys[i]);
        if (!raw) continue;
        var msgs = JSON.parse(raw);
        if (Array.isArray(msgs) && msgs.length) {
          var s = newSession();
          s.messages = msgs.slice(-MAX_STORED);
          s.title = deriveTitle(s.messages);
          localStorage.removeItem(keys[i]);
          return { activeId: s.id, sessions: [s] };
        }
      } catch (e) { /* ignore */ }
    }
    return null;
  }
  function freshStore() {
    var migrated = tryMigrateLegacy();
    if (migrated) return migrated;
    var s = newSession();
    return { activeId: s.id, sessions: [s] };
  }
  function loadStore() {
    var raw = null;
    try { raw = localStorage.getItem(SESSIONS_KEY); } catch (e) { /* ignore */ }
    if (raw) {
      try {
        var parsed = JSON.parse(raw);
        if (parsed && Array.isArray(parsed.sessions)) {
          parsed.sessions = parsed.sessions.filter(function (s) { return s && s.id; });
          parsed.sessions.forEach(function (s) {
            if (!Array.isArray(s.messages)) s.messages = [];
            if (typeof s.title !== "string") s.title = "";
            if (!s.createdAt) s.createdAt = Date.now();
            if (!s.updatedAt) s.updatedAt = s.createdAt;
          });
          if (parsed.sessions.length) {
            if (!parsed.activeId || !parsed.sessions.some(function (s) { return s.id === parsed.activeId; })) {
              parsed.activeId = parsed.sessions[0].id;
            }
            store = parsed;
            return;
          }
        }
      } catch (e) { /* ignore */ }
    }
    store = freshStore();
  }
  function getActive() {
    var s = null;
    for (var i = 0; i < store.sessions.length; i++) {
      if (store.sessions[i].id === store.activeId) { s = store.sessions[i]; break; }
    }
    if (!s) {
      if (!store.sessions.length) store.sessions.push(newSession());
      s = store.sessions[0];
      store.activeId = s.id;
    }
    return s;
  }
  function pruneSessions() {
    if (store.sessions.length <= MAX_SESSIONS) return;
    var kept = store.sessions.slice().sort(function (a, b) { return b.updatedAt - a.updatedAt; });
    var activeId = store.activeId;
    kept = kept.filter(function (s, i) { return i < MAX_SESSIONS || s.id === activeId; });
    store.sessions = kept;
  }
  function saveStore(opts) {
    pruneSessions();
    try { localStorage.setItem(SESSIONS_KEY, JSON.stringify(store)); } catch (e) { /* ignore */ }
    if (useServerChat && !(opts && opts.skipServer)) {
      fetch("/api/chat/state", {
        method: "PUT",
        credentials: "same-origin",
        headers: csrfHeaders(),
        body: JSON.stringify({ messages: getActive().messages.slice(-MAX_STORED) })
      }).catch(function () {});
    }
  }
  function sessionTitle(s) {
    return s.title || "New conversation";
  }

  /* ====================================================================
     Relative time
     ==================================================================== */
  function formatWhen(ts) {
    var d = new Date(ts);
    var now = new Date();
    if (d.toDateString() === now.toDateString()) {
      return "Today · " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    var y = new Date(now);
    y.setDate(now.getDate() - 1);
    if (d.toDateString() === y.toDateString()) return "Yesterday";
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  }

  /* ====================================================================
     Rail — session list
     ==================================================================== */
  function renderRail(stagger) {
    sessionsList.innerHTML = "";
    var sorted = store.sessions.slice().sort(function (a, b) { return b.updatedAt - a.updatedAt; });
    sorted.forEach(function (s, i) {
      var li = document.createElement("li");
      li.className = "rail-item" + (s.id === store.activeId ? " active" : "");
      li.setAttribute("data-id", s.id);

      var open = document.createElement("button");
      open.type = "button";
      open.className = "rail-item-open";
      var title = document.createElement("span");
      title.className = "rail-item-title";
      title.textContent = sessionTitle(s);
      var when = document.createElement("span");
      when.className = "when";
      when.textContent = formatWhen(s.updatedAt);
      open.appendChild(title);
      open.appendChild(when);
      open.addEventListener("click", function () { switchSession(s.id); });

      var del = document.createElement("button");
      del.type = "button";
      del.className = "rail-item-del";
      del.setAttribute("aria-label", "Delete conversation");
      del.innerHTML = "&times;";
      del.addEventListener("click", function (e) {
        e.stopPropagation();
        deleteSession(s.id);
      });

      li.appendChild(open);
      li.appendChild(del);

      if (stagger && !prefersReducedMotion) {
        li.style.opacity = "0";
        li.style.transform = "translateX(-8px)";
        li.style.transition = "opacity 360ms var(--ease-out-quart), transform 360ms var(--ease-out-expo)";
        setTimeout(function () { li.style.opacity = ""; li.style.transform = ""; }, 120 + i * 36);
      }
      sessionsList.appendChild(li);
    });
  }

  function switchSession(id) {
    if (isStreaming) return;
    if (id === store.activeId) {
      if (isMobile()) collapseRail();
      return;
    }
    store.activeId = id;
    saveStore({ skipServer: true });
    renderRail();
    renderActiveThread();
    if (isMobile()) collapseRail();
  }

  function deleteSession(id) {
    if (isStreaming) return;
    var idx = -1;
    for (var i = 0; i < store.sessions.length; i++) {
      if (store.sessions[i].id === id) { idx = i; break; }
    }
    if (idx === -1) return;
    var wasActive = store.sessions[idx].id === store.activeId;
    store.sessions.splice(idx, 1);
    if (!store.sessions.length) store.sessions.push(newSession());
    if (wasActive) {
      var newest = store.sessions.slice().sort(function (a, b) { return b.updatedAt - a.updatedAt; })[0];
      store.activeId = newest.id;
    }
    saveStore({ skipServer: true });
    renderRail();
    if (wasActive) renderActiveThread();
  }

  function createSession() {
    if (isStreaming) return;
    var s = newSession();
    store.sessions.push(s);
    store.activeId = s.id;
    saveStore({ skipServer: true });
    renderRail();
    renderActiveThread();
    input.focus();
    if (isMobile()) collapseRail();
  }

  /* ====================================================================
     Render the active conversation
     ==================================================================== */
  function renderActiveThread() {
    var active = getActive();
    thread.innerHTML = "";
    currentSources = [];
    updateCitationsAffordance();
    closeCitations();
    if (active.messages.length) {
      welcome.hidden = true;
      active.messages.forEach(function (m) {
        if (m.role === "user") {
          addMessage("user", m.content);
        } else if (m.role === "assistant") {
          var refs = addMessage("assistant", "");
          refs.content.innerHTML = renderMarkdown(m.content || "");
          addCopyButton(refs.content);
        }
      });
    } else {
      welcome.hidden = false;
    }
    headerName.textContent = sessionTitle(active);
    instantScrollToBottom();
  }

  /* ====================================================================
     Messages
     ==================================================================== */
  function addMessage(role, text) {
    var msg = document.createElement("div");
    msg.className = "msg " + (role === "user" ? "from-user" : "from-bot");

    var who = document.createElement("div");
    who.className = "who";
    var dot = document.createElement("span");
    dot.className = "dot";
    who.appendChild(dot);
    who.appendChild(document.createTextNode(role === "user" ? "You" : "Hindu Scriptures"));
    msg.appendChild(who);

    var bubble = document.createElement("div");
    bubble.className = "bubble";

    var content = null;
    if (role === "user") {
      bubble.textContent = text;
    } else {
      content = document.createElement("div");
      content.className = "msg-content";
      bubble.appendChild(content);
    }
    msg.appendChild(bubble);
    thread.appendChild(msg);
    return { msg: msg, bubble: bubble, content: content };
  }

  /* ====================================================================
     Send
     ==================================================================== */
  function autosize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  }

  function setSendMode(streaming) {
    if (streaming) {
      sendBtn.innerHTML = STOP_ICON;
      sendBtn.classList.add("is-streaming");
      sendBtn.setAttribute("aria-label", "Stop");
      sendBtn.onclick = cancelStream;
    } else {
      sendBtn.innerHTML = SEND_ICON;
      sendBtn.classList.remove("is-streaming");
      sendBtn.setAttribute("aria-label", "Send");
      sendBtn.onclick = sendMessage;
    }
  }

  function sendMessage() {
    if (isStreaming) return;
    var text = input.value.trim();
    if (!text) return;

    var active = getActive();
    var historyForApi = active.messages.slice();

    input.value = "";
    autosize();
    welcome.hidden = true;

    // user message — persist immediately so the rail + reload stay honest
    addMessage("user", text);
    active.messages.push({ role: "user", content: text });
    if (!active.title) active.title = deriveTitle(active.messages);
    active.updatedAt = Date.now();
    if (active.messages.length > MAX_STORED) active.messages = active.messages.slice(-MAX_STORED);
    headerName.textContent = sessionTitle(active);
    saveStore({ skipServer: true });
    renderRail();

    // assistant placeholder
    var refs = addMessage("assistant", "");
    refs.bubble.classList.add("is-streaming");
    refs.content.innerHTML =
      '<span class="typing-indicator"><span></span><span></span><span></span></span>';

    stickToBottom = true;
    unread = 0;
    hidePill();
    forceScrollToBottom();

    isStreaming = true;
    setSendMode(true);

    var wordCount = text.split(/\s+/).filter(Boolean).length;
    if (wordCount <= 4) {
      doSimpleQuery(text, refs, historyForApi);
    } else {
      doAgentStream(text, refs, historyForApi);
    }
  }

  function cancelStream() {
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
  }

  function finishStreaming(refs) {
    isStreaming = false;
    abortController = null;
    setSendMode(false);
    if (refs && refs.bubble) refs.bubble.classList.remove("is-streaming");
    refreshAuthBar();
    scrollIfPinned();
    input.focus();
  }

  function commitTurn(question, answer) {
    if (!answer) return;
    var active = getActive();
    active.messages.push({ role: "assistant", content: answer });
    if (active.messages.length > MAX_STORED) active.messages = active.messages.slice(-MAX_STORED);
    active.updatedAt = Date.now();
    saveStore();
  }

  /* ====================================================================
     Simple query (short questions, no agent)
     ==================================================================== */
  function doSimpleQuery(question, refs, history) {
    abortController = new AbortController();
    var timeoutId = setTimeout(function () { abortController.abort(); }, REQUEST_TIMEOUT_MS);

    fetch(ragApiUrl("/api/query"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question }),
      signal: abortController.signal,
      credentials: "same-origin"
    })
      .then(function (r) {
        if (r.status === 401) {
          window.location.href = "/auth/login?next=" +
            encodeURIComponent(window.location.pathname + window.location.search);
          return Promise.reject({ name: "Auth" });
        }
        return r.ok ? r.json() : r.json().then(function (d) { return Promise.reject(d); });
      })
      .then(function (data) {
        clearTimeout(timeoutId);
        refs.content.innerHTML = renderMarkdown(data.answer || "");
        addCopyButton(refs.content);
        if (data.sources && data.sources.length) {
          attachCitations(refs.msg, mapSimpleSources(data.sources));
        }
        commitTurn(question, data.answer || "");
        finishStreaming(refs);
      })
      .catch(function (err) {
        clearTimeout(timeoutId);
        if (err && err.name === "Auth") return;
        if (err && err.name === "AbortError") {
          refs.content.innerHTML =
            '<div class="msg-error">Request timed out or cancelled. Try again.</div>';
        } else {
          refs.content.innerHTML =
            '<div class="msg-error">' + escHtml((err && err.error) || "Something went wrong.") + "</div>";
        }
        finishStreaming(refs);
      });
  }

  /* ====================================================================
     Streaming agent call
     ==================================================================== */
  function doAgentStream(question, refs, history) {
    abortController = new AbortController();
    var timeoutId = setTimeout(function () { abortController.abort(); }, REQUEST_TIMEOUT_MS);

    var thinkingEl = document.createElement("div");
    thinkingEl.className = "thinking-steps";
    thinkingEl.hidden = true;
    refs.bubble.insertBefore(thinkingEl, refs.content);

    var payload = { question: question, history: history, voice: currentVoice };
    var answerText = "";

    fetch(ragApiUrl("/api/agent/stream"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: abortController.signal,
      credentials: "same-origin"
    })
      .then(function (response) {
        if (response.status === 401) {
          return response.json().then(function (d) {
            if (d.error === "guest_limit_exceeded") return Promise.reject({ name: "GuestLimit", body: d });
            return Promise.reject({ name: "Auth401", body: d });
          });
        }
        if (!response.ok) return response.json().then(function (d) { return Promise.reject(d); });

        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = "";

        function processChunk() {
          return reader.read().then(function (result) {
            if (result.done) {
              clearTimeout(timeoutId);
              commitTurn(question, answerText);
              finishStreaming(refs);
              return;
            }
            buffer += decoder.decode(result.value, { stream: true });
            var lines = buffer.split("\n");
            buffer = lines.pop();

            for (var i = 0; i < lines.length; i++) {
              var line = lines[i];
              if (line.indexOf("data: ") !== 0) continue;
              var event;
              try { event = JSON.parse(line.slice(6)); } catch (e) { continue; }

              switch (event.type) {
                case "thinking":
                  addThinkingStep(thinkingEl, "thought", event.content);
                  break;
                case "tool_call":
                  addThinkingStep(thinkingEl, "tool", formatToolCall(event.name, event.input));
                  break;
                case "tool_result":
                  addThinkingStep(thinkingEl, "result", event.summary || "Done");
                  break;
                case "answer_chunk":
                  answerText += event.content;
                  refs.content.innerHTML = renderMarkdown(answerText);
                  scrollIfPinned();
                  break;
                case "citations":
                  if (event.refs && event.refs.length) {
                    attachCitations(refs.msg, mapAgentRefs(event.refs));
                  }
                  break;
                case "followups":
                  if (event.questions && event.questions.length) {
                    addFollowupChips(refs.msg, event.questions);
                  }
                  break;
                case "done":
                  if (thinkingEl.children.length === 0) thinkingEl.remove();
                  addCopyButton(refs.content);
                  break;
                case "error":
                  refs.content.innerHTML =
                    '<div class="msg-error">' + escHtml(event.content) + "</div>";
                  break;
              }
            }
            return processChunk();
          });
        }
        return processChunk();
      })
      .catch(function (err) {
        clearTimeout(timeoutId);
        if (err && err.name === "GuestLimit") {
          var next = encodeURIComponent(window.location.pathname + window.location.search);
          refs.content.innerHTML =
            '<div class="msg-error">You have used your free messages. ' +
            '<a href="/auth/login?next=' + next + '">Sign in</a> to continue.</div>';
          finishStreaming(refs);
          return;
        }
        if (err && err.name === "AbortError") {
          if (!answerText) {
            refs.content.innerHTML =
              '<div class="msg-error">Request timed out or cancelled. Try again.</div>';
          } else {
            commitTurn(question, answerText);
          }
        } else {
          refs.content.innerHTML =
            '<div class="msg-error">' + escHtml((err && err.error) || "Something went wrong.") + "</div>";
        }
        finishStreaming(refs);
      });
  }

  /* ====================================================================
     Thinking steps
     ==================================================================== */
  function addThinkingStep(container, type, text) {
    container.hidden = false;
    var step = document.createElement("div");
    step.className = "think-step think-" + type;
    var icons = { thought: "💭", tool: "🔍", result: "✓" };
    var icon = document.createElement("span");
    icon.className = "think-icon";
    icon.textContent = icons[type] || "";
    var body = document.createElement("span");
    body.className = "think-text";
    body.textContent = text;
    step.appendChild(icon);
    step.appendChild(body);
    container.appendChild(step);
    container.scrollTop = container.scrollHeight;
    scrollIfPinned();
  }
  function formatToolCall(name, inputObj) {
    var parts = [String(name || "").replace(/_/g, " ")];
    if (inputObj) {
      if (inputObj.query) parts.push('"' + inputObj.query + '"');
      if (inputObj.source_text) parts.push("in " + inputObj.source_text);
      if (inputObj.verse_ref) parts.push(inputObj.verse_ref);
      if (inputObj.school) parts.push("(" + inputObj.school + ")");
    }
    return parts.join(" — ");
  }

  /* ====================================================================
     Citations
     ==================================================================== */
  function mapSimpleSources(sources) {
    return sources.map(function (src, i) {
      var meta = src.metadata || {};
      var quote = src.translation || src.commentary_text || "";
      if (quote.length > 280) quote = quote.slice(0, 280) + "…";
      return {
        n: i + 1,
        ref: src.header || "Source " + (i + 1),
        book: meta.source_text || meta.tradition || "",
        dev: src.sanskrit || "",
        quote: quote
      };
    });
  }
  function mapAgentRefs(refs) {
    return refs.map(function (ref, i) {
      return { n: i + 1, ref: String(ref), book: "", dev: "", quote: "" };
    });
  }

  function attachCitations(msgEl, sources) {
    if (!sources || !sources.length) return;
    var existing = msgEl.querySelector(".cite-tray");
    if (existing) existing.remove();

    var tray = document.createElement("div");
    tray.className = "cite-tray";
    sources.forEach(function (s) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "cite-chip";
      var n = document.createElement("span");
      n.className = "n";
      n.textContent = s.n;
      chip.appendChild(n);
      chip.appendChild(document.createTextNode(s.ref));
      chip.addEventListener("click", function () { openCitations(sources); });
      tray.appendChild(chip);
    });
    msgEl.appendChild(tray);

    currentSources = sources;
    updateCitationsAffordance();
  }

  function updateCitationsAffordance() {
    if (currentSources.length) {
      citationsCount.textContent = currentSources.length;
      citationsBtn.classList.add("is-visible");
    } else {
      citationsBtn.classList.remove("is-visible");
    }
  }

  function renderCitationCards(sources) {
    citationsList.innerHTML = "";
    if (!sources || !sources.length) {
      var empty = document.createElement("div");
      empty.className = "c-empty";
      empty.textContent = "No sources cited for this reply.";
      citationsList.appendChild(empty);
      return;
    }
    sources.forEach(function (s) {
      var card = document.createElement("div");
      card.className = "c-card";

      var top = document.createElement("div");
      top.className = "top";
      var n = document.createElement("span");
      n.className = "n";
      n.textContent = s.n;
      var ref = document.createElement("span");
      ref.className = "ref";
      ref.textContent = s.ref;
      top.appendChild(n);
      top.appendChild(ref);
      if (s.book) {
        var book = document.createElement("span");
        book.className = "book";
        book.textContent = s.book;
        top.appendChild(book);
      }
      card.appendChild(top);

      if (s.dev) {
        var dev = document.createElement("div");
        dev.className = "dev";
        dev.textContent = s.dev;
        card.appendChild(dev);
      }
      if (s.quote) {
        var quote = document.createElement("div");
        quote.className = "quote";
        quote.textContent = s.quote;
        card.appendChild(quote);
      }
      citationsList.appendChild(card);
    });
  }

  function openCitations(sources) {
    var list = sources || currentSources;
    if (!list || !list.length) return;
    renderCitationCards(list);
    app.classList.add("citations-open");
    if (isMobile()) collapseRail();
    syncScrim();
  }
  function closeCitations() {
    app.classList.remove("citations-open");
    syncScrim();
  }
  function toggleCitations() {
    if (app.classList.contains("citations-open")) closeCitations();
    else openCitations(currentSources);
  }

  /* ====================================================================
     Follow-up chips
     ==================================================================== */
  function addFollowupChips(msgEl, questions) {
    var existing = msgEl.querySelector(".followup-chips");
    if (existing) existing.remove();
    var wrap = document.createElement("div");
    wrap.className = "followup-chips";
    questions.forEach(function (q) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "followup-chip";
      chip.textContent = q;
      chip.addEventListener("click", function () {
        if (isStreaming) return;
        input.value = q;
        sendMessage();
      });
      wrap.appendChild(chip);
    });
    msgEl.appendChild(wrap);
    scrollIfPinned();
  }

  /* ====================================================================
     Copy button
     ==================================================================== */
  function addCopyButton(contentEl) {
    if (contentEl.querySelector(".copy-btn")) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-btn";
    btn.textContent = "Copy";
    btn.addEventListener("click", function () {
      var text = contentEl.innerText || contentEl.textContent || "";
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = "Copied";
        setTimeout(function () { btn.textContent = "Copy"; }, 1500);
      }).catch(function () {});
    });
    contentEl.appendChild(btn);
  }

  /* ====================================================================
     Markdown renderer
     ==================================================================== */
  function renderMarkdown(text) {
    var html = String(text == null ? "" : text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    html = html.replace(/^&gt;\s?(.*)$/gm, '<div class="verse-quote">$1</div>');
    html = html.replace(/(<\/div>\n?<div class="verse-quote">)/g, "<br>");
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
    html = html.replace(/`([^`]+)`/g, '<code class="verse-ref">$1</code>');
    html = html.replace(/^---$/gm, '<hr class="section-break">');
    html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>');
    html = html.replace(/^[-*] (.+)$/gm, "<li>$1</li>");
    html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul class="md-list">$1</ul>');
    html = html.replace(/^\d+\.\s(.+)$/gm, '<li class="ol-item">$1</li>');
    html = html.replace(/((?:<li class="ol-item">.*?<\/li>\n?)+)/g, '<ol class="md-olist">$1</ol>');

    html = html.split(/\n{2,}/).map(function (block) {
      block = block.trim();
      if (!block) return "";
      if (block.indexOf("<div") === 0 || block.indexOf("<h") === 0 ||
          block.indexOf("<ul") === 0 || block.indexOf("<ol") === 0 ||
          block.indexOf("<hr") === 0 || block.indexOf("<li") === 0) {
        return block;
      }
      return "<p>" + block.replace(/\n/g, "<br>") + "</p>";
    }).join("\n");

    return html;
  }

  function escHtml(str) {
    return String(str == null ? "" : str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ====================================================================
     Scroll — smart tail-follow + jump pill
     ==================================================================== */
  function onScroll() {
    var el = scrollArea;
    var nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    stickToBottom = nearBottom;
    if (el.scrollTop > 12) mainEl.classList.add("scrolled");
    else mainEl.classList.remove("scrolled");
    if (nearBottom) { unread = 0; hidePill(); }
  }
  function scrollIfPinned() {
    if (stickToBottom) {
      scrollToBottom();
    } else if (isStreaming) {
      unread++;
      showPill();
    }
  }
  function scrollToBottom() {
    requestAnimationFrame(function () { scrollArea.scrollTop = scrollArea.scrollHeight; });
  }
  function instantScrollToBottom() {
    scrollArea.scrollTop = scrollArea.scrollHeight;
    stickToBottom = true;
  }
  function forceScrollToBottom() {
    stickToBottom = true;
    unread = 0;
    hidePill();
    scrollArea.scrollTo({
      top: scrollArea.scrollHeight,
      behavior: prefersReducedMotion ? "auto" : "smooth"
    });
  }
  function showPill() {
    pillCount.textContent = unread;
    pill.classList.add("is-visible");
  }
  function hidePill() {
    pill.classList.remove("is-visible");
  }

  /* ====================================================================
     Rail / citations / scrim chrome
     ==================================================================== */
  function isMobile() { return window.innerWidth <= 960; }
  function collapseRail() { app.classList.add("rail-collapsed"); syncScrim(); }
  function toggleRail() {
    var collapsed = app.classList.toggle("rail-collapsed");
    if (!collapsed && isMobile()) closeCitations();
    syncScrim();
  }
  function syncScrim() {
    var mobile = isMobile();
    var railOpen = mobile && !app.classList.contains("rail-collapsed");
    var citeOpen = mobile && app.classList.contains("citations-open");
    if (railOpen || citeOpen) {
      scrim.hidden = false;
      requestAnimationFrame(function () { scrim.classList.add("is-visible"); });
    } else {
      scrim.classList.remove("is-visible");
      setTimeout(function () {
        if (!scrim.classList.contains("is-visible")) scrim.hidden = true;
      }, 320);
    }
  }
  function onResize() {
    var mobile = isMobile();
    // Crossing into mobile: rail + citations become overlays — start them closed
    // so they don't ambush the reader (and the scrim doesn't arm spuriously).
    if (mobile && !lastMobile) {
      app.classList.add("rail-collapsed");
      app.classList.remove("citations-open");
    }
    lastMobile = mobile;
    syncScrim();
  }

  /* ====================================================================
     Settings drawer
     ==================================================================== */
  function openDrawer() { drawerOverlay.classList.add("open"); }
  function closeDrawer() { drawerOverlay.classList.remove("open"); }

  /* ====================================================================
     Voices
     ==================================================================== */
  function loadVoices() {
    fetch(ragApiUrl("/api/voices"), { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (voices) {
        voiceList.innerHTML = "";
        Object.keys(voices).forEach(function (key) {
          var v = voices[key];
          var btn = document.createElement("button");
          btn.type = "button";
          btn.className = "voice-option" + (key === currentVoice ? " active" : "");
          var name = document.createElement("span");
          name.className = "voice-name";
          name.textContent = v.name;
          btn.appendChild(name);
          btn.addEventListener("click", function () {
            currentVoice = key;
            try { localStorage.setItem("hs-voice", key); } catch (e) { /* ignore */ }
            voiceList.querySelectorAll(".voice-option").forEach(function (b) {
              b.classList.remove("active");
            });
            btn.classList.add("active");
          });
          voiceList.appendChild(btn);
        });
      })
      .catch(function () {});
  }

  /* ====================================================================
     Corpus badge
     ==================================================================== */
  function loadCorpusBadge() {
    fetch(ragApiUrl("/api/sources"), { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.total_verses) {
          var texts = (data.sources && data.sources.length) || 0;
          corpusBadge.textContent =
            data.total_verses.toLocaleString() + " verses · " + texts + " texts";
        }
      })
      .catch(function () {});
  }

  /* ====================================================================
     Auth
     ==================================================================== */
  function updateAuthHrefs() {
    var next = encodeURIComponent(window.location.pathname + window.location.search);
    if (loginBtn) loginBtn.href = "/auth/login?next=" + next;
    if (signupBtn) signupBtn.href = "/auth/register?next=" + next;
  }

  function refreshAuthBar() {
    return fetch("/api/auth/me", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        updateAuthHrefs();
        useServerChat = !!(data && data.logged_in);
        if (data && data.logged_in && data.email) {
          authUserLabel.textContent = data.email;
          guestHint.textContent = "Signed in";
          acctAvatar.textContent = data.email.charAt(0).toUpperCase();
          if (logoutBtn) logoutBtn.hidden = false;
          if (loginBtn) loginBtn.hidden = true;
          if (signupBtn) signupBtn.hidden = true;
        } else {
          authUserLabel.textContent = "Guest";
          acctAvatar.textContent = "ॐ";
          if (logoutBtn) logoutBtn.hidden = true;
          if (loginBtn) loginBtn.hidden = false;
          if (signupBtn) signupBtn.hidden = false;
          if (data && typeof data.guest_messages_remaining === "number" && data.guest_limit > 0) {
            var rem = data.guest_messages_remaining;
            guestHint.textContent = rem === 0
              ? "Sign in to continue"
              : rem + " free message" + (rem === 1 ? "" : "s") + " left";
          } else {
            guestHint.textContent = "Seeker";
          }
        }
        return data;
      })
      .catch(function () {
        useServerChat = false;
        return {};
      });
  }

  function reconcileServerChat() {
    if (!useServerChat) return;
    fetch("/api/chat/state", { credentials: "same-origin" })
      .then(function (r) { return r.status === 401 ? null : r.json(); })
      .then(function (d) {
        if (!d || !d.messages || !d.messages.length) return;
        var active = getActive();
        if (active.messages.length) return; // local conversation wins
        active.messages = d.messages.slice(-MAX_STORED);
        if (!active.title) active.title = deriveTitle(active.messages);
        active.updatedAt = Date.now();
        saveStore({ skipServer: true });
        renderRail();
        renderActiveThread();
      })
      .catch(function () {});
  }

  /* ====================================================================
     Welcome verse of the day
     ==================================================================== */
  var currentWelcomeRef = "";

  function dayOfYearLocal(d) {
    var start = new Date(d.getFullYear(), 0, 0);
    return Math.floor((d - start) / 86400000);
  }

  function loadWelcomeVerse() {
    fetch(RAG_PREFIX + "/static/data/welcome-verses.json", { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) throw new Error("bad"); return r.json(); })
      .then(function (list) {
        if (!Array.isArray(list) || !list.length) throw new Error("empty");
        var v = list[dayOfYearLocal(new Date()) % list.length];
        if (!v || !v.ref || !v.eng) throw new Error("bad row");
        currentWelcomeRef = v.ref;
        verseRef.textContent = v.ref;
        verseEng.textContent = v.eng;
        if (v.dev && String(v.dev).trim()) {
          verseDev.textContent = v.dev;
          verseDev.hidden = false;
        }
        if (v.iast && String(v.iast).trim()) {
          verseIast.textContent = v.iast;
          verseIast.hidden = false;
        }
        verseLeaf.hidden = false;
        requestAnimationFrame(function () { verseLeaf.classList.add("is-in"); });
      })
      .catch(function () {
        currentWelcomeRef = "";
        verseLeaf.hidden = true;
      });
  }

  function primeVerseQuestion(template) {
    if (!currentWelcomeRef) return;
    input.value = template.replace(/\{ref\}/g, currentWelcomeRef);
    autosize();
    input.focus();
  }

  /* ====================================================================
     Prompt chips
     ==================================================================== */
  function buildPrompts() {
    PROMPTS.forEach(function (p) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip";
      var topic = document.createElement("span");
      topic.className = "topic";
      topic.textContent = p.topic;
      var text = document.createElement("span");
      text.className = "text";
      text.textContent = p.label;
      var arrow = document.createElement("span");
      arrow.className = "arrow";
      arrow.textContent = "→";
      text.appendChild(arrow);
      btn.appendChild(topic);
      btn.appendChild(text);
      btn.addEventListener("click", function () {
        if (isStreaming) return;
        input.value = p.q;
        sendMessage();
      });
      promptsEl.appendChild(btn);
    });
  }

  /* ====================================================================
     Init
     ==================================================================== */
  function init() {
    setSendMode(false);
    loadStore();
    renderRail(true);
    renderActiveThread();
    buildPrompts();

    lastMobile = isMobile();
    if (lastMobile) app.classList.add("rail-collapsed");

    // composer
    sendBtn.onclick = sendMessage;
    input.addEventListener("input", autosize);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // chrome
    railToggle.addEventListener("click", toggleRail);
    newRailBtn.addEventListener("click", createSession);
    newChatBtn.addEventListener("click", createSession);
    themeToggle.addEventListener("click", toggleTheme);
    citationsBtn.addEventListener("click", toggleCitations);
    citationsClose.addEventListener("click", closeCitations);
    pill.addEventListener("click", forceScrollToBottom);
    scrollArea.addEventListener("scroll", onScroll, { passive: true });

    scrim.addEventListener("click", function () {
      app.classList.add("rail-collapsed");
      app.classList.remove("citations-open");
      syncScrim();
    });

    // drawer
    settingsBtn.addEventListener("click", openDrawer);
    drawerClose.addEventListener("click", closeDrawer);
    drawerOverlay.addEventListener("click", function (e) {
      if (e.target === drawerOverlay) closeDrawer();
    });
    clearHistoryBtn.addEventListener("click", function () {
      if (isStreaming) return;
      var s = newSession();
      store = { activeId: s.id, sessions: [s] };
      saveStore();
      renderRail();
      renderActiveThread();
      closeDrawer();
    });

    // verse CTAs
    verseExplain.addEventListener("click", function () {
      primeVerseQuestion("Please explain {ref} in simple, plain language. What is this verse saying, and why does it matter?");
    });
    verseApply.addEventListener("click", function () {
      primeVerseQuestion("How can the teaching in {ref} apply to daily life today? Please stay grounded in scripture.");
    });

    // logout
    if (logoutBtn) {
      logoutBtn.addEventListener("click", function () {
        fetch("/auth/logout", {
          method: "POST",
          credentials: "same-origin",
          headers: csrfHeaders(),
          body: "{}"
        }).then(function (res) {
          if (res.ok) window.location.href = RAG_PREFIX ? RAG_PREFIX + "/" : "/";
        }).catch(function () {});
      });
    }

    // global keys
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      if (drawerOverlay.classList.contains("open")) { closeDrawer(); return; }
      if (app.classList.contains("citations-open")) { closeCitations(); return; }
      if (isMobile() && !app.classList.contains("rail-collapsed")) { collapseRail(); }
    });

    window.addEventListener("resize", onResize);
    syncScrim();

    updateAuthHrefs();
    loadCorpusBadge();
    loadVoices();
    loadWelcomeVerse();
    refreshAuthBar().then(reconcileServerChat);

    autosize();
    input.focus();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
