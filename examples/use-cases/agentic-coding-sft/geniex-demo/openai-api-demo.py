import json
import base64
import os
import subprocess
import urllib.parse

from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:18181/v1",
    api_key="geniex",
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for travel information about a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                },
                "required": ["query"],
            },
        },
    }
]


from ddgs import DDGS


def web_search(query: str) -> list[dict]:
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
    # macOS `open -a` does not exist on Windows; start the default browser there.
    if os.name == "nt":
        os.startfile(url)
    else:
        subprocess.Popen(["open", "-a", "Google Chrome", url])
    return [
        {"title": r["title"], "snippet": r["body"], "url": r["href"]}
        for r in DDGS().text(query, max_results=3)
    ]


IMAGE_PATH = "C:/Users/zhiyu/OneDrive/Desktop/qualcomm-code/demo/san-diego.jpg"

with open(IMAGE_PATH, "rb") as f:
    IMAGE_BASE64 = base64.b64encode(f.read()).decode("utf-8")
IMAGE_URL = f"data:image/jpeg;base64,{IMAGE_BASE64}"

messages = [
    {
        "role": "system",
        "content": (
            "You are a travel assistant. Call the web_search tool to look up any "
            "location the user asks about before answering. Once you receive the tool "
            "results, do not call the tool again - use them to write a short, friendly "
            "reply for the user. Emit tool calls in the exact format: "
            "<tool_call>{\"name\": \"web_search\", \"arguments\": {\"query\": "
            "\"<your query>\"}}</tool_call>"
        ),
    },
    {
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": IMAGE_URL}},
            {
                "type": "text",
                "text": "Identify the landmark, then call web_search for travel tips about it.",
            },
        ],
    },
]

# Step 1 - VLM identifies the landmark and requests a web_search call.
first = client.chat.completions.create(
    model="qualcomm/Qwen3-VL-4B-Instruct",
    messages=messages,
    tools=tools,
    tool_choice="auto",
    max_tokens=512,
    extra_body={"enable_think": False},
)
print("=== Step 1 raw ===")
print("finish_reason:", first.choices[0].finish_reason)
print("content:", first.choices[0].message.content)
print("tool_calls:", first.choices[0].message.tool_calls)

if not first.choices[0].message.tool_calls:
    raise SystemExit("no tool_calls in step 1 - model did not emit <tool_call>")

call = first.choices[0].message.tool_calls[0]
print("call.function.name:", call.function.name)
print("call.function.arguments:", call.function.arguments)

# Step 2 - run the tool, feed the result back.
result = web_search(**json.loads(call.function.arguments))

# Feed the tool result back as a fresh text-only conversation (no image) so the
# VLM's second turn does not re-run the vision encoder.
followup_messages = [
    messages[0],
    {"role": "user", "content": "Summarize travel tips using the search results below."},
    first.choices[0].message,
    {
        "role": "tool",
        "tool_call_id": call.id,
        "content": json.dumps(result),
    },
]

final = client.chat.completions.create(
    model="qualcomm/Qwen3-VL-4B-Instruct",
    messages=followup_messages,
    max_tokens=256,
    extra_body={"enable_think": False},
)
print("=== Step 2 raw ===")
print("finish_reason:", final.choices[0].finish_reason)
print("content:", final.choices[0].message.content)
print("tool_calls:", final.choices[0].message.tool_calls)