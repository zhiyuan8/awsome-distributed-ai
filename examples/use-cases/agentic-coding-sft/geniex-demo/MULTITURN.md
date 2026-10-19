# Multi-turn demo: public Qwen3-1.7B fails, `agent-v2` fixes the bug

`compare.py` runs both models through the same sandboxed agent loop (view, edit, run tests, submit) on an injected bug from public HumanEval, and grades each with the original tests. Left column is the public Qwen3-1.7B, right column is `agent-v2-epoch2`.

Requires ARM64 Windows or Linux, the GenieX Python SDK, Git Bash on `PATH` (Windows), and `agent-1p7b-16k-v2-epoch2-q8_0.gguf`.

## 1. Set up

From `examples/use-cases/agentic-coding-sft/geniex-demo` (this directory). The venv lives next to `src/`, one level up. `src/requirements.txt` also pulls PyTorch, which has no Windows ARM64 wheel, so install the packages this demo imports:

```powershell
cd ..
python -m venv geniex-env
.\geniex-env\Scripts\Activate.ps1
pip install "geniex==0.9.1" "transformers==4.57.1" rich human-eval pytest
cd geniex-demo
geniex pull unsloth/Qwen3-1.7B-GGUF:Q8_0
hf download zackliqcom/aws-qualcomm-demo --include "v2-epoch2/*" --local-dir models
```

Build `tasks_root/` next to `src/` from public HumanEval. `Join-Path` keeps the filename `tasks.jsonl`; a literal `tasks_root\tasks.jsonl` in some pastes becomes a tab plus `asks.jsonl`.

```powershell
New-Item -ItemType Directory -Force -Path ..\tasks_root | Out-Null
New-Item -ItemType File -Force -Path (Join-Path ..\tasks_root tasks.jsonl) | Out-Null
python -c @"
import gzip, json, human_eval, os
src = os.path.join(os.path.dirname(human_eval.__file__), 'data', 'HumanEval.jsonl.gz')
dst = os.path.join('..', 'tasks_root', 'humaneval.jsonl')
with gzip.open(src, 'rt', encoding='utf-8') as f, open(dst, 'w', encoding='utf-8') as out:
    for line in f:
        r = json.loads(line)
        out.write(json.dumps({k: r[k] for k in ('task_id', 'entry_point', 'prompt', 'canonical_solution', 'test')}) + '\n')
print('wrote', sum(1 for _ in open(dst, encoding='utf-8')), 'tasks')
"@
```

## 2. Run

Still in `geniex-demo`. Answers go through a file, not a PowerShell pipe: `compare.py` prints the injected diff before reading the round count, and a pipe deadlocks there. `llama_cpp:cpu` avoids the Hexagon NPU `ROPE` crash.

```powershell
$env:PATH = "..\geniex-env\Scripts;C:\Program Files\Git\bin;$env:PATH"
$env:PYTHONUTF8 = "1"
$env:GENIEX_DEVICE_MAP = "llama_cpp:cpu"
$env:GENIEX_BASE = (Join-Path $env:USERPROFILE ".cache\geniex\models\unsloth\Qwen3-1.7B-GGUF\Qwen3-1.7B-Q8_0.gguf") -replace '\\','/'
$env:GENIEX_FULL = (Resolve-Path "models\v2-epoch2\agent-1p7b-16k-v2-epoch2-q8_0.gguf").Path -replace '\\','/'
@'
fib

20
'@ | Set-Content -Encoding ascii answers.txt
@'
import os, random, runpy, sys
random.seed(7)
src = os.path.abspath(os.path.join(os.path.dirname(__file__) or ".", "..", "src"))
sys.path.insert(0, src)
sys.argv = ["compare.py", "--backend", "geniex", "--mode", "inject",
            "--tasks", "../tasks_root", "--out", "../compare_out/demo_fib"]
runpy.run_path(os.path.join(src, "compare.py"), run_name="__main__")
'@ | Set-Content -Encoding ascii run_fib.py
cmd /c "..\geniex-env\Scripts\python.exe -u run_fib.py < answers.txt"
```

- **Paths:** use forward slashes (`C:/...`). A backslash path or `/c/...` is treated as a model ID and GenieX tries to download it.
- **`bash`:** Git Bash must be on `PATH`; without it the sandbox fails with `FileNotFoundError`.
- **`random.seed(7)`:** fixes which bug is injected. Without it the bug varies between runs.

The three input lines answer the prompts:

| Line | Prompt |
|---|---|
| `fib` | HumanEval function name |
| (empty) | Bug type; default is the first one (`arithmetic` for `fib`) |
| `20` | Number of rounds; default is 1, which stops after the first tool call |

You can also type the three answers when prompted instead of piping them.

## 3. Expected result

```text
  BASE Qwen3-1.7B                        FULL fine-tune
   1 $ ls /testbed                        1 view /testbed
   2 $ ls -R /testbed                     2 view lib/fib.py
   3 edit lib/fib.py x no match  (x2)     3 view tests/test_fib.py
   4 stopped, replied in text             4 edit lib/fib.py ok
                                          5 submit
  NOT FIXED                              FIXED tests pass
```

The injected bug is `fib(n - 1) + fib(n + 2)`. The fine-tune reads the file and the test, edits `n + 2` back to `n - 2`, and submits. The public model only lists the directory, then fails to apply its edit.

## 4. Other tasks

Replace `fib` with another function. These also had the public model fail and `agent-v2-epoch2` fix the bug with `random.seed(7)`:

| Function | Injected bug |
|---|---|
| `fib` | `fib(n - 2)` to `fib(n + 2)` |
| `truncate_number` | `number % 1.0` to `number // 1.0` |
| `mean_absolute_deviation` | `x - mean` to `x + mean` |
| `monotonic` | `or` to `and` |

Sampling is stochastic, so the exact turns differ between runs. Over 7 tasks `agent-v2-epoch2` fixed 4 and the public model 0. Small sample, so treat it as a trend rather than a metric.
