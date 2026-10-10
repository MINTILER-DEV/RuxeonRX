"""Version 1 local session IPC client."""
import json
import socket


class Client:
    def __init__(self, path):
        self.path = str(path)

    def call(self, method, **params):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(15)
            connection.connect(self.path)
            connection.sendall((json.dumps({"version": 1, "method": method, "params": params}) + "\n").encode())
            with connection.makefile("rb") as stream:
                answer = json.loads(stream.readline(2 * 1024 * 1024))
        if not answer.get("ok"):
            raise RuntimeError(answer.get("error", "service error"))
        return answer.get("result")
