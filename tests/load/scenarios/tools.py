"""Tool calls, retrieval, uploads, approvals and routine bursts."""

from locust import HttpUser, between, task


class ToolUser(HttpUser):
    """Mix of tool, retrieval, upload, approval and routine traffic."""

    wait_time = between(0.1, 0.5)

    @task(6)
    def tool(self) -> None:
        self.client.post("/api/v1/tools/calls", json={"name": "echo"}, name="tool")

    @task(3)
    def retrieval(self) -> None:
        self.client.post("/api/v1/knowledge/search", json={"query": "policy"}, name="retrieval")

    @task(1)
    def upload(self) -> None:
        self.client.post("/api/v1/files", data=b"x" * 1024, name="upload")

    @task(1)
    def approval(self) -> None:
        self.client.post("/api/v1/approvals/load:approve", json={}, name="approval")

    @task(1)
    def routines(self) -> None:
        self.client.post("/api/v1/routines/burst", json={"count": 10}, name="routines")
