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

GenieX only runs on ARM64 Windows / Linux ARM64. Set up a dedicated venv (PowerShell):

```powershell
python -m venv geniex-env
.\geniex-env\Scripts\Activate.ps1
pip install -r src\requirements.txt
```

`src/requirements.txt` pulls in `geniex`, `transformers`, and `rich` (the table display
`compare.py` uses for both backends) — installing `geniex` on its own is not enough, you'll hit
`ModuleNotFoundError: No module named 'rich'` partway through model loading.

`--mode inject`/`paste` read `humaneval.jsonl` from `$env:AGENT_TASKS` (default
`/fsx/agent_tasks/v1`, which doesn't exist off the training cluster — without this you'll hit
`FileNotFoundError: .../humaneval.jsonl`). Build a standalone copy from the public `human-eval`
PyPI package (ships the same `HumanEval.jsonl.gz`; `tasks.jsonl` only needs to exist, `--mode
inject`/`paste` build their own repos on the fly and don't read its contents):

```powershell
pip install human-eval
$tasks = "$env:LOCALAPPDATA\geniex-compare-tasks"
New-Item -ItemType Directory -Force -Path $tasks | Out-Null
New-Item -ItemType File -Force -Path "$tasks\tasks.jsonl" | Out-Null
python -c @"
import gzip, json, human_eval, os
src = os.path.join(os.path.dirname(human_eval.__file__), 'data', 'HumanEval.jsonl.gz')
dst = os.path.join(r'$tasks', 'humaneval.jsonl')
with gzip.open(src, 'rt', encoding='utf-8') as f, open(dst, 'w', encoding='utf-8') as out:
    for line in f:
        r = json.loads(line)
        out.write(json.dumps({k: r[k] for k in ('task_id', 'entry_point', 'prompt', 'canonical_solution', 'test')}) + '\n')
"@
$env:AGENT_TASKS = $tasks
```

Then, from `src/`:

```powershell
python compare.py --backend geniex `
  --geniex-base 'local/agent-v2-epoch2' `
  --geniex-full 'unsloth/Qwen3.5-2B-GGUF' `
  --mode inject
```

(PowerShell's line-continuation character is the backtick `` ` ``, not `\` — a trailing `\` is
parsed as a new statement and fails with `Missing expression after unary operator '--'`. A single
line works too, with no continuation characters needed.)

`--geniex-base`/`--geniex-full` also accept a name registered in the GenieX cache
(`~/.cache/geniex/models`) instead of a raw path — handy for reusing the same model across runs
without retyping the path. Register with the CLI's `localfs` hub, one `.gguf` per directory
(`--local-path` ingests every file in the directory, so two `.gguf`s side by side would both get
copied into each pull as a redundant "extra file"):

```powershell
geniex pull local/agent-r64 --model-hub localfs --local-path 'C:\path\to\models\r64'
geniex pull local/agent-v2-epoch2 --model-hub localfs --local-path 'C:\path\to\models\v2-epoch2'
```

then pass `--geniex-base local/agent-r64 --geniex-full local/agent-v2-epoch2` instead of the raw
paths above — resolved straight from the cache, no hub lookup.

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

## Known issue: tool-call arguments must be a JSON string, not a dict

`step()` in `compare.py` stores each assistant turn's `tool_calls[].function.arguments` as a
parsed dict (vLLM's Jinja chat template re-encodes it itself via `| tojson`). GenieX's chat
template binding instead calls `.encode()` on `arguments` directly, so passing a dict crashes
with `AttributeError: 'dict' object has no attribute 'encode'` on the second agent turn (the
first turn has no prior tool call yet, so it isn't caught until the model calls a tool once).
`GenieXEngine.render` now re-encodes a copy of the conversation's `arguments` to a JSON string
before calling `apply_chat_template`, leaving the shared `conv` (and the vLLM path) untouched.

## Status

- Code change: done (`src/compare.py` `GenieXEngine` + `--backend geniex`; `src/agent_env.py`
  Windows guards; tool-call argument encoding fix above).
- Mechanism smoke test (base GGUF loaded twice, `--mode inject` on `monotonic`/`boolean`):
  completed end to end in 6 turns — viewed the file, edited it, ran `pytest`, submitted, bug
  fixed.
- Real base-vs-fine-tune comparison: pending the actual GGUF files from the training run.
