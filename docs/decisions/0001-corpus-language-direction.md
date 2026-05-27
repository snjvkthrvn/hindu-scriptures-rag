# ADR 0001: Corpus language direction — Sanskrit-first

- **Status:** Accepted
- **Date:** 2026-05-24
- **Decision owner:** repo owner
- **Inputs:** owner directive ("no English RAG") plus a three-way analysis that independently converged — Gemini 3.1 Pro Preview (product/authenticity), Codex (code & data integrity, run with workspace permissions), and a filesystem corpus audit (Claude Code).

## Context

The verse corpus (`final/verses_enriched.json`) grew from ~118,338 records (authoritative Sanskrit recensions) to **214,580** via an English-translation expansion (the `claude/corpus-fixes-and-english-merger` branch / PR #9). An audit showed the growth was largely English-driven and introduced data-integrity problems:

- **~93,030 verses (43%)** are an "Itihasa/Dutt" append — a 19th-c. Calcutta-vulgate recension of the Mahābhārata/Rāmāyaṇa added mainly to carry English. It **thematically overlaps** the Critical-Edition Mahābhārata (73,816) and Valmiki Rāmāyaṇa (22,742) already present; **59,796** of it has no chapter/section metadata.
- **3,212 records are English-only with no Sanskrit** (Rāmāyaṇa 1,830; Mahābhārata 890; Aṣṭāvakra Gītā 298; Yoga Sūtras 194).
- **Parser ID-collapse bugs:** Upaniṣads had already been fixed; Rāmcharitmānas still had 823 colliding IDs at decision time. Follow-up execution also found duplicate IDs in Yajurveda and Valmiki Rāmāyaṇa source data. Because the indexer uses `verse_id` as the Qdrant point ID (`indexer.py:211`, hashed in `vector_store.py:126`), **duplicate IDs silently overwrite points** during reindex.
- A **circular build**: `english-v1-rag/build_english_verses.py` reads English *from* `final/verses_enriched.json`, which `merge_english.py` *writes to* — this fossilized corruption into `verses_english_only.json`.
- At decision time, the indexer embedded `translation > transliteration > sanskrit` (`indexer.py:31`), so **English dominated dense ranking** — it was not display-only.
- `final/metadata.json` was stale at decision time (reported 118,358 vs 214,580 actual; the UI reads it for totals at `app_factory.py:428`).

**Question:** should the corpus be **English-augmented** (keep ~214k, English as a primary retrieval signal) or **Sanskrit-first** (~118k authoritative Sanskrit, English supplementary at most)?

## Decision

**Adopt a Sanskrit-first corpus.** The authoritative Sanskrit verse is the sole canonical, indexed unit.

1. **Remove from the main corpus** the Dutt duplicate-recension append (~93k) and the English-only no-Sanskrit records (~3.2k). The corpus returns to ~118k authoritative-recension verses.
2. **English becomes an attached layer, not a separate verse.** Where a clean, *aligned* translation exists (Bhagavad Gītā, Upaniṣads, partial Vedas), keep it as a `translation` field and embed a **concatenation of Sanskrit + IAST + English** — so English queries still match, but the retrieved unit is the authoritative verse. Where no aligned translation exists (CE Mahābhārata, Valmiki Rāmāyaṇa, Rāmcharitmānas), the verse is Sanskrit-only and cross-lingual retrieval relies on the embedding model + transliteration.
3. **Keep `/beta` (English-only) as a separate experiment** if desired, but **sever its write-back** into the canonical corpus (break the circular build).

This honors the owner's directive, preserves textual authenticity (no mixing recensions/translations as if equivalent), and is bounded engineering rather than an open-ended data program.

## How the decision was reached

Three independent analyses converged on Sanskrit-first:

- **Gemini 3.1 Pro Preview** (product/authenticity): comparable projects (SuttaCentral, Quran/Bible parallel-text tools, Perseus) anchor on the original and attach translations as layers; none index alternate recensions to harvest translations. Recommended Sanskrit-first + the "middle path" data model.
- **Codex** (code/data integrity): English-augmented is a multi-week program (model recensions/translators/alignment, dedup, break the circular build, dual-collection reindex); Sanskrit-first cleanup is bounded (~2–5 days) and lets the merge/append/English-only machinery be deleted.
- **Corpus audit** (Claude Code): quantified the 43% English-driven bulk, the recension overlap, and the integrity bugs above.

## Consequences

**Positive:** smaller, authentic, maintainable corpus; delete the buggy English-merge/append/circular-build machinery; remove recension pollution from retrieval.

**Work required (~2–5 days):**
- Regenerate `final/` to ~118k (exclude Dutt / English-only sources).
- **Fix Rāmcharitmānas ID generation** (`parse_all_scriptures.py:606/651`) — *must precede any reindex*, or ~823 verses are silently dropped in Qdrant.
- Drop the "translation = Sanskrit" fallback (`parse_upanishad_csv.py:144`).
- Change the indexer from translation-first to concatenated/Sanskrit-first embeddable text.
- Add duplicate-ID and metadata-count guards; regenerate `final/metadata.json`.
- Reindex Qdrant.

**Implementation status (2026-05-25):**
- Phase 1/1.5 completed in `ad5cc76`: Rāmcharitmānas kaand normalization fixed, Upaniṣad fallback removed, a global duplicate-ID assertion added, and Yajurveda/Valmiki Rāmāyaṇa duplicate source IDs disambiguated.
- Phase 2 regenerated `final/` from patched parsers: `final/verses.json`, `final/verses_enriched.json`, and `final/metadata.json` now contain **118,338** records with **0 duplicate IDs** on disk.
- Phase 3 severed the circular English build: `merge_english.py` and the Dutt append downloader were removed, and the English beta builder no longer reads from canonical `final/`.
- Phase 5 switched the Qdrant indexer to Sanskrit-first concatenated embedding text (`sanskrit + transliteration + translation`), while preserving translation-only beta indexing behavior.
- Phase 6 implemented a lightweight BM25 alias layer: sparse index/query text now expands Devanāgarī → IAST plus diacritic-stripped/common ASCII forms (`कृष्ण`, `kṛṣṇa`, `krsna`, `krishna`; `mokṣa`, `moksha`). Dense embedding queries remain provider-native.
- Phase 7 preflight added exact Qdrant point-count assertions for verse/commentary chunks. The regenerated corpus should index to **132,285** points (118,338 verses + 13,947 commentaries).
- Still open: reindex Qdrant.

**Key risk — IAST/transliteration normalization.** `krishna` / `kṛṣṇa` / `शिव` fracture lexical (BM25) matching. The implemented mitigation is BM25-only alias expansion on both corpus and query text. It uses `indic-transliteration` for Devanāgarī → IAST and local ASCII/common-spelling folds for Sanskrit terms. Full Harvard-Kyoto/Aksharamukha-style normalization remains unnecessary unless retrieval tests show a concrete gap after reindex.

## Alternatives considered

- **English-augmented (rejected):** keep ~214k with English as a primary signal. Rejected because it contradicts the owner directive, mixes recensions/translations (authenticity loss), and is a multi-week data program with high integrity risk (circular build, unclassified Dutt records, dedup, dual-collection reindex).

## References

- PR #9 (`claude/corpus-fixes-and-english-merger`) — the English expansion this decision steps back from.
- Analyst reports: Gemini 3.1 Pro Preview & Codex (run 2026-05-24); corpus audit findings (same session).
