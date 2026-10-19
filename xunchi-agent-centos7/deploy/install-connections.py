#!/usr/bin/env python3
"""CentOS user installation. Preserve old command, config and current processes."""
from __future__ import print_function
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile

BEGIN = "# >>> xunchi IC branding managed entry >>>"
END = "# <<< xunchi IC branding managed entry <<<"
FOLDER = "xunchi-IC-agent-0.2.0-connections.1"


def strip_block(content):
    if BEGIN not in content and END not in content:
        return content
    if content.count(BEGIN) != 1 or content.count(END) != 1:
        raise ValueError("Ambiguous managed entry; .bashrc was not changed")
    first, rest = content.split(BEGIN, 1)
    unused, last = rest.split(END, 1)
    return first + last.lstrip("\r\n")


def atomic_write(path, content):
    fd, name = tempfile.mkstemp(prefix=".xunchi-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, str(path))
    finally:
        if os.path.exists(name):
            os.unlink(name)


def verify(root):
    manifest = json.loads((root / "FILES.json").read_text(encoding="utf-8"))
    for entry in manifest:
        item = root / entry["path"]
        resolved = item.resolve()
        if os.path.commonpath([str(root.resolve()), str(resolved)]) != str(root.resolve()):
            raise ValueError("Package entry escapes its directory")
        if entry.get("link"):
            if not item.is_symlink() or os.readlink(str(item)) != entry["link"]:
                raise ValueError("Package link mismatch: " + entry["path"])
            continue
        sha = hashlib.sha256()
        with item.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                sha.update(block)
        if sha.hexdigest() != entry["sha256"]:
            raise ValueError("Package checksum mismatch: " + entry["path"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("Install on Linux x86_64 as your normal EDA user")
    if os.geteuid() == 0:
        raise ValueError("Use your normal EDA user, not root/su")
    home = Path.home().resolve()
    bashrc = home / ".bashrc"
    if bashrc.is_symlink():
        raise ValueError(".bashrc is a symlink; automatic editing is not supported")
    original = bashrc.read_text(encoding="utf-8") if bashrc.exists() else ""
    stripped = strip_block(original)
    if args.rollback:
        if stripped != original:
            atomic_write(bashrc, stripped)
        print("Managed xunchi entry removed. Open a new terminal to restore the previous entry.")
        print("Existing opencode-centos7 and installed files were preserved.")
        return
    bundle = Path(__file__).resolve().parent
    verify(bundle)
    destination = (args.destination or home / ".local/opt" / FOLDER).expanduser().resolve()
    if os.path.commonpath([str(home), str(destination)]) != str(home) or destination == home:
        raise ValueError("Destination must be a new directory inside your home")
    if destination.exists():
        raise ValueError("Destination already exists; no overwrite performed: " + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(bundle), str(destination), symlinks=True)
    verify(destination)
    result = subprocess.run([str(destination / "opencode"), "--version"], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
    if result.returncode or result.stdout.strip() != "1.19.0":
        print(result.stderr, file=sys.stderr)
        raise ValueError("New engine failed its version check; shell startup was not changed. Files: " + str(destination))
    if bashrc.exists():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = bashrc.with_name(".bashrc.before-xunchi-" + stamp)
        shutil.copy2(str(bashrc), str(backup))
        print("BASHRC_BACKUP=" + str(backup))
    command = "bash " + shlex.quote(str(destination / "start.sh"))
    updated = stripped.rstrip("\r\n") + "\n\n" + BEGIN + "\n"
    updated += "alias xunchi-agent-centos7=" + shlex.quote(command) + "\n" + END + "\n"
    atomic_write(bashrc, updated)
    print("INSTALLED=" + str(destination))
    print("Open a new normal terminal, then run: xunchi-agent-centos7")
    print("Display name: xunchi-IC-agent. Original command: opencode-centos7")
    print("No existing model config, session or running Virtuoso process was changed.")
    print("Rollback: python3 " + shlex.quote(str(destination / "install.py")) + " --rollback")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("INSTALL_FAILED: " + str(error), file=sys.stderr)
        sys.exit(2)
