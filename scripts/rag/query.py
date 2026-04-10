"""Query the Hindu Scriptures RAG system.

Uses Qdrant hybrid search (dense Cohere + sparse BM25) and Claude for generation.
Falls back to Ollama if Anthropic API key is not set.

Usage:
    from scripts.rag.query import query_rag
    answer = query_rag("What does the Bhagavad Gita say about duty?")
"""

import llm as llm_module
from config import LLMProvider, RAGConfig
from sanskrit_gloss import augment_context_with_sanskrit_gloss
from search import format_context, search

from prompt_templates import QUERY_PROMPT_TEMPLATE, SYSTEM_PROMPT


def query_rag(
    question: str,
    config: RAGConfig | None = None,
    filter_dict: dict | None = None,
) -> dict:
    """Full RAG pipeline: hybrid search → format prompt → Claude → answer + sources.

    Returns dict with keys: answer, sources.
    """
    if config is None:
        config = RAGConfig()

    # Retrieve via hybrid search
    results = search(question, config=config, filters=filter_dict)

    if not results:
        return {
            "answer": "No relevant scripture passages were found for your question.",
            "sources": [],
        }

    # Format prompt; Haiku pre-pass for Devanagari reading aids, then main model for the answer
    context = format_context(results)
    context = augment_context_with_sanskrit_gloss(context, results, question, config)
    user_prompt = QUERY_PROMPT_TEMPLATE.format(context=context, question=question)

    # Call LLM
    if config.llm_provider == LLMProvider.ANTHROPIC:
        answer = llm_module.generate(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            config=config,
        )
    elif config.llm_provider == LLMProvider.OLLAMA:
        # Fallback to Ollama via LangChain
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

    return {
        "answer": answer,
        "sources": results,
    }
