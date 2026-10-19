# Multi-turn demo: public Qwen3-1.7B fails, `agent-v2` fixes the bug

`compare.py` runs both models through the same sandboxed agent loop (view, edit, run tests, submit) on an injected bug from public HumanEval, and grades each with the original tests. Left column is the public Qwen3-1.7B, right column is `agent-v2-epoch2`.

Requires ARM64 Windows or Linux, the GenieX Python SDK, Git Bash on `PATH` (Windows), and `agent-1p7b-16k-v2-epoch2-q8_0.gguf`.

## 1. Set up

From `examples/use-cases/agentic-coding-sft/`:

```powershell
python -m venv geniex-env
.\geniex-env\Scripts\Activate.ps1
pip install -r src\requirements.txt
geniex pull Qwen/Qwen3-1.7B-GGUF:Q8_0
```

Build `tasks_root/` (next to `src/`) from public HumanEval:

```powershell
mkdir tasks_root
New-Item tasks_root	asks.jsonl -ItemType File
python -c "import gzip,json,urllib.request as u; d=gzip.decompress(u.urlopen('https://github.com/openai/human-eval/raw/master/data/HumanEval.jsonl.gz').read()).decode(); open('tasks_root/humaneval.jsonl','w',encoding='utf-8').writelines(json.dumps({k:r[k] for k in ('task_id','entry_point','prompt','canonical_solution','test')})+'
' for r in map(json.loads,d.splitlines()))"
```

## 2. Run

```powershell
$env:PATH = "C:\Program Files\Git\bin;$env:PATH"
$env:PYTHONUTF8 = 1
$env:GENIEX_BASE = 'C:/Users/<you>/.cache/geniex/models/Qwen/Qwen3-1.7B-GGUF/Qwen3-1.7B-Q8_0.gguf'
$env:GENIEX_FULL = 'C:/path/to/agent-1p7b-16k-v2-epoch2-q8_0.gguf'
cd src

"fib`n`n20`n" | python -c 'import random,runpy,sys; random.seed(7); sys.argv=["compare.py","--backend","geniex","--mode","inject","--tasks","../tasks_root","--out","../compare_out/demo_fib"]; runpy.run_path("compare.py",run_name="__main__")'
```

- **Paths:** use forward slashes (`C:/...`). A backslash path or `/c/...` is treated as a model ID and GenieX tries to download it.
- **`bash`:** the first line adds Git Bash to `PATH`; without it the sandbox fails with `FileNotFoundError`.
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
