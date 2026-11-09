# Platform proof (platform verification, Layer 3)

`scripts/platform_proof.py` walks one product story across the whole platform with a real
model, from a clean store, and asserts a real outcome at each step. Where the tool matrix
(Layer 1) proves each tool runs and the gym (Layer 2) measures tool-choice accuracy, this
proves the features work **together**.

## The story

1. **Build an agent from a sentence** — the builder drafts a valid agent definition with the
   reasoning model (no scripted fallback).
2. **Chat and use a tool** — that agent runs `general.code` to compute a product it cannot do
   in its head, and quotes the exact result.
3. **Answer from knowledge, grounded** — a passage is added to a collection; the agent
   searches knowledge and cites the token from it.
4. **Remember a preference** — a stated preference becomes a stored memory fact.

The exit code is non-zero if any step fails. It runs in process on the demo tenant with the
reasoning alias pointed at the cert model (the gym's live path), so it needs no running
stack; the HTTP/sign-in/multi-process layer is covered by `full_stack_smoke.py` and the
`web-e2e` suite.

## Run it

```bash
AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY=... uv run python scripts/platform_proof.py
```

The cert key is read from the environment and never printed.

## Result (2026-11-09, Qwen3-32B)

**4/4 steps passed.** The builder drafted a 345-character agent, the agent used `general.code`
and returned the exact product, cited the knowledge token, and stored the preference as a
memory fact. The whole platform works together with a real model.

Note: the chat step deliberately asks for a calculation the model cannot do unaided, so it
must run the tool — an earlier simpler task let the model answer directly without one, the
same shortcut the gym's chain finding describes.
