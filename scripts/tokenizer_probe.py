"""Bounded CPU-only probe; no HTTP client, model load, or evaluator access."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from equipment_desk.tokenizer import (DEFAULT_GGUF_PATH, MAX_PROMPT_BYTES,
                                     TokenizerError, load_tokenizer)

SAMPLES = ("<|endoftext|>", "<|im_start|>", "<|im_end|>", "<think>", "</think>",
           "한국어 장비 사양을 확인합니다.", "Frequency: 10 MHz ~ 40 GHz",
           "8 mm, 0.1 mm &times; 20", "앞😀  원문\r\n그대로\n", "I'm 12345 test",
           "<|im_start|>system\n원문만 확인.<|im_end|>\n<|im_start|>user\n장비?<|im_end|>\n<|im_start|>assistant\n<think>\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Count the exact already-rendered prompt on CPU.")
    parser.add_argument("--gguf", type=Path, default=DEFAULT_GGUF_PATH)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--samples", action="store_true", help="Hardcoded CPU smoke samples only")
    source.add_argument("--prompt-file", type=Path, help="UTF-8 already-rendered prompt; contents are not echoed")
    source.add_argument("--stdin", action="store_true", help="Read exact UTF-8 prompt bytes from stdin")
    parser.add_argument("--include-ids", action="store_true")
    args = parser.parse_args(argv)
    try:
        tokenizer = load_tokenizer(args.gguf)
        if args.prompt_file is not None or args.stdin:
            if args.prompt_file is not None:
                path = args.prompt_file.resolve()
                project = Path(__file__).resolve().parents[1]
                for denied in ("eval", "evaluation", "gold"):
                    prohibited = project / denied
                    if path == prohibited or prohibited in path.parents:
                        raise TokenizerError("evaluator_file_denied", "Evaluator files are not runtime prompt input")
                with path.open("rb") as handle:
                    raw = handle.read(MAX_PROMPT_BYTES + 1)
            else:
                raw = sys.stdin.buffer.read(MAX_PROMPT_BYTES + 1)
            if len(raw) > MAX_PROMPT_BYTES:
                raise TokenizerError("prompt_byte_budget", "Rendered prompt exceeds the CPU byte bound")
            prompt = raw.decode("utf-8")
            result = tokenizer.count_rendered_prompt(prompt)
            if args.include_ids:
                result["token_ids"] = tokenizer.encode(prompt)
            print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        else:
            report = []
            for prompt in SAMPLES:
                item = tokenizer.count_rendered_prompt(prompt)
                item["sample"] = prompt
                item["token_ids"] = tokenizer.encode(prompt)
                item["raw_roundtrip_verified"] = (
                    tokenizer._engine.decode(list(item["token_ids"]), skip_special_tokens=False) == prompt)
                report.append(item)
            print(json.dumps({"provenance": dict(tokenizer.provenance),
                              "samples": report, "runner_crosscheck_verified": False},
                             ensure_ascii=True, sort_keys=True, indent=2))
        return 0
    except (TokenizerError, OSError, UnicodeError) as exc:
        code = exc.code if isinstance(exc, TokenizerError) else "prompt_file_unavailable_or_invalid"
        print(json.dumps({"error": {"code": code, "message": "CPU tokenizer preflight failed closed"}}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
