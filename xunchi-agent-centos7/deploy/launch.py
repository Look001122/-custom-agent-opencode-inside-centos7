#!/usr/bin/env python3
"""No credential prompt at shell startup. Own ephemeral config lifecycle."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from connections import Store, read_json, private_dir, atomic_json, ConnectionError


def launch(root, arguments):
    root = Path(root)
    home = Path.home()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))) / "xunchi-agent-centos7"
    cache = Path(os.environ.get("XDG_CACHE_HOME", str(home / ".cache"))) / "xunchi-agent-centos7"
    private_dir(cache)
    if os.environ.get("OPENCODE_CONFIG_CONTENT"):
        raise ConnectionError("此版连接管理暂不导入 OPENCODE_CONFIG_CONTENT；请先将配置保存为 JSON 文件，或使用旧入口")
    # Explicit user configuration wins; the legacy Bailian file is only a migration source.
    legacy = home / "opencode-bailian-v1.json"
    fallback = legacy if legacy.exists() else config_home.parent / "opencode/opencode.json"
    source = Path(os.environ.get("OPENCODE_CONFIG", str(fallback))).expanduser()
    base = read_json(source, {})
    with tempfile.TemporaryDirectory(prefix="session-", dir=str(cache)) as session:
        store = Store(config_home, session, base)
        store.migrate()
        store.render()
        atomic_json(Path(session) / "base.json", base)
        env = os.environ.copy()
        env.update(OPENCODE_CONFIG=str(store.runtime), XUNCHI_CONNECTIONS_HOME=str(config_home),
                   XUNCHI_SESSION_DIR=session, XUNCHI_CONNECTIONS_BACKEND=str(root / "connections.py"),
                   XUNCHI_CONNECTIONS_PYTHON=sys.executable)
        env.pop("OPENCODE_CONFIG_CONTENT", None)
        env.pop("LD_LIBRARY_PATH", None)
        env.pop("LD_PRELOAD", None)
        argv = [str(root / "opencode")] + arguments
        if os.environ.get("XUNCHI_TERMINAL_PROFILE", "legacy-vte") == "legacy-vte" and os.isatty(0) and os.isatty(1):
            argv = [sys.executable, str(root / "terminal_compat.py")] + argv
        process = subprocess.Popen(argv, env=env)
        previous = {}
        def forward(signum, frame):
            if process.poll() is None:
                process.send_signal(signum)
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[signum] = signal.signal(signum, forward)
        try:
            return process.wait()
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)


if __name__ == "__main__":
    try:
        sys.exit(launch(sys.argv[1], sys.argv[2:]))
    except ConnectionError as error:
        print("XunChi: " + str(error), file=sys.stderr)
        sys.exit(2)
