# Development revision before held-out evaluation

Issued after inspecting one of the four declared development query families (the N9030A carrier-frequency question), and before opening any evaluation-case contents or running held-out model calls. Original source, v1 gold, E6/E8 erratum and the prior freeze document remain unchanged. This is not an outcome-based edit of evaluation cases.

The v1 lexical exact-ID boundary required a non-alphanumeric character after N9030A. A Korean postposition in “N9030A에” defeated the exact match. R44 still appeared third in the three-record packet, so the two v1 development model attempts abstained even though the source phrase “Maximum 44GHz Carrier Frequency” was present. A third one-record attempt under the same long prompt also abstained. A separate diagnostic using the same one record and a shorter generic extraction instruction cited the source and proposed 44GHz, but misclassified the quantity as frequency_range. That diagnostic is not a benchmark arm or a scored success.

Lexical v2 allows a Hangul syllable at an exact ASCII model identifier boundary while still rejecting Latin/digit supersets. It keeps BM25 parameters, normalization, top-k, exact-duplicate handling and full-record packing unchanged. A regression with “N9030A에” and synthetic N9030A1/XN9030A guards was added. The ranker is versioned as lexical_v2; v1 development traces are preserved.

Prompt v2 is shorter and generic. It asks the model to locate the matching record/field and quote raw text, defines the property-label vocabulary without stating any case answer, and retains untrusted-source, no invented availability/access and uncertainty rules. The same v2 system prompt and schema are used in both final eight-record generation arms. The schema allows an empty facts array, but rejects SUPPORTED with no fact. Template, model pin, no-truncation, output reserve, source set, and E6/E8 erratum stay fixed.

All final method comparisons must use the final v2 ranker and prompt, rather than pooling v1 diagnostic outcomes into the score. No gain in generalization or final quality is claimed here. We will record v2 development tests separately and evaluate the still-unopened twelve evaluation cases only after v2 is committed and fit-checked.

## Final pre-evaluation identity

- Prompt revision: p06_prompt_v2; contract digest d457cf4b880fd1932d9cec02130060f6b2aa2a9aff2d5d41a83b3f08be345ecf.
- Prompt/schema source SHA-256: 07ef9c7f1c9d13218a32fdfd98d302e4e1d000cd16180289a59a512c69fd7790.
- These values identify the final v2 candidate; runner/template/source pins remain in model-freeze.md.
