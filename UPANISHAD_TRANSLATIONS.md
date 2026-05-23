# Upanishad English Translations — Historical Notes

> **Status: historical reference.** This document records a one-off browser-automated scrape of three Max Müller Upanishad translations from sacred-texts.com (Feb 2026). It does NOT describe the current ingestion path: the running corpus pulls Upanishad data from the `indian-scriptures` GitHub repo, not from sacred-texts.com. See [README.md](README.md) for the current corpus sources.
>
> sacred-texts.com is now unreachable from automated pipelines (Cloudflare challenge + ClaudeBot opt-out in robots.txt), so the scrape documented here is not reproducible. The extracted text was folded into the corpus when this was current, and the documentation is preserved for provenance.

## What was extracted

Three Upanishad translations, Max Müller (Sacred Books of the East), public domain:

| Upanishad | Verses | SBE volume | Year |
|---|---:|---|---|
| Isha (Îsâ-Upanishad) | 18 | SBE 1 | 1879 |
| Mundaka | 65 | SBE 15 | 1884 |
| Taittiriya (Taittirîyaka) | 20 | SBE 15 | 1884 |

A fourth target — Mandukya Upanishad — was not extracted because the SBE volumes Sacred Texts hosts don't include it (Mandukya is in K. Narayanasvami Aiyar's "Thirty Shorter Upanishads", which is not in their main collection).

## What's in the corpus now

The 546 Upanishad verses in `final/verses_enriched.json` come from the `indian-scriptures` GitHub repo (CC-BY-4.0). The Mueller translations from the scrape above were integrated into the parallel English-only RAG; see `english-v1-rag/build_english_verses.py` for how they're loaded from `translations/isha_upanishad_mueller.csv` and `translations/mundaka_upanishad_mueller.csv`.

The main corpus is partial on Upanishads (Chandogya absent, Brihadaranyaka 104/891, Taittiriya 20/71, Katha 71/119) — that's a limitation of the `indian-scriptures` source CSVs, not of these Mueller translations. Completing the Upanishads would require a different source repo or a fresh sanctioned scrape.

## Original extraction notes

- **Extracted:** 2026-02-11
- **Method:** Chrome browser automation with JavaScript rendering (Cloudflare requires JS)
- **Total verses retrieved:** 103 (18 + 65 + 20)
- **Translation quality:** Academic / scholarly (Max Müller — SBE series)
- **Encoding:** UTF-8 with Devanagari support
- **Footnotes:** Müller's footnotes preserved separately

The original page URLs (preserved for citation):

- Isha: `https://sacred-texts.com/hin/sbe01/sbe01243.htm`
- Mundaka: `https://sacred-texts.com/hin/sbe15/sbe15016.htm` through `sbe15021.htm` (six sections)
- Taittiriya: 31 individual pages across `sbe15/...` covering Prathama, Dwitiya, and Tritiya Anuvakas
