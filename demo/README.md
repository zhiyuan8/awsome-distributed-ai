# GenieX Demo session (AWS - Qualcomm)


### Testing details

| Task | Injected bug | Vanilla | r16 | v64-latest |
| --- | --- | --- | --- | --- |
| fib | `fib(n - 2)` → `fib(n + 2)` | ✗ | ✗ | ✓ |
| mean_absolute_deviation | `x - mean` → `x + mean` | ✗ | ✗ | ✓ |
| monotonic | `or` → `and` | ✗ | ✓ | ✓ |
| truncate_number | `% 1.0` → `// 1.0` | ✗ | ✗ | ✓ |
| below_threshold | `>=` → `>` | ✗ | ✗ | ✗ |
| has_close_elements | `a - b` → `a + b` | ✗ | ✗ | ✗ |
| sum_product | init `0` → `1` | ✗ | ✗ | ✗ |

Each row is one `compare.py --mode inject` run on the matching HumanEval function: a
bug is injected into the canonical solution, and the model must find and fix it in a
sandboxed repo using tools (the model never sees the injected diff above).

### Input prompt sent to the model

System message ([agent_tools.py](../examples/use-cases/agentic-coding-sft/src/agent_tools.py)):

```text
You are a coding agent working in a Python repository. Use the tools to explore the
code, make the required change, verify it, and call `submit` when done.
```

User message template ([agent_eval.py](../examples/use-cases/agentic-coding-sft/src/agent_eval.py)),
filled in for the `fib` row above:

```text
I'm working in the Python repository at /testbed. There's a bug in the function `fib`:
it doesn't behave the way its docstring describes, and its unit test fails. Please find
the bug and fix it. The tests are in /testbed/tests and run with `python -m pytest`.
Don't modify the tests. Call `submit` when you're done.
```

Alongside these messages, three tools are exposed to the model: `bash`,
`str_replace_editor` (view/create/str_replace/insert/undo_edit), and `submit`. The model
must call them to inspect `lib/fib.py` and `tests/test_fib.py`, locate the bug itself,
edit the file, and submit — it is not told what the diff is.

## GenieX backend for `compare.py`

Source: [GENIEX.md](../examples/use-cases/agentic-coding-sft/GENIEX.md).

