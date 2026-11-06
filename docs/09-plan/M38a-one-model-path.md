# M38a — One model path

Goal: product code has one way to reach a model, an OpenAI-compatible endpoint, and holds no fake model,
scripted turn or demo fixture. A test may use a stand-in. It lives in `ar_testing` and is registered from test
or dev setup as an ordinary provider, so a test runs the code a customer runs
([OQ-94](../open-questions.md)).

Source: [the tool review, section D](../testing/tools-review-2026-11-05/tools-review.md). Depends on:
M38-T03. M38-T04 onwards follow this milestone, because it deletes branches in the turn that those tasks
would otherwise refactor and keep. One pull request for each task. Paths are under
`libs/ar_domain/src/ar_domain/` unless they start with another top-level folder.

Every task leaves CI green. A task that removes a scripted path moves the tests and browser specs that used
it onto the stand-in in the same pull request.

## M38a-T00 Removal plan

**Do:** this file, section D of the review, the plan README row, the rule in `AGENTS.md`, and OQ-94.

## M38a-T01 The stand-in is an ordinary provider

**Do:**

- The scripted model server takes its script set from the URL path (`/s/<set>/v1`), so a provider of kind
  `openai_compatible` reaches it with a base URL and no special header.
- `ar_testing.stand_in` starts the server on a free loopback port for a test session and registers it in a
  store through the same calls a person uses: a provider, a model and the aliases. Product code gains no
  test hook, because a test reaches the stand-in over HTTP like any endpoint.
- A test can load a script for its own script set.

**Done when:** a turn against the stand-in, registered as an ordinary provider, runs the real agent loop and
calls a tool. No product code changes.

**Tests:** `services/fake_llm/tests/unit/test_script_path.py`; `test_m38a_stand_in_provider.py`.

## M38a-T02 No scripted answer in a deployed turn

Each of these runs today whatever the environment.

Split into five pull requests: T02a the provider and alias tests, T02b eval runs, T02c delegated children and
the model-free knowledge answer, T02d the scripted agent draft, T02e the `slow` keyword and the `fake:`
fallback, which lands with T03 because the tests that read them move at the same time.

T02f is a defect found while doing T02b: the single model call that a tool-less agent makes posted to the
gateway URL, or to the scripted server's URL, and not to the tenant's provider. It is fixed on its own before
T02b, because an eval of a tool-less agent needs it. T04 removes that second path altogether.

**Do:**

- Delete the `slow` keyword and the canned sentences in `chat/service.py` `_tokens`. A failed model call is an
  error, never `fake: ...`.
- `_probe` reports a provider that does not answer as failed. It sends no script header.
- An eval run calls the agent loop. `evals/runner.py` `scripted_reply` is deleted.
- A delegated child runs the agent loop. `skills/delegate.py` `_scripted_result` is deleted.
- `knowledge/answer.py` `compose` no longer writes an answer without a model call.
- The builder returns the validation errors when a draft cannot be repaired. `scripted_definition` and the
  `builder_scripts`, `builder_strict` and `builder_responder` hooks leave the product dataclass.

**Done when:** no path in a turn, an eval or a draft produces text that a model did not write.

**Tests:** `test_m38a_no_scripted_answer.py`; the tests and specs that asserted the canned text move to the stand-in.

## M38a-T03 Tests take the model's answer from the stand-in

**Do:** the unit tests that run a turn with no stub, and the browser specs that read the in-process echo, use
the stand-in. A dev script registers it as a provider for `make dev` and for the Playwright web server, with
a scenario for each answer a spec expects. Product code still has its fallback until T07.

**Done when:** no test or spec depends on the in-process `fake:` answer.

**Tests:** the changed tests are the evidence. This is the largest task.

## M38a-T04 No keyword turns

**Do:** delete `skills/turn.py` `maybe_compose` and `tools/chat_loop.py` `maybe_tools`, with the `ask me`
and `/tool name {json}` triggers. Their tests and specs drive the agent loop through stand-in scenarios.
The approval pause keeps one implementation.

**Done when:** `generate` calls the agent loop and nothing else decides the answer.

**Tests:** `test_m38a_turn_path.py`.

## M38a-T05 Fixtures live in the test library

**Do:**

- Move the `tickets`, `echo`, `petstore` and `warehouse` servers, the `desk` agent, the canned `web.fetch`,
  `control.checkpoint`, `control.propose_change` and their data to `ar_testing`. They are registered
  through `tools/handlers.py` `register_endpoint`.
- Remove the `memory://` defaults. A server of kind `sql` or `openapi` needs a real endpoint, a data
  connection needs a real DSN, and no credential is minted for a `memory://` token URL.

**Done when:** `ar_domain` names no demo server, and a store built without the test library has none.

**Tests:** `test_m38a_no_fixtures.py`.

## M38a-T06 Embeddings without a fake

**Do:**

Knowledge and memory were done by M38b-T07b: they embed with the model the tenant registered, refuse
without one (OQ-98), and the stand-in vectors come from the test model server over HTTP. What is left:

- Tool search embeds the catalogue with the model the tenant registered. With no embedding model it ranks
  by words and says so.
- `tools/logic.py` `hash_embedding` is deleted.

**Done when:** no product path computes a hash vector.

**Tests:** `test_m38a_embeddings.py`.

## M38a-T07 The fake branches are deleted

**Do:** remove `fake_models_allowed`, the provider kind `fake` (with a migration that deletes such rows and
tightens the check), the `real` field of `_completion_call`, the seeded provider in `chat/service.py` and
`seed/m2.py`, the echo in `services/model_gateway`, the placeholder `model_step` and `ToolTurnWorkflow`, and
the `fake-llm` entries in Compose, Helm and the docs. The stand-in server moves from `services/fake_llm`
into `ar_testing`, and the dev Procfile starts it from there. A tenant with no model is told to connect one.

**Done when:** a search of `libs/*/src` and `services/*/src`, leaving out `ar_testing`, finds no `fake` model,
script or fixture.

**Tests:** `test_m38a_one_model_path.py`; migration tested up and down.

## Exit

`make check` and `make test` pass. `make dev` starts with the stand-in registered by the dev script, and chat
answers without an external key. A store built for `prod` has no provider, and a turn says that a model must
be connected.
