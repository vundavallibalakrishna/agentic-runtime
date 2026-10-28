# M21b sandbox boundaries

`general.code` and `general.shell` run in a directory that belongs to one run. The child environment is built from scratch. `AR_*` values, database URLs and the parent environment are not copied in.

When the kernel allows user namespaces, the command also runs under `unshare` with a new mount, pid and (unless network is enabled) net namespace. The process pivots onto a root that bind-mounts the interpreter and the run workspace. The host home directory, `/etc` (except resolvers when network is on), platform secrets and the database socket are not mounted. A new pid namespace hides the host process table, so the parent environment is not readable through `/proc`.

Network stays off unless the agent override sets `network` true. With network off, the net namespace has no route. With network on, every URL written in the command must be on the egress allow list, and private, link-local and metadata addresses are denied. That scan does not packet-filter a host the script computes at runtime. The Squid egress proxy from M6 remains the deployment control for production computers.

If `unshare` is refused, the command runs as a scrubbed subprocess with the workspace as its working directory. File tools still reject paths outside the workspace. That fallback can read the host filesystem and is not a security boundary. The unit test records which mode ran.

Breakout checks in `libs/ar_common/tests/unit/test_isolate.py` and `libs/ar_domain/tests/unit/test_m21b_tools.py`:

- A parent `AR_CERT_LLM_API_KEY` is absent from the child environment and from its stdout.
- In namespace mode, `/etc/passwd` does not exist in the child and a connection to `1.1.1.1` fails.
- `general.read_file` of `/etc/passwd` is rejected.
- A shell command that names a URL is rejected while network is off.
- An HTTP secret is replaced with `[redacted]` in the tool result and is not stored on the call.
- Fetched HTML is reduced to text. Script bodies are dropped. The text is labelled untrusted data and wrapped before it re-enters the prompt.
