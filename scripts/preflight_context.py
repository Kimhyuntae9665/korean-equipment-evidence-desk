"""Two-arm development-query render/token fit probe; no generation or evaluator reads."""
import fcntl
import hashlib
import json
import os
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
tooling=Path.home()/"ax-lab/artifacts/p06-tokenizer-tooling"
sys.path.insert(0,str(tooling))
from equipment_desk.catalog import load_snapshot
from equipment_desk.retrieval import retrieve,all_context,pack_records
from equipment_desk.model_contract import MODEL,CONTEXT_LIMIT,OUTPUT_RESERVE,NUM_PREDICT,CONTRACT_REVISION,schema,messages,contract_digest
from equipment_desk import llm

QUESTION="N9030A에 적힌 최대 반송파 주파수는 얼마인가?"
snapshot=load_snapshot(ROOT/"data")
client=llm.Client(snapshot)
all_ids=[r["document_id"] for r in snapshot.records]
ranking=retrieve(QUESTION,snapshot.records,top_k=3)
def check(method):
    records=ranking["records"] if method=="rag" else all_context(snapshot.records)["records"]
    packed=pack_records(records,100000)
    payload={"model":MODEL,"messages":messages(QUESTION,packed["text"]),
             "format":schema(all_ids),"stream":False,"think":False,
             "truncate":False,"shift":False,"keep_alive":"30s",
             "options":{"num_ctx":CONTEXT_LIMIT,"num_predict":NUM_PREDICT,
                        "temperature":0,"seed":42},
             "_debug_render_only":True}
    begin=time.monotonic()
    output=llm._post("/api/chat",payload,75)
    rendered=output.get("_debug_info",{}).get("rendered_template")
    if not isinstance(rendered,str):raise RuntimeError("render_only_missing_template")
    token=client.tokenizer.count_rendered_prompt(rendered)
    return {"method":method,"ranker_method":ranking["method"],"prompt_revision":CONTRACT_REVISION,"query_sha256":hashlib.sha256(QUESTION.encode()).hexdigest(),
            "source_catalog_sha256":snapshot.provenance["catalog_sha256"],
            "model_layer_digest":client.tokenizer.provenance["model_manifest_layer_digest"],
            "template_sha256":llm.TEMPLATE_SHA256,
            "contract_digest":contract_digest(all_ids),
            "packed_sha256":packed["digest"],"packed_bytes":packed["byte_count"],
            "document_ids":packed["document_ids"],
            "input_tokens_cpu":token["input_tokens"],
            "rendered_prompt_sha256":token["rendered_prompt_sha256"],
            "rendered_prompt_utf8_bytes":token["prompt_utf8_bytes"],
            "context_limit":CONTEXT_LIMIT,"output_reserve":OUTPUT_RESERVE,
            "fits":token["input_tokens"]+OUTPUT_RESERVE<=CONTEXT_LIMIT,
            "elapsed_wall_s":round(time.monotonic()-begin,3),
            "runner_parity_verified":False,
            "generation_requests":0}
path=llm.lock_path()
lease=llm._open_lease()
try:
    fcntl.flock(lease.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    if os.path.lexists(str(path)+".blocked"):
        raise RuntimeError("inference_blocked_after_timeout")
    llm._model_paths()
    show=llm._post("/api/show",{"model":MODEL},10)
    if hashlib.sha256(show["template"].encode()).hexdigest()!=llm.TEMPLATE_SHA256:
        raise RuntimeError("model_template_changed")
    try:
        receipts=[check("rag"),check("all")]
    except TimeoutError:
        llm._latch_timeout(lease)
        raise
    llm._model_paths()
    target=ROOT/"artifacts/preflight"
    target.mkdir(parents=True,exist_ok=True)
    out=target/"development-render-fit-v3.json"
    if out.exists():raise RuntimeError("preflight_receipt_already_exists")
    out.write_text(json.dumps(receipts,ensure_ascii=False,indent=2))
    print(json.dumps({"path":str(out),"arms":[
        {"method":r["method"],"input_tokens":r["input_tokens_cpu"],
         "reserve":r["output_reserve"],"limit":r["context_limit"],
         "fits":r["fits"],"packed_bytes":r["packed_bytes"],
         "elapsed_wall_s":r["elapsed_wall_s"]} for r in receipts]},
        ensure_ascii=False))
finally:
    if lease not in llm.BLOCKED_LEASES:lease.close()
