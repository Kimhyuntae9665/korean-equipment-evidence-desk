import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from equipment_desk.catalog import load_snapshot
from equipment_desk import llm
from equipment_desk.model_contract import check_proposal

class FakeTokenizer:
    provenance={"model_manifest_layer_digest":"sha256:3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f"}
    def __init__(self,count):self.count=count
    def count_rendered_prompt(self,rendered):
        return {"input_tokens":self.count,"rendered_prompt_sha256":hashlib.sha256(rendered.encode()).hexdigest(),
                "prompt_utf8_bytes":len(rendered.encode())}

class ModelCPUContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=load_snapshot(ROOT/"data")
        cls.ids=[r["document_id"] for r in cls.snapshot.records]
    def setUp(self):
        # CPU contract tests use a synthetic installed-model path, so CI needs no Ollama weights.
        model_paths = patch.object(llm, "_model_paths", return_value=(None, None))
        model_paths.start()
        self.addCleanup(model_paths.stop)

    def test_false_supported_without_quote_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"supported_without_citation"):
            check_proposal({"answer_state":"SUPPORTED","facts":[],
                "unknowns":[],"owner_questions":[]},self.ids)
    def test_preflight_overflow_stops_before_actual_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock=Path(tmp)/"inference.lock"
            with patch.object(llm,"load_tokenizer",return_value=FakeTokenizer(8000)),patch.object(
                llm,"lock_path",return_value=lock),patch.object(
                llm,"TEMPLATE_SHA256",hashlib.sha256(b"template").hexdigest()),patch.object(
                llm,"_trace",return_value="fake-cpu-trace"),patch.object(
                llm,"_post",side_effect=[{"template":"template"},{"_debug_info":{"rendered_template":"full prompt"}}]) as post:
                client=llm.Client(self.snapshot)
                with self.assertRaisesRegex(RuntimeError,"context_overflow_preflight"):
                    client("질문",'{"documents":[]}',self.ids[:3],self.snapshot,"rag","all")
                self.assertEqual(post.call_count,2)
                self.assertEqual(post.call_args_list[1].args[0],"/api/chat")
                debug_payload=post.call_args_list[1].args[1]
                self.assertIs(debug_payload["_debug_render_only"],True)
                self.assertIs(debug_payload["truncate"],False)
                self.assertIs(debug_payload["shift"],False)
                self.assertIs(debug_payload["think"],False)
                self.assertEqual(debug_payload["options"]["num_ctx"],8192)
                self.assertFalse(Path(str(lock)+".blocked").exists())
    def test_runner_count_mismatch_missing_and_bool_rejected(self):
        for reported in (499,None,True):
            with self.subTest(reported=reported),tempfile.TemporaryDirectory() as tmp:
                lock=Path(tmp)/"inference.lock"
                reply={"done":True,"done_reason":"stop","message":{"content":json.dumps({
                    "answer_state":"NOT_ESTABLISHED","facts":[],"unknowns":[],"owner_questions":[]})}}
                if reported is not None:reply["prompt_eval_count"]=reported
                fake=[{"template":"template"},{"_debug_info":{"rendered_template":"full prompt"}},reply]
                with patch.object(llm,"load_tokenizer",return_value=FakeTokenizer(500)),patch.object(
                    llm,"lock_path",return_value=lock),patch.object(
                    llm,"TEMPLATE_SHA256",hashlib.sha256(b"template").hexdigest()),patch.object(
                    llm,"_trace",return_value="fake-cpu-trace"),patch.object(
                    llm,"_post",side_effect=fake) as post:
                    client=llm.Client(self.snapshot)
                    with self.assertRaisesRegex(RuntimeError,"runner_token_count_mismatch"):
                        client("질문",'{"documents":[]}',self.ids[:3],self.snapshot,"rag","all")
                    self.assertEqual(post.call_count,3)
    def test_model_manifest_drift_before_generation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock=Path(tmp)/"inference.lock"
            with patch.object(llm,"load_tokenizer",return_value=FakeTokenizer(500)),patch.object(
                llm,"lock_path",return_value=lock),patch.object(
                llm,"TEMPLATE_SHA256",hashlib.sha256(b"template").hexdigest()),patch.object(
                llm,"_trace",return_value="fake-cpu-trace"),patch.object(
                llm,"_model_paths",side_effect=[(None,None),(None,None),RuntimeError("model_manifest_changed")]),patch.object(
                llm,"_post",side_effect=[{"template":"template"},{"_debug_info":{"rendered_template":"full prompt"}}]) as post:
                client=llm.Client(self.snapshot)
                with self.assertRaisesRegex(RuntimeError,"model_manifest_changed"):
                    client("질문",'{"documents":[]}',self.ids[:3],self.snapshot,"rag","all")
                self.assertEqual(post.call_count,2)

    def test_no_cross_snapshot_generation(self):
        with patch.object(llm,"load_tokenizer",return_value=FakeTokenizer(1)):
            client=llm.Client(self.snapshot)
        other=load_snapshot(ROOT/"data")
        with self.assertRaisesRegex(ValueError,"model_scope_invalid"):
            client("x","{}",self.ids[:1],other,"rag","all")

if __name__=="__main__":unittest.main()
