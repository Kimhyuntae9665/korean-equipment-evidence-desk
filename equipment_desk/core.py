"""Public-catalog evidence desk. Sources and receipts are read only to visitors."""
from __future__ import annotations
import hashlib
import json
import secrets
import time
import unicodedata
from collections.abc import Mapping
from .catalog import load_snapshot, canonical_bytes, to_plain
from .retrieval import retrieve, all_context, pack_records, BudgetError
from .evidence import validate_facts, EvidenceError

METHODS = frozenset(("source", "rag", "all"))
CORPORA = frozenset(("small8", "preview50"))
SCOPES = frozenset(("all", "internal", "external"))
MAX_QUESTION = 1000
MAX_CONTEXT_BYTES = 100000
MAX_RECEIPTS = 100
POLICY_GATE_REVISION = "p06_public_catalog_gate_v1"

class DeskError(ValueError):
    def __init__(self, code, message):
        self.code=code
        super().__init__(message)

def eligible_records(snapshot, scope):
    if scope not in SCOPES: raise DeskError("invalid_scope","Unknown display scope")
    if scope=="all": return snapshot.records
    needle="내부" if scope=="internal" else "외부"
    return tuple(record for record in snapshot.records
                 if needle in record["fields"].get("공동활용 허용범위",""))

def _question(value):
    if not isinstance(value,str) or not value.strip() or len(value)>MAX_QUESTION:
        raise DeskError("invalid_question","Question must be within 1000 characters")
    return value.strip()

def policy_gate(question):
    """Public snapshot cannot establish live status or physical asset identity."""
    value=unicodedata.normalize("NFKC",question).casefold()
    if (any(word in value for word in ("예약", "booking", "교정 상태", "calibration",
                                      "접근 권한", "방문 권한", "입장 권한"))
            or ("현재" in value and "사용 가능" in value)
            or ("오늘" in value and "가능 시간" in value)):
        return {"code":"live_state_not_in_catalog",
                "reason":"공개 목록에는 현재 예약·교정·방문 권한 상태가 없습니다.",
                "owner_question":"운영 담당자에게 현재 상태와 접근 절차를 확인해 주세요.",
                "model_called":False,"revision":POLICY_GATE_REVISION}
    if (("물리" in value or "실제 장비" in value or "physical" in value)
            and any(word in value for word in ("동일", "같은", "합쳐", "하나", "same", "identical"))):
        return {"code":"physical_identity_not_in_preview",
                "reason":"자료 기록 ID와 같은 모델명은 동일 물리 장비의 증거가 아닙니다.",
                "owner_question":"소유자에게 별도 자산 식별자와 기록 관계를 확인해 주세요.",
                "model_called":False,"revision":POLICY_GATE_REVISION}
    return None

def _source_states(records):
    warnings=[]
    for record in records:
        fields=record["fields"]
        warnings.append({"document_id":record["document_id"],
            "sharing_scope_as_written":fields.get("공동활용 허용범위",""),
            "physical_identity_verified":False,"current_booking_known":False,
            "current_calibration_known":False,"visitor_access_granted":False})
    return warnings

def _identity(snapshot,corpus,scope,method,question,selected_ids,pack_digest):
    return hashlib.sha256(canonical_bytes({
        "catalog_sha256":snapshot.provenance["catalog_sha256"],
        "manifest_sha256":snapshot.provenance["manifest_sha256"],
        "corpus":corpus,"scope":scope,"method":method,"question":question,
        "selected_ids":selected_ids,"pack_digest":pack_digest,"contract":"p06_v1",
        "policy_gate_revision":POLICY_GATE_REVISION})).hexdigest()

