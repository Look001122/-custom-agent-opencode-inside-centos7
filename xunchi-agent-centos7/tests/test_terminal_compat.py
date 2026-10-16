import importlib.util
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest

if os.name == "posix":
    import fcntl
    import pty
    import struct
    import termios
    MODULE = Path(__file__).resolve().parents[1] / "deploy/terminal_compat.py"
    spec = importlib.util.spec_from_file_location("terminal_compat", str(MODULE))
    compat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compat)

PROBES = (b"\x1b[>0q\x1bP+q4d73\x1b\\\x1b[?2027$p\x1b[?2031$p"
          b"\x1b[?1004$p\x1b[?2004$p\x1b[?2026$p\x1b[?u"
          b"\x1b]99;i=opentui-notifications:p=?;\x1b\\\x1b]1337;Capabilities\x1b\\"
          b"\x1b_Gi=31337;AAAA\x1b\\\x1b]52;c;BASE64_TEST\x07")


@unittest.skipUnless(os.name == "posix", "Linux tty required")
class TerminalCompatTests(unittest.TestCase):
    def test_split_probes_preserve_utf8_titles_and_drawing(self):
        visible = "正常中文、XunChi".encode("utf-8")
        supported = b"\x1b]0;XunChi\x07\x1b[38;2;43;179;222m" + visible + b"\x1b[0m\x1b[?1006h"
        for width in (1, 2, 3, 7, 65536):
            parser = compat.LegacyOutput()
            wrapped = b"\x1bPtmux;" + PROBES.replace(b"\x1b", b"\x1b\x1b") + b"\x1b\\"
            data = PROBES + supported + PROBES + wrapped
            result = b"".join(parser.feed(data[i:i+width]) for i in range(0, len(data), width))
            self.assertEqual(result, supported)

    def test_large_and_truncated_control_payloads_do_not_leak(self):
        parser = compat.LegacyOutput()
        self.assertEqual(parser.feed(b"\x1b]52;c;" + b"A" * 80000), b"")
        self.assertEqual(parser.feed(b"\x1b\\after"), b"after")
        self.assertEqual(parser.feed(b"\x1b[?2026$"), b"")

    def start_pty(self, code):
        temp = tempfile.TemporaryDirectory(prefix="xunchi-tty-test-")
        self.addCleanup(temp.cleanup)
        fixture = Path(temp.name) / "child.py"
        fixture.write_text(code, encoding="utf-8")
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        attributes = termios.tcgetattr(slave)
        proc = subprocess.Popen([sys.executable, str(MODULE), sys.executable, str(fixture)],
                                stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
        self.addCleanup(lambda: proc.kill() if proc.poll() is None else None)
        return proc, master, slave, attributes

    def read_until(self, master, proc, marker):
        result = bytearray()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            ready, unused, unused_error = select.select([master], [], [], 0.1)
            if ready:
                result.extend(os.read(master, 65536))
            if marker in result or (proc.poll() is not None and not ready):
                return bytes(result)
        self.fail("Timed out waiting for tty output: " + repr(bytes(result)[-500:]))

    def test_pty_roundtrip_paste_resize_and_exit_restore(self):
        pasted = "\x1b[200~中文\nhello\x1b[201~".encode("utf-8")
        code = '''import os, tty, fcntl, termios, struct
tty.setraw(0)
payload = %r
for value in payload:
    os.write(1, bytes([value]))
os.write(1, b"\\x1b]0;XunChi\\x07READY")
data = b""
while len(data) < %d:
    data += os.read(0, 1024)
os.write(1, b"ECHO_HEX=" + data.hex().encode() + b"\\n")
size = fcntl.ioctl(0, termios.TIOCGWINSZ, b"\\0"*8)
os.write(1, b"SIZE=" + str(struct.unpack("HHHH", size)[:2]).encode())
os._exit(7)
''' % (PROBES, len(pasted))
        proc, master, slave, before = self.start_pty(code)
        initial = self.read_until(master, proc, b"READY")
        self.assertIn(b"\x1b]0;XunChi\x07READY", initial)
        self.assertNotIn(b"opentui-notifications", initial)
        self.assertNotIn(b"2026$p", initial)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 32, 100, 0, 0))
        proc.send_signal(signal.SIGWINCH)
        time.sleep(0.1)
        os.write(master, pasted)
        final = self.read_until(master, proc, b"IMPOSSIBLE_MARKER")
        self.assertEqual(proc.wait(timeout=3), 7)
        self.assertIn(b"ECHO_HEX=" + pasted.hex().encode(), final)
        self.assertIn(b"SIZE=(32, 100)", final)
        self.assertEqual(termios.tcgetattr(slave), before)
        self.assertIn(b"\x1b[?1006l", final)
        self.assertIn(b"\x1b[?2004l", final)

    def test_sigterm_restores_tty_and_propagates_exit(self):
        code = 'import os, tty, time\ntty.setraw(0)\nos.write(1, b"READY")\ntime.sleep(30)\n'
        proc, master, slave, before = self.start_pty(code)
        self.read_until(master, proc, b"READY")
        proc.terminate()
        self.read_until(master, proc, b"IMPOSSIBLE_MARKER")
        self.assertEqual(proc.wait(timeout=3), 143)
        self.assertEqual(termios.tcgetattr(slave), before)

    def test_noninteractive_output_and_exit_are_unchanged(self):
        code = 'import os; os.write(1, %r); os._exit(9)' % PROBES
        result = subprocess.run([sys.executable, str(MODULE), sys.executable, "-c", code],
                                input=b"", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 9, result.stderr)
        self.assertEqual(result.stdout, PROBES)


if __name__ == "__main__":
    unittest.main()
