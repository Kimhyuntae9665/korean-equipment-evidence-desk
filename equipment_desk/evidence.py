"""Exact raw citation checks, without semantic entailment or numeric inference."""
from __future__ import annotations

from collections.abc import Mapping
from .catalog import Snapshot, record_sha256

FACT_KEYS = frozenset(("document_id", "field", "quote", "claim", "quantity_label",
                       "value", "unit", "context"))
MAX_FACTS = 8
MAX_TOTAL_TEXT_BYTES = 32768


class EvidenceError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def validate_facts(facts, snapshot: Snapshot, *, allowed_document_ids=None):
    if not isinstance(snapshot, Snapshot):
        raise EvidenceError("invalid_snapshot", "An admitted immutable snapshot is required")
    if not isinstance(facts, list) or len(facts) > MAX_FACTS:
        raise EvidenceError("invalid_facts", "Facts must be a list containing at most eight items")
    admitted = set(snapshot.record_hashes)
    if allowed_document_ids is None:
        allowed = admitted
    else:
        if not isinstance(allowed_document_ids, (list, tuple, set, frozenset)) or any(
                not isinstance(doc_id, str) for doc_id in allowed_document_ids):
            raise EvidenceError("invalid_scope", "Allowed document IDs must be an explicit sequence")
        allowed = set(allowed_document_ids)
        if not allowed.issubset(admitted):
            raise EvidenceError("invalid_scope", "Allowed document IDs are outside the admitted snapshot")
    total_bytes = 0
    validated = []
    for fact in facts:
        if not isinstance(fact, Mapping) or set(fact) != FACT_KEYS:
            raise EvidenceError("invalid_fact_schema", "Fact must contain exactly the eight declared keys")
        for key in ("document_id", "field", "quote", "claim"):
            value = fact[key]
            if not isinstance(value, str) or not value or len(value) > (8000 if key == "quote" else 2000):
                raise EvidenceError("invalid_fact_type", "Fact identity, quote and claim must be bounded nonempty strings")
        for key in ("quantity_label", "value", "unit", "context"):
            value = fact[key]
            if value is not None and (not isinstance(value, str) or len(value) > 2000):
                raise EvidenceError("invalid_fact_type", "Quantity annotations and context must be bounded strings or null")
        try:
            total_bytes += sum(len(value.encode("utf-8")) for value in fact.values() if isinstance(value, str))
        except UnicodeError as exc:
            raise EvidenceError("invalid_fact_text", "Fact text must contain valid Unicode scalars") from exc
        if total_bytes > MAX_TOTAL_TEXT_BYTES:
            raise EvidenceError("evidence_text_budget", "Fact text exceeds its UTF-8 byte budget")
        doc_id = fact["document_id"]
        if doc_id not in admitted or doc_id not in allowed:
            raise EvidenceError("document_outside_scope", "Cited document is outside the admitted selected scope")
        record = snapshot.by_id(doc_id)
        if record_sha256(record) != snapshot.record_hashes[doc_id]:
            raise EvidenceError("source_hash_mismatch", "Admitted record integrity check failed")
        field = fact["field"]
        if field not in record["fields"]:
            raise EvidenceError("unknown_field", "Cited raw field is not present")
        raw, quote = record["fields"][field], fact["quote"]
        start = raw.find(quote)
        if start < 0:
            raise EvidenceError("quote_not_raw", "Quote must match stored raw text exactly")
        if raw.find(quote, start + 1) >= 0:
            raise EvidenceError("ambiguous_quote", "Quote occurs more than once in its raw field")
        validated.append({**dict(fact), "span": [start, start + len(quote)],
                          "source_hash": snapshot.provenance["catalog_sha256"],
                          "record_hash": snapshot.record_hashes[doc_id],
                          "citation_validated": True, "semantic_entailment_verified": False})
    return validated
