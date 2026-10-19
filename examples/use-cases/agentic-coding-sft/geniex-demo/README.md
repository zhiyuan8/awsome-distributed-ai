# GenieX Demo session (AWS - Qualcomm)

## 1. Import the models

Run a local model: https://geniex.aihub.qualcomm.com/en/models/supported#run-a-local-gguf-model

```powershell
# https://huggingface.co/zackliqcom/aws-qualcomm-demo
cd examples\use-cases\agentic-coding-sft\geniex-demo

python -m venv geniex-env
.\geniex-env\Scripts\Activate.ps1
pip install -r requirements.txt
```

```
hf download zackliqcom/aws-qualcomm-demo --local-dir .
geniex pull local/agent-v2-epoch2 --model-hub localfs --local-path v2-epoch2

# :Q8_0 skips the precision prompt
geniex pull unsloth/Qwen3-1.7B-GGUF:Q8_0
```

## 2. Try GenieX CLI and Start the server
check what models you have
```
geniex list
```
expected at least
```
┌───────────────────────────────┬─────────┬────────────┐
│ NAME                          │ SIZE    │ PRECISIONS │
├───────────────────────────────┼─────────┼────────────┤
│ local/agent-v2-epoch2         │ 1.8 GiB │ Q4_0       │
│ unsloth/Qwen3-1.7B-GGUF       │ 1.7 GiB │ Q8_0       │
└───────────────────────────────┴─────────┴────────────┘
```

You can try NPU or CPU inference
```
geniex infer unsloth/Qwen3-1.7B-GGUF
geniex infer unsloth/Qwen3-1.7B-GGUF --compute CPU
```

Start server:
```powershell
geniex serve
```


## 3. Test agentic coding

In a second terminal, from this directory:

```powershell
python ask.py unsloth/Qwen3-1.7B-GGUF:Q8_0
python ask.py  local/agent-v2-epoch2:Q8_0
```

## 4. Agentic coding benchmark
Kill the server, from this directory, after section 1. Tasks are in [../tasks_root](../tasks_root). At the prompts type `fib`, Enter, then `20`. Git Bash must be on `PATH`.

```powershell
# NPU. Registered model ids from section 1, not .gguf paths.
$env:PATH = "..\geniex-env\Scripts;C:\Program Files\Git\bin;$env:PATH"
$env:PYTHONUTF8 = "1"
$env:GENIEX_DEVICE_MAP = "npu"
python ..\src\compare.py --backend geniex --mode inject --tasks ..\tasks_root --geniex-base unsloth/Qwen3-1.7B-GGUF --geniex-full local/agent-v2-epoch2
```

Full run result:

| Task | Injected bug | Vanilla | Finetuned |
| --- | --- | --- | --- | --- |
| fib | `fib(n - 2)` → `fib(n + 2)` | ✗ | ✓ |
| mean_absolute_deviation | `x - mean` → `x + mean` | ✗ | ✓ |
| monotonic | `or` → `and` | ✗ | ✓ |
| truncate_number | `% 1.0` → `// 1.0` | ✗ | ✓ |
| below_threshold | `>=` → `>` | ✗ | ✗ |
| has_close_elements | `a - b` → `a + b` | ✗ | ✗ |
| sum_product | init `0` → `1` | ✗ | ✗ |


## 5. Other agentic demos
With server on, run
```bash
geniex pull qualcomm/Qwen3-VL-4B-Instruct 
geniex serve
```
Then run
```bash
python openai-api-demo.py
```