class Desk:
    def __init__(self,data_dir,model_client=None):
        self.data_dir=data_dir
        self.snapshots={name:load_snapshot(data_dir,name) for name in ("small8","preview50")}
        self.model_client=model_client
        self.receipts={}

    def _verified(self,corpus):
        if corpus not in CORPORA: raise DeskError("invalid_corpus","Unknown corpus")
        fresh=load_snapshot(self.data_dir,corpus)
        loaded=self.snapshots[corpus]
        if (fresh.provenance["catalog_sha256"]!=loaded.provenance["catalog_sha256"]
                or fresh.provenance["rights_sha256"]!=loaded.provenance["rights_sha256"]):
            raise DeskError("source_changed","Admitted source changed; refresh the project snapshot")
        return loaded

    def catalog(self,corpus="small8",scope="all"):
        snap=self._verified(corpus)
        records=eligible_records(snap,scope)
        return {"corpus":corpus,"scope":scope,
            "records":[{"document_id":r["document_id"],"fields":dict(r["fields"]),
                "record_hash":snap.record_hashes[r["document_id"]]} for r in records],
            "provenance":to_plain(snap.provenance),"warnings":_source_states(records),
            "rights_notice":"Public catalog preview. Sharing labels are not visitor authorization."}

    def query(self,body):
        if not isinstance(body,Mapping) or set(body)-{"question","scope","method","corpus"}:
            raise DeskError("invalid_request","Only declared request fields accepted")
        question=_question(body.get("question"))
        method=body.get("method","source")
        corpus=body.get("corpus","small8")
        scope=body.get("scope","all")
        if method not in METHODS: raise DeskError("invalid_method","Unknown method")
        if corpus not in CORPORA: raise DeskError("invalid_corpus","Unknown corpus")
        if corpus=="preview50" and method!="source":
            raise DeskError("retrieval_only_corpus","50-record corpus is retrieval only")
        snapshot=self._verified(corpus)
        eligible=eligible_records(snapshot,scope)
        begun=time.monotonic()
        ranking=retrieve(question,eligible,top_k=3)
        chosen=ranking["records"] if method!="all" else all_context(eligible)["records"]
        packed=pack_records(chosen,MAX_CONTEXT_BYTES)
        retrieval_ms=(time.monotonic()-begun)*1000
        rid=secrets.token_hex(12)
        receipt={"receipt_id":rid,"contract":"p06_v1","corpus":corpus,"scope":scope,
            "method":method,"question":question,
            "selected_document_ids":packed["document_ids"],
            "selected_records":chosen,
            "source_warnings":_source_states(chosen),
            "ranking":{"scores":ranking["scores"],"index_digest":ranking["index_digest"],
                "index_cost":ranking["index_cost"],"exact_model_ids":ranking["exact_model_ids"],
                "top_k_requested":ranking["top_k_requested"]},
            "context":{"sha256":packed["digest"],"bytes":packed["byte_count"],
                "token_count":None,"all_context_order_fixed":method=="all"},
            "fingerprint":_identity(snapshot,corpus,scope,method,question,
                                    packed["document_ids"],packed["digest"]),
            "source":{"catalog_sha256":snapshot.provenance["catalog_sha256"],
                "manifest_sha256":snapshot.provenance["manifest_sha256"],
                "record_hashes":{d:snapshot.record_hashes[d] for d in packed["document_ids"]},
                "catalog_date":snapshot.provenance.get("catalog_date"),
                "publisher":snapshot.provenance.get("publisher")},
            "facts":[],"answer_state":"NOT_GENERATED","unknowns":[],
            "owner_questions":[],"citation_check":{"raw_span_checked":False,
                "semantic_entailment_verified":False},
            "generation_status":"source_lookup_only" if method=="source" else "model_unavailable",
            "model_metrics":None,"retrieval_ms":round(retrieval_ms,3),
            "rule_gate":None,"error":None}
        if method!="source":
            gate=policy_gate(question)
            if gate is not None:
                receipt.update(generation_status="policy_abstained",answer_state="NOT_ESTABLISHED",
                    unknowns=[gate["reason"]],owner_questions=[gate["owner_question"]],
                    rule_gate=gate,error=gate["code"])
            elif self.model_client is not None:
                try:
                    proposal,metrics=self.model_client(question,packed["text"],
                        packed["document_ids"],snapshot,method,scope)
                    facts=validate_facts(proposal["facts"],snapshot,
                        allowed_document_ids=packed["document_ids"])
                    receipt["context"]["token_count"]=metrics.get("input_count_cpu_reconstructed")
                    receipt["context"]["rendered_prompt_sha256"]=metrics.get("rendered_prompt_sha256")
                    receipt.update(facts=facts,answer_state=proposal["answer_state"],
                        unknowns=proposal["unknowns"],owner_questions=proposal["owner_questions"],
                        citation_check={"raw_span_checked":True,
                            "semantic_entailment_verified":False},
                        generation_status="model_validated_citations_only",
                        model_metrics=metrics)
                except (EvidenceError,DeskError,ValueError,RuntimeError,TimeoutError) as error:
                    known={"context_overflow_preflight","model_template_changed",
                           "inference_busy","inference_blocked_after_timeout",
                           "inference_timeout_completion_unverified","invalid_model_json_or_schema",
                           "incomplete_generation","render_only_missing_template",
                           "ollama_unavailable","model_response_budget",
                           "runner_token_count_mismatch","model_manifest_changed",
                           "model_manifest_unavailable"}
                    label=getattr(error,"code",None)
                    if label is None:
                        label=str(error) if str(error) in known or str(error).startswith("ollama_http_") else type(error).__name__
                    receipt.update(generation_status="model_rejected_or_unavailable",error=label)
            else:
                receipt["error"]="model_not_enabled_until_token_preflight"
        if len(self.receipts)>=MAX_RECEIPTS:
            self.receipts.pop(next(iter(self.receipts)))
        self.receipts[rid]=receipt
        return receipt

    def get_receipt(self,receipt_id):
        try:receipt=self.receipts[receipt_id]
        except KeyError as error:raise DeskError("unknown_receipt","Unknown receipt") from error
        self._verified(receipt["corpus"])
        return receipt
