# Independent pre-public P06 source review

Astra low read the P06 Python source without editing, running tests, reading evaluator cases or making model/GPU calls. The first pass found two Medium issues before any P06 generation:

1. The client recorded a CPU token count versus runner prompt_eval_count comparison but did not reject missing, boolean or unequal runner values.
2. A mutable qwen3:4b tag could point at different GGUF weights while the receipt still attributed the pinned local tokenizer layer.

The corrected client now verifies the installed manifest's model and template layers at initialization, before rendering, before generation and after the response. It also requires a real integer runner prompt_eval_count exactly equal to the CPU count, rejecting any mismatch before returning a proposal. CPU mock tests cover wrong, missing and boolean counts plus model-layer drift before generation. These checks are conservative: a false mismatch fails rather than yielding an answer. Actual Ollama runner parity and context fit still require the later P06 GPU stage. A tag repoint and reversal strictly between two filesystem reads is not independently attested by this check; public evaluation is tied to the recorded installed digest and request trace.

The reviewer otherwise identified no additional High/Medium in the bounded source review. Citation validity means exact raw field span, selected document and hash only. Semantic claim support requires separate evaluation and is not certified by this review.
