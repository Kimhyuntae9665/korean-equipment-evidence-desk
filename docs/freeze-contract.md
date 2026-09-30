# Pre-model contract

Original Library ZIP and exact delivered files are unchanged; delivery manifest hashes are authoritative. Runtime corpus is8selected public-preview records or separate50-record retrieval distractor corpus. Original gold remains evaluator-only. The E6/E8 scoring erratum is separately versioned and predates every P06 model call; all methods use v1 gold + this erratum.

ExperimentA: sameeligible8records/model/template/schema/query/scope. Source-only lookup, frozen lexical top-k3 generation and all-context fixedorder generation are distinct arms. Scope defaultall8, no physical dedup. ExperimentB50-record retrieval only, reported separately. No dense encoder/download.

Lexical v1: NFKC+HTML-unescape for index ONLY, preserve raw strings. Unicode alphabetic/digit tokens, Korean character bigrams within runs, fixedBM25 k1=1.2 b=.75. Exact mentioned model identifier selects all same-model records in source-order before other ranking; ties documentIDlexical. Topk3 means up to3whole records; never omit an eligible exact-ID duplicate silently. If exactmatching records exceedk, retainall orfailexplicitbudget. No tuning on evaluationoutputs. Field spans are Unicode codepoint offsets of rawstoredstrings; citationvalidator must refuse normalized quotes/raw mismatch.

Model JSON contains observed field/span/quote-backed facts, uncertainty, owner questions, answerstate. Server supplies source/scope/model/template/provenance envelope; model doesnotinvent it. No ungrounded capability/access/booking guarantee. Sameoutputschema/systemprompt forRAG/allcontext. Actualtoken/context preflight must precedegeneration andreserveoutputheadroom; inputoverflowfailsclosed. CAGunverifieduntildirectprefixKVreuse/suffixreset/invalidationevidence, notkeep_alive orprompt_eval_count.

Initialsource/gold/receipt/texttracebudget10MiB, weights/media excluded. Savefailedattempts. No modelweights/vectorDB/provideraccounts/securitysettings/unapproveddeletion.
