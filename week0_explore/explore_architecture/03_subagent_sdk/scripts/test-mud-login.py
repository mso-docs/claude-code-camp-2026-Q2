#!/usr/bin/env python3
"""Fast mock-server check for the bounded CircleMUD login state machine."""

from __future__ import annotations

import os
from pathlib import Path
import runpy
import socket
import threading
import time


PROJECT_DIR = Path(__file__).resolve().parent.parent
driver = runpy.run_path(str(PROJECT_DIR / ".ollama/.agents/tools/mud-session.py"), run_name="mud_login_test")
MudSession = driver["MudSession"]


def read_line(connection: socket.socket) -> str:
    data = bytearray()
    while not data.endswith(b"\n"):
        chunk = connection.recv(1)
        if not chunk:
            raise AssertionError("client disconnected during mock login")
        data.extend(chunk)
    return data.decode("utf-8").strip("\r\n")


def serve(listener: socket.socket, errors: list[BaseException]) -> None:
    try:
        connection, _ = listener.accept()
        with connection:
            connection.sendall(b"By what name do you wish to be known? ")
            assert read_line(connection) == "test-user"
            connection.sendall(b"Password: ")
            assert read_line(connection) == "test-password"
            connection.sendall(b"Welcome to the test MUD!\r\nPress RETURN to continue.\r\n")
            assert read_line(connection) == ""
            connection.sendall(b"1) Enter the game\r\nChoice: ")
            assert read_line(connection) == "1"
            connection.sendall(b"Mock Starting Room\r\nA safe room used for tests.\r\n> ")
            assert read_line(connection) == "look"
            connection.sendall(b"Mock Starting Room\r\n> ")
    except BaseException as exc:
        errors.append(exc)
    finally:
        listener.close()


def main() -> int:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    errors: list[BaseException] = []
    thread = threading.Thread(target=serve, args=(listener, errors), daemon=True)
    thread.start()

    os.environ["MUD_LOGIN_TIMEOUT"] = "5"
    started = time.monotonic()
    session = MudSession("127.0.0.1", listener.getsockname()[1], timeout=5)
    session.open()
    try:
        room = session.login("test-user", "test-password")
        assert "Mock Starting Room" in room
        session.send("look")
        assert "Mock Starting Room" in session.read_until_prompt(timeout=2)
    finally:
        session.close()
    thread.join(timeout=2)
    if errors:
        raise errors[0]
    elapsed = time.monotonic() - started
    assert elapsed < 3, f"mock login took too long: {elapsed:.2f}s"
    print(f"Mock login passed in {elapsed:.2f}s with no model-managed sleeps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
