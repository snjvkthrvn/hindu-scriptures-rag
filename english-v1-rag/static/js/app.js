(function () {
  "use strict";

  /** Empty at `/`, `/main` when full-corpus UI is mounted under a blueprint. */
  var RAG_PREFIX = (document.body.getAttribute("data-api-base") || "").replace(
    /\/$/,
    "",
  );
  function ragApiUrl(path) {
    return RAG_PREFIX + path;
  }

  function csrfHeaders() {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const token = csrfMeta ? csrfMeta.getAttribute("content") : "";
    const h = { "Content-Type": "application/json" };
    if (token) {
      h["X-CSRFToken"] = token;
    }
    return h;
  }

  /* ====================================================================
     DOM refs
     ==================================================================== */
  const chatMessages = document.getElementById("chatMessages");
  const chatInput = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const welcome = document.getElementById("welcome");
  const corpusBadge = document.getElementById("corpusBadge");
  const newChatBtn = document.getElementById("newChatBtn");
  const themeToggle = document.getElementById("themeToggle");
  const settingsBtn = document.getElementById("settingsBtn");
  const drawerOverlay = document.getElementById("drawerOverlay");
  const drawerClose = document.getElementById("drawerClose");
  const voiceList = document.getElementById("voiceList");
  const clearHistoryBtn = document.getElementById("clearHistoryBtn");
  const authUserLabel = document.getElementById("authUserLabel");
  const logoutBtn = document.getElementById("logoutBtn");
  const loginBtn = document.getElementById("loginBtn");
  const signupBtn = document.getElementById("signupBtn");
  const guestHint = document.getElementById("guestHint");

  /** When true, chat is loaded/saved via /api/chat/state; else localStorage. */
  var useServerChat = false;

  let conversationHistory = [];
  let isStreaming = false;
  let abortController = null;
  let currentVoice = localStorage.getItem("hs-voice") || "elder";

  /* ====================================================================
     Theme
     ==================================================================== */
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("hs-theme", theme);
    themeToggle.textContent = theme === "dark" ? "\u2600" : "\u263E";
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) {
      metaTheme.content = theme === "dark" ? "#0F0C0A" : "#3D0C0C";
    }
  }

  (function initTheme() {
    const saved = localStorage.getItem("hs-theme");
    if (saved) {
      applyTheme(saved);
    } else {
      const prefersDark = window.matchMedia(
        "(prefers-color-scheme: dark)",
      ).matches;
      applyTheme(prefersDark ? "dark" : "light");
    }
  })();

  function updateAuthHrefs() {
    const next = encodeURIComponent(
      window.location.pathname + window.location.search,
    );
    if (loginBtn) {
      loginBtn.href = "/auth/login?next=" + next;
    }
    if (signupBtn) {
      signupBtn.href = "/auth/register?next=" + next;
    }
  }

  function refreshAuthBar() {
    return fetch("/api/auth/me", { credentials: "same-origin" })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        updateAuthHrefs();
        useServerChat = !!(data && data.logged_in);
        if (data.logged_in && data.email) {
          if (authUserLabel) {
            authUserLabel.textContent = data.email;
            authUserLabel.hidden = false;
          }
          if (logoutBtn) logoutBtn.hidden = false;
          if (loginBtn) loginBtn.hidden = true;
          if (signupBtn) signupBtn.hidden = true;
          if (guestHint) guestHint.hidden = true;
        } else {
          if (authUserLabel) {
            authUserLabel.textContent = "";
            authUserLabel.hidden = true;
          }
          if (logoutBtn) logoutBtn.hidden = true;
          if (loginBtn) loginBtn.hidden = false;
          if (signupBtn) signupBtn.hidden = false;
          if (guestHint) {
            if (
              typeof data.guest_messages_remaining === "number" &&
              data.guest_limit > 0
            ) {
              var rem = data.guest_messages_remaining;
              guestHint.textContent =
                rem === 0
                  ? "Sign in to continue"
                  : rem + " free message" + (rem === 1 ? "" : "s") + " left";
              guestHint.hidden = false;
            } else {
              guestHint.hidden = true;
            }
          }
        }
        return data;
      })
      .catch(function () {
        useServerChat = false;
        return {};
      });
  }
  updateAuthHrefs();

  if (logoutBtn) {
    logoutBtn.addEventListener("click", function () {
      fetch("/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: csrfHeaders(),
        body: "{}",
      }).then(function () {
        window.location.href = RAG_PREFIX ? RAG_PREFIX + "/" : "/";
      });
    });
  }

  themeToggle.addEventListener("click", function () {
    const current =
      document.documentElement.getAttribute("data-theme") || "light";
    applyTheme(current === "dark" ? "light" : "dark");
  });

  /* ====================================================================
     Drawer
     ==================================================================== */
  function openDrawer() {
    drawerOverlay.classList.add("open");
    document.body.style.overflow = "hidden";
  }
  function closeDrawer() {
    drawerOverlay.classList.remove("open");
    document.body.style.overflow = "";
  }

  settingsBtn.addEventListener("click", openDrawer);
  drawerClose.addEventListener("click", closeDrawer);
  drawerOverlay.addEventListener("click", function (e) {
    if (e.target === drawerOverlay) closeDrawer();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && drawerOverlay.classList.contains("open")) {
      closeDrawer();
    }
  });

  /* ====================================================================
     Voice picker
     ==================================================================== */
  function loadVoices() {
    fetch(ragApiUrl("/api/voices"), { credentials: "same-origin" })
      .then(function (r) {
        return r.json();
      })
      .then(function (voices) {
        voiceList.innerHTML = "";
        Object.keys(voices).forEach(function (key) {
          var v = voices[key];
          var btn = document.createElement("button");
          btn.className =
            "voice-option" + (key === currentVoice ? " active" : "");
          btn.innerHTML =
            '<span class="voice-name">' + escHtml(v.name) + "</span>";
          btn.addEventListener("click", function () {
            currentVoice = key;
            localStorage.setItem("hs-voice", key);
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
  loadVoices();

  /* ====================================================================
     Conversation persistence (localStorage for guests, server for logged-in)
     ==================================================================== */
  var STORAGE_KEY = "hs-conversations" + (RAG_PREFIX ? "-main" : "");
  var MAX_STORED = 50;

  function applyMessagesToUI(data) {
    if (!Array.isArray(data) || data.length === 0) return;
    conversationHistory = data;
    welcome.hidden = true;
    conversationHistory.forEach(function (msg) {
      if (msg.role === "user") {
        addMessage("user", msg.content);
      } else if (msg.role === "assistant") {
        var el = addMessage("assistant", "");
        var contentEl = el.querySelector(".msg-content");
        contentEl.innerHTML = renderMarkdown(msg.content);
        addCopyButton(contentEl);
      }
    });
    scrollToBottom();
  }

  function loadConversationLocal() {
    try {
      var data = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (Array.isArray(data) && data.length > 0) {
        applyMessagesToUI(data);
      }
    } catch (e) {
      /* ignore */
    }
  }

  function loadChatHistoryAfterAuth() {
    if (!useServerChat) {
      loadConversationLocal();
      return;
    }
    fetch("/api/chat/state", { credentials: "same-origin" })
      .then(function (r) {
        if (r.status === 401) {
          useServerChat = false;
          loadConversationLocal();
          return null;
        }
        return r.json();
      })
      .then(function (d) {
        if (!d) return;
        if (d.messages && d.messages.length > 0) {
          applyMessagesToUI(d.messages);
          return;
        }
        try {
          var raw = localStorage.getItem(STORAGE_KEY);
          if (raw) {
            var parsed = JSON.parse(raw);
            if (Array.isArray(parsed) && parsed.length > 0) {
              applyMessagesToUI(parsed);
              saveConversation();
              localStorage.removeItem(STORAGE_KEY);
            }
          }
        } catch (e) {
          /* ignore */
        }
      })
      .catch(function () {
        loadConversationLocal();
      });
  }

  function saveConversation() {
    var trimmed = conversationHistory.slice(-MAX_STORED);
    if (useServerChat) {
      fetch("/api/chat/state", {
        method: "PUT",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: trimmed }),
      }).catch(function () {});
      return;
    }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
    } catch (e) {
      /* ignore */
    }
  }

  refreshAuthBar().then(function () {
    loadChatHistoryAfterAuth();
  });

  clearHistoryBtn.addEventListener("click", function () {
    localStorage.removeItem(STORAGE_KEY);
    conversationHistory = [];
    saveConversation();
    chatMessages.innerHTML = "";
    chatMessages.appendChild(welcome);
    welcome.hidden = false;
    closeDrawer();
  });

  /* ====================================================================
     Corpus badge
     ==================================================================== */
  fetch(ragApiUrl("/api/sources"), { credentials: "same-origin" })
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      if (data.total_verses) {
        corpusBadge.textContent =
          data.total_verses.toLocaleString() +
          " verses \u00B7 " +
          data.sources.length +
          " texts";
      }
    })
    .catch(function () {});

  /* ====================================================================
     Input
     ==================================================================== */
  chatInput.addEventListener("input", function () {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + "px";
  });

  chatInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener("click", sendMessage);

  document.querySelectorAll(".prompt-chip").forEach(function (btn) {
    btn.addEventListener("click", function () {
      chatInput.value = btn.dataset.q;
      sendMessage();
    });
  });

  newChatBtn.addEventListener("click", function () {
    conversationHistory = [];
    saveConversation();
    chatMessages.innerHTML = "";
    chatMessages.appendChild(welcome);
    welcome.hidden = false;
    chatInput.value = "";
    chatInput.style.height = "auto";
  });

  /* ====================================================================
     Send message
     ==================================================================== */
  function sendMessage() {
    var text = chatInput.value.trim();
    if (!text || isStreaming) return;

    welcome.hidden = true;
    addMessage("user", text);
    chatInput.value = "";
    chatInput.style.height = "auto";

    var assistantEl = addMessage("assistant", "");
    var contentEl = assistantEl.querySelector(".msg-content");
    var thinkingEl = document.createElement("div");
    thinkingEl.className = "thinking-steps";
    contentEl.parentNode.insertBefore(thinkingEl, contentEl);

    contentEl.innerHTML =
      '<span class="typing-indicator"><span></span><span></span><span></span></span>';
    scrollToBottom();

    var wordCount = text.split(/\s+/).filter(Boolean).length;
    if (wordCount <= 4) {
      doSimpleQuery(text, contentEl, thinkingEl);
    } else {
      doAgentStream(text, contentEl, thinkingEl);
    }
  }

  /* ====================================================================
     Add message bubble
     ==================================================================== */
  function addMessage(role, text) {
    var wrapper = document.createElement("div");
    wrapper.className = "msg msg-" + role;
    var bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    if (role === "user") {
      bubble.innerHTML = '<div class="msg-content">' + escHtml(text) + "</div>";
    } else {
      bubble.innerHTML =
        '<div class="msg-avatar">&#x0950;</div>' +
        '<div class="msg-body"><div class="msg-content"></div></div>';
    }

    wrapper.appendChild(bubble);
    chatMessages.appendChild(wrapper);
    scrollToBottom();
    return wrapper;
  }

  /* ====================================================================
     Simple query (no agent)
     ==================================================================== */
  var REQUEST_TIMEOUT_MS = 75000;

  function doSimpleQuery(question, contentEl, thinkingEl) {
    isStreaming = true;
    sendBtn.disabled = true;
    abortController = new AbortController();
    var timeoutId = setTimeout(function () {
      abortController.abort();
    }, REQUEST_TIMEOUT_MS);

    showStopBtn();

    fetch(ragApiUrl("/api/query"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question }),
      signal: abortController.signal,
      credentials: "same-origin",
    })
      .then(function (r) {
        if (r.status === 401) {
          window.location.href =
            "/auth/login?next=" +
            encodeURIComponent(
              window.location.pathname + window.location.search,
            );
          return Promise.reject({ name: "Auth" });
        }
        return r.ok
          ? r.json()
          : r.json().then(function (d) {
              return Promise.reject(d);
            });
      })
      .then(function (data) {
        clearTimeout(timeoutId);
        thinkingEl.remove();
        contentEl.innerHTML = renderMarkdown(data.answer || "");
        addCopyButton(contentEl);
        if (data.sources && data.sources.length) {
          addSourceCards(
            contentEl.closest(".msg-body") || contentEl.parentNode,
            data.sources,
          );
        }
        if (data.answer) {
          conversationHistory.push({ role: "user", content: question });
          conversationHistory.push({ role: "assistant", content: data.answer });
          if (conversationHistory.length > MAX_STORED) {
            conversationHistory = conversationHistory.slice(-MAX_STORED);
          }
          saveConversation();
        }
        finishStreaming();
      })
      .catch(function (err) {
        clearTimeout(timeoutId);
        thinkingEl.remove();
        if (err && err.name === "GuestLimit") {
          var nextQ = encodeURIComponent(
            window.location.pathname + window.location.search,
          );
          contentEl.innerHTML =
            '<div class="msg-error">You have used your free messages. <a href="/auth/login?next=' +
            nextQ +
            '">Sign in</a> to continue.</div>';
          finishStreaming();
          refreshAuthBar();
          return;
        }
        if (err.name === "AbortError") {
          contentEl.innerHTML =
            '<div class="msg-error">Request timed out or cancelled. Try again.</div>';
        } else {
          contentEl.innerHTML =
            '<div class="msg-error">' +
            escHtml(err.error || "Something went wrong.") +
            "</div>";
        }
        finishStreaming();
      });
  }

  /* ====================================================================
     Streaming agent call
     ==================================================================== */
  function doAgentStream(question, contentEl, thinkingEl) {
    isStreaming = true;
    sendBtn.disabled = true;
    abortController = new AbortController();
    var timeoutId = setTimeout(function () {
      abortController.abort();
    }, REQUEST_TIMEOUT_MS);

    showStopBtn();

    var payload = {
      question: question,
      history: conversationHistory,
      voice: currentVoice,
    };

    var answerText = "";
    var msgBody = contentEl.closest(".msg-body") || contentEl.parentNode;

    fetch(ragApiUrl("/api/agent/stream"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: abortController.signal,
      credentials: "same-origin",
    })
      .then(function (response) {
        if (response.status === 401) {
          return response.json().then(function (d) {
            if (d.error === "guest_limit_exceeded") {
              return Promise.reject({ name: "GuestLimit", body: d });
            }
            return Promise.reject({ name: "Auth401", body: d });
          });
        }
        if (!response.ok)
          return response.json().then(function (d) {
            return Promise.reject(d);
          });

        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = "";

        function processChunk() {
          return reader.read().then(function (result) {
            if (result.done) {
              clearTimeout(timeoutId);
              if (answerText) {
                conversationHistory.push({ role: "user", content: question });
                conversationHistory.push({
                  role: "assistant",
                  content: answerText,
                });
                if (conversationHistory.length > MAX_STORED) {
                  conversationHistory = conversationHistory.slice(-MAX_STORED);
                }
                saveConversation();
              }
              finishStreaming();
              return;
            }

            buffer += decoder.decode(result.value, { stream: true });
            var lines = buffer.split("\n");
            buffer = lines.pop();

            for (var i = 0; i < lines.length; i++) {
              var line = lines[i];
              if (!line.startsWith("data: ")) continue;
              var event;
              try {
                event = JSON.parse(line.slice(6));
              } catch (e) {
                continue;
              }

              switch (event.type) {
                case "thinking":
                  addThinkingStep(thinkingEl, "thought", event.content);
                  break;
                case "tool_call":
                  addThinkingStep(
                    thinkingEl,
                    "tool",
                    formatToolCall(event.name, event.input),
                  );
                  break;
                case "tool_result":
                  addThinkingStep(
                    thinkingEl,
                    "result",
                    event.summary || "Done",
                  );
                  break;
                case "answer_chunk":
                  answerText += event.content;
                  contentEl.innerHTML = renderMarkdown(answerText);
                  scrollToBottom();
                  break;
                case "citations":
                  if (event.refs && event.refs.length) {
                    addCitationBar(msgBody, event.refs);
                  }
                  break;
                case "followups":
                  if (event.questions && event.questions.length) {
                    addFollowupChips(msgBody, event.questions);
                  }
                  break;
                case "done":
                  if (thinkingEl.children.length === 0) thinkingEl.remove();
                  addCopyButton(contentEl);
                  break;
                case "error":
                  contentEl.innerHTML =
                    '<div class="msg-error">' +
                    escHtml(event.content) +
                    "</div>";
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
          var nextS = encodeURIComponent(
            window.location.pathname + window.location.search,
          );
          contentEl.innerHTML =
            '<div class="msg-error">You have used your free messages. <a href="/auth/login?next=' +
            nextS +
            '">Sign in</a> to continue.</div>';
          finishStreaming();
          refreshAuthBar();
          return;
        }
        if (err.name === "AbortError") {
          contentEl.innerHTML =
            contentEl.innerHTML ||
            '<div class="msg-error">Request timed out or cancelled. Try again.</div>';
        } else {
          contentEl.innerHTML =
            '<div class="msg-error">' +
            escHtml(err.error || "Something went wrong.") +
            "</div>";
        }
        finishStreaming();
      });
  }

  function cancelStream() {
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
  }

  var SEND_ICON =
    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>';

  function showStopBtn() {
    sendBtn.innerHTML =
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>';
    sendBtn.disabled = false;
    sendBtn.classList.add("cancel-mode");
    sendBtn.onclick = cancelStream;
  }

  function finishStreaming() {
    isStreaming = false;
    abortController = null;
    sendBtn.innerHTML = SEND_ICON;
    sendBtn.disabled = false;
    sendBtn.classList.remove("cancel-mode");
    sendBtn.onclick = sendMessage;
    chatInput.focus();
    refreshAuthBar();
  }

  /* ====================================================================
     Thinking steps
     ==================================================================== */
  function addThinkingStep(container, type, text) {
    container.hidden = false;
    var step = document.createElement("div");
    step.className = "think-step think-" + type;
    var icons = {
      thought: "\uD83D\uDCAD",
      tool: "\uD83D\uDD0D",
      result: "\u2705",
    };
    step.innerHTML =
      '<span class="think-icon">' +
      (icons[type] || "") +
      '</span><span class="think-text">' +
      escHtml(text) +
      "</span>";
    container.appendChild(step);
    scrollToBottom();
  }

  function formatToolCall(name, input) {
    var parts = [name.replace(/_/g, " ")];
    if (input) {
      if (input.query) parts.push('"' + input.query + '"');
      if (input.source_text) parts.push("in " + input.source_text);
      if (input.verse_ref) parts.push(input.verse_ref);
      if (input.school) parts.push("(" + input.school + ")");
    }
    return parts.join(" \u2014 ");
  }

  /* ====================================================================
     Citation bar
     ==================================================================== */
  function addCitationBar(container, refs) {
    var bar = document.createElement("div");
    bar.className = "citation-bar";
    refs.forEach(function (ref) {
      var pill = document.createElement("span");
      pill.className = "citation-pill";
      pill.textContent = ref;
      bar.appendChild(pill);
    });
    container.appendChild(bar);
    scrollToBottom();
  }

  /* ====================================================================
     Follow-up chips
     ==================================================================== */
  function addFollowupChips(container, questions) {
    var wrapper = document.createElement("div");
    wrapper.className = "followup-chips";
    questions.forEach(function (q) {
      var chip = document.createElement("button");
      chip.className = "followup-chip";
      chip.textContent = q;
      chip.addEventListener("click", function () {
        chatInput.value = q;
        sendMessage();
      });
      wrapper.appendChild(chip);
    });
    container.appendChild(wrapper);
    scrollToBottom();
  }

  /* ====================================================================
     Markdown renderer
     ==================================================================== */
  function renderMarkdown(text) {
    var html = text
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
    html = html.replace(
      /((?:<li>.*?<\/li>\n?)+)/g,
      '<ul class="md-list">$1</ul>',
    );
    html = html.replace(/^\d+\.\s(.+)$/gm, '<li class="ol-item">$1</li>');
    html = html.replace(
      /((?:<li class="ol-item">.*?<\/li>\n?)+)/g,
      '<ol class="md-olist">$1</ol>',
    );

    html = html
      .split(/\n{2,}/)
      .map(function (block) {
        block = block.trim();
        if (!block) return "";
        if (
          block.startsWith("<div") ||
          block.startsWith("<h") ||
          block.startsWith("<ul") ||
          block.startsWith("<ol") ||
          block.startsWith("<hr") ||
          block.startsWith("<li")
        ) {
          return block;
        }
        return "<p>" + block.replace(/\n/g, "<br>") + "</p>";
      })
      .join("\n");

    return html;
  }

  /* ====================================================================
     Copy button
     ==================================================================== */
  function addCopyButton(contentEl) {
    var btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.title = "Copy answer";
    btn.textContent = "Copy";
    btn.addEventListener("click", function () {
      var text = contentEl.innerText || contentEl.textContent;
      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = "Copied";
        setTimeout(function () {
          btn.textContent = "Copy";
        }, 1500);
      });
    });
    contentEl.appendChild(btn);
  }

  /* ====================================================================
     Source citation cards
     ==================================================================== */
  function addSourceCards(container, sources) {
    var wrapper = document.createElement("details");
    wrapper.className = "source-cards";
    var summary = document.createElement("summary");
    summary.textContent =
      sources.length + " source" + (sources.length !== 1 ? "s" : "") + " cited";
    wrapper.appendChild(summary);

    sources.forEach(function (src) {
      var card = document.createElement("div");
      card.className = "source-card";
      var header = escHtml(src.header || "Unknown");
      var body = escHtml(src.translation || "").substring(0, 200);
      if (src.translation && src.translation.length > 200) body += "...";
      var meta = src.metadata || {};
      var tags = [meta.source_text, meta.category, meta.tradition]
        .filter(Boolean)
        .map(escHtml);

      card.innerHTML =
        '<div class="source-header">' +
        header +
        "</div>" +
        (body ? '<div class="source-text">' + body + "</div>" : "") +
        (tags.length
          ? '<div class="source-tags">' +
            tags
              .map(function (t) {
                return '<span class="source-tag">' + t + "</span>";
              })
              .join("") +
            "</div>"
          : "");
      wrapper.appendChild(card);
    });

    container.appendChild(wrapper);
    scrollToBottom();
  }

  /* ====================================================================
     Welcome verse of the day (Option B)
     ==================================================================== */
  var currentWelcomeRef = "";

  function welcomeVersesJsonUrl() {
    return RAG_PREFIX + "/static/data/welcome-verses.json";
  }

  function dayOfYearLocal(d) {
    var start = new Date(d.getFullYear(), 0, 0);
    var diff = d - start;
    return Math.floor(diff / 86400000);
  }

  function loadWelcomeVerse() {
    var section = document.getElementById("welcomeVerseSection");
    var refEl = document.getElementById("welcomeVerseRef");
    var devEl = document.getElementById("welcomeVerseDev");
    var iastEl = document.getElementById("welcomeVerseIast");
    var engEl = document.getElementById("welcomeVerseEng");
    var promptLabel = document.getElementById("welcomePromptsLabel");
    if (!section || !refEl || !engEl) return;

    fetch(welcomeVersesJsonUrl(), { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("bad");
        return r.json();
      })
      .then(function (list) {
        if (!Array.isArray(list) || list.length === 0) throw new Error("empty");
        var idx = dayOfYearLocal(new Date()) % list.length;
        var v = list[idx];
        if (!v || !v.ref || !v.eng) throw new Error("bad row");
        currentWelcomeRef = v.ref;
        refEl.textContent = v.ref;
        engEl.textContent = v.eng;
        if (v.dev && String(v.dev).trim()) {
          devEl.textContent = v.dev;
          devEl.hidden = false;
        } else {
          devEl.textContent = "";
          devEl.hidden = true;
        }
        if (v.iast && String(v.iast).trim()) {
          iastEl.textContent = v.iast;
          iastEl.hidden = false;
        } else {
          iastEl.textContent = "";
          iastEl.hidden = true;
        }
        section.hidden = false;
        if (promptLabel) promptLabel.hidden = false;
      })
      .catch(function () {
        currentWelcomeRef = "";
        section.hidden = true;
        if (promptLabel) promptLabel.hidden = true;
      });
  }

  function primeVerseQuestion(template) {
    if (!currentWelcomeRef) return;
    chatInput.value = template.replace(/\{ref\}/g, currentWelcomeRef);
    chatInput.dispatchEvent(new Event("input", { bubbles: true }));
    chatInput.focus();
  }

  var verseCtaExplain = document.getElementById("verseCtaExplain");
  var verseCtaApply = document.getElementById("verseCtaApply");
  if (verseCtaExplain) {
    verseCtaExplain.addEventListener("click", function () {
      primeVerseQuestion(
        "Please explain {ref} in simple, plain language. What is this verse saying, and why does it matter?",
      );
    });
  }
  if (verseCtaApply) {
    verseCtaApply.addEventListener("click", function () {
      primeVerseQuestion(
        "How can the teaching in {ref} apply to daily life today? Please stay grounded in scripture.",
      );
    });
  }

  loadWelcomeVerse();

  /* ====================================================================
     Helpers
     ==================================================================== */
  function scrollToBottom() {
    requestAnimationFrame(function () {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    });
  }

  function escHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
})();
