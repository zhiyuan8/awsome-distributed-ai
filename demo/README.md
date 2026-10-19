## Results

| Model | Fixed |
| --- | --- |
| Qwen3-1.7B-Q8_0 (vanilla) | 0/7 |
| r16 | 1/7 |
| r64-latest | 4/7 |

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

### Setup

Verified on Windows ARM64 with a GGUF already cached locally (`geniex-py pull <model>`).

1. Create a dedicated venv and install deps (`geniex`, `transformers`, `rich` — `pip install
   geniex` alone is not enough, `compare.py` imports `transformers`/`rich` unconditionally):

   ```powershell
   python -m venv geniex-env
   .\geniex-env\Scripts\Activate.ps1
   pip install -r ..\examples\use-cases\agentic-coding-sft\src\requirements.txt
   ```

2. `--mode inject` still reads `tasks.jsonl`/`humaneval.jsonl` from a tasks dir even though it
   builds its own bug-fix repos on the fly. Make an empty `tasks.jsonl` and a `humaneval.jsonl`
   converted from the public HumanEval dataset (fields: `task_id, entry_point, prompt,
   canonical_solution, test`), and point `AGENT_TASKS` at that directory:

   ```powershell
   $tasks = "$env:LOCALAPPDATA\geniex-compare-tasks"
   New-Item -ItemType Directory -Force -Path $tasks | Out-Null
   New-Item -ItemType File -Force -Path "$tasks\tasks.jsonl" | Out-Null
   # then write $tasks\humaneval.jsonl from openai_humaneval / HumanEval.jsonl.gz
   $env:AGENT_TASKS = $tasks
   ```

3. `bash` (the agent's shell tool) needs to resolve on `PATH` — Git for Windows' `bash.exe`
   works. Non-Latin-1 HumanEval sources also need `$env:PYTHONUTF8 = "1"`.

4. Run, from `examples/use-cases/agentic-coding-sft/src` (no `src/` prefix on the script path —
   you're already inside it):

   ```powershell
   python compare.py --backend geniex `
     --geniex-base 'local/agent-v2-epoch2' `
     --geniex-full 'unsloth/Qwen3-1.7B-GGUF' `
     --mode inject
   ```

   (PowerShell's line-continuation character is the backtick, not `\`.) Omit `--geniex-full` to
   compare the base model against itself as a smoke test.

Note: `GenieXEngine.render` in `compare.py` re-encodes each assistant turn's `tool_calls[].function.arguments`
to a JSON string before calling GenieX's `apply_chat_template` — GenieX's tokenizer binding calls
`.encode()` on `arguments` directly and raises `AttributeError: 'dict' object has no attribute
'encode'` otherwise, whereas `step()` stores `arguments` as a parsed dict for vLLM's Jinja
template (which applies its own `tojson`). This fix is already in
[compare.py](../examples/use-cases/agentic-coding-sft/src/compare.py); without it, `--mode
inject` crashes on the second agent turn (after the first tool call is appended to the
conversation).

With this setup, a `--mode inject` run against the cached base GGUF (no `--geniex-full`) on
`monotonic`/`boolean` completed in 6 turns, editing the file, running `pytest`, and submitting
with the bug fixed — confirming the mechanism end to end.

