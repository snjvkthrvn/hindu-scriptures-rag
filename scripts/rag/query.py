"""Query the Hindu Scriptures RAG system.

Uses Qdrant hybrid search (dense embeddings + sparse BM25) and Claude for generation.
Falls back to Ollama if Anthropic API key is not set.

Usage:
    from scripts.rag.query import query_rag
    answer = query_rag("What does the Bhagavad Gita say about duty?")
"""

import llm as llm_module
from config import RAGConfig, LLMProvider
from sanskrit_gloss import augment_context_with_sanskrit_gloss
from search import format_context, search

from prompt_templates import QUERY_PROMPT_TEMPLATE, SYSTEM_PROMPT
from api_security import validate_and_prepare_question, wrap_untrusted_user_text
from moderation import (
    check_openai_user_moderation,
    check_openai_output_moderation,
    finalize_model_output,
)


def query_rag(
    question: str,
    config: RAGConfig | None = None,
    filter_dict: dict | None = None,
) -> dict:
    """Full RAG pipeline: single-corpus search → format prompt → Claude → answer + sources.

    Returns dict with keys: answer, sources.
    """
    if config is None:
        config = RAGConfig()

    question = validate_and_prepare_question(question, config)
    check_openai_user_moderation(question, config)

    # Retrieve from the full corpus only; the English app adds cross-corpus routing above this.
    results = search(question, config=config, filters=filter_dict)

    if not results:
        return {
            "answer": "No relevant scripture passages were found for your question.",
            "sources": [],
        }

    # Format prompt; Haiku pre-pass for Devanagari reading aids, then main model for the answer
    context = format_context(results)
    context = augment_context_with_sanskrit_gloss(context, results, question, config)
    user_block = wrap_untrusted_user_text(question)
    user_prompt = QUERY_PROMPT_TEMPLATE.format(context=context, user_message=user_block)

    # Call LLM
    if config.llm_provider == LLMProvider.ANTHROPIC:
        answer = llm_module.generate(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            config=config,
        )
    elif config.llm_provider == LLMProvider.OLLAMA:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_ollama import ChatOllama

        ollama = ChatOllama(
            model=config.ollama_model,
            base_url=config.ollama_base_url,
            temperature=config.temperature,
        )
        response = ollama.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )
        answer = response.content
    elif config.llm_provider == LLMProvider.OPENAI:
        from openai import OpenAI

        client = OpenAI(api_key=config.openai_api_key)
        resp = client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        answer = resp.choices[0].message.content
    else:
        raise ValueError(f"Unsupported LLM provider: {config.llm_provider}")

    answer = answer or ""
    if config.llm_provider == LLMProvider.OPENAI:
        answer = check_openai_output_moderation(answer, config)
    answer = finalize_model_output(answer, config)

    return {
        "answer": answer,
        "sources": results,
    }
