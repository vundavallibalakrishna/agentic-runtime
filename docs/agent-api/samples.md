# Samples

Generic calls. Replace the origin and the key. Nothing here is tied to an industry.

A reply's `content` array is additive. A `followups` part lists short prompts you can send next. `responseFormat` is a JSON Schema checked against the answer. When the agent already has `output.jsonSchema`, the request schema is the one used for that turn. The model is told the schema, and a reply that does not match is sent back to it once. If the answer still does not match, the run ends `failed` with code `repair_exhausted`; you never receive text that breaks the schema as the answer.

## Review a document, then ask a follow-up

Upload a text file, send it, then send one of the follow-up prompts from `content`.

```bash
FILE=$(curl -s https://runtime.example/v1/agents/assistant/files \
  -H "Authorization: Bearer ara_<prefix><secret>" \
  -F "upload=@notes.txt" \
  -F "mime_type=text/plain")
FILE_ID=$(printf '%s' "$FILE" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -s https://runtime.example/v1/agents/assistant:run \
  -H "Authorization: Bearer ara_<prefix><secret>" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"Review the attached notes. List what is missing.\",\"attachmentIds\":[\"$FILE_ID\"],\"suggestFollowups\":true}"
```

```python
import json
import urllib.request

base = "https://runtime.example/v1/agents/assistant"
key = "ara_<prefix><secret>"


def post(path: str, body: dict) -> dict:
    request = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


reply = post(
    ":run",
    {
        "text": "Review the attached notes. List what is missing.",
        "attachmentIds": ["FILE_ID"],
        "suggestFollowups": True,
    },
)
followups = [
    prompt
    for part in reply.get("content", [])
    if part.get("type") == "followups"
    for prompt in part.get("prompts", [])
]
if followups:
    print(post(":run", {"text": followups[0]}))
```

```typescript
const base = "https://runtime.example/v1/agents/assistant";
const headers = {
  Authorization: "Bearer ara_<prefix><secret>",
  "Content-Type": "application/json",
};

const reply = await fetch(`${base}:run`, {
  method: "POST",
  headers,
  body: JSON.stringify({
    text: "Review the attached notes. List what is missing.",
    attachmentIds: ["FILE_ID"],
    suggestFollowups: true,
    responseFormat: {
      type: "object",
      properties: {
        summary: { type: "string" },
        missing: { type: "array", items: { type: "string" } },
      },
      required: ["summary", "missing"],
    },
  }),
}).then((response) => response.json());

const prompts: string[] = (reply.content ?? [])
  .filter((part: { type?: string }) => part.type === "followups")
  .flatMap((part: { prompts?: string[] }) => part.prompts ?? []);
```

## Turn a CSV into a chart

The chart tool writes a PNG. The same rows are on the tool presentation so a client can draw them again. The PNG is the record.

```bash
curl -s https://runtime.example/v1/agents/assistant/files \
  -H "Authorization: Bearer ara_<prefix><secret>" \
  -F "upload=@counts.csv" \
  -F "mime_type=text/csv"

curl -s https://runtime.example/v1/agents/assistant:run \
  -H "Authorization: Bearer ara_<prefix><secret>" \
  -H "Content-Type: application/json" \
  -d '{"text":"Read the attached CSV and draw a bar chart of the two columns.","attachmentIds":["FILE_ID"]}'
```

```python
post(
    ":run",
    {
        "text": "Read the attached CSV and draw a bar chart of the two columns.",
        "attachmentIds": ["FILE_ID"],
    },
)
```

```typescript
await fetch(`${base}:run`, {
  method: "POST",
  headers,
  body: JSON.stringify({
    text: "Read the attached CSV and draw a bar chart of the two columns.",
    attachmentIds: ["FILE_ID"],
  }),
});
```
