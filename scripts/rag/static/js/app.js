(function () {
    "use strict";

    // --- DOM refs ---
    const chatMessages  = document.getElementById("chatMessages");
    const chatInput     = document.getElementById("chatInput");
    const sendBtn       = document.getElementById("sendBtn");
    const welcome       = document.getElementById("welcome");
    const corpusBadge   = document.getElementById("corpusBadge");
    const newChatBtn    = document.getElementById("newChatBtn");

    let conversationHistory = [];
    let isStreaming = false;
    let abortController = null;

    // --- Load corpus info ---
    fetch("/api/sources")
        .then(r => r.json())
        .then(data => {
            if (data.total_verses) {
                corpusBadge.textContent = data.total_verses.toLocaleString() + " verses · " + data.sources.length + " texts";
            }
        })
        .catch(() => {});

    // --- Auto-resize textarea ---
    chatInput.addEventListener("input", () => {
        chatInput.style.height = "auto";
        chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + "px";
    });

    // --- Send on Enter (shift+enter for newline) ---
    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    sendBtn.addEventListener("click", sendMessage);

    // --- Prompt chips ---
    document.querySelectorAll(".prompt-chip").forEach(btn => {
        btn.addEventListener("click", () => {
            chatInput.value = btn.dataset.q;
            sendMessage();
        });
    });

    // --- New chat ---
    newChatBtn.addEventListener("click", () => {
        conversationHistory = [];
        chatMessages.innerHTML = "";
        chatMessages.appendChild(welcome);
        welcome.hidden = false;
        chatInput.value = "";
        chatInput.style.height = "auto";
    });

    // --- Send message ---
    function sendMessage() {
        const text = chatInput.value.trim();
        if (!text || isStreaming) return;

        // Hide welcome
        welcome.hidden = true;

        // Add user bubble
        addMessage("user", text);
        chatInput.value = "";
        chatInput.style.height = "auto";

        // Add assistant bubble (placeholder)
        const assistantEl = addMessage("assistant", "");
        const contentEl = assistantEl.querySelector(".msg-content");
        const thinkingEl = document.createElement("div");
        thinkingEl.className = "thinking-steps";
        contentEl.parentNode.insertBefore(thinkingEl, contentEl);

        // Show typing indicator
        contentEl.innerHTML = '<span class="typing-indicator"><span></span><span></span><span></span></span>';

        scrollToBottom();
        doAgentStream(text, contentEl, thinkingEl);
    }

    // --- Add message bubble ---
    function addMessage(role, text) {
        const wrapper = document.createElement("div");
        wrapper.className = "msg msg-" + role;

        const bubble = document.createElement("div");
        bubble.className = "msg-bubble";

        if (role === "user") {
            bubble.innerHTML = '<div class="msg-content">' + escHtml(text) + '</div>';
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

    // --- Streaming agent call ---
    function doAgentStream(question, contentEl, thinkingEl) {
        isStreaming = true;
        sendBtn.disabled = true;
        abortController = new AbortController();

        // Show cancel button
        sendBtn.textContent = "Cancel";
        sendBtn.disabled = false;
        sendBtn.onclick = cancelStream;

        const payload = {
            question: question,
            history: conversationHistory,
        };

        let answerText = "";

        fetch("/api/agent/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            signal: abortController.signal,
        })
        .then(response => {
            if (!response.ok) return response.json().then(d => Promise.reject(d));

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            function processChunk() {
                return reader.read().then(({ done, value }) => {
                    if (done) {
                        // Save to conversation history
                        if (answerText) {
                            conversationHistory.push({ role: "user", content: question });
                            conversationHistory.push({ role: "assistant", content: answerText });
                            if (conversationHistory.length > 20) {
                                conversationHistory = conversationHistory.slice(-20);
                            }
                        }
                        finishStreaming();
                        return;
                    }

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split("\n");
                    buffer = lines.pop();

                    for (const line of lines) {
                        if (!line.startsWith("data: ")) continue;
                        let event;
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
                                contentEl.innerHTML = renderMarkdown(answerText);
                                scrollToBottom();
                                break;

                            case "done":
                                if (thinkingEl.children.length === 0) {
                                    thinkingEl.remove();
                                }
                                break;

                            case "error":
                                contentEl.innerHTML = '<div class="msg-error">' + escHtml(event.content) + '</div>';
                                break;
                        }
                    }

                    return processChunk();
                });
            }

            return processChunk();
        })
        .catch(err => {
            if (err.name === "AbortError") {
                contentEl.innerHTML = contentEl.innerHTML || '<div class="msg-error">Cancelled.</div>';
            } else {
                contentEl.innerHTML = '<div class="msg-error">' + escHtml(err.error || "Something went wrong.") + '</div>';
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

    function finishStreaming() {
        isStreaming = false;
        abortController = null;
        // Restore send button
        sendBtn.textContent = "\u2191";
        sendBtn.disabled = false;
        sendBtn.onclick = sendMessage;
        chatInput.focus();
    }

    // --- Thinking steps inside assistant bubble ---
    function addThinkingStep(container, type, text) {
        container.hidden = false;
        const step = document.createElement("div");
        step.className = "think-step think-" + type;

        const icons = { thought: "\uD83D\uDCAD", tool: "\uD83D\uDD0D", result: "\u2705" };
        step.innerHTML = '<span class="think-icon">' + (icons[type] || "") + '</span><span class="think-text">' + escHtml(text) + '</span>';
        container.appendChild(step);
        scrollToBottom();
    }

    function formatToolCall(name, input) {
        const parts = [name.replace(/_/g, " ")];
        if (input) {
            if (input.query) parts.push('"' + input.query + '"');
            if (input.source_text) parts.push("in " + input.source_text);
            if (input.verse_ref) parts.push(input.verse_ref);
            if (input.school) parts.push("(" + input.school + ")");
        }
        return parts.join(" \u2014 ");
    }

    // --- Markdown renderer (supports verse blocks) ---
    function renderMarkdown(text) {
        let html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // Verse quote blocks: > **BG 2.47** ... (blockquote style)
        html = html.replace(/^&gt;\s?(.*)$/gm, '<div class="verse-quote">$1</div>');

        // Merge consecutive verse-quote divs into one block
        html = html.replace(/(<\/div>\n?<div class="verse-quote">)/g, '<br>');

        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        // Italic
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

        // Code/verse refs in backticks
        html = html.replace(/`([^`]+)`/g, '<code class="verse-ref">$1</code>');

        // Horizontal rule
        html = html.replace(/^---$/gm, '<hr class="section-break">');

        // Headers
        html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>');

        // Lists — wrap consecutive <li> runs (non-greedy per block)
        html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
        html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul class="md-list">$1</ul>');

        // Numbered lists — wrap consecutive numbered items in <ol>
        html = html.replace(/^\d+\.\s(.+)$/gm, '<li class="ol-item">$1</li>');
        html = html.replace(/((?:<li class="ol-item">.*?<\/li>\n?)+)/g, '<ol class="md-olist">$1</ol>');

        // Paragraphs: split on double newlines
        html = html
            .split(/\n{2,}/)
            .map(block => {
                block = block.trim();
                if (!block) return "";
                // Don't wrap already-wrapped elements
                if (block.startsWith("<div") || block.startsWith("<h") || block.startsWith("<ul") || block.startsWith("<ol") || block.startsWith("<hr") || block.startsWith("<li")) {
                    return block;
                }
                return "<p>" + block.replace(/\n/g, "<br>") + "</p>";
            })
            .join("\n");

        return html;
    }

    // --- Helpers ---
    function scrollToBottom() {
        requestAnimationFrame(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    function escHtml(str) {
        if (!str) return "";
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }
})();
