"""Local HTTP backend: record real upstream arrival times, no external service."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit, parse_qs
import json


def backend(port=0):
    records, lock = [], Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            request = urlsplit(self.path)
            query = parse_qs(request.query)
            entry = {"path": request.path, "key": query.get("key", [""])[0],
                     "id": query.get("id", [""])[0], "arrival": monotonic()}
            with lock:
                records.append(entry)
            body = json.dumps(entry).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    class Server(ThreadingHTTPServer):
        request_queue_size = 128

    server = Server(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server, records


if __name__ == "__main__":
    server, records = backend(19090)
    print("Listening on 127.0.0.1:19090", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        print(json.dumps(records, indent=2))
