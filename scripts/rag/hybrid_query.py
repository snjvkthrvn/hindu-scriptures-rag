"""Retrieval-only hybrid search across English and full corpora."""

from __future__ import annotations

from config import RAGConfig
from search import search

from hybrid_router import RetrievalMode, route_question, should_escalate

_RRF_K = 60


def result_identity(result: dict) -> tuple[str, str, str]:
    verse_or_id = result.get("verse_id") or result.get("id")
    if not verse_or_id:
        source_key = result.get("source_text", "")
        location_key = f"{result.get('chapter', '')}:{result.get('verse_num', '')}"
        text_key = (
            result.get("sanskrit")
            or result.get("transliteration")
            or result.get("translation")
            or result.get("commentary_text")
            or ""
        )
        verse_or_id = f"{source_key}|{location_key}|{text_key[:120]}"
    return (
        verse_or_id,
        result.get("chunk_type", "verse"),
        result.get("author", ""),
    )


def choose_richer_result(left: dict, right: dict) -> dict:
    left_richness = sum(
        bool(left.get(field)) for field in ("sanskrit", "transliteration", "commentary_text")
    )
    right_richness = sum(
        bool(right.get(field)) for field in ("sanskrit", "transliteration", "commentary_text")
    )
    if right_richness > left_richness:
        return right
    return left


def dedupe_results(results: list[dict]) -> list[dict]:
    deduped: dict[tuple[str, str, str], dict] = {}
    for result in results:
        identity = result_identity(result)
        if identity in deduped:
            deduped[identity] = choose_richer_result(deduped[identity], result)
        else:
            deduped[identity] = result
    return list(deduped.values())


def fuse_ranked_results(english_results: list[dict], full_results: list[dict], top_k: int) -> list[dict]:
    scored: dict[tuple[str, str, str], dict] = {}

    for corpus, corpus_results in (
        (RetrievalMode.ENGLISH.value, english_results),
        (RetrievalMode.FULL.value, full_results),
    ):
        for idx, result in enumerate(corpus_results, start=1):
            identity = result_identity(result)
            rrf_score = 1.0 / (_RRF_K + idx)
            annotated = dict(result)
            annotated["corpus"] = corpus
            annotated["retrieval_rank"] = idx
            annotated["retrieval_mode"] = RetrievalMode.BOTH.value
            if identity in scored:
                current = scored[identity]
                current["rrf_score"] += rrf_score
                current["result"] = choose_richer_result(current["result"], annotated)
                current["retrieval_rank"] = min(current["retrieval_rank"], idx)
            else:
                scored[identity] = {
                    "result": annotated,
                    "rrf_score": rrf_score,
                    "retrieval_rank": idx,
                }

    fused = []
    for entry in scored.values():
        result = dict(entry["result"])
        result["rrf_score"] = entry["rrf_score"]
        result["retrieval_rank"] = min(
            result.get("retrieval_rank", entry["retrieval_rank"]),
            entry["retrieval_rank"],
        )
        fused.append(result)

    fused.sort(
        key=lambda item: (
            -item.get("rrf_score", 0.0),
            item.get("retrieval_rank", 999999),
        )
    )
    return fused[:top_k]


def _secondary_filter_dict(filter_dict: dict | None) -> dict | None:
    if not filter_dict:
        return filter_dict
    secondary_filters = dict(filter_dict)
    for filter_key in ("source_text", "category", "tradition"):
        secondary_filters.pop(filter_key, None)
    return secondary_filters or None


def _safe_search(question: str, *, config: RAGConfig, filter_dict: dict | None) -> list[dict]:
    return search(question, config=config, filters=filter_dict)


def hybrid_search(
    question: str,
    *,
    english_config: RAGConfig,
    full_config: RAGConfig,
    filter_dict: dict | None = None,
) -> tuple[list[dict], str]:
    mode = route_question(question)
    english_filter_dict = filter_dict
    full_filter_dict = filter_dict
    english_results: list[dict] | None = None
    full_results: list[dict] | None = None
    english_error = None
    full_error = None

    if mode == RetrievalMode.ENGLISH:
        try:
            english_results = _safe_search(
                question,
                config=english_config,
                filter_dict=english_filter_dict,
            )
        except Exception as exc:  # pragma: no cover - behavior tested via fallback
            english_error = exc
            mode = RetrievalMode.BOTH
        if english_error is None and not should_escalate(question, mode, english_results, english_config.top_k):
            return english_results, mode.value
        full_filter_dict = _secondary_filter_dict(filter_dict)
    elif mode == RetrievalMode.FULL:
        try:
            full_results = _safe_search(question, config=full_config, filter_dict=full_filter_dict)
        except Exception as exc:  # pragma: no cover - behavior tested via fallback
            full_error = exc
            mode = RetrievalMode.BOTH
        if full_error is None and not should_escalate(question, mode, full_results, full_config.top_k):
            return full_results, mode.value
        english_filter_dict = _secondary_filter_dict(filter_dict)

    if english_results is None and english_error is None:
        try:
            english_results = _safe_search(
                question,
                config=english_config,
                filter_dict=english_filter_dict,
            )
        except Exception as exc:  # pragma: no cover - behavior tested via fallback
            english_error = exc

    if full_results is None and full_error is None:
        try:
            full_results = _safe_search(question, config=full_config, filter_dict=full_filter_dict)
        except Exception as exc:  # pragma: no cover - behavior tested via fallback
            full_error = exc

    if english_error and full_error:
        raise RuntimeError("Both hybrid search paths failed") from full_error
    if english_error:
        return full_results[: full_config.top_k], RetrievalMode.FULL.value
    if full_error:
        return english_results[: english_config.top_k], RetrievalMode.ENGLISH.value

    return (
        fuse_ranked_results(english_results, full_results, top_k=full_config.top_k),
        RetrievalMode.BOTH.value,
    )
