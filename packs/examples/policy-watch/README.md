# Policy watch (example pack)

A content pack that watches public web pages for changes and reports what changed. It
contains no code. Everything it does, it does with tools the platform already ships:
`web.discover`, `documents.ingest`, `documents.diff`, `documents.create` and
`knowledge.search`. The parts that are specific to one subject (which sites to watch, and
what counts as a change that matters) are in this pack and nowhere in the platform.

## What it installs

| Resource | Name | What it is |
|---|---|---|
| Skill | `policy-watch-sources` | The list of sources and the settings. Edit this to change what is watched. |
| Agent | `policy-watch` | Reads the sources, compares each page with its last copy, and writes a digest. |
| Routine | `Policy watch` | Runs the agent at 07:00 and 13:00 (Asia/Kolkata). Installed paused. |

## Install and turn on

1. **Allow the hosts.** On Policies, Web access, add the host of every address in the
   source list. As shipped that is `www.rbi.org.in`.
2. **Install the pack.** Post `manifest.json` to `POST /api/v1/content-packs:install`. An
   install that requires signed packs needs the manifest signed with a key the install
   trusts (`AR_PACK_TRUSTED_KEYS`); this example is not signed.
3. **Publish the skill, then the agent.** Both arrive as drafts.
4. **Edit the sources** in the skill if you want different ones, and name the knowledge
   collections that hold your own policies. Publish the skill again.
5. **Resume the routine.** Nothing runs until you do. Or open a chat with the agent and
   say "Run the policy watch now".

## What a run does

- The first run stores a copy of each page and reports nothing: there is nothing to
  compare with yet.
- A later run asks each page whether it changed. An unchanged page costs one small request
  and is not mentioned.
- A changed page is stored as a new copy, compared with the one before, and the agent
  decides whether the change matters. If it does, the agent searches your own policies for
  the sections it touches and writes a digest.
- A run with nothing to report answers in one line.

The digest is a document in the library. Every copy of every page is kept, so the evidence
for a change can be opened later.

## Proof

The pack has been run on a real public site with a real model: see
[the report](../../../docs/testing/policy-watch-2026-11/report.md).

## What it does not do

- **It does not get round a site.** A site that refuses, a robots.txt that disallows an
  address, or a challenge page is reported under "Could not check".
- **It does not edit a policy.** It suggests a next step; a person decides.
- **It does not send mail by itself.** The routine delivers to its owner's conversation. Add
  an email or webhook delivery on the routine to send the result elsewhere; the first time,
  its owner approves the delivery. A delivery sends every run's result, including the
  one-line "no change" answer.
- **It does not read a licensed feed.** `vendor_feeds` in the source list is for a feed
  connector, which is not part of this pack.

## Changing the pack

The agent's instructions are in `agent.md` and the source list in `sources.md`. After
editing either, rebuild the manifest:

```bash
uv run python packs/examples/policy-watch/build_manifest.py
```

A test fails if `manifest.json` is not what the source files build.
