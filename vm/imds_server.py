import errno
import http.server
import os
import signal
import socketserver
import subprocess
import threading
import time

PORT = 8000
TIMEOUT_SECONDS = 120

META_DATA_PATH = "vm/meta-data"
USER_DATA_PATH = "vm/user-data"


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class Handler(http.server.BaseHTTPRequestHandler):
    fetched = {
        "meta-data": False,
        "user-data": False,
    }

    state_lock = threading.Lock()
    last_activity = time.monotonic()

    def do_GET(self):
        with self.state_lock:
            Handler.last_activity = time.monotonic()

        if self.path == "/meta-data":
            self.serve_file("meta-data", META_DATA_PATH)

        elif self.path == "/user-data":
            self.serve_file("user-data", USER_DATA_PATH)

        else:
            self.send_response(404)
            self.end_headers()

        with self.state_lock:
            complete = all(Handler.fetched.values())

        if complete:
            print("meta-data and user-data served; shutting down")
            threading.Thread(
                target=shutdown_server,
                daemon=True,
            ).start()

    def serve_file(self, name, path):
        try:
            with open(path, "rb") as f:
                data = f.read()

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

            with self.state_lock:
                Handler.fetched[name] = True

        except FileNotFoundError:
            print(f"File not found: {path}")
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def find_processes_using_port(port):
    """
    Find PIDs listening on a TCP port.

    Works on macOS/Linux using lsof.
    """
    try:
        result = subprocess.run(
            [
                "lsof",
                "-nP",
                "-t",
                f"-iTCP:{port}",
                "-sTCP:LISTEN",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print("ERROR: lsof is not installed.")
        return []

    pids = set()

    for line in result.stdout.splitlines():
        line = line.strip()

        if line.isdigit():
            pid = int(line)

            # Don't accidentally kill ourselves.
            if pid != os.getpid():
                pids.add(pid)

    return list(pids)


def kill_process(pid):
    """Try to gracefully terminate a process, then force kill it."""
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to PID {pid}")
    except ProcessLookupError:
        return
    except PermissionError:
        print(f"Permission denied killing PID {pid}")
        return

    # Give it a few seconds to exit.
    deadline = time.monotonic() + 5

    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            print(f"PID {pid} exited")
            return
        except PermissionError:
            return

        time.sleep(0.1)

    # Still alive -- force it.
    try:
        print(f"PID {pid} did not exit; sending SIGKILL")
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def free_port(port):
    """Kill whatever process is listening on the port."""
    pids = find_processes_using_port(port)

    if not pids:
        print(f"Could not find a process using port {port}")
        return

    for pid in pids:
        print(f"Port {port} is already in use by PID {pid}")
        kill_process(pid)

    # Wait until the port is actually free.
    deadline = time.monotonic() + 5

    while time.monotonic() < deadline:
        if not find_processes_using_port(port):
            print(f"Port {port} is now free")
            return

        time.sleep(0.2)

    raise RuntimeError(
        f"Port {port} is still in use after attempting to free it"
    )


def create_server():
    """
    Try to create the server.

    If the port is already occupied, kill the process using it
    and try again.
    """
    try:
        return ReusableTCPServer(("0.0.0.0", PORT), Handler)

    except OSError as exc:
        if exc.errno != errno.EADDRINUSE:
            raise

        print(f"Port {PORT} is already in use.")
        free_port(PORT)

        # Retry binding.
        for attempt in range(10):
            try:
                return ReusableTCPServer(("0.0.0.0", PORT), Handler)

            except OSError as retry_exc:
                if retry_exc.errno != errno.EADDRINUSE:
                    raise

                print(
                    f"Port still busy, retrying "
                    f"({attempt + 1}/10)..."
                )
                time.sleep(0.5)

        raise RuntimeError(
            f"Unable to bind to port {PORT} after killing "
            f"the existing process."
        )


def timeout_monitor():
    """Shut down after 2 minutes with no requests."""
    while True:
        time.sleep(1)

        with Handler.state_lock:
            idle_time = time.monotonic() - Handler.last_activity

        if idle_time >= TIMEOUT_SECONDS:
            print("No activity for 2 minutes; shutting down")
            shutdown_server()
            return


def shutdown_server():
    """Safely shut down the HTTP server."""
    try:
        httpd.shutdown()
    except Exception:
        pass


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

httpd = create_server()

threading.Thread(
    target=timeout_monitor,
    daemon=True,
).start()

print(f"NoCloud server running on port {PORT}")
print(f"Will shut down after {TIMEOUT_SECONDS} seconds of inactivity.")

try:
    httpd.serve_forever()

except KeyboardInterrupt:
    print("\nInterrupted; shutting down")

finally:
    httpd.server_close()
    print("Server stopped")
