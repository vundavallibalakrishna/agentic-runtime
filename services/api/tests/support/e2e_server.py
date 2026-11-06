"""The API process the browser tests run against.

It is the product's own application, started with no database and given the demo tenant:
its people, agents, fixtures and example conversations. The demo tenant is test data, so
it is put in from here. A product process never creates it, and one that cannot reach its
database is not ready.

    uv run python services/api/tests/support/e2e_server.py
"""

import os

# Say "no database" before the application reads its settings.
os.environ["AR_DURABLE_STATE"] = "memory"

import uvicorn

from ar_api.main import LISTEN_PORT, create_application
from ar_common.host_ports import listen_port


def main() -> None:
    """Build the application over the demo tenant and listen on ``AR_PORT``."""
    app = create_application()
    store = app.state.chat
    store.seed_demo_tenant()
    store.seed_showcase()
    uvicorn.run(app, host="127.0.0.1", port=listen_port("AR_PORT", LISTEN_PORT))


if __name__ == "__main__":
    main()
