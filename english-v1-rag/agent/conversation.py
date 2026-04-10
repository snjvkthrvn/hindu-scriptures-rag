"""Re-export ConversationMemory from the shared RAG infrastructure."""

import importlib.util
from pathlib import Path

# Directly load the shared module to avoid circular imports
_shared_conv = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "rag" / "agent" / "conversation.py"
)
_spec = importlib.util.spec_from_file_location("_shared_conversation", _shared_conv)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ConversationMemory = _mod.ConversationMemory
