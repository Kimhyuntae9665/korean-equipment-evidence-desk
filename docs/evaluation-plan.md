# Evidence evaluation plan

This plan is frozen before P06 model generation. The delivered v1 gold and separately versioned E6/E8 interpretation erratum stay unchanged; all arms report v1 gold + this erratum. Evaluation case content is not a runtime dependency.

## Experiment A: eight admitted records

For each of the same sixteen frozen query IDs (four development, twelve evaluation), use one fixed eight-record catalog and scope, installed qwen3:4b digest/template and the same answer schema. The source-only arm ranks with lexical/identifier lookup, returns the original field and document ID and makes no model call. The lexical RAG arm supplies its frozen top-k3 whole records; exact model duplicates may exceed k and are never silently removed. The all-context arm supplies all eight whole records in source order. Each generation gets an independent receipt and failure state.

Before any generation, a CPU counter reads the exact rendered prompt for that arm and checks 8192 total context with 1024 reserved for output. Set truncate:false and shift:false; a budget failure is a recorded failure. Choose any smaller corpus before viewing evaluation outputs, if the complete eight-record corpus will not fit. Do not silently drop records. A CPU reconstructed token count remains provisional until compared with an actual runner receipt. Actual whole-request wall time and Ollama total_duration are recorded separately, including structured-output retries if any. No request automatically retries after a timeout.

Measure separately:
- required source fact and quantity presence, with their exact document ID;
- complete multi-record citation coverage where the question requires multiple source records;
- exact raw quote, correct field and source date/scope support;
- interpretation of units, entity, qualifiers and certainty beyond the raw substring check;
- uncertainty, abstention and owner-clarification question quality;
- inappropriate claim of booking, visitor access, calibration, compatibility, physical identity or hazardous settings;
- failed, unsupported, truncated or invalid JSON output;
- elapsed wall time, runner durations, prompt and generated counts, VRAM/RAM and model/template/source fingerprints.

A quote-span check is mechanical and does not certify the meaning of a claim. The source-only retrieval score is coverage, not answer accuracy. Full-context is reported as all-context with warm runtime; CAG/prefix KV reuse is unverified unless direct prefix reuse and invalidation evidence becomes available. prompt_eval_count is not cache-hit proof on installed Ollama 0.17.7. Do not combine engineering test counts, retrieval coverage and model answer scores into one number.

## Experiment B: fifty admitted preview records

Run source-only lexical distractor retrieval on the separately frozen reserved query IDs, with the same ranker settings. Record top-k exact IDs and required spans against that corpus only. Its aggregate is not directly comparable to Experiment A's eight-record generation scores; product families overlap and neither experiment proves unseen-product generalization.

## Source and system changes

Source bytes, document revision, sharing scope, model GGUF layer digest, template, system prompt, schema, corpus ordering and method form each receipt fingerprint. A changed admitted source fails a hash check; an old receipt is no longer served as current. Confirm a subsequent unrelated question has its own fingerprint and no model-answer cache is claimed. If any source/catalog update is desired later, issue a new manifest and benchmark version before comparing results. The current catalog is a captured public preview, not current inventory.
