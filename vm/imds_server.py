import http.server
import socketserver
import threading

PORT = 8000

META_DATA_PATH = "vm/meta-data"
USER_DATA_PATH = "vm/user-data"


class Handler(http.server.SimpleHTTPRequestHandler):
    fetched = {
        "meta-data": False,
        "user-data": False,
    }

    def do_GET(self):
        if self.path == "/meta-data":
            self.fetched["meta-data"] = True
            self.serve_file(META_DATA_PATH)

        elif self.path == "/user-data":
            self.fetched["user-data"] = True
            self.serve_file(USER_DATA_PATH)

        else:
            self.send_response(404)
            self.end_headers()

        # Only shut down once BOTH have been served at least once
        if all(self.fetched.values()):
            threading.Thread(target=shutdown_server, daemon=True).start()

    def serve_file(self, path):
        try:
            with open(path, "rb") as f:
                data = f.read()

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()


def shutdown_server():
    print("meta-data and user-data served; shutting down")
    httpd.shutdown()


with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"NoCloud server running on {PORT}")
    httpd.serve_forever()