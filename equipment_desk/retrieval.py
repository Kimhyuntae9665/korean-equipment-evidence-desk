"""Frozen CPU lexical retrieval over raw admitted whole records."""
from __future__ import annotations

import hashlib
import html
import math
import re
import time
import unicodedata
from collections import Counter

from .catalog import canonical_bytes, to_plain, validate_records

METHOD = "lexical_v2"
K1 = 1.2
B = 0.75
MAX_QUERY_CHARS = 4000


class RetrievalError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class BudgetError(RetrievalError):
    def __init__(self, required_bytes, max_bytes):
        self.required_bytes = required_bytes
        self.max_bytes = max_bytes
        super().__init__("context_byte_budget", "Whole-record context exceeds its byte budget")


def normalize_index(text):
    return unicodedata.normalize("NFKC", html.unescape(text)).casefold()


def tokenize(text):
    """Unicode alphanumeric runs plus overlapping bigrams within Korean runs."""
    text = normalize_index(text)
    words, current = [], []
    for char in text:
        if char.isalnum():
            current.append(char)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    tokens = ["w:" + word for word in words]
    for run in re.findall(r"[가-힣]+", text):
        tokens.extend("k:" + run[index:index + 2] for index in range(len(run) - 1))
    return tokens


def _exact_model(query, model):
    normalized = normalize_index(model)
    if len(normalized) < 2 or not any(char.isalnum() for char in normalized):
        return False
    start = 0
    while True:
        index = query.find(normalized, start)
        if index < 0:
            return False
        end = index + len(normalized)
        before = index == 0 or not query[index - 1].isalnum() or "가" <= query[index - 1] <= "힣"
        after = end == len(query) or not query[end].isalnum() or "가" <= query[end] <= "힣"
        if before and after:
            return True
        start = index + 1


def _copy(records):
    validate_records(records)
    return [to_plain(record) for record in records]


def retrieve(query, records, top_k=3):
    if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:
        raise RetrievalError("invalid_query", "Query must be nonempty and within 4000 characters")
    if type(top_k) is not int or not 1 <= top_k <= 100:
        raise RetrievalError("invalid_top_k", "top_k must be an integer from 1 to 100")
    raw_records = _copy(records)
    started = time.perf_counter()
    frequencies = [Counter(tokenize(" ".join(record["fields"].values()))) for record in raw_records]
    lengths = [sum(counter.values()) for counter in frequencies]
    document_frequency = Counter()
    for counter in frequencies:
        document_frequency.update(counter.keys())
    count = len(raw_records)
    average_length = sum(lengths) / count if count else 0
    identity = {"method": METHOD, "normalization": "NFKC_html_unescape_casefold_index_only",
                "tokens": "Unicode_alnum_runs_and_Korean_run_bigrams", "k1": K1, "b": B,
                "query_terms": "unique", "records": raw_records}
    digest = hashlib.sha256(canonical_bytes(identity)).hexdigest()
    built = time.perf_counter()
    terms = set(tokenize(query))
    scores = []
    for counter, length in zip(frequencies, lengths):
        score = 0.0
        for term in sorted(terms):
            frequency = counter.get(term, 0)
            if not frequency:
                continue
            df = document_frequency[term]
            idf = math.log(1 + (count - df + 0.5) / (df + 0.5))
            denominator = frequency + K1 * (1 - B + B * length / average_length)
            score += idf * frequency * (K1 + 1) / denominator
        scores.append(score)
    normalized_query = normalize_index(query)
    exact_indices = [index for index, record in enumerate(raw_records)
                     if _exact_model(normalized_query, record["fields"].get("모델명", ""))]
    exact_set = set(exact_indices)
    remainder = sorted((index for index in range(count) if index not in exact_set),
                       key=lambda index: (-scores[index], raw_records[index]["document_id"]))
    # Exact model duplicates are separate source rows; never discard one to fit k.
    selected = exact_indices + remainder[:max(0, top_k - len(exact_indices))]
    ended = time.perf_counter()
    score_rows = [{"document_id": raw_records[index]["document_id"], "score": scores[index],
                   "rank": rank + 1, "exact_model_match": index in exact_set}
                  for rank, index in enumerate(selected)]
    return {"method": METHOD, "records": [raw_records[index] for index in selected],
            "document_ids": [raw_records[index]["document_id"] for index in selected],
            "scores": score_rows, "index_digest": digest,
            "exact_model_ids": list(dict.fromkeys(raw_records[index]["fields"]["모델명"] for index in exact_indices)),
            "index_cost": {"build_ms": (built - started) * 1000,
                           "query_ms": (ended - built) * 1000, "documents": count,
                           "vocabulary_terms": len(document_frequency),
                           "indexed_tokens": sum(lengths), "k1": K1, "b": B},
            "top_k_requested": top_k, "selected_record_count": len(selected)}


def all_context(records):
    copied = _copy(records)
    return {"method": "source_order_all_context", "records": copied,
            "document_ids": [record["document_id"] for record in copied],
            "digest": hashlib.sha256(canonical_bytes(copied)).hexdigest()}


def pack_records(records, max_bytes):
    """Serialize every selected raw field in source/selection order, or fail.

    Byte preflight is not a model token/context estimate; callers must separately
    run the actual tokenizer preflight before inference.
    """
    if type(max_bytes) is not int or max_bytes < 0:
        raise RetrievalError("invalid_byte_budget", "Byte budget must be a nonnegative integer")
    copied = _copy(records)
    text = json_text = canonical_bytes({"documents": copied}).decode("utf-8")
    encoded = json_text.encode("utf-8")
    if len(encoded) > max_bytes:
        raise BudgetError(len(encoded), max_bytes)
    return {"text": text, "byte_count": len(encoded), "budget_bytes": max_bytes,
            "digest": hashlib.sha256(encoded).hexdigest(), "records": copied,
            "document_ids": [record["document_id"] for record in copied]}
