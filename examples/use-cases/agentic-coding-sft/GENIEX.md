# GenieX backend for `compare.py`

This adds a second inference backend to `src/compare.py`, alongside the original vLLM one, so the
base-vs-fine-tuned comparison can run against the merged+quantized **GGUF** produced by the
`gguf-convert` pipeline step, via [GenieX](https://github.com/qualcomm/GenieX) instead of vLLM.

## Why

`compare.py`'s `Engine` class (model loading + chat-template rendering + generation) is the only
backend-specific part of the file. Everything else — the sandboxed `bash`/`str_replace_editor`
tool execution (`agent_env.py`), the multi-turn agent loop, tool-call parsing, scoring, and the
Rich-table display — is plain Python with no vLLM dependency, and works unchanged for any backend
that can render a tools-aware chat template and generate text from it.

GenieX's Python SDK (`pip install geniex`) can:
- load a local `.gguf` file directly, in-process, no server (`AutoModelForCausalLM.from_pretrained(path, device_map="llama_cpp")`)
- apply a tools-aware chat template (`model.tokenizer.apply_chat_template(messages, tools=[...], enable_thinking=..., add_generation_prompt=...)`), via the same llama.cpp jinja mechanism `geniex serve`'s OpenAI-compatible endpoint uses, so a Qwen3 GGUF emits the same `<tool_call>{"name":...,"arguments":{...}}</tool_call>` format the training data uses
- generate text (`model.generate(prompt, ...)`)

The one gap — GenieX returns raw text, not a parsed tool call — is already solved by this repo's
own `agent_env.py::parse_assistant()`, which works on raw text regardless of backend. So the only
new code needed is a `GenieXEngine` class with the same `render`/`generate`/`count_tokens`/`models`
contract as the existing `Engine`.

## Usage

```bash
pip install geniex   # ARM64 Windows / Linux ARM64 only

python compare.py --backend geniex \
  --geniex-base /path/to/base-Q8_0.gguf \
  --geniex-full /path/to/finetuned-Q8_0.gguf \
  --mode inject
```

Omit `--geniex-full` to compare the base model against itself (useful as a smoke test) or to run
single-model modes. `--mode inject`/`paste` work out of the box (they build tasks on the fly from
the public HumanEval dataset). `--mode showcase`/`quick` need `tasks.jsonl`/`humaneval.jsonl` under
`--tasks` (see `make_agent_tasks.py`) — not required to validate the mechanism itself.

## What's needed to run the real base-vs-fine-tune comparison

Not blocked on code — blocked on artifacts: the actual `base` and fine-tuned+merged+quantized
GGUF files from the training pipeline (`gguf-convert` step). These aren't published anywhere;
they only exist on the training cluster's FSx volume after a training run. We don't need the
private `tasks.jsonl`/150-task eval set — `--mode inject` reproduces equivalent bug-fix tasks from
the public HumanEval dataset using this repo's own bug-injection code.

## Known platform differences (Windows)

`agent_env.py`'s `TaskEnv` drops bash commands to an unprivileged uid (`os.geteuid`/`os.chown`/
`os.killpg`) as a Linux-pod hardening measure. These calls don't exist on Windows; the sandbox now
guards them (`os.name == "posix"`) and simply skips the uid-drop there — fine for a local
single-user run. `bash` itself runs via Git Bash on `PATH`. Sandbox paths are also normalized so
`/testbed` maps consistently regardless of `/` vs `\` separators.

Running on Windows:
- set `PYTHONUTF8=1` (HumanEval sources contain non-cp1252 characters)
- `--mode inject`/`paste` still read `<--tasks>/tasks.jsonl` and `humaneval.jsonl`; for a
  standalone run create an empty `tasks.jsonl` and a `humaneval.jsonl` converted from the public
  `HumanEval.jsonl.gz` (fields: `task_id, entry_point, prompt, canonical_solution, test`)

## Status

- Code change: done (`src/compare.py` `GenieXEngine` + `--backend geniex`; `src/agent_env.py`
  Windows guards).
- Mechanism smoke test (base GGUF loaded twice, `--mode inject`, confirms tools-aware rendering +
  `<tool_call>` parsing + sandboxed grading work end to end): see test evidence in the PR/commit
  this file ships with.
- Real base-vs-fine-tune comparison: pending the actual GGUF files from the training run.
