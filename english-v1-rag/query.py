"""Query the English-only Hindu Scriptures RAG system.

Same pipeline as scripts/rag/query.py but uses local English prompts.
"""

# english_config sets up sys.path (eng_dir first, then rag_dir)
import llm as llm_module
from config import LLMProvider, RAGConfig
from sanskrit_gloss import augment_context_with_sanskrit_gloss
from search import format_context, search

from english_config import get_english_config  # noqa: F401 — side-effect: path setup
from prompt_templates import QUERY_PROMPT_TEMPLATE, SYSTEM_PROMPT


def query_rag(
    question: str,
    config: RAGConfig | None = None,
    filter_dict: dict | None = None,
) -> dict:
    """Full RAG pipeline: hybrid search -> format prompt -> Claude -> answer + sources."""
    if config is None:
        config = get_english_config()

    results = search(question, config=config, filters=filter_dict)

    if not results:
        return {
            "answer": "No relevant scripture passages were found for your question.",
            "sources": [],
        }

    context = format_context(results)
    context = augment_context_with_sanskrit_gloss(context, results, question, config)
    user_prompt = QUERY_PROMPT_TEMPLATE.format(context=context, question=question)

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
    }
