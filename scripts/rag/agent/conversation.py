"""Conversation memory with sliding window for multi-turn dialogues.

Keeps the last N user/assistant exchanges so follow-up questions work:
  User: "What does the Gita say about yoga?"  → search + answer
  User: "What about chapter 6 specifically?"   → context-aware re-search
"""

from collections import deque


class ConversationMemory:
    """Sliding window conversation memory."""

    def __init__(self, window: int = 10):
        self.window = window
        self._messages: deque[dict] = deque(maxlen=window * 2)  # pairs of user+assistant

    def add(self, role: str, content: str):
        """Add a message to memory."""
        self._messages.append({"role": role, "content": content})

    def get_messages(self) -> list[dict]:
        """Get conversation history as a list of message dicts for the API."""
        return list(self._messages)

    def clear(self):
        self._messages.clear()

    def __len__(self):
        return len(self._messages)
