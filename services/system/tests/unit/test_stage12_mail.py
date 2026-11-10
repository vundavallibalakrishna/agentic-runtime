"""SMTP notification activity. The first attempt is refused. Proof: contract."""

from __future__ import annotations

import threading
from socketserver import StreamRequestHandler, ThreadingTCPServer

from temporalio.worker import Worker

from ar_system.workflows.notification_mail import NotificationEmailWorkflow, send_smtp_notification


class _Sink(StreamRequestHandler):
    def handle(self) -> None:
        self.wfile.write(b"220 ready\r\n")
        collecting = False
        lines: list[str] = []
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            line = raw.decode(errors="replace").strip()
            if collecting:
                if line == ".":
                    collecting = False
                    self.server.messages.append("\n".join(lines))  # type: ignore[attr-defined]
                    lines = []
                    self.wfile.write(b"250 ok\r\n")
                else:
                    lines.append(line)
                continue
            if line.upper().startswith("DATA"):
                self.server.attempts += 1  # type: ignore[attr-defined]
                if self.server.attempts == 1:  # type: ignore[attr-defined]
                    self.wfile.write(b"450 try again\r\n")
                    continue
                collecting = True
                self.wfile.write(b"354 go\r\n")
                continue
            if line.upper().startswith("QUIT"):
                self.wfile.write(b"221 bye\r\n")
                return
            self.wfile.write(b"250 ok\r\n")


async def test_smtp_activity_retries_then_delivers(temporal_env: object) -> None:
    server = ThreadingTCPServer(("127.0.0.1", 0), _Sink)
    server.attempts = 0  # type: ignore[attr-defined]
    server.messages = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    client = temporal_env.client  # type: ignore[attr-defined]
    try:
        async with Worker(
            client,
            task_queue="ar-system-mail",
            workflows=[NotificationEmailWorkflow],
            activities=[send_smtp_notification],
        ):
            result = await client.execute_workflow(
                NotificationEmailWorkflow.run,
                {
                    "host": "127.0.0.1",
                    "port": port,
                    "to": "ada@example.com",
                    "subject": "Reset your password",
                    "body": "token-body",
                    "from": "noreply@dev.local",
                },
                id="stage12-mail",
                task_queue="ar-system-mail",
            )
        assert result["sent"] is True
        assert result["attempts"] >= 2
        assert server.messages  # type: ignore[attr-defined]
        assert "token-body" in server.messages[0]  # type: ignore[attr-defined]
        assert "Reset your password" in server.messages[0]  # type: ignore[attr-defined]
    finally:
        server.shutdown()
