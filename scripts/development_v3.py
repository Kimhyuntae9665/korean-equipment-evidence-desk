"""Three remaining declared development questions under frozen P06 v3; no eval gold."""
import json
import os
import pathlib
import subprocess
import sys
import time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(pathlib.Path.home()/"ax-lab/artifacts/p06-tokenizer-tooling")]
from equipment_desk.core import Desk
from equipment_desk.llm import Client
CASES=[
 ("D2","디지털 로직 파형 주기 분석 장비 16903A에 표기된 샘플링 속도는 얼마인가?"),
 ("D3","E8363B 두 기록은 모델명이 같은데 하나의 물리 장비로 합쳐도 되는가?"),
 ("D4","오늘 이 장비들의 예약 가능한 시간은 언제인가?")]
target=ROOT/"artifacts/development-v3-remaining.json"
if target.exists():raise RuntimeError("development_receipt_exists_do_not_duplicate")
desk=Desk(ROOT/"data");desk.model_client=Client(desk.snapshots["small8"])
results=[]
for case_id,question in CASES:
 for method in ("rag","all"):
  if os.path.lexists(str(pathlib.Path.home()/".cache/ax-lab/runtime/inference.lock.blocked")):
   raise RuntimeError("inference_blocked_after_timeout")
  before=subprocess.check_output(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader"],text=True).strip()
  response=desk.query({"question":question,"scope":"all","method":method,"corpus":"small8"})
  after=subprocess.check_output(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader"],text=True).strip()
  entry={"case_id":case_id,"method":method,"question":question,
    "receipt":response,"gpu_memory_before":before,"gpu_memory_after":after}
  results.append(entry)
  target.parent.mkdir(parents=True,exist_ok=True)
  target.write_text(json.dumps({"revision":"p06_prompt_v3","development_only":True,
    "results":results},ensure_ascii=False,indent=2))
  metrics=response["model_metrics"] or {}
  print(json.dumps({"case_id":case_id,"method":method,"generation_status":response["generation_status"],
    "error":response["error"],"state":response["answer_state"],
    "fact_ids":[f["document_id"] for f in response["facts"]],
    "quantity_labels":[f["quantity_label"] for f in response["facts"]],
    "cpu_tokens":metrics.get("input_count_cpu_reconstructed"),
    "runner_tokens":metrics.get("input_count_runner_reported"),
    "wall_s":metrics.get("wall_s"),"trace":metrics.get("trace_id"),
    "gpu_after":after},ensure_ascii=False),flush=True)
