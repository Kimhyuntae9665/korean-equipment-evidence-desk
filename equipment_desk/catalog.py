"""Frozen admitted catalogs; no evaluator files are consulted."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

ADMISSION_MANIFEST_SHA256 = "34ab006877470aa8541418efeb2b6f61c9c7d5d670121a83572b12252db4bdf5"
CORPORA = MappingProxyType({"small8": "catalog-small-8.json", "preview50": "catalog-preview-50.json"})
FIELD_NAMES = frozenset(("한글장비명", "영문장비명", "모델명", "제작사", "활용범위",
                         "공동활용 허용범위", "장비설명", "구성 및 성능"))
MAX_FILE_BYTES = 10 * 1024 * 1024


class CatalogError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def canonical_bytes(value) -> bytes:
    return json.dumps(to_plain(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def to_plain(value):
    if isinstance(value, Mapping):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_plain(item) for item in value]
    return value


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError("duplicate_json_key", "Duplicate JSON object key")
        result[key] = value
    return result


def _json(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_object_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              CatalogError("invalid_json", "Non-finite JSON value")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogError("invalid_json", "Invalid UTF-8 JSON source") from exc


def _read(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as handle:
            raw = handle.read(limit + 1)
    except OSError as exc:
        raise CatalogError("source_unavailable", "Admitted source unavailable") from exc
    if len(raw) > limit:
        raise CatalogError("source_budget", "Admitted source exceeds byte budget")
    return raw


def record_sha256(record: Mapping) -> str:
    return hashlib.sha256(canonical_bytes(record)).hexdigest()


def validate_records(records):
    if not isinstance(records, (tuple, list)):
        raise CatalogError("invalid_records", "Records must be a sequence")
    seen = set()
    for record in records:
        if not isinstance(record, Mapping) or set(record) != {"document_id", "fields"}:
            raise CatalogError("invalid_record", "Record must contain document_id and raw fields")
        doc_id = record["document_id"]
        if not isinstance(doc_id, str) or not doc_id or len(doc_id) > 200 or doc_id in seen:
            raise CatalogError("invalid_document_id", "Document IDs must be nonempty and unique")
        seen.add(doc_id)
        fields = record["fields"]
        if not isinstance(fields, Mapping) or not fields or not set(fields).issubset(FIELD_NAMES):
            raise CatalogError("invalid_fields", "Only admitted projected catalog fields are allowed")
        if any(not isinstance(value, str) for value in fields.values()):
            raise CatalogError("invalid_field_value", "Raw catalog fields must be strings")
    return records


@dataclass(frozen=True)
class Snapshot:
    records: tuple
    provenance: Mapping
    record_hashes: Mapping
    _records_by_id: Mapping

    def by_id(self, document_id: str):
        try:
            return self._records_by_id[document_id]
        except (KeyError, TypeError) as exc:
            raise CatalogError("unknown_document", "Document is outside the admitted snapshot") from exc

    def to_dict(self):
        return {"records": to_plain(self.records), "provenance": to_plain(self.provenance),
                "record_hashes": to_plain(self.record_hashes)}


def load_snapshot(data_dir, corpus="small8", *, expected_manifest_sha256=ADMISSION_MANIFEST_SHA256):
    """Verify exact admitted bytes, then return an immutable single-corpus snapshot.

    A different manifest hash must be explicitly pinned by a caller, including
    synthetic unit fixtures. This is not a hash-verification bypass.
    """
    if corpus not in CORPORA:
        raise CatalogError("unknown_corpus", "Corpus must be small8 or preview50")
    if not isinstance(expected_manifest_sha256, str) or len(expected_manifest_sha256) != 64:
        raise CatalogError("invalid_manifest_pin", "An exact SHA256 manifest pin is required")
    directory = Path(data_dir)
    manifest_raw = _read(directory / "admission-manifest.json", 65536)
    actual_manifest_hash = hashlib.sha256(manifest_raw).hexdigest()
    if actual_manifest_hash != expected_manifest_sha256:
        raise CatalogError("manifest_hash_mismatch", "Admission manifest differs from its frozen pin")
    manifest = _json(manifest_raw)
    if not isinstance(manifest, dict) or manifest.get("gold_runtime_excluded") is not True:
        raise CatalogError("invalid_manifest", "Manifest must exclude evaluator data")
    entries = manifest.get("runtime_files")
    if not isinstance(entries, list):
        raise CatalogError("invalid_manifest", "Runtime admission entries are required")
    by_name = {}
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"file", "sha256", "bytes"}:
            raise CatalogError("invalid_manifest", "Invalid admission entry")
        name, digest, count = item["file"], item["sha256"], item["bytes"]
        if name not in {*CORPORA.values(), "source-rights.json"} or name in by_name:
            raise CatalogError("invalid_manifest", "Only fixed runtime filenames may be admitted")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise CatalogError("invalid_manifest", "Invalid source hash")
        if type(count) is not int or not 0 <= count <= MAX_FILE_BYTES:
            raise CatalogError("invalid_manifest", "Invalid admitted byte count")
        by_name[name] = item
    selected = CORPORA[corpus]
    if selected not in by_name or "source-rights.json" not in by_name:
        raise CatalogError("invalid_manifest", "Selected corpus and source rights must be admitted")
    verified = {}
    for name in (selected, "source-rights.json"):
        entry = by_name[name]
        raw = _read(directory / name, entry["bytes"])
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise CatalogError("source_hash_mismatch", "Admitted source bytes changed")
        verified[name] = _json(raw)
    catalog, rights = verified[selected], verified["source-rights.json"]
    if not isinstance(catalog, dict) or not isinstance(rights, dict):
        raise CatalogError("invalid_source", "Catalog and source rights must be JSON objects")
    records = catalog.get("records")
    validate_records(records)
    if type(catalog.get("admitted_preview_rows")) is not int or catalog["admitted_preview_rows"] != len(records):
        raise CatalogError("invalid_record_count", "Declared admitted row count differs from source")
    frozen_records = tuple(_freeze(record) for record in records)
    hashes = {record["document_id"]: record_sha256(record) for record in frozen_records}
    provenance = {
        "corpus": corpus, "catalog_file": selected, "catalog_sha256": by_name[selected]["sha256"],
        "manifest_sha256": actual_manifest_hash, "rights_sha256": by_name["source-rights.json"]["sha256"],
        "record_count": len(records), "document_id_kind": "snapshot_row",
        "source_url": catalog.get("source_url"), "publisher": catalog.get("publisher"),
        "catalog_date": catalog.get("catalog_date"), "retrieved_at_utc": catalog.get("retrieved_at_utc"),
        "captured_as": catalog.get("captured_as"), "limitations": catalog.get("limitations", []),
        "rights": rights,
    }
    return Snapshot(frozen_records, _freeze(provenance), _freeze(hashes),
                    MappingProxyType({record["document_id"]: record for record in frozen_records}))
