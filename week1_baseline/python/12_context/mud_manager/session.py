"""Long-lived telnet connection to a CircleMUD server.

A background thread continuously drains the socket into an internal
buffer, stripping telnet IAC negotiation bytes. The agent loop sends a
command and then calls read_until_quiet() (or read_until() for a known
prompt) to collect both the command's response and any async chatter
that arrived in the meantime."""

from __future__ import annotations

import re
import socket
import threading
import time

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4000
DEFAULT_TIMEOUT = 10.0

# Telnet protocol bytes we recognise. We don't negotiate — we just consume
# and discard IAC sequences so they don't pollute the buffer.
IAC = 0xFF
DONT = 0xFE
DO = 0xFD
WONT = 0xFC
WILL = 0xFB
SB = 0xFA
SE = 0xF0


class Error(Exception):
    pass


class ConnectionError(Error):  # noqa: A001 - matches Ruby's MudManager::Session::ConnectionError
    pass


class LoginError(Error):
    pass


class Timeout(Error):
    pass


class Session:
    def __init__(self, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.host = host
        self.port = port
        self._timeout = timeout
        self._socket: socket.socket | None = None
        self._reader: threading.Thread | None = None
        self._buffer = ""
        self._cond = threading.Condition()
        self._closed = False
        self._last_recv_at: float | None = None
        self._logged_in = False

    def open(self) -> "Session":
        if self._socket:
            raise Error("already open")
        try:
            self._socket = socket.create_connection((self.host, self.port))
        except OSError as e:
            raise ConnectionError(f"connect {self.host}:{self.port} failed: {e}") from e
        self._closed = False
        self._start_reader()
        return self

    def is_open(self) -> bool:
        return self._socket is not None and not self._closed

    def is_logged_in(self) -> bool:
        return self._logged_in

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._logged_in = False
        try:
            if self._socket:
                self._socket.close()
        except OSError:
            pass  # already closed / broken — fine
        if self._reader:
            self._reader.join(1)
        # Not narrowing a race, closing one: the reader thread's own loop
        # (see _start_reader below) now checks self._closed before every
        # recv(), so by the time join() returns — or even times out — the
        # reader is done touching self._socket. Nulling it here used to be
        # able to race a slow-to-notice reader thread straight into an
        # AttributeError ('NoneType' object has no attribute 'recv'), most
        # visible under the eval harness's rapid open-look-close preflight
        # checks (evals/boukensha_agent.py's check_starting_room()), which
        # exercise this path far more often than a normal long-lived play
        # session ever did.
        self._socket = None
        self._reader = None

    def send_command(self, command) -> str:
        """Accepts None (send a bare Enter — Ruby's :return/:enter symbol
        sentinel becomes Python's None, its natural "no value"), a str, a
        Primitives Command, or anything with __str__. A trailing newline is
        appended."""
        if not self.is_open():
            raise Error("session not open")
        if command is None:
            line = ""
        elif hasattr(command, "raw"):
            line = command.raw
        else:
            line = str(command)
        self._socket.sendall((line + "\r\n").encode("utf-8"))
        return line

    send = send_command

    def drain(self) -> str:
        """Drain whatever is currently buffered and return it. Non-blocking."""
        with self._cond:
            out, self._buffer = self._buffer, ""
            return out

    def read_until_quiet(self, quiet_seconds: float = 1.0, *, timeout: float | None = None) -> str:
        """Block until quiet_seconds have elapsed with no new bytes arriving,
        or timeout total seconds pass. Returns whatever accumulated. This is
        the workhorse for "send a command, get the full response"."""
        if not self.is_open():
            raise Error("session not open")
        deadline = self._monotime() + (timeout if timeout is not None else self._timeout)
        with self._cond:
            while True:
                remaining_total = deadline - self._monotime()
                if remaining_total <= 0:
                    break

                if self._last_recv_at is not None and (self._monotime() - self._last_recv_at) >= quiet_seconds and self._buffer:
                    break

                if self._last_recv_at is not None and self._buffer:
                    wait_for = quiet_seconds - (self._monotime() - self._last_recv_at)
                else:
                    wait_for = remaining_total
                wait_for = min(wait_for, remaining_total)
                if wait_for <= 0:
                    break
                self._cond.wait(wait_for)

            out, self._buffer = self._buffer, ""
            return out

    def read_until(self, pattern: str | re.Pattern, *, timeout: float | None = None) -> str:
        """Block until the buffer contains the given pattern (str or compiled
        regex), then return everything up to and including the match. Raises
        Timeout if timeout seconds pass without a match."""
        if not self.is_open():
            raise Error("session not open")
        regexp = pattern if isinstance(pattern, re.Pattern) else re.compile(re.escape(pattern))
        deadline = self._monotime() + (timeout if timeout is not None else self._timeout)
        with self._cond:
            while True:
                m = regexp.search(self._buffer)
                if m:
                    cut = m.end()
                    out = self._buffer[:cut]
                    self._buffer = self._buffer[cut:]
                    return out
                remaining = deadline - self._monotime()
                if remaining <= 0:
                    raise Timeout(f"read_until {pattern!r} after {timeout}s")
                if self._closed:
                    raise ConnectionError("socket closed while waiting")
                self._cond.wait(remaining)

    # CircleMUD terminates every command response with a prompt that ends in
    # "> " (greater-than space). Waiting for that sentinel is faster and more
    # deterministic than relying on a silence window — it returns as soon as
    # the server signals it has finished processing the command.
    #
    # Falls back to draining the buffer if the prompt is never seen within
    # the timeout (e.g. during combat when extra async lines may slip in).
    PROMPT_SENTINEL = "> "

    def read_until_prompt(self, *, timeout: float | None = None) -> str:
        try:
            return self.read_until(self.PROMPT_SENTINEL, timeout=timeout)
        except Timeout:
            print("[MudManager.Session] prompt not detected within timeout; returning buffered content")
            return self.drain()

    def login(self, username: str, password: str) -> str:
        """Walk the CircleMUD login dance."""
        self.read_until(re.compile(r"By what name do you wish to be known.*\?", re.IGNORECASE))

        # Enter Username
        self.send_command(username)

        # Expect Password Prompt — but the server takes this same fork to ask
        # "Did I get that right, <name> (Y/N)?" when it does NOT recognize
        # username as an existing player, which is otherwise indistinguishable
        # from a real prompt here: it also contains the substring "password"
        # a few lines later ("Give me a password for <name>"), so a regex
        # that only looks for "Password" would silently follow the
        # new-character path and eventually time out waiting for a
        # "Welcome/Reconnecting/Wrong password" line that never arrives —
        # leaving the socket parked mid-prompt for the caller to stumble
        # into. Detect the confirmation prompt explicitly and bail instead of
        # ever agreeing to create a new character with this name.
        after_name = self.read_until(
            re.compile(r"Password|Did I get that right", re.IGNORECASE)
        )
        if re.search(r"Did I get that right", after_name, re.IGNORECASE):
            self.send_command("n")  # decline — do not create a new character
            raise LoginError(
                f"server did not recognize {username!r} as an existing player "
                "(offered to create a new character instead) — declined"
            )

        # Enter Password
        self.send_command(password)

        output = self.read_until(re.compile(r"Welcome|Reconnecting|Wrong password", re.IGNORECASE))
        if re.search(r"Reconnecting", output, re.IGNORECASE):
            pass  # already in-world, skip menu
        elif re.search(r"Welcome", output, re.IGNORECASE):
            # fresh login, handle menu
            self.send_command(None)  # enter for main menu
            self.send_command(1)  # enter the game
            self.read_until_quiet()
        elif re.search(r"Wrong password", output, re.IGNORECASE):
            raise LoginError("wrong password")
        self._logged_in = True
        return output

    # ----- internals -----

    def _start_reader(self) -> None:
        def run() -> None:
            try:
                while True:
                    # A local reference, checked together with self._closed,
                    # so this thread never dereferences self._socket after
                    # close() (running concurrently on another thread) has
                    # already nulled it out — that race used to surface as
                    # "AttributeError: 'NoneType' object has no attribute
                    # 'recv'" on the *next* loop iteration after a socket
                    # closed mid-read.
                    sock = self._socket
                    if self._closed or sock is None:
                        break
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    text = self._strip_iac(chunk)
                    if text:
                        with self._cond:
                            self._buffer += text
                            self._last_recv_at = self._monotime()
                            self._cond.notify_all()
            except OSError:
                pass  # remote closed / connection reset — fall through
            except AttributeError:
                pass  # self._socket was nulled by a concurrent close() — same as a clean shutdown
            except Exception as e:
                print(f"[MudManager.Session] reader error: {type(e).__name__}: {e}")
            finally:
                with self._cond:
                    self._closed = True
                    self._cond.notify_all()

        self._reader = threading.Thread(target=run, daemon=True)
        self._reader.start()

    # Telnet protocol IAC stripper. The MUD may interleave:
    #   IAC (WILL|WONT|DO|DONT) <option>            — 3 bytes
    #   IAC SB <option> ... IAC SE                  — variable
    #   IAC IAC                                     — literal 0xFF byte
    # We discard all of them. CircleMUD's negotiation is mostly echo
    # toggling around the password prompt, which we don't honor.
    @staticmethod
    def _strip_iac(data: bytes) -> str:
        out = bytearray()
        i = 0
        n = len(data)
        while i < n:
            b = data[i]
            if b == IAC:
                nxt = data[i + 1] if i + 1 < n else None
                if nxt is None:
                    break
                elif nxt == IAC:
                    out.append(0xFF)
                    i += 2
                elif nxt in (WILL, WONT, DO, DONT):
                    i += 3
                elif nxt == SB:
                    j = i + 2
                    while j < n and not (data[j] == IAC and j + 1 < n and data[j + 1] == SE):
                        j += 1
                    i = j + 2
                else:
                    i += 2
            else:
                out.append(b)
                i += 1
        return out.decode("utf-8", errors="replace")

    @staticmethod
    def _monotime() -> float:
        return time.monotonic()
