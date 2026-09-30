# Architecture provenance

This is a code-derived architecture diagram, not a deployment or benchmark claim. The PNG is the README's first illustration; the SVG is its self-contained editable source.

## Actual topology

- **JSON** denotes the admitted KERI DOM-preview projection, loaded from immutable local JSON. It is not the full original CSV or a live factory connection.
- **Browser** is the vanilla JavaScript UI. It sends explicit query/scope/method choices to the loopback Python HTTP server and receives raw records, receipts, and source-checked citations.
- **Python CPU** covers Python standard-library HTTP, immutable snapshot admission, lexical BM25 selection, whole-record packing, and exact raw-quote/span checks. Receipts are in-memory, bounded to 100, and disappear on restart. There is no SQLite or vector database.
- Dashed arrows denote the **optional** generation branch. Python first obtains the exact Ollama-rendered prompt and uses CPU **Tokenizers** for bounded GGUF-metadata-based input preflight. The original rendered bytes are preserved.
- **Ollama** serves the existing pinned **Qwen3 4B** model. Their curved association denotes the model used by that runtime. A process lock and a shared user OS lease serialize requests; a persistent blocked marker prevents retry after unresolved timeout. No parallel GPU execution is depicted.
- The Ollama-to-Python arrow represents a proposed structured answer. Python checks selected-source admission and exact citations before returning it to the browser. Exact citation validation is not semantic entailment.
- Experiment A separates source-only, RAG, and all-context on the same eight admitted rows. Experiment B is fifty-row retrieval-only. All-context is not a claim of CAG/prefix-KV reuse.

The diagram does not assert that the optional runtime was invoked during this documentation task. The integration owner separately reported matching CPU/runner counts of 1199 and 2822 for two development calls, both NOT_ESTABLISHED. Frozen model evaluation and UI integration results remain separate evidence; this documentation lane made no model calls.

## Logo and symbol assets

The Python, JavaScript, Ollama, and Qwen path glyphs came from the already-approved local Simple Icons asset set. Simple Icons artwork is community-maintained; it does not imply vendor endorsement. The upstream [CC0-1.0 license](https://github.com/simple-icons/simple-icons/blob/develop/LICENSE.md) covers that artwork; trademark rights remain separate.

| Glyph | Original source | SHA256 of admitted SVG |
|---|---|---|
| Python | [Simple Icons python.svg](https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/python.svg) | `ad9468e1c4903f73ae7eebfbe980f0f727a10db695be3d914e7d8bd25356a862` |
| JavaScript | [Simple Icons javascript.svg](https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/javascript.svg) | `c9be35a7a861ebe80ae4ee706d05004b99ee59fc63db69da6dcc10776718434b` |
| Ollama | [Simple Icons ollama.svg](https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/ollama.svg) | `9c62bf0159ee96c8b58c86a732f33b002b4b3bb165ec86e8ecca51ad6a82dab6` |
| Qwen | [Simple Icons qwen.svg](https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/qwen.svg) | `36854c60b26bfa5a0cc0d4123727c0ef559efba6f129c0dfa623f3c443fe3e5b` |

JSON braces and the six Tokenizers token boxes are original generic function symbols created for this diagram. They are not official KERI or Hugging Face logos. SQLite artwork is not used.

Each branded source has a square `0 0 24 24` viewBox. Direct path embedding uses uniform scaling: the Python/Ollama/Qwen glyphs fit a 68×68 box, and the JavaScript glyph fits a 52×52 box within its yellow tile. Explicit fitted dimensions preserve proportions; the SVG has no external images, fonts, scripts, or network dependencies.

A consumer-downloaded synthetic logo-rendering compatibility image was viewed at its original 800×510 size as a style reference. Its dark dotted canvas, rounded light cards, curved connectors, and names below symbols guided composition. Its synthetic topology was not copied. Reference bytes: 44,578; SHA256 `c6ad5fda762ea72fb40020e56e6242d74b86c9adff00d95b8027f7981e250df8`. The reference image is not bundled here.

## Inspected source fingerprints

Inspection used source HEAD `d33715a2e6d0cb74bff5fbed57a9e75009b2314e`. The adapter was concurrently under root-owned integration; these SHA256 values identify the actual inspected working-tree bytes rather than implying every file was committed at that HEAD.

| Relative source | SHA256 |
|---|---|
| equipment_desk/catalog.py | `dd18f24a2ba19299e530f48dd474c7f83f253896e29270ed6f4bd01d6633309c` |
| equipment_desk/retrieval.py | `1a8597c73bb35a179745195ac0fc9a8e23dd742bce38a9b38978b836229d5f55` |
| equipment_desk/evidence.py | `ef5a1c8d5af2d503424e854b2154fa2bdf272679f3abb5b201115f70f7d2f4bc` |
| equipment_desk/core.py | `ae3411039fdcd4f6b9dfd7680ae1c93884d062e69264dc1168de94ac3f4cf6f8` |
| equipment_desk/server.py | `bf7b1f28471381572d80ad3c36b9649de8050d5e880f13c03e6648176ce5ea39` |
| equipment_desk/llm.py | `27bc9164bd3f3f931f484a0a9b97d32ce8db794f332c7fc529a452a472e9d49b` |
| equipment_desk/tokenizer.py | `2138d43f7a065ccf0b03f95d46971b04c176de945284a73d64937b43cc5e5815` |
| equipment_desk/model_contract.py | `64994e2f3e7b7468b0a72a337ac2c6a9e5c3c4a8a1f240d96b1c0026dd8e498b` |
| static/app.js | `15eab50e07703e93457e879c37a087f692a0ea4486d27e8ffec54bf38eb25c7d` |

The final lexical method is `lexical_v2`. Development D1 exposed a `lexical_v1` exact-ID boundary failure on `N9030A에` (R44 ranked third); the integration owner versioned a Korean-affix boundary correction before opening evaluation keys. No heldout accuracy improvement is asserted.

Source admission freeze: `1d1bde71f4836486595d527d4703be4834b9efa9`. Admission manifest SHA256: `34ab006877470aa8541418efeb2b6f61c9c7d5d670121a83572b12252db4bdf5`. Neither evaluator files nor runtime model calls were used to design or verify this diagram.

## Render and actual pixel checks

The existing CPU `rsvg-convert` renderer produced a 720×530 PNG. Rebuild with `python3 scripts/render_architecture.py`; this helper installs nothing and invokes no model.

- SVG: 13,185 bytes; SHA256 `b81f1240a4e11f6b92bb7331c8c27f808529ad097e04082c5002cd57e3bfc407`.
- PNG: 51,766 bytes; SHA256 `bb0376d69021ffaaf3bcfebc518fe7f0bede3309262975cc95329ffb1f564009`.
- Actual full-size PNG pixels and an actual Chrome headless 360 px image rendering were viewed. Names, glyph proportions, arrowheads, branches, and card clearances were checked. The 360 px rendering retained readable short labels.
- The private 360×300 verification capture is 23,179 bytes; SHA256 `ded23a3fc621eb9d873b3fa8e6addebcc98a5f20f62dfbecd897dfd54d44ac7c`. It is not a claim of published-image verification, app browser testing, or an actual model demonstration.

The README links the [KERI primary catalog](https://www.data.go.kr/data/15018891/fileData.do) for source rights/default-sharing warnings and the [LS ELECTRIC corporate sustainability report](https://www.ls-electric.com/ko/company/data/2025_2026_LSELECTRIC_Sustainability_Report_ENG.pdf#page=11) as a workflow analogy. The LS wording is a corporate self-report of an evolving technical-knowledge platform and a support framework being built, not independent outcome proof.
