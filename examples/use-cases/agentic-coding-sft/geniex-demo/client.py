"""GenieX Python SDK client — Python equivalent of the `curl .../v1/chat/completions` example in
`demo/README.md` ("3. Send a request"), using `AutoModelForCausalLM.from_pretrained()` +
`.generate()` directly instead of going through `geniex serve`'s OpenAI-compatible HTTP endpoint.
See: https://geniex.aihub.qualcomm.com/en/run/python/quickstart

Usage (from a venv with `pip install geniex`):
    python client.py --model local/agent-v2-epoch2
    python client.py --model local/agent-r64
"""
import argparse

from geniex import AutoModelForCausalLM

SYSTEM = ("You are a coding agent working in a Python repository. Use the tools to explore the "
          "code, make the required change, verify it, and call `submit` when done.")

USER = (
    "There's a bug in `truncate_number` in /testbed/lib/truncate_number.py: it doesn't behave "
    "the way its docstring describes. Here is the file:\n\n"
    "```python\n"
    "def truncate_number(number: float) -> float:\n"
    "    \"\"\"Return the decimal part of the number.\n"
    "    >>> truncate_number(3.5)\n"
    "    0.5\n"
    "    \"\"\"\n"
    "    return number // 1.0\n"
    "```\n\n"
    "Fix it with str_replace_editor."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "str_replace_editor",
        "description": "Edit files. `str_replace` replaces one exact occurrence of old_str "
                       "with new_str.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "enum": ["view", "str_replace"]},
            "path": {"type": "string"},
            "old_str": {"type": "string"},
            "new_str": {"type": "string"},
        }, "required": ["command", "path"]}}},
    {"type": "function", "function": {
        "name": "submit",
        "description": "Submit the changes once the task is complete.",
        "parameters": {"type": "object", "properties": {}}}},
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model", default="local/agent-v2-epoch2",
                    help="bare registered cache name (not 'name:quant' — that's the HTTP "
                         "server's own routing syntax; the SDK's from_pretrained() doesn't "
                         "parse it, falls through to a hub pull, and raises 'Hub rejected "
                         "request; authentication required' for an unknown id). Use "
                         "--precision to pick a quant instead")
    ap.add_argument("--precision", default=None,
                    help="quant to select, e.g. Q8_0 (only needed if --model has more than "
                         "one cached precision)")
    ap.add_argument("--device-map", default="npu",
                    help="'auto' | 'cpu' | 'gpu' | 'npu' | 'hybrid' | '<runtime>:<compute-unit>'. "
                         "If you hit 'cannot run the operation(ROPE)' on HTP0, pass "
                         "'llama_cpp:cpu' to force CPU")
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--temperature", type=float, default=0.0)
    a = ap.parse_args()

    model = AutoModelForCausalLM.from_pretrained(
        a.model, precision=a.precision, device_map=a.device_map)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}]
    prompt = model.tokenizer.apply_chat_template(
        messages, tools=TOOLS, tokenize=False, add_generation_prompt=True, enable_thinking=False)

    output = model.generate(prompt, max_new_tokens=a.max_tokens, temperature=a.temperature)
    print(output.text)
    model.close()


if __name__ == "__main__":
    main()
