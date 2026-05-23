"""Query the English-only Hindu Scriptures RAG system.

Same pipeline as scripts/rag/query.py but uses local English prompts.
"""

import llm as llm_module
from api_security import validate_and_prepare_question, wrap_untrusted_user_text
from config import LLMProvider, RAGConfig
from hybrid_query import hybrid_search
from moderation import (
    check_openai_output_moderation,
    check_openai_user_moderation,
    finalize_model_output,
)
from sanskrit_gloss import augment_context_with_sanskrit_gloss
from search import format_context

from english_config import get_english_config, get_full_corpus_config  # noqa: F401 — side-effect: path setup
from prompt_templates import QUERY_PROMPT_TEMPLATE, SYSTEM_PROMPT


def query_rag(
    question: str,
    config: RAGConfig | None = None,
    filter_dict: dict | None = None,
) -> dict:
    """Full RAG pipeline: hybrid search -> format prompt -> Claude -> answer + sources."""
    if config is None:
        config = get_english_config()

    question = validate_and_prepare_question(question, config)
    check_openai_user_moderation(question, config)

    full_search_config = get_full_corpus_config(config, top_k=config.top_k)
    results, retrieval_mode = hybrid_search(
        question,
        english_config=config,
        full_config=full_search_config,
        filter_dict=filter_dict,
    )

    if not results:
        return {
            "answer": "No relevant scripture passages were found for your question.",
            "sources": [],
            "retrieval_mode": retrieval_mode,
        }

    context = format_context(results)
    context = augment_context_with_sanskrit_gloss(context, results, question, config)
    user_block = wrap_untrusted_user_text(question)
    user_prompt = QUERY_PROMPT_TEMPLATE.format(context=context, user_message=user_block)

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
    else:
        raise ValueError(f"Unsupported LLM provider: {config.llm_provider}")

    return {
        "answer": answer,
        "sources": results,
        "retrieval_mode": retrieval_mode,
    }
