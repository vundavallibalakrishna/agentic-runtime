"""Chat turns: 10 sustained starts/s in the full run, a few users in CI."""

from locust import HttpUser, between, task


class ChatUser(HttpUser):
    """POST a message and open the SSE stream."""

    wait_time = between(0.1, 0.4)

    @task(5)
    def turn(self) -> None:
        posted = self.client.post(
            "/api/v1/conversations/demo/messages",
            json={"text": "status"},
            name="chat-turn",
        )
        if posted.status_code == 202:
            self.client.get("/api/v1/runs/load/events", name="sse")

    @task(1)
    def health(self) -> None:
        self.client.get("/healthz", name="simple-get")
