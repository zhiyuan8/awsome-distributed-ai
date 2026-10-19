import json
import sys
import urllib.request

model = sys.argv[1]
path = sys.argv[2] if len(sys.argv) > 2 else "fib.py"
fn = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
code = open(path, encoding="utf-8").read()

tools = [
    {"type": "function", "function": {
        "name": "str_replace_editor",
        "description": "Edit files. `str_replace` replaces one exact occurrence of old_str with new_str.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "enum": ["view", "str_replace"]},
            "path": {"type": "string"},
            "old_str": {"type": "string"},
            "new_str": {"type": "string"}},
            "required": ["command", "path"]}}},
    {"type": "function", "function": {
        "name": "submit",
        "description": "Submit the changes once the task is complete.",
        "parameters": {"type": "object", "properties": {}}}},
]
messages = [
    {"role": "system", "content": "You are a coding agent working in a Python repository. Use the tools "
     "to explore the code, make the required change, verify it, and call `submit` when done."},
    {"role": "user", "content": f"There's a bug in `{fn}` in /testbed/lib/{fn}.py: it doesn't behave the "
     f"way its docstring describes. Here is the file:\n\n```python\n{code}```\n\nFix it with str_replace_editor."},
]
# GenieX's llama_cpp sampler treats 0 as "unset" (temperature 0 -> 0.8), so pin greedy decoding with top_k=1.
body = {"model": model, "messages": messages, "tools": tools, "top_k": 1, "seed": 42,
        "max_tokens": 512, "stream": False, "enable_think": False}

def post(payload):
    req = urllib.request.Request("http://127.0.0.1:18181/v1/chat/completions",
                                 json.dumps(payload).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=600))


# A system-only request resets the server's cached session, so repeated runs start clean.
post({**body, "messages": messages[:1]})
msg = post(body)["choices"][0]["message"]

print(f"== {model}")
for call in msg.get("tool_calls") or []:
    args = json.loads(call["function"]["arguments"])
    if args.get("command") == "str_replace":
        old = args.get("old_str", "").splitlines()
        new = args.get("new_str", "").splitlines()
        changed = [(o, n) for o, n in zip(old, new) if o != n]
        if not changed and len(old) == len(new):
            print("no change (old_str == new_str)")
        for o, n in changed:
            print(f"- {o.strip()}\n+ {n.strip()}")
    else:
        print(call["function"]["name"], args)
if not msg.get("tool_calls"):
    print("no tool call:", (msg.get("content") or "")[:300])
