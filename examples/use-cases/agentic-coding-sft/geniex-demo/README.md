# GenieX demo: public Qwen3-1.7B vs fine-tuned `agent-v2-epoch2`

Both models run on GenieX (`geniex serve`, llama.cpp backend), get the same prompt and tools, and give different answers.

Requires ARM64 Windows or Linux, the GenieX CLI, Python 3.9+, and `agent-1p7b-16k-v2-epoch2-q8_0.gguf`.

## 1. Import the models

```powershell
mkdir models\v2
copy C:\path\to\agent-1p7b-16k-v2-epoch2-q8_0.gguf models\v2\
geniex pull local/agent-v2-epoch2 --model-hub localfs --local-path models\v2
geniex pull unsloth/Qwen3-1.7B-GGUF:Q8_0
```

`--local-path` takes a directory, not a `.gguf` file.

## 2. Start the server

```powershell
geniex serve
```

## 3. Send the prompt to both models

In a second terminal:

```powershell
python ask.py unsloth/Qwen3-1.7B-GGUF:Q8_0
python ask.py local/agent-v2-epoch2:Q8_0
```

`ask.py` sends one `/v1/chat/completions` request with greedy decoding (`top_k=1`) and thinking off, so every run gives the same output:

- **System:** `You are a coding agent working in a Python repository. Use the tools to explore the code, make the required change, verify it, and call submit when done.`
- **User:** `There's a bug in fib in /testbed/lib/fib.py: it doesn't behave the way its docstring describes. Here is the file: <fib.py> Fix it with str_replace_editor.`
- **Tools:** `str_replace_editor` (`view`, `str_replace`) and `submit`.

The bug in [fib.py](fib.py): `if n != 1: return 1` should be `if n == 1: return 1`, so `fib(10)` returns 1 instead of 55.

## 4. Compare the results

`ask.py` prints the line the model's `str_replace` call changes:

```text
== unsloth/Qwen3-1.7B-GGUF:Q8_0
no change (old_str == new_str)
== local/agent-v2-epoch2:Q8_0
- if n != 1:
+ if n == 1:
```

| Model | Result |
|---|---|
| Public Qwen3-1.7B | Calls the tool but leaves the code unchanged. Bug remains. |
| agent-v2-epoch2 | Fixes the condition. `fib(10) == 55`. |

## Multi-turn version

To run the same comparison through the full agent loop (view, edit, run tests, submit) with `compare.py`, see [MULTITURN.md](MULTITURN.md).
