# Webhooks

This is the webhook delivery the product already has. There is no second signing scheme.

Outbound deliveries use the headers in [domain events](../05-contracts/domain-events.md):

- `X-AR-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, t + "." + body)>`
- `X-AR-Event-Id`
- `X-AR-Topic`

`run.completed` is one topic. The payload names the run, the conversation, the agent, the trigger, the status, the usage and the final message id. It does not include the prompt or the answer text.

Receivers answer 2xx within 10 seconds and ignore a repeat of the same `X-AR-Event-Id`. A routine webhook uses the same `X-AR-Signature` header on `POST /api/v1/hooks/routines/{token}`. The secret is shown when the routine is created or rotated, and not after that.

Verify with the secret you stored:

```python
import hashlib
import hmac

def signed(secret: str, timestamp: str, body: bytes, header: str) -> bool:
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header, f"t={timestamp},v1={expected}")
```

```bash
# header shape, not a live call
# X-AR-Signature: t=1710000000,v1=<hex>
# X-AR-Topic: run.completed
```

```typescript
import { createHmac, timingSafeEqual } from "node:crypto";

export function signed(secret: string, timestamp: string, body: string, header: string): boolean {
  const digest = createHmac("sha256", secret).update(`${timestamp}.${body}`).digest("hex");
  const expected = `t=${timestamp},v1=${digest}`;
  const left = Buffer.from(header);
  const right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}
```
