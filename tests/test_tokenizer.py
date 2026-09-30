import dataclasses
import hashlib
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest import mock

import equipment_desk.tokenizer as module
from equipment_desk.tokenizer import (DEFAULT_GGUF_PATH, EXPECTED_METADATA_SHA256,
                                     GGUFTokenizer, TokenizerError, load_tokenizer,
                                     read_gguf_metadata)


def string(text):
    raw = text.encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw


def value(kind, item):
    formats = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f",
               7: "B", 10: "Q", 11: "q", 12: "d"}
    if kind in formats:
        return struct.pack("<" + formats[kind], item)
    if kind == 8:
        return string(item)
    if kind == 9:
        inner_kind, items = item
        return struct.pack("<IQ", inner_kind, len(items)) + b"".join(value(inner_kind, x) for x in items)
    raise AssertionError("Unsupported test value")


def gguf(entries=(), tensor_count=1, version=3):
    return b"GGUF" + struct.pack("<IQQ", version, tensor_count, len(entries)) + b"".join(
        string(key) + struct.pack("<I", kind) + value(kind, item) for key, kind, item in entries)


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "synthetic.gguf"

    def tearDown(self):
        self.temp.cleanup()

    def read(self, raw):
        self.path.write_bytes(raw)
        return read_gguf_metadata(self.path)

    def error(self, code, raw):
        with self.assertRaises(TokenizerError) as context:
            self.read(raw)
        self.assertEqual(context.exception.code, code)

    def test_standard_scalar_types_and_string_arrays_are_read_exactly(self):
        entries = [("u8", 0, 255), ("i8", 1, -7), ("u16", 2, 60000), ("i16", 3, -300),
                   ("u32", 4, 123456), ("i32", 5, -123456), ("float", 6, 1.25),
                   ("bool", 7, True), ("text", 8, "원문 &times; 😀"),
                   ("tokens", 9, (8, ["한글", " raw "])), ("u64", 10, 2**40),
                   ("i64", 11, -(2**40)), ("double", 12, 1.125)]
        prefix = gguf(entries)
        metadata = self.read(prefix + b"NOT_TENSOR_METADATA_OR_WEIGHTS")
        self.assertEqual(metadata.version, 3)
        self.assertEqual(metadata.metadata_bytes, len(prefix))
        self.assertEqual(metadata.metadata_sha256, hashlib.sha256(prefix).hexdigest())
        self.assertEqual(metadata.values["tokens"], ("한글", " raw "))
        self.assertEqual(metadata.values["text"], "원문 &times; 😀")
        self.assertEqual(metadata.values["u64"], 2**40)
        self.assertIs(metadata.values["bool"], True)
        with self.assertRaises(TypeError):
            metadata.values["text"] = "mutated"

    def test_reader_never_crosses_metadata_end_into_tensor_or_weights(self):
        prefix = gguf([("name", 8, "synthetic")], tensor_count=398)
        class Guard(io.BytesIO):
            def read(self, size=-1):
                if size < 0 or self.tell() + size > len(prefix):
                    raise AssertionError("Attempted tensor/weight read")
                return super().read(size)
        with mock.patch.object(Path, "open", return_value=Guard(prefix + b"WEIGHTS")):
            metadata = read_gguf_metadata(self.path)
        self.assertEqual(metadata.metadata_bytes, len(prefix))
        self.assertEqual(metadata.tensor_count, 398)

    def test_invalid_magic_version_and_truncation_fail_closed(self):
        self.error("gguf_magic", b"NOPE")
        self.error("gguf_version", gguf(version=2))
        self.error("truncated_gguf", b"GGUF" + b"\x03")
        self.error("truncated_gguf", gguf([("text", 8, "abc")])[:-1])

    def test_duplicate_and_empty_keys_rejected(self):
        self.error("metadata_duplicate_key", gguf([("key", 8, "a"), ("key", 8, "b")]))
        self.error("metadata_duplicate_key", gguf([("", 8, "a")]))

    def test_unsupported_scalar_and_empty_array_type_rejected(self):
        header = gguf([])
        raw = header[:16] + struct.pack("<Q", 1) + string("key") + struct.pack("<I", 99)
        self.error("metadata_type", raw)
        raw = header[:16] + struct.pack("<Q", 1) + string("key") + struct.pack("<IIQ", 9, 99, 0)
        self.error("metadata_type", raw)

    def test_invalid_boolean_is_not_coerced_to_truthy(self):
        self.error("metadata_bool", gguf([("bool", 7, 2)]))

    def test_invalid_utf8_metadata_rejected(self):
        prefix = gguf([])[:16] + struct.pack("<Q", 1) + string("key") + struct.pack("<IQ", 8, 1)
        self.error("metadata_unicode", prefix + b"\xff")

    def test_oversized_string_array_header_and_total_read_budget(self):
        prefix = gguf([])[:16] + struct.pack("<Q", 1)
        self.error("metadata_string_budget", prefix + struct.pack("<Q", module.MAX_STRING_BYTES + 1))
        self.error("metadata_array_budget", prefix + string("array") + struct.pack(
            "<IIQ", 9, 0, module.MAX_ARRAY_ITEMS + 1))
        self.error("metadata_count", b"GGUF" + struct.pack("<IQQ", 3, 100001, 0))
        self.error("metadata_count", b"GGUF" + struct.pack("<IQQ", 3, 0, 2049))
        with mock.patch.object(module, "MAX_METADATA_BYTES", 23):
            self.error("metadata_budget", gguf())

    def test_nested_arrays_have_a_depth_bound(self):
        nested = (0, [1])
        for _ in range(6):
            nested = (9, [nested])
        self.error("metadata_depth", gguf([("nested", 9, nested)]))

    def test_metadata_pin_failure_precedes_engine_import(self):
        raw = gguf([("tokenizer.ggml.model", 8, "gpt2")])
        self.path.write_bytes(raw)
        with mock.patch.object(module.importlib, "import_module", side_effect=AssertionError("Engine accessed")):
            with self.assertRaises(TokenizerError) as context:
                load_tokenizer(self.path)
        self.assertEqual(context.exception.code, "metadata_hash_mismatch")

    def test_missing_gguf_is_a_safe_typed_error(self):
        with self.assertRaises(TokenizerError) as context:
            read_gguf_metadata(self.path)
        self.assertEqual(context.exception.code, "gguf_unavailable")


class PromptBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.engine = mock.Mock()
        self.engine.encode.return_value.ids = [1, 2]
        self.tokenizer = GGUFTokenizer(self.engine, MappingProxyType({"test": "synthetic"}))

    def test_prompt_hash_preserves_raw_utf8_crlf_entities_and_spaces(self):
        prompt = "앞😀  &times;\r\n"
        result = self.tokenizer.count_rendered_prompt(prompt)
        self.engine.encode.assert_called_once_with(prompt, add_special_tokens=False)
        self.assertEqual(result["rendered_prompt_sha256"], hashlib.sha256(prompt.encode()).hexdigest())
        self.assertEqual(result["prompt_utf8_bytes"], len(prompt.encode()))
        self.assertEqual(result["input_tokens"], 2)
        self.assertFalse(result["runner_crosscheck_verified"])

    def test_wrong_type_lone_surrogate_and_byte_overflow_fail_before_encode(self):
        for prompt, code in [(None, "invalid_prompt"), ("\ud800", "invalid_prompt_unicode"),
                             ("x" * (module.MAX_PROMPT_BYTES + 1), "prompt_byte_budget")]:
            with self.assertRaises(TokenizerError) as context:
                self.tokenizer.encode(prompt)
            self.assertEqual(context.exception.code, code)
        self.engine.encode.assert_not_called()

    def test_engine_failure_is_not_reported_as_a_count(self):
        self.engine.encode.side_effect = RuntimeError("private internal")
        with self.assertRaises(TokenizerError) as context:
            self.tokenizer.count("raw")
        self.assertEqual(context.exception.code, "tokenization_failed")
        self.assertNotIn("private internal", str(context.exception))


@unittest.skipUnless(DEFAULT_GGUF_PATH.is_file() and importlib.util.find_spec("tokenizers"),
                     "Requires existing GGUF and explicitly installed pinned CPU tokenizer")
class ExistingQwenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokenizer = load_tokenizer()
        cls.metadata = read_gguf_metadata()

    def test_exact_existing_metadata_pin_and_sizes(self):
        self.assertEqual(self.metadata.metadata_sha256, EXPECTED_METADATA_SHA256)
        self.assertEqual(self.metadata.metadata_bytes, 5933099)
        self.assertEqual(self.tokenizer.provenance["vocabulary_size"], 151936)
        self.assertEqual(self.tokenizer.provenance["merge_count"], 151387)
        self.assertEqual(self.tokenizer.provenance["special_tokens"], 26)

    def test_known_special_token_ids_and_no_automatic_bos_eos(self):
        for text, token_id in [("<|endoftext|>", 151643), ("<|im_start|>", 151644),
                               ("<|im_end|>", 151645), ("<think>", 151667),
                               ("</think>", 151668)]:
            self.assertEqual(self.tokenizer.encode(text), (token_id,))
        self.assertEqual(self.tokenizer.encode(""), ())
        self.assertNotIn(151643, self.tokenizer.encode("plain text"))
        self.assertNotIn(151645, self.tokenizer.encode("plain text"))

    def test_every_control_user_defined_token_keeps_its_gguf_id(self):
        values = self.metadata.values
        for token_id, (token, kind) in enumerate(zip(values["tokenizer.ggml.tokens"],
                                                    values["tokenizer.ggml.token_type"])):
            if kind in (2, 3, 4):
                self.assertEqual(self.tokenizer.encode(token), (token_id,))
        unused_id = values["tokenizer.ggml.token_type"].index(5)
        self.assertNotIn(unused_id, self.tokenizer.encode(values["tokenizer.ggml.tokens"][unused_id]))

    def test_raw_roundtrip_korean_entities_fullwidth_emoji_and_newlines(self):
        samples = ["한국어 장비 사양을 확인합니다.", "Ａ와 A는 원문이 다릅니다.",
                   "8 mm, 0.1 mm &times; 20", "앞😀  원문\r\n그대로\n",
                   "I'm 12345 test", "text<|im_end|>text", "\t끝  "]
        for text in samples:
            ids = self.tokenizer.encode(text)
            self.assertEqual(self.tokenizer._engine.decode(list(ids), skip_special_tokens=False), text)
        self.assertNotEqual(self.tokenizer.encode("Ａ"), self.tokenizer.encode("A"))
        self.assertNotEqual(self.tokenizer.encode("&times;"), self.tokenizer.encode("×"))

    def test_qwen_regex_splits_numbers_as_individual_digits(self):
        self.assertEqual(self.tokenizer.encode("12345"), (16, 17, 18, 19, 20))
        self.assertEqual(self.tokenizer.encode("I'm 12345 test"),
                         (40, 2776, 220, 16, 17, 18, 19, 20, 1273))

    def test_frozen_cpu_korean_and_unit_smoke_counts_not_runner_claims(self):
        self.assertEqual(self.tokenizer.count("한국어 장비 사양을 확인합니다."), 11)
        self.assertEqual(self.tokenizer.count("Frequency: 10 MHz ~ 40 GHz"), 11)
        self.assertFalse(self.tokenizer.count_rendered_prompt("한국어")["runner_crosscheck_verified"])

    def test_fully_rendered_prompt_specials_and_generation_prefix_preserved(self):
        prompt = "<|im_start|>system\n원문만 확인.<|im_end|>\n<|im_start|>user\n장비?<|im_end|>\n<|im_start|>assistant\n<think>\n"
        ids = self.tokenizer.encode(prompt)
        self.assertEqual(ids.count(151644), 3)
        self.assertEqual(ids.count(151645), 2)
        self.assertEqual(ids.count(151667), 1)
        self.assertEqual(self.tokenizer._engine.decode(list(ids), skip_special_tokens=False), prompt)
        self.assertEqual(self.tokenizer.count_rendered_prompt(prompt)["rendered_prompt_sha256"],
                         hashlib.sha256(prompt.encode()).hexdigest())

    def test_wrong_configuration_or_metadata_hash_fails_closed(self):
        with self.assertRaises(TokenizerError) as context:
            load_tokenizer(expected_metadata_sha256="0" * 64)
        self.assertEqual(context.exception.code, "metadata_hash_mismatch")
        values = dict(self.metadata.values)
        values["tokenizer.ggml.add_bos_token"] = True
        changed = dataclasses.replace(self.metadata, values=MappingProxyType(values))
        with mock.patch.object(module, "read_gguf_metadata", return_value=changed):
            with self.assertRaises(TokenizerError) as context:
                load_tokenizer()
        self.assertEqual(context.exception.code, "tokenizer_config_mismatch")

    def test_engine_missing_or_wrong_version_is_typed_failure(self):
        with mock.patch.object(module.importlib, "import_module", side_effect=ImportError("missing")):
            with self.assertRaises(TokenizerError) as context:
                load_tokenizer()
        self.assertEqual(context.exception.code, "tokenizers_unavailable")
        with mock.patch.object(module.importlib, "import_module", return_value=SimpleNamespace(__version__="0.0")):
            with self.assertRaises(TokenizerError) as context:
                load_tokenizer()
        self.assertEqual(context.exception.code, "engine_version_mismatch")


if __name__ == "__main__":
    unittest.main()
