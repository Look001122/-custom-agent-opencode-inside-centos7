#!/usr/bin/env python3
"""CentOS 7 terminal transport: suppress unsupported probes, restore tty on exit.

Python 3.6 standard library only. No prompt text, credentials or transcript is
written to disk. UTF-8 input and ordinary terminal drawing bytes pass unchanged.
"""
import errno
import fcntl
import os
import pty
import re
import select
import signal
import sys
import termios
import time
import tty


class LegacyOutput:
    """Parse complete escape records across reads; never regex UTF-8 text."""

    def __init__(self):
        self.pending = bytearray()
        self.mode = None
        self.last_escape = False
        self.oversized = False
        self.tmux = False

    def feed(self, data):
        output = bytearray()
        for value in data:
            if self.mode is None:
                if value == 27:
                    self.mode = "escape"
                    self.pending = bytearray([value])
                else:
                    output.append(value)
                continue
            if not self.oversized:
                self.pending.append(value)
            if self.mode == "escape":
                self.mode = {91: "csi", 93: "osc", 80: "dcs", 95: "apc", 94: "pm"}.get(value)
                if self.mode is None:
                    output.extend(self.pending)
                    self.pending.clear()
                continue
            complete = False
            if self.mode == "csi":
                complete = 64 <= value <= 126
            else:
                if self.mode == "dcs" and self.pending == b"\x1bPtmux;":
                    self.tmux = True
                complete = (self.mode == "osc" and value == 7) or (self.last_escape and value == 92)
                self.last_escape = value == 27 and not (self.tmux and self.last_escape)
            if len(self.pending) > 65536:
                self.pending.clear()
                self.oversized = True
            if not complete:
                continue
            record = bytes(self.pending)
            if not self.oversized and self.allowed(record):
                output.extend(record)
            self.pending.clear()
            self.mode = None
            self.last_escape = False
            self.oversized = False
            self.tmux = False
        return bytes(output)

    def allowed(self, record):
        if record.startswith((b"\x1bP", b"\x1b_", b"\x1b^")):
            return False  # DCS/APC/PM probes and image protocols, not text UI.
        if record.startswith(b"\x1b]"):
            command = record[2:].split(b";", 1)[0]
            return command not in (b"22", b"52", b"66", b"99", b"1337")
        if record.startswith(b"\x1b["):
            if re.fullmatch(br"\x1b\[\?[0-9;]+\$p", record):
                return False  # DECRQM, including 1004/2004/2026 mode probes.
            if re.fullmatch(br"\x1b\[>[0-9;]*q", record):
                return False  # XTVERSION.
            if re.fullmatch(br"\x1b\[[?><=][0-9;]*u", record):
                return False  # Kitty keyboard query/push/pop, legacy keys used.
            if re.fullmatch(br"\x1b\[>4;[0-9]+m", record):
                return False  # Keep normal xterm key encoding.
            if record in (b"\x1b[?2026h", b"\x1b[?2026l"):
                return False
        return True


def write_all(fd, data):
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        view = view[written:]


def run(argv):
    if not argv:
        raise ValueError("Expected the engine path and its arguments")
    if not os.isatty(0) or not os.isatty(1):
        os.execvp(argv[0], argv)
    attributes = termios.tcgetattr(0)
    window = fcntl.ioctl(0, termios.TIOCGWINSZ, b"\0" * 8)
    output = LegacyOutput()
    handlers = {}
    child = None
    master = None
    status = None
    try:
        # Raw mode precedes child startup so replies cannot be echoed by the
        # outer tty while OpenTUI is still initializing its own slave tty.
        tty.setraw(0, termios.TCSANOW)
        child, master = pty.fork()
        if child == 0:
            try:
                fcntl.ioctl(0, termios.TIOCSWINSZ, window)
                os.environ["OPENTUI_GRAPHICS"] = "0"
                os.environ["OPENTUI_NOTIFICATIONS"] = "0"
                os.environ["OPENTUI_NOTIFICATION_PROTOCOL"] = "none"
                os.environ["OPENTUI_FORCE_EXPLICIT_WIDTH"] = "0"
                os.execvp(argv[0], argv)
            except OSError as error:
                os.write(2, ("XunChi launch failed: " + str(error) + "\n").encode())
                os._exit(127)

        def resize(signum, frame):
            size = fcntl.ioctl(0, termios.TIOCGWINSZ, b"\0" * 8)
            fcntl.ioctl(master, termios.TIOCSWINSZ, size)

        def forward(signum, frame):
            try:
                os.killpg(child, signum)
            except ProcessLookupError:
                pass

        for signum in (signal.SIGWINCH, signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
            handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, resize if signum == signal.SIGWINCH else forward)
        resize(None, None)
        # Keep multiline paste framed even though DECRQM detection is blocked.
        # OpenTUI's input parser recognizes bracketed paste independently.
        write_all(1, b"\x1b[?2004h")
        exited_at = None
        while True:
            pid, state = os.waitpid(child, os.WNOHANG | os.WUNTRACED) if status is None else (0, 0)
            if pid and os.WIFSTOPPED(state):
                termios.tcsetattr(0, termios.TCSANOW, attributes)
                os.kill(os.getpid(), signal.SIGSTOP)
                tty.setraw(0, termios.TCSANOW)
                resize(None, None)
                os.killpg(child, signal.SIGCONT)
            elif pid:
                status = state
                exited_at = time.monotonic()
            readable, unused, unused_error = select.select([master] + ([0] if status is None else []), [], [], 0.05)
            if master in readable:
                try:
                    data = os.read(master, 65536)
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
                    data = b""
                if not data:
                    break
                write_all(1, output.feed(data))
            if 0 in readable:
                data = os.read(0, 65536)
                if not data:
                    forward(signal.SIGHUP, None)
                else:
                    write_all(master, data)
            # A detached descendant retaining the slave must not trap the UI.
            if exited_at is not None and time.monotonic() - exited_at > 0.15:
                break
        if status is None:
            unused_pid, status = os.waitpid(child, 0)
    finally:
        for signum, previous in handlers.items():
            signal.signal(signum, previous)
        if master is not None:
            os.close(master)
        # No screen clearing: keep the normal exit summary and shell history.
        try:
            write_all(1, b"\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?1004l\x1b[?2004l\x1b[0m\x1b[?25h\x1b[?1049l\x1b]0;\x07")
        finally:
            termios.tcsetattr(0, termios.TCSAFLUSH, attributes)
    return os.WEXITSTATUS(status) if os.WIFEXITED(status) else 128 + os.WTERMSIG(status)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
