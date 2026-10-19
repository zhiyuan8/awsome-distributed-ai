# GenieX demo: public Qwen3-1.7B vs fine-tuned `agent-v2-epoch2`

Both models run on GenieX (`geniex serve`, llama.cpp backend). They get the same prompt and tools, and give different answers.

Requires ARM64 Windows or Linux, the GenieX CLI, Python 3.9+, and `agent-1p7b-16k-v2-epoch2-q8_0.gguf`.

## 1. Import the models

```powershell
mkdir models\v2
copy C:\path\to\agent-1p7b-16k-v2-epoch2-q8_0.gguf models\v2\
geniex pull local/agent-v2-epoch2 --model-hub localfs --local-path models\v2
geniex pull Qwen/Qwen3-1.7B-GGUF:Q8_0
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

`ask.py` sends one `/v1/chat/completions` request (temperature 0, thinking off):

- **System:** `You are a coding agent working in a Python repository. Use the tools to explore the code, make the required change, verify it, and call submit when done.`
- **User:** `There's a bug in truncate_number in /testbed/lib/truncate_number.py: it doesn't behave the way its docstring describes. Here is the file: <truncate_number.py> Fix it with str_replace_editor.`
- **Tools:** `str_replace_editor` (`view`, `str_replace`) and `submit`.

The bug in [truncate_number.py](truncate_number.py): `return number // 1.0` returns the integer part, but the docstring asks for the decimal part (`truncate_number(3.5) == 0.5`).

## 4. Compare the results

`ask.py` prints the line the model's `str_replace` call changes:

```text
== Qwen/Qwen3-1.7B-GGUF:Q8_0
- return number // 1.0
+ return number / 1.0
== local/agent-v2-epoch2:Q8_0
- return number // 1.0
+ return number - (number // 1.0)
```

| Model | Result |
|---|---|
| Public Qwen3-1.7B | Wrong: `3.5 / 1.0 = 3.5`. Bug remains. |
| agent-v2-epoch2 | Fixed: `3.5 - 3.0 = 0.5`. |

The public model's wrong edit can vary between runs (e.g. it may leave the line unchanged); agent-v2-epoch2's fix has been the same on every run.
