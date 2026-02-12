"""ReAct agent loop using Claude's native tool_use API.

Flow:
  User question
    → Claude reasons (sees tool definitions)
    → Claude calls tool(s) via tool_use blocks
    → Tool results returned to Claude
    → Claude may call more tools or give final answer
    → Final answer with citations
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import RAGConfig
from prompt_templates import AGENT_SYSTEM_PROMPT
import llm as llm_module
from agent.tools import TOOL_DEFINITIONS, execute_tool
from agent.conversation import ConversationMemory


def run_agent(
    question: str,
    config: RAGConfig | None = None,
    memory: ConversationMemory | None = None,
) -> dict:
    """Run the agentic RAG loop.

    Returns:
        {
            "answer": str,          # Final synthesized answer
            "tool_calls": list,     # List of tool calls made
            "sources": list,        # Verse references found
        }
    """
    if config is None:
        config = RAGConfig()

    # Build messages from conversation memory + new question
    if memory is None:
        memory = ConversationMemory(window=config.conversation_window)

    messages = memory.get_messages()
    messages.append({"role": "user", "content": question})

    tool_calls_log = []
    max_turns = config.max_agent_turns

    for turn in range(max_turns):
        # Call Claude with tools
        response = llm_module.generate_with_tools(
            system=AGENT_SYSTEM_PROMPT,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            config=config,
        )

        # Check stop reason
        if response.stop_reason == "end_turn":
            # Claude is done — extract final answer
            answer = "".join(
                block.text for block in response.content if block.type == "text"
            )
            memory.add("user", question)
            memory.add("assistant", answer)

            return {
                "answer": answer,
                "tool_calls": tool_calls_log,
            }

        elif response.stop_reason == "tool_use":
            # Claude wants to call tools — execute them
            # Build the assistant message content (preserve text + tool_use blocks)
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({
                        "type": "text",
                        "text": block.text,
                    })
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            messages.append({"role": "assistant", "content": assistant_content})

            # Execute each tool call
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input

                # Log the tool call
                input_summary = _summarize_input(tool_name, tool_input)
                tool_calls_log.append({
                    "name": tool_name,
                    "input": tool_input,
                    "input_summary": input_summary,
                })

                # Execute (with error recovery so Claude can retry)
                try:
                    result_text = execute_tool(tool_name, tool_input, config)
                except Exception as e:
                    result_text = f"Error executing {tool_name}: {e}. Try a different query or tool."

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

            messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason
            answer = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return {
                "answer": answer or "I encountered an issue processing your question.",
                "tool_calls": tool_calls_log,
            }

    # Max turns exceeded
    return {
        "answer": "I've done extensive research but couldn't fully answer your question within the allowed steps. Here's what I found so far.",
        "tool_calls": tool_calls_log,
    }


def run_agent_stream(
    question: str,
    config: RAGConfig | None = None,
    history: list | None = None,
):
    """Streaming version — yields SSE events for the frontend.

    Event types:
        {"type": "thinking", "content": "..."} — Claude's reasoning text
        {"type": "tool_call", "name": "...", "input": {...}} — Tool being called
        {"type": "tool_result", "name": "...", "summary": "..."} — Tool result summary
        {"type": "answer_chunk", "content": "..."} — Streaming final answer
        {"type": "done", "tool_calls": [...]} — Completion signal
    """
    if config is None:
        config = RAGConfig()

    memory = ConversationMemory(window=config.conversation_window)
    if history:
        for msg in history:
            memory.add(msg.get("role", "user"), msg.get("content", ""))

    messages = memory.get_messages()
    messages.append({"role": "user", "content": question})

    tool_calls_log = []
    max_turns = config.max_agent_turns

    for turn in range(max_turns):
        response = llm_module.generate_with_tools(
            system=AGENT_SYSTEM_PROMPT,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            config=config,
        )

        if response.stop_reason == "end_turn":
            answer = ""
            for block in response.content:
                if block.type == "text":
                    answer += block.text
                    yield {"type": "answer_chunk", "content": block.text}

            # Persist to memory for consistency with non-streaming path
            memory.add("user", question)
            memory.add("assistant", answer)

            yield {"type": "done", "tool_calls": tool_calls_log}
            return

        elif response.stop_reason == "tool_use":
            # Emit thinking text
            for block in response.content:
                if block.type == "text" and block.text.strip():
                    yield {"type": "thinking", "content": block.text}

            # Build assistant message
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            messages.append({"role": "assistant", "content": assistant_content})

            # Execute tools
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                input_summary = _summarize_input(block.name, block.input)
                yield {"type": "tool_call", "name": block.name, "input": block.input}

                tool_calls_log.append({
                    "name": block.name,
                    "input": block.input,
                    "input_summary": input_summary,
                })

                try:
                    result_text = execute_tool(block.name, block.input, config)
                except Exception as e:
                    result_text = f"Error executing {block.name}: {e}. Try a different query or tool."

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

                # Emit a short summary
                result_lines = result_text.strip().split("\n")
                summary = result_lines[0][:120] if result_lines else "No results"
                yield {"type": "tool_result", "name": block.name, "summary": summary}

            messages.append({"role": "user", "content": tool_results})

        else:
            answer = "".join(
                block.text for block in response.content if block.type == "text"
            )
            yield {"type": "answer_chunk", "content": answer or "Something went wrong."}
            yield {"type": "done", "tool_calls": tool_calls_log}
            return

    yield {"type": "answer_chunk", "content": "Reached maximum research steps."}
    yield {"type": "done", "tool_calls": tool_calls_log}


def _summarize_input(tool_name: str, tool_input: dict) -> str:
    """Create a short human-readable summary of a tool call."""
    if tool_name == "search_scriptures":
        q = tool_input.get("query", "")
        src = tool_input.get("source_text", "")
        return f'"{q}"' + (f" in {src}" if src else "")
    elif tool_name == "search_story":
        q = tool_input.get("query", "")
        src = tool_input.get("source_text", "")
        win = tool_input.get("context_window", 10)
        summary = f'story: "{q}"'
        if src:
            summary += f" in {src}"
        summary += f" (±{win} verses)"
        return summary
    elif tool_name == "search_commentaries":
        q = tool_input.get("query", "")
        school = tool_input.get("school", "")
        return f'"{q}"' + (f" ({school})" if school else "")
    elif tool_name in ("get_verse", "compare_schools"):
        return tool_input.get("verse_ref", "")
    return json.dumps(tool_input)[:80]
