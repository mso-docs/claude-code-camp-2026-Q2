#!/usr/bin/env python3
"""Keep one authenticated CircleMUD socket alive and accept commands on stdin."""

from __future__ import annotations

import os
import re
import select
import socket
import sys
import time


IAC = 0xFF
DONT = 0xFE
DO = 0xFD
WONT = 0xFC
WILL = 0xFB
SB = 0xFA
SE = 0xF0


class MudError(RuntimeError):
    pass


class MudSession:
    def __init__(self, host: str, port: int, timeout: float = 30.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.buffer = ""
        self.telnet_state = "normal"

    def open(self) -> None:
        try:
            self.sock = socket.create_connection((self.host, self.port), self.timeout)
            self.sock.setblocking(False)
        except OSError as exc:
            raise MudError(f"connect {self.host}:{self.port} failed: {exc}") from exc

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def send(self, command: str = "") -> None:
        if self.sock is None:
            raise MudError("session is not open")
        try:
            self.sock.sendall(command.encode("utf-8") + b"\r\n")
        except OSError as exc:
            raise MudError(f"send failed: {exc}") from exc

    def read_until(self, pattern: re.Pattern[str], timeout: float | None = None) -> str:
        deadline = time.monotonic() + (timeout or self.timeout)
        while True:
            match = pattern.search(self.buffer)
            if match:
                output = self.buffer[: match.end()]
                self.buffer = self.buffer[match.end() :]
                return output
            if time.monotonic() >= deadline:
                raise MudError(f"timed out waiting for {pattern.pattern!r}")
            self._receive(deadline)

    def read_until_quiet(self, quiet: float = 1.0, timeout: float = 10.0) -> str:
        deadline = time.monotonic() + timeout
        last_data_at: float | None = None
        while time.monotonic() < deadline:
            before = len(self.buffer)
            self._receive(min(deadline, time.monotonic() + quiet))
            if len(self.buffer) > before:
                last_data_at = time.monotonic()
            if self.buffer and last_data_at is not None:
                if time.monotonic() - last_data_at >= quiet:
                    break
        output, self.buffer = self.buffer, ""
        return output

    def read_until_prompt(self, timeout: float = 10.0) -> str:
        try:
            return self.read_until(re.compile(r">\s*$", re.MULTILINE), timeout)
        except MudError:
            return self.read_until_quiet(timeout=2.0)

    def login(self, username: str, password: str) -> None:
        self.read_until(re.compile(r"By what name do you wish to be known.*\?", re.I))
        self.send(username)
        self.read_until(re.compile(r"Password", re.I))
        self.send(password)

        result = self.read_until(re.compile(r"Welcome|Reconnecting|Wrong password", re.I))
        if re.search(r"Wrong password", result, re.I):
            raise MudError("wrong password")
        if re.search(r"Welcome", result, re.I):
            self.send("")
            self.read_until_quiet(quiet=0.5, timeout=10.0)
            self.send("1")
            self.read_until_quiet(quiet=1.0, timeout=10.0)

    def _receive(self, deadline: float) -> None:
        if self.sock is None:
            raise MudError("session is not open")
        wait = max(0.0, min(0.25, deadline - time.monotonic()))
        readable, _, _ = select.select([self.sock], [], [], wait)
        if not readable:
            return
        try:
            chunk = self.sock.recv(4096)
        except BlockingIOError:
            return
        except OSError as exc:
            raise MudError(f"receive failed: {exc}") from exc
        if not chunk:
            raise MudError("server closed the connection")
        self.buffer += self._strip_telnet(chunk).decode("utf-8", errors="replace")

    def _strip_telnet(self, chunk: bytes) -> bytes:
        output = bytearray()
        for byte in chunk:
            if self.telnet_state == "normal":
                if byte == IAC:
                    self.telnet_state = "iac"
                else:
                    output.append(byte)
            elif self.telnet_state == "iac":
                if byte == IAC:
                    output.append(IAC)
                    self.telnet_state = "normal"
                elif byte in (WILL, WONT, DO, DONT):
                    self.telnet_state = "negotiate"
                elif byte == SB:
                    self.telnet_state = "subnegotiation"
                else:
                    self.telnet_state = "normal"
            elif self.telnet_state == "negotiate":
                self.telnet_state = "normal"
            elif self.telnet_state == "subnegotiation":
                if byte == IAC:
                    self.telnet_state = "subnegotiation_iac"
            elif self.telnet_state == "subnegotiation_iac":
                self.telnet_state = "normal" if byte == SE else "subnegotiation"
        return bytes(output)


def main() -> int:
    try:
        username = os.environ["MUD_USERNAME"]
        password = os.environ["MUD_PASSWORD"]
        host = os.environ.get("MUD_HOST", "localhost")
        port = int(os.environ.get("MUD_PORT", "4000"))

        session = MudSession(host, port)
        session.open()
        try:
            session.login(username, password)
            print("MUD_LOGIN_OK", flush=True)
            session.send("look")
            print(session.read_until_prompt(), flush=True)
            print("MUD_COMMAND_DONE", flush=True)

            for line in sys.stdin:
                command = line.strip()
                if not command:
                    continue
                if command == "__close__":
                    break
                session.send(command)
                print(session.read_until_prompt(), flush=True)
                print("MUD_COMMAND_DONE", flush=True)
        finally:
            session.close()
    except KeyError as exc:
        print(f"MUD_LOGIN_ERROR: missing environment variable {exc.args[0]}", file=sys.stderr)
        return 2
    except (MudError, OSError, ValueError) as exc:
        print(f"MUD_LOGIN_ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
