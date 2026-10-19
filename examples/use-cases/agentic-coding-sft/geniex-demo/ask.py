import json
import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:18181/v1"


def resolve_model(name):
    # Served ids are "repo:QUANT". A missing quant (this GGUF is Q4_0) is HTTP 400.
    ids = [m["id"] for m in json.load(urllib.request.urlopen(f"{URL}/models", timeout=30))["data"]]
    if name in ids:
        return name
    base = name.split(":", 1)[0]
    matches = [i for i in ids if i == base or i.startswith(base + ":")]
    if len(matches) == 1:
        print(f"{name} is not cached; using {matches[0]}")
        return matches[0]
    have = ", ".join(matches or ids)
    raise SystemExit(f"{name} is not served. Available: {have}")


model = resolve_model(sys.argv[1])
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
    req = urllib.request.Request(f"{URL}/chat/completions",
                                 json.dumps(payload).encode(), {"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=600))
    except urllib.error.HTTPError as e:
        # Surface the server body; urllib otherwise only prints "HTTP Error 400: Bad Request".
        raise SystemExit(f"HTTP {e.code}: {e.read().decode(errors='replace')}") from None


# The prompt names /testbed/lib/<file>.py. Keep that copy in memory and apply edits there.
canon = f"/testbed/lib/{fn}.py"
files = {canon: code}


def locate(path):
    norm = (path or canon).replace("\\", "/").rstrip("/")
    if norm in files or norm.endswith("/" + fn + ".py") or norm.endswith(fn + ".py"):
        return canon
    return None


def run_tool(name, args):
    # Only view and str_replace. A shell command in `command` stops the loop; it is not run.
    if name == "submit":
        return "Submitted.", True
    if name != "str_replace_editor":
        return None, True
    cmd, path = args.get("command"), args.get("path") or canon
    if cmd not in ("view", "str_replace"):
        return None, True
    key = locate(path)
    if cmd == "view" and key is None and path.replace("\\", "/").rstrip("/") in (
            "/testbed", "/testbed/lib"):
        return f"Here's the files and directories up to 2 levels deep in {path}:\n{canon}", False
    if key is None:
        return f"The path {path} does not exist. Please provide a valid path.", False
    text = files[key]
    if cmd == "view":
        lines = text.split("\n")
        body = "\n".join(f"{i:6}\t{line}" for i, line in enumerate(lines, 1))
        return f"Here's the result of running `cat -n` on {key}:\n{body}\n", False
    old, new = args.get("old_str"), args.get("new_str") or ""
    if not isinstance(old, str) or old == "":
        return "Parameter `old_str` is required for command: str_replace", False
    n = text.count(old)
    if n == 0:
        return f"No replacement was performed, old_str `{old}` did not appear verbatim in {key}.", False
    if n > 1:
        return f"No replacement was performed. Multiple occurrences of old_str in {key}.", False
    files[key] = text.replace(old, new, 1)
    # Stop once the file bytes change. Later doctest / python checks are not run.
    return f"The file {key} has been edited.", files[key] != text


def show_diff(before, after):
    import difflib
    diff = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                         fromfile=f"a/{fn}.py", tofile=f"b/{fn}.py"))
    print(diff or "no code change")


# A system-only request resets the server's cached session, so repeated runs start clean.
post({**body, "messages": messages[:1]})
print(f"== {model}")
for turn in range(1, 9):
    msg = post({**body, "messages": messages})["choices"][0]["message"]
    calls = msg.get("tool_calls") or []
    if not calls:
        break
    messages.append({"role": "assistant", "content": msg.get("content") or "",
                     "tool_calls": msg["tool_calls"]})
    done = False
    for call in calls:
        raw = call["function"]["arguments"]
        args = json.loads(raw) if isinstance(raw, str) else raw
        obs, stop = run_tool(call["function"]["name"], args)
        done = done or stop or obs is None
        if obs is not None:
            messages.append({"role": "tool", "tool_call_id": call.get("id") or f"call_{turn}",
                             "content": obs})
    if done:
        break

show_diff(code, files[canon])
