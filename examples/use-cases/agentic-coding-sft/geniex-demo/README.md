# GenieX Demo session (AWS - Qualcomm)

## 1. Import the models

Run a local model: https://geniex.aihub.qualcomm.com/en/models/supported#run-a-local-gguf-model

```powershell
# https://huggingface.co/zackliqcom/aws-qualcomm-demo
cd examples\use-cases\agentic-coding-sft\geniex-demo

hf download zackliqcom/aws-qualcomm-demo --local-dir .
geniex pull local/agent-v2-epoch2 --model-hub localfs --local-path v2-epoch2

# when prompted, select Q8_0
geniex pull unsloth/Qwen3-1.7B-GGUF
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
python ask.py local/agent-v2-epoch2:Q8_0
```

## 4. Agentic coding benchmark




Full run result:

| Task | Injected bug | Vanilla | r16 | v64-latest |
| --- | --- | --- | --- | --- |
| fib | `fib(n - 2)` → `fib(n + 2)` | ✗ | ✗ | ✓ |
| mean_absolute_deviation | `x - mean` → `x + mean` | ✗ | ✗ | ✓ |
| monotonic | `or` → `and` | ✗ | ✓ | ✓ |
| truncate_number | `% 1.0` → `// 1.0` | ✗ | ✗ | ✓ |
| below_threshold | `>=` → `>` | ✗ | ✗ | ✗ |
| has_close_elements | `a - b` → `a + b` | ✗ | ✗ | ✗ |
| sum_product | init `0` → `1` | ✗ | ✗ | ✗ |
