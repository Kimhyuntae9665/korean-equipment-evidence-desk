# P06 pre-evaluation generation freeze

Issued before every P06 model request and before reading any evaluation case outcome.

- Base delivered v1 gold SHA-256: 185b28959db3e67f107b884d79f5ebaa169388daa820c1608a337b2818b9c8e1.
- Separately versioned KERI-v1-E6-E8-interpretation-1 SHA-256: 4a41d0616feb028bf74bf15465b0f23e8a2a7fba2ed4677854066a1fd860553f.
- Report each arm as v1 gold + this erratum. Research-side original gold hash as supplied is separately recorded in the erratum; delivered bundle manifest is the byte authority. No domain adjudication is asserted.
- Admitted runtime manifest SHA-256: 34ab006877470aa8541418efeb2b6f61c9c7d5d670121a83572b12252db4bdf5; selected eight-record catalog SHA-256: d0e5cad515090391f745a93551084cabfde89b4c97cee2aeea3de6bffdc01479.
- Ranker: equipment_desk/retrieval.py committed at 6cfe165e; BM25 k1 1.2 / b 0.75, exact model duplicates source order, top-k3 whole records.
- Generation contract digest (schema, system prompt, model, context and output budgets): 4d685d197ced4a8bb6defd75de39a41a50e4bca66e3b70fa42cb838fac9b3b3b. It is shared by lexical RAG and all-context. The user-message wrapper lives in committed model_contract.py; its source hash is 64994e2f3e7b7468b0a72a337ac2c6a9e5c3c4a8a1f240d96b1c0026dd8e498b.
- CPU tokenizer implementation committed at 1280d1f8. Metadata SHA-256: 82e92c41ef7f47671922432da66dce6a15bb89d54b429f410820f47e91583621. Runner count parity remains unverified until P06 regains the GPU lease.
- Installed Ollama template SHA-256: 2d54db2b9bb29ce7db54fea63a891f5859603813c555b1f88b5e0994652897f9. GGUF model layer digest: sha256:3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f.
- Experiment A: same eight records, same sixteen frozen query IDs, same scope, same schema/model/digest. Source-only lexical lookup has no model call. Lexical RAG top-k3 and source-order all-context are separate model arms. Each gets its own required fact, quote, abstention, inappropriate access/capability and latency receipt. Actual model failures stay failures.
- Experiment B: separate 50-record retrieval distractor evaluation; generation prohibited. Its aggregate must not be compared directly to eight-record generation results.
- All-context is not labeled CAG unless direct prefix KV reuse, suffix reset, source update, scope/model/template mismatch and eviction behavior can be evidenced. Ollama v0.17.7 prompt_eval_count alone is insufficient.
- Before any generation, count each complete Ollama rendered prompt using the installed GGUF vocabulary and reserve 1024 tokens of the 8192 context. A failed fit blocks that request. Do not drop records, silently truncate or shift context. CPU reconstructed tokenizer must be cross-checked against actual runner counts; report parity limits.
- Initial source/gold/receipt/text-trace budget 10 MiB excluding media and existing weights. Quotes are raw-codepoint spans, not semantic proof. Sharing labels do not grant visitor access.
