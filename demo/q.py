import json, sys, urllib.request
model, code, fn = sys.argv[1], open(sys.argv[2], encoding="utf-8").read(), sys.argv[3]
tools = [{"type":"function","function":{"name":"str_replace_editor","description":"Edit files. `str_replace` replaces one exact occurrence of old_str with new_str.","parameters":{"type":"object","properties":{"command":{"type":"string","enum":["view","str_replace"]},"path":{"type":"string"},"old_str":{"type":"string"},"new_str":{"type":"string"}},"required":["command","path"]}}},
         {"type":"function","function":{"name":"submit","description":"Submit the changes once the task is complete.","parameters":{"type":"object","properties":{}}}}]
msgs = [{"role":"system","content":"You are a coding agent working in a Python repository. Use the tools to explore the code, make the required change, verify it, and call `submit` when done."},
        {"role":"user","content":f"There's a bug in `{fn}` in /testbed/lib/{fn}.py: it doesn't behave the way its docstring describes. Here is the file:\n\n```python\n{code}```\n\nFix it with str_replace_editor."}]
body = {"model":model,"messages":msgs,"tools":tools,"temperature":0,"max_tokens":512,"stream":False,"enable_think":False}
r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:18181/v1/chat/completions", json.dumps(body).encode(), {"Content-Type":"application/json"}), timeout=300)
m = json.load(r)["choices"][0]["message"]
print((m.get("content") or "")[:200]); [print(c["function"]["name"], c["function"]["arguments"]) for c in m.get("tool_calls") or []]