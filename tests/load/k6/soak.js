import http from "k6/http";
import { check, sleep } from "k6";

// Soak against a running API. Default host matches the live-certification port list.
export const options = {
  scenarios: {
    soak: {
      executor: "constant-vus",
      vus: 5,
      duration: __ENV.K6_DURATION || "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
  },
};

const base = __ENV.AR_API_URL || "http://127.0.0.1:8010";

export default function () {
  const health = http.get(`${base}/healthz`);
  check(health, { "health answers": (response) => response.status === 200 });
  const ready = http.get(`${base}/readyz`);
  check(ready, { "ready answers": (response) => response.status === 200 || response.status === 503 });
  sleep(1);
}
