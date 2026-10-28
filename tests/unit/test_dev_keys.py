"""Bootstrap produces usable public service keys without rotating existing private keys."""

import base64
import importlib.util
import shlex
from pathlib import Path

import orjson
from cryptography.hazmat.primitives import serialization

from ar_common.internal_jwt import public_jwk


def test_bootstrap_repairs_legacy_jwks_and_preserves_private_key(tmp_path: Path) -> None:
    path = Path(__file__).resolve().parents[2] / "scripts" / "dev_keys.py"
    spec = importlib.util.spec_from_file_location("dev_keys", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ENV = tmp_path / ".env"
    module.main()
    first = module.ENV.read_text()
    values = {
        key: shlex.split(value)[0]
        for key, value in (line.split("=", 1) for line in first.splitlines())
    }
    private = serialization.load_pem_private_key(
        values["AR_INTERNAL_JWT_PRIVATE_KEY"].replace("\\n", "\n").encode(), password=None
    )
    public = (
        private.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    assert orjson.loads(values["AR_INTERNAL_JWT_JWKS"]) == {"keys": [public_jwk(public, "dev")]}
    module.main()
    assert module.ENV.read_text() == first
    module.ENV.write_text(
        first.replace("AR_DB_ENCRYPTION_KEYS='", "AR_DB_ENCRYPTION_KEYS=").replace("}'", "}", 1)
    )
    module.main()
    assert module.ENV.read_text() == first
    legacy = (
        "\n".join(
            line
            if not line.startswith("AR_INTERNAL_JWT_JWKS=")
            else "AR_INTERNAL_JWT_JWKS=" + base64.b64encode(public.encode()).decode()
            for line in first.splitlines()
        )
        + "\n"
    )
    module.ENV.write_text(legacy)
    module.main()
    assert module.ENV.read_text() == first