This adds a second inference backend to
[compare.py](../examples/use-cases/agentic-coding-sft/src/compare.py), alongside the original vLLM one, so the
base-vs-fine-tuned comparison can run against the merged+quantized **GGUF** produced by the
`gguf-convert` pipeline step, via [GenieX](https://github.com/qualcomm/GenieX) instead of vLLM.

### Why

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

### Setup

Verified on Windows ARM64 with a GGUF already cached locally (`geniex-py pull <model>`).

GenieX only runs on ARM64 Windows / Linux ARM64. Create a dedicated venv and install deps
(`geniex`, `transformers`, `rich` — `pip install geniex` alone is not enough, `compare.py` imports
`transformers`/`rich` unconditionally; installing `geniex` on its own hits
`ModuleNotFoundError: No module named 'rich'` partway through model loading):

```powershell
# from demo/
python -m venv geniex-env
.\geniex-env\Scripts\Activate.ps1
pip install -r ..\examples\use-cases\agentic-coding-sft\src\requirements.txt
```

`--mode inject`/`paste` read `humaneval.jsonl` from `$env:AGENT_TASKS` (default
`/fsx/agent_tasks/v1`, which doesn't exist off the training cluster — without this you'll hit
`FileNotFoundError: .../humaneval.jsonl`). They still read `tasks.jsonl` even though they build
their own bug-fix repos on the fly and don't read its contents. Build a standalone copy from the
public `human-eval` PyPI package (ships the same `HumanEval.jsonl.gz`):

```powershell
# public HumanEval -> local tasks dir (tasks.jsonl only needs to exist)
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

`bash` (the agent's shell tool) needs to resolve on `PATH` — Git for Windows' `bash.exe` works.
Non-Latin-1 HumanEval sources also need `$env:PYTHONUTF8 = "1"`.

Run, from `examples/use-cases/agentic-coding-sft/src` (no `src/` prefix on the script path —
you're already inside it):

```powershell
# PowerShell line continuation is the backtick, not \
python compare.py --backend geniex `
  --geniex-base 'local/agent-v2-epoch2' `
  --geniex-full 'unsloth/Qwen3-1.7B-GGUF' `
  --mode inject
```

(PowerShell's line-continuation character is the backtick `` ` ``, not `\` — a trailing `\` is
parsed as a new statement and fails with `Missing expression after unary operator '--'`. A single
line works too, with no continuation characters needed.) Omit `--geniex-full` to compare the base
model against itself as a smoke test, or to run single-model modes.

`--geniex-base`/`--geniex-full` also accept a name registered in the GenieX cache
(`~/.cache/geniex/models`) instead of a raw path — handy for reusing the same model across runs
without retyping the path. Register with the CLI's `localfs` hub, one `.gguf` per directory
(`--local-path` ingests every file in the directory, so two `.gguf`s side by side would both get
copied into each pull as a redundant "extra file"):

```powershell
# one .gguf per directory; names resolve from the GenieX cache
geniex pull local/agent-r64 --model-hub localfs --local-path 'C:\path\to\models\r64'
geniex pull local/agent-v2-epoch2 --model-hub localfs --local-path 'C:\path\to\models\v2-epoch2'
```

then pass `--geniex-base local/agent-r64 --geniex-full local/agent-v2-epoch2` instead of the raw
paths above — resolved straight from the cache, no hub lookup.

`--mode inject`/`paste` work out of the box (they build tasks on the fly from the public HumanEval
dataset). `--mode showcase`/`quick` need `tasks.jsonl`/`humaneval.jsonl` under `--tasks` (see
`make_agent_tasks.py`) — not required to validate the mechanism itself.

### What's needed to run the real base-vs-fine-tune comparison

Not blocked on code — blocked on artifacts: the actual `base` and fine-tuned+merged+quantized
GGUF files from the training pipeline (`gguf-convert` step). These aren't published anywhere;
they only exist on the training cluster's FSx volume after a training run. We don't need the
private `tasks.jsonl`/150-task eval set — `--mode inject` reproduces equivalent bug-fix tasks from
the public HumanEval dataset using this repo's own bug-injection code.

### Known platform differences (Windows)

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

### Known issue: tool-call arguments must be a JSON string, not a dict

`step()` in `compare.py` stores each assistant turn's `tool_calls[].function.arguments` as a
parsed dict (vLLM's Jinja chat template re-encodes it itself via `| tojson`). GenieX's chat
template binding instead calls `.encode()` on `arguments` directly, so passing a dict crashes
with `AttributeError: 'dict' object has no attribute 'encode'` on the second agent turn (the
first turn has no prior tool call yet, so it isn't caught until the model calls a tool once).
`GenieXEngine.render` now re-encodes a copy of the conversation's `arguments` to a JSON string
before calling `apply_chat_template`, leaving the shared `conv` (and the vLLM path) untouched.
This fix is already in [compare.py](../examples/use-cases/agentic-coding-sft/src/compare.py).

### Status

- Code change: done (`src/compare.py` `GenieXEngine` + `--backend geniex`; `src/agent_env.py`
  Windows guards; tool-call argument encoding fix above).
- Mechanism smoke test (base GGUF loaded twice, `--mode inject` on `monotonic`/`boolean`):
  completed end to end in 6 turns — viewed the file, edited it, ran `pytest`, submitted, bug
  fixed. With the setup above, a `--mode inject` run against the cached base GGUF (no
  `--geniex-full`) confirms the mechanism end to end.
- Real base-vs-fine-tune comparison: the 7-task inject results at the top of this file
  (`Qwen3-1.7B-Q8_0` 0/7, `r16` 1/7, `r64-latest` 4/7).


## Results

| Model | Fixed |
| --- | --- |
| Qwen3-1.7B-Q8_0 (vanilla) | 0/7 |
| r16 | 1/7 |
| r64-latest | 4/7 |
