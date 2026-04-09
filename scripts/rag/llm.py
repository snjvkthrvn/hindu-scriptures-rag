"""Claude LLM wrapper using the anthropic SDK directly (no LangChain).

Supports:
  - Simple question answering (generate)
  - Tool use for the agentic layer (generate_with_tools)
  - Streaming responses
"""

import anthropic

from config import RAGConfig


def get_client(config: RAGConfig | None = None) -> anthropic.Anthropic:
    if config is None:
        config = RAGConfig()
    return anthropic.Anthropic(
        api_key=config.anthropic_api_key,
        timeout=config.api_timeout_sec,
    )


def generate(
    system: str,
    messages: list[dict],
    config: RAGConfig | None = None,
) -> str:
    """Generate a response from Claude (no tools).

    Args:
        system: System prompt.
        messages: List of {"role": "user"|"assistant", "content": ...} dicts.
        config: RAG config.

    Returns:
        Assistant response text.
    """
    if config is None:
        config = RAGConfig()

    client = get_client(config)
    response = client.messages.create(
        model=config.anthropic_model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        system=system,
        messages=messages,
    )

    # Extract text from content blocks
    return "".join(
        block.text for block in response.content if block.type == "text"
    )


def generate_with_tools(
    system: str,
    messages: list[dict],
    tools: list[dict],
    config: RAGConfig | None = None,
) -> anthropic.types.Message:
    """Generate a response from Claude with tool use enabled.

    Returns the full Message object so the caller can inspect tool_use blocks.
    """
    if config is None:
        config = RAGConfig()

    client = get_client(config)
    return client.messages.create(
        model=config.anthropic_model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        system=system,
        messages=messages,
        tools=tools,
    )


def generate_stream(
    system: str,
    messages: list[dict],
    config: RAGConfig | None = None,
):
    """Stream a response from Claude. Yields text chunks.

    Usage:
        for chunk in generate_stream(system, messages):
            print(chunk, end="", flush=True)
    """
    if config is None:
        config = RAGConfig()

    client = get_client(config)

    with client.messages.stream(
        model=config.anthropic_model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        system=system,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
