# Development revision 3: answer-state consistency

Issued before any evaluation-case content was opened or evaluated. The original v1 gold, E6/E8 erratum and earlier development traces are retained unchanged.

Under prompt v2, the declared N9030A development question produced raw-quote-supported 44GHz facts from R44 in both lexical-RAG and all-context. The model simultaneously labeled the answer NOT_ESTABLISHED and repeated the answered question as unknown. Mechanical quote validation accepted the spans, but the proposal was semantically self-contradictory. These two v2 calls are development failures, not two scored successes.

The generic v3 rule tells the model that a directly answered question uses SUPPORTED, a partly answered question uses PARTIAL and NOT_ESTABLISHED has no facts. The deterministic validator now rejects NOT_ESTABLISHED with any fact, just as it rejects SUPPORTED without a fact. Other uncertainty states may retain observed facts and request clarification. No case-specific value, model number or reference answer is added to the prompt. All RAG and all-context final calls must share v3 prompt, schema, source, context budget and model pin.

This change was made on development data only. The final evaluation score remains unmeasured and previous development traces remain separate. v3 must be committed and fit-checked before any evaluation calls.

## Final pre-evaluation identity

- Prompt revision p06_prompt_v3; contract digest cdbee459c15ed519c1a8c3a3f00327afd3318a3c0777614daf0fbf0097cc5a90.
- Prompt/schema source SHA-256 38b152aed148e8d053cb3228a77efbace6a787cac50c1ca64ef10f7623ea130d.
