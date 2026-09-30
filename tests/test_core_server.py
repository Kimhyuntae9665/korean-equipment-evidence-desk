import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from equipment_desk.core import Desk,DeskError
from equipment_desk.catalog import CatalogError
from equipment_desk.server import make_server

class DeskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desk=Desk(ROOT/"data")
    def test_source_rag_all_evidence_is_separated(self):
        body={"question":"N9030A 최대 반송파 주파수","scope":"all","corpus":"small8"}
        source=self.desk.query({**body,"method":"source"})
        rag=self.desk.query({**body,"method":"rag"})
        full=self.desk.query({**body,"method":"all"})
        self.assertEqual(source["generation_status"],"source_lookup_only")
        self.assertEqual(source["facts"],[])
        self.assertEqual(rag["generation_status"],"model_unavailable")
        self.assertEqual(full["generation_status"],"model_unavailable")
        self.assertIsNone(rag["context"]["token_count"])
        self.assertEqual(len(full["selected_document_ids"]),8)
        self.assertNotEqual(full["context"]["sha256"],rag["context"]["sha256"])
        self.assertFalse(source["citation_check"]["semantic_entailment_verified"])
        self.assertEqual(self.desk.get_receipt(source["receipt_id"])["fingerprint"],source["fingerprint"])
    def test_missing_access_not_granted_by_catalog_sharing(self):
        data=self.desk.catalog("small8","external")
        self.assertTrue(data["records"])
        self.assertTrue(all(not warning["visitor_access_granted"] for warning in data["warnings"]))
        self.assertEqual([r["document_id"] for r in data["records"]],
                         [r["document_id"] for r in self.desk.snapshots["small8"].records
                          if "외부" in r["fields"]["공동활용 허용범위"]])
    def test_retrieval_distractor_corpus_generation_denied(self):
        result=self.desk.query({"question":"E8363B","corpus":"preview50","method":"source"})
        self.assertEqual(result["corpus"],"preview50")
        with self.assertRaisesRegex(DeskError,"retrieval only"):
            self.desk.query({"question":"E8363B","corpus":"preview50","method":"all"})
    def test_output_invalid_quote_does_not_become_validated_answer(self):
        def fake(question,packed,ids,snapshot,method,scope):
            return {"facts":[{"document_id":ids[0],"field":"모델명","quote":"NEVER_IN_SOURCE",
                    "claim":"fabricated","quantity_label":None,"value":None,"unit":None,
                    "context":None}],"answer_state":"SUPPORTED","unknowns":[],"owner_questions":[]},{}
        desk=Desk(ROOT/"data",model_client=fake)
        result=desk.query({"question":"E8363B","method":"rag"})
        self.assertEqual(result["generation_status"],"model_rejected_or_unavailable")
        self.assertEqual(result["facts"],[])
        self.assertEqual(result["error"],"quote_not_raw")
    def test_empty_scope_or_bad_inputs_do_not_synthesize_facts(self):
        for body in ({"question":"","method":"source"},
                     {"question":"x","scope":"factory_admin"},
                     {"question":"x","method":"admin"},
                     {"question":"x","method":"source","anything":1}):
            with self.assertRaises(DeskError):self.desk.query(body)
    def test_live_state_and_physical_identity_are_policy_abstentions_without_model(self):
        def forbidden_model(*args):
            raise AssertionError("model_must_not_run")
        desk=Desk(ROOT/"data",model_client=forbidden_model)
        for question,expected in (("오늘 이 장비들의 예약 가능한 시간은 언제인가?",
                                  "live_state_not_in_catalog"),
                                 ("E8363B 두 기록은 하나의 물리 장비로 합쳐도 되는가?",
                                  "physical_identity_not_in_preview")):
            for method in ("rag","all"):
                with self.subTest(question=question,method=method):
                    receipt=desk.query({"question":question,"method":method})
                    self.assertEqual(receipt["generation_status"],"policy_abstained")
                    self.assertEqual(receipt["error"],expected)
                    self.assertEqual(receipt["facts"],[])
                    self.assertEqual(receipt["answer_state"],"NOT_ESTABLISHED")
                    self.assertFalse(receipt["rule_gate"]["model_called"])
                    self.assertIsNone(receipt["model_metrics"])
        source=desk.query({"question":"오늘 예약 가능한 시간","method":"source"})
        self.assertEqual(source["generation_status"],"source_lookup_only")
        self.assertIsNone(source["rule_gate"])

    def test_source_mutation_blocks_new_and_stored_receipts(self):
        with tempfile.TemporaryDirectory() as temp:
            data=Path(temp)
            for name in ("admission-manifest.json","catalog-small-8.json",
                         "catalog-preview-50.json","source-rights.json"):
                shutil.copy2(ROOT/"data"/name,data/name)
            desk=Desk(data)
            old=desk.query({"question":"N9030A","method":"source"})
            with (data/"catalog-small-8.json").open("ab") as handle:
                handle.write(b" ")
            with self.assertRaises(CatalogError):
                desk.query({"question":"N9030A","method":"source"})
            with self.assertRaises(CatalogError):
                desk.get_receipt(old["receipt_id"])
    def test_scope_and_unrelated_question_change_fingerprint(self):
        a=self.desk.query({"question":"E8363B","scope":"all","method":"source"})
        b=self.desk.query({"question":"E8363B","scope":"internal","method":"source"})
        c=self.desk.query({"question":"N9030A","scope":"all","method":"source"})
        self.assertNotEqual(a["fingerprint"],b["fingerprint"])
        self.assertNotEqual(a["fingerprint"],c["fingerprint"])
        self.assertEqual(a["source"]["catalog_sha256"],c["source"]["catalog_sha256"])

    def test_http_roundtrip_and_host_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            static=Path(temp);(static/"index.html").write_text("sample")
            server=make_server(self.desk,0,static)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                base=f"http://127.0.0.1:{server.server_port}"
                def request(path,body=None,host=None):
                    data=None if body is None else json.dumps(body).encode()
                    headers={"Content-Type":"application/json"}
                    if host:headers["Host"]=host
                    return urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=3)
                with request("/api/catalog") as response:
                    catalog=json.load(response)
                    self.assertEqual(len(catalog["records"]),8)
                    self.assertEqual(response.headers["X-Content-Type-Options"],"nosniff")
                with request("/api/query",{"question":"N9030A","method":"source"}) as response:
                    receipt=json.load(response)["receipt"]
                with request("/api/receipts/"+receipt["receipt_id"]) as response:
                    self.assertEqual(json.load(response)["receipt"]["fingerprint"],receipt["fingerprint"])
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request("/api/catalog",host="evil.example")
                self.assertEqual(error.exception.code,403)
            finally:server.shutdown();server.server_close();thread.join(3)

if __name__=="__main__":unittest.main()
