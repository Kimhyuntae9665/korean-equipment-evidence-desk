"""Bounded serial local Ollama client, with exact rendered-prompt CPU preflight.

The shared-lock/barrier design follows the independently tested AX Lab P04 client;
this copy is kept inside P06 so the public project has no cross-project import.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
import socket
import stat
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from .model_contract import MODEL,CONTEXT_LIMIT,OUTPUT_RESERVE,NUM_PREDICT,schema,messages,check_proposal,contract_digest
from .tokenizer import load_tokenizer

BASE="http://127.0.0.1:11434"
TEMPLATE_SHA256="2d54db2b9bb29ce7db54fea63a891f5859603813c555b1f88b5e0994652897f9"
THREAD_LOCK=threading.Lock()
EXPECTED_MODEL_LAYER="sha256:3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f"
EXPECTED_TEMPLATE_LAYER="sha256:"+TEMPLATE_SHA256
DISABLED=None
BLOCKED_LEASES=[]
MAX_TRACE_BYTES=2*1024*1024
MAX_TOTAL_TRACE_BYTES=8*1024*1024
def _model_paths():
    configured=os.environ.get("AX_LAB_OLLAMA_MODELS_DIR") or os.environ.get("OLLAMA_MODELS")
    root=Path(configured) if configured else Path("/usr/share/ollama/.ollama/models")
    if not root.is_absolute() or "\x00" in str(root):
        raise RuntimeError("model_store_configuration_invalid")
    manifest=root/"manifests"/"registry.ollama.ai"/"library"/"qwen3"/"4b"
    try:
        with manifest.open("rb") as handle:raw=handle.read(65537)
    except OSError as error:raise RuntimeError("model_manifest_unavailable") from error
    if len(raw)>65536:raise RuntimeError("model_manifest_budget")
    try:data=json.loads(raw)
    except (UnicodeError,json.JSONDecodeError) as error:
        raise RuntimeError("model_manifest_invalid") from error
    layers=data.get("layers") if isinstance(data,dict) else None
    if not isinstance(layers,list):raise RuntimeError("model_manifest_invalid")
    bytype={}
    for layer in layers:
        if not isinstance(layer,dict):raise RuntimeError("model_manifest_invalid")
        kind,digest=layer.get("mediaType"),layer.get("digest")
        if kind in ("application/vnd.ollama.image.model","application/vnd.ollama.image.template"):
            if kind in bytype:raise RuntimeError("model_manifest_ambiguous")
            bytype[kind]=digest
    if bytype.get("application/vnd.ollama.image.model")!=EXPECTED_MODEL_LAYER or bytype.get("application/vnd.ollama.image.template")!=EXPECTED_TEMPLATE_LAYER:
        raise RuntimeError("model_manifest_changed")
    blob=root/"blobs"/EXPECTED_MODEL_LAYER.replace(":","-")
    if not blob.is_file():raise RuntimeError("model_blob_unavailable")
    return manifest,blob

def lock_path():
    value=os.environ.get("AX_LAB_INFERENCE_LOCK")
    path=Path(value) if value is not None else Path.home()/".cache"/"ax-lab"/"runtime"/"inference.lock"
    if not path.is_absolute() or "\x00" in str(path):raise RuntimeError("invalid_inference_lock_configuration")
    return path
def _open_lease():
    path=lock_path()
    parent=path.parent
    if not parent.exists():raise RuntimeError("inference_lock_directory_unavailable")
    dirfd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        meta=os.fstat(dirfd)
        if meta.st_uid!=os.geteuid() or stat.S_IMODE(meta.st_mode)&0o077:
            raise RuntimeError("unsafe_inference_lock_directory")
        fd=os.open(path.name,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,
                   0o600,dir_fd=dirfd)
        item=os.fstat(fd)
        if not stat.S_ISREG(item.st_mode) or item.st_uid!=os.geteuid():
            os.close(fd);raise RuntimeError("unsafe_inference_lock_file")
        os.fchmod(fd,0o600)
        return os.fdopen(fd,"a")
    finally:os.close(dirfd)
def _marker(path):
    return Path(str(path)+".blocked")
def _latch_timeout(lease):
    global DISABLED
    DISABLED="inference_timeout_completion_unverified"
    path=lock_path()
    dirfd=None;fd=None
    try:
        dirfd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:fd=os.open(_marker(path).name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
                       0o600,dir_fd=dirfd)
        except FileExistsError:return
        os.write(fd,b"HTTP timeout: server completion unverified; manual shared-runtime recovery required.\n")
        os.fsync(fd)
    except OSError:
        BLOCKED_LEASES.append(lease)
        DISABLED="inference_timeout_barrier_write_failed_keep_process_alive"
    finally:
        if fd is not None:os.close(fd)
        if dirfd is not None:os.close(dirfd)
def _post(endpoint,payload,timeout):
    raw=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode("utf-8")
    request=urllib.request.Request(BASE+endpoint,data=raw,
        headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:
            data=response.read(MAX_TRACE_BYTES+1)
            if len(data)>MAX_TRACE_BYTES:raise RuntimeError("model_response_budget")
            return json.loads(data)
    except (TimeoutError,socket.timeout) as error:
        raise TimeoutError("ollama_timeout") from error
    except urllib.error.HTTPError as error:
        # HTTP errors do not prove missing data; record their code without raw prompt text.
        raise RuntimeError("ollama_http_"+str(error.code)) from error
    except urllib.error.URLError as error:
        if isinstance(error.reason,(TimeoutError,socket.timeout)):
            raise TimeoutError("ollama_timeout") from error
        raise RuntimeError("ollama_unavailable") from error
def _trace(payload,render,preflight,response,wall_s,error=None):
    folder=Path(__file__).resolve().parents[1]/"artifacts/model-calls"
    folder.mkdir(parents=True,exist_ok=True)
    trace_id=uuid.uuid4().hex
    item={"request":payload,"rendered_template":render,"preflight":preflight,
          "response":response,"wall_s":wall_s,"error":error}
    raw=json.dumps(item,ensure_ascii=False,allow_nan=False,indent=2).encode()
    if len(raw)>MAX_TRACE_BYTES:raise RuntimeError("trace_budget")
    used=sum(item.stat().st_size for item in folder.glob("*.json") if item.is_file())
    if used+len(raw)>MAX_TOTAL_TRACE_BYTES:raise RuntimeError("trace_budget")
    path=folder/(trace_id+".json")
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    with os.fdopen(fd,"wb") as handle:handle.write(raw)
    return trace_id
class Client:
    def __init__(self,snapshot):
        self.snapshot=snapshot
        self.all_doc_ids=tuple(record["document_id"] for record in snapshot.records)
        _,blob=_model_paths()
        self.tokenizer=load_tokenizer(blob)
    def __call__(self,question,packed_text,selected_ids,snapshot,method,scope):
        global DISABLED
        if DISABLED:raise RuntimeError(DISABLED)
        if snapshot is not self.snapshot or method not in ("rag","all"):
            raise ValueError("model_scope_invalid")
        if not THREAD_LOCK.acquire(blocking=False):raise RuntimeError("inference_busy")
        lease=None;started=time.monotonic()
        try:
            lease=_open_lease()
            try:fcntl.flock(lease.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as error:raise RuntimeError("inference_busy") from error
            if os.path.lexists(_marker(lock_path())):
                raise RuntimeError("inference_blocked_after_timeout")
            _model_paths()
            show=_post("/api/show",{"model":MODEL},10)
            template=show.get("template")
            if not isinstance(template,str) or hashlib.sha256(template.encode()).hexdigest()!=TEMPLATE_SHA256:
                raise RuntimeError("model_template_changed")
            prompt=messages(question,packed_text)
            payload={"model":MODEL,"messages":prompt,"format":schema(self.all_doc_ids),
                     "stream":False,"think":False,"truncate":False,"shift":False,
                     "keep_alive":"30s","options":{"num_ctx":CONTEXT_LIMIT,
                     "num_predict":NUM_PREDICT,"temperature":0,"seed":42}}
            try:
                debug=_post("/api/chat",{**payload,"_debug_render_only":True},60)
                rendered=debug.get("_debug_info",{}).get("rendered_template")
                if not isinstance(rendered,str):
                    raise RuntimeError("render_only_missing_template")
                preflight=self.tokenizer.count_rendered_prompt(rendered)
                if preflight["input_tokens"]+OUTPUT_RESERVE>CONTEXT_LIMIT:
                    _trace(payload,rendered,preflight,None,time.monotonic()-started,
                           "context_overflow_preflight")
                    raise RuntimeError("context_overflow_preflight")
                _model_paths()
                response=_post("/api/chat",payload,120)
            except TimeoutError:
                _latch_timeout(lease)
                raise
            trace_id=_trace(payload,rendered,preflight,response,time.monotonic()-started)
            _model_paths()
            if not isinstance(response,dict) or response.get("done") is not True or response.get("done_reason")=="length":
                raise RuntimeError("incomplete_generation")
            message=response.get("message")
            if not isinstance(message,dict) or not isinstance(message.get("content"),str):
                raise RuntimeError("model_message_invalid")
            if message.get("tool_calls"):raise RuntimeError("unexpected_tool_call")
            try:proposal=check_proposal(json.loads(message["content"]),self.all_doc_ids)
            except (ValueError,TypeError) as error:raise RuntimeError("invalid_model_json_or_schema") from error
            raw_prompt_count=response.get("prompt_eval_count")
            if type(raw_prompt_count) is not int or raw_prompt_count != preflight["input_tokens"]:
                raise RuntimeError("runner_token_count_mismatch")
            metrics={key:response[key] for key in
                ("total_duration","load_duration","prompt_eval_duration","prompt_eval_count",
                 "eval_duration","eval_count","done_reason") if key in response}
            metrics.update({"wall_s":round(time.monotonic()-started,3),"trace_id":trace_id,
                "model":MODEL,"model_layer_digest":self.tokenizer.provenance["model_manifest_layer_digest"],
                "template_sha256":TEMPLATE_SHA256,"contract_sha256":contract_digest(self.all_doc_ids),
                "think_requested":False,"thinking_characters":len(message.get("thinking","")),
                "input_count_cpu_reconstructed":preflight["input_tokens"],
                "rendered_prompt_sha256":preflight["rendered_prompt_sha256"],
                "input_count_runner_reported":raw_prompt_count,
                "runner_crosscheck_equal":raw_prompt_count==preflight["input_tokens"],
                "context_limit":CONTEXT_LIMIT,"output_reserve":OUTPUT_RESERVE,
                "truncate":False,"shift":False,"concurrency":1,
                "cag_prefix_kv_reuse_verified":False})
            return proposal,metrics
        finally:
            if lease is not None and lease not in BLOCKED_LEASES:lease.close()
            THREAD_LOCK.release()
