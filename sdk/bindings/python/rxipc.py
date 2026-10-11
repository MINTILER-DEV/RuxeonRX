"""Version 1 local session IPC client."""
import json
import socket

MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class Client:
    def __init__(self, path, timeout=60):
        self.path = str(path)
        self.timeout = timeout

    def call(self, method, **params):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(self.timeout)
            connection.connect(self.path)
            connection.sendall((json.dumps({"version": 1, "method": method, "params": params}) + "\n").encode())
            with connection.makefile("rb") as stream:
                encoded = stream.readline(MAX_RESPONSE_BYTES + 1)
                if len(encoded) > MAX_RESPONSE_BYTES or not encoded.endswith(b"\n"):
                    raise RuntimeError("IPC response exceeds the limit or is incomplete")
                answer = json.loads(encoded)
        if not answer.get("ok"):
            raise RuntimeError(answer.get("error", "service error"))
        return answer.get("result")
