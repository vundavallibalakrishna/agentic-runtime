# Records pack

Optional signed pack for the records desk: sealed items, holds, retention schedules, guest grants, export bundles, the register and run records.

Core does not import this package. It stays uninstalled until a tenant enables it.

```bash
AR_PACKS_DIR=packs AR_PACK_SIGNATURE_REQUIRED=1 AR_PACK_TRUSTED_KEYS=records-example \
  uv run python -c "print('set AR_PACKS_DIR to packs when starting the API')"
```

`key.pub` is the example public key. `signature.b64` is an Ed25519 signature over the JCS SHA-256 of `manifest.json`. The private key is not in the repository.
