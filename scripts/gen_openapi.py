"""Export the public OpenAPI document from the api app. No server required."""

from pathlib import Path

import orjson

from ar_api.main import create_application
from ar_domain.exposure.spec import agent_paths

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    app = create_application()
    document = app.openapi()
    target = ROOT / "openapi.json"
    target.write_bytes(orjson.dumps(document, option=orjson.OPT_INDENT_2) + b"\n")
    print(f"wrote {target}")
    agent = ROOT / "docs" / "agent-api" / "openapi.json"
    agent.parent.mkdir(parents=True, exist_ok=True)
    agent.write_bytes(orjson.dumps(agent_paths(document), option=orjson.OPT_INDENT_2) + b"\n")
    print(f"wrote {agent}")


if __name__ == "__main__":
    main()
