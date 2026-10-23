import http.client
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


TOKEN = os.getenv("WEBHOOK_TOKEN")

if not TOKEN:
    raise SystemExit(
        "Set WEBHOOK_TOKEN before starting the webhook gateway."
    )


class WebhookProxy(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type="text/plain"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.respond(404, b"Not found")

    def do_POST(self):
        if self.path != "/webhook":
            self.respond(404, b"Not found")
            return

        supplied_token = self.headers.get("X-Webhook-Token", "")

        if not secrets.compare_digest(supplied_token, TOKEN):
            self.respond(401, b"Invalid webhook token")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.respond(400, b"Invalid request length")
            return

        if not 0 < length <= 65536:
            self.respond(413, b"Request must be between 1 and 65536 bytes")
            return

        body = self.rfile.read(length)
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            8000,
            timeout=20,
        )

        try:
            connection.request(
                "POST",
                "/webhook",
                body=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Token": supplied_token,
                },
            )

            response = connection.getresponse()

            self.respond(
                response.status,
                response.read(),
                response.getheader(
                    "Content-Type",
                    "application/json",
                ),
            )

        except (OSError, http.client.HTTPException):
            self.respond(502, b"Local backend unavailable")

        finally:
            connection.close()

    def log_message(self, format, *args):
        # Do not log request bodies or authentication headers.
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(
        ("127.0.0.1", 8082),
        WebhookProxy,
    )

    print("Webhook gateway running on local port 8082.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
