# CPU tokenizer provenance and limits

The CPU tool reconstructs the installed GGUF byte-level BPE tokenizer. It accepts the exact, already-rendered Ollama prompt as one string. It does not render chat messages, change whitespace or HTML entities, download a tokenizer/model, read tensor information or weights, or request inference.

Every result reports `count_kind=cpu_reconstructed_bpe` and `runner_crosscheck_verified=false`. These CPU results are not yet an exact-Ollama-runner claim. Before a formal experiment, the root must compare the same rendered strings against the actual runner and preserve the prompt hashes and observed counts. A mismatch blocks the experiment; do not substitute byte/character estimates. Successful decoding back to the original raw prompt and known special IDs are necessary CPU checks, not sufficient runner-parity evidence.

## Existing source and pins

- Existing Ollama manifest model layer: `sha256:3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f`.
- Existing model blob is resolved locally; no model download or modification occurs.
- GGUF v3 header plus key/value metadata: 5,933,099 bytes; SHA256 `82e92c41ef7f47671922432da66dce6a15bb89d54b429f410820f47e91583621`. Reading stops before tensor information.
- Metadata says `model=gpt2`, `pre=qwen2`, 151,936 vocabulary strings and 151,387 ordered merges. BOS is 151643, EOS is 151645, and automatic BOS is false. No EOS processor is added.
- Twenty CONTROL and six USER_DEFINED tokens are parsed as special strings with their original IDs. The 267 UNUSED tokens are not registered as specials.
- Qwen2 regex SHA256: `c44a912d90a3fa0951a201b559433f35d8816c26b4be8b3cbd00670bcd985398`.
- The model layer digest is the existing manifest identity, not a new full-weight hash verification. Only the metadata region is rehashed.

The parser accepts standard GGUF scalar/string/array value types, with bounds of 32 MiB total metadata, 2 MiB per string, 2,000,000 array items, 2,048 key/value entries and bounded nesting. Magic, version, duplicate keys, unsupported types, malformed booleans, truncation and source/configuration/hash changes fail closed. Prompt input is valid UTF-8 and bounded to 1 MiB; it is never truncated.

## Official CPU package

Hugging Face `tokenizers==0.23.2` is pinned. The installed official PyPI wheel is `tokenizers-0.23.2-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`, 3,386,843 bytes, published SHA256 `41c2f84d172449b4dadb9cdc508e3e364076613c35b16e76ecfe47a60d1e3305`. This release is Apache-2.0. No dependencies were installed.

A minimal isolated environment for users who need CPU counts:

~~~sh
python3 -m venv .venv
.venv/bin/python -m pip install --index-url https://pypi.org/simple --only-binary=:all: --no-deps --no-cache-dir tokenizers==0.23.2
.venv/bin/python scripts/tokenizer_probe.py --samples
.venv/bin/python scripts/tokenizer_probe.py --prompt-file /path/to/already-rendered-utf8-prompt.txt
~~~

The implementation builds BPE from the GGUF token-ID ordering and merge ordering. It uses Qwen2 regex splitting followed by the package's GPT2 ByteLevel encoding with `add_prefix_space=false` and `use_regex=false`. There is no text normalizer, postprocessor, padding, dropout or truncation. Special strings use `normalized=false`, no stripping and no word-boundary requirement. Known special IDs and the complete byte alphabet are checked during construction.

## Interface and checks

`read_gguf_metadata(path)` returns immutable metadata and its exact region hash. `load_tokenizer(path)` requires the pinned metadata/configuration and CPU-engine version. Its methods are `encode(rendered_prompt)`, `count(rendered_prompt)` and `count_rendered_prompt(rendered_prompt)`. The last returns the CPU count, exact UTF-8 prompt byte length and SHA256, plus tokenizer provenance. Render/template identity remains server-owned.

Known single-token IDs are `<|endoftext|>=151643`, `<|im_start|>=151644`, `<|im_end|>=151645`, `<think>=151667` and `</think>=151668`. The CPU smoke strings “한국어 장비 사양을 확인합니다.” and “Frequency: 10 MHz ~ 40 GHz” each count eleven tokens. These are development checks, separate from evaluation questions and actual-runner evidence.

The CPU suite covers all supported metadata types; stopping before weights; malformed/bounded metadata; special IDs; Qwen single-digit splitting; raw Korean/fullwidth/emoji/HTML-entity/CRLF round trips; prompt hashes; and safe missing-engine/configuration failures. Installed-GGUF checks require the existing model and pinned CPU wheel; they are explicitly skipped on environments without them.

## Primary implementation references

- [Ollama v0.17.7 vendored llama.cpp tokenizer](https://github.com/ollama/ollama/blob/v0.17.7/llama/llama.cpp/src/llama-vocab.cpp): Qwen2 pretokenization, byte-level BPE and special-token partition.
- [Hugging Face tokenizers v0.23.2 ByteLevel implementation](https://github.com/huggingface/tokenizers/blob/v0.23.2/tokenizers/src/pre_tokenizers/byte_level.rs): GPT2 byte-to-Unicode mapping and explicit regex/prefix-space controls.
- [GGUF format](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md): header, metadata key/value layout and standard value types.
- [Official PyPI release metadata](https://pypi.org/pypi/tokenizers/0.23.2/json): package/wheel identity and published hashes.
