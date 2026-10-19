#!/usr/bin/env python3
"""Upgrade branding while keeping the active launcher's connection workflow."""
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

from install_common import BEGIN, END, atomic_write, strip_block, verify

FOLDER = "xunchi-agent-0.1.1-identity.1"


def current_bundle(content, selected):
    if selected:
        return selected.expanduser().resolve()
    block = content.split(BEGIN, 1)[1].split(END, 1)[0] if BEGIN in content else content
    aliases = [line for line in block.splitlines() if line.strip().startswith("alias xunchi-agent-centos7=")]
    if len(aliases) != 1:
        raise ValueError("Cannot identify one active launcher. Run: type xunchi-agent-centos7; then use --current-dir with its package directory")
    value = shlex.split(aliases[0].strip()[len("alias xunchi-agent-centos7="):])
    command = shlex.split(value[0]) if len(value) == 1 else value
    if len(command) != 2 or command[0] != "bash" or Path(command[1]).name != "start.sh":
        raise ValueError("Unknown launcher format; no shell configuration was changed. Use --current-dir with the installed package directory")
    return Path(command[1]).expanduser().resolve().parent


def managed_block(content):
    if BEGIN not in content:
        return ""
    return BEGIN + content.split(BEGIN, 1)[1].split(END, 1)[0] + END + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-dir", type=Path)
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64" or os.geteuid() == 0:
        raise ValueError("Run as your normal Linux x86_64 EDA user, without su/sudo")
    bundle = Path(__file__).resolve().parent
    home = Path.home().resolve()
    bashrc = home / ".bashrc"
    if bashrc.is_symlink():
        raise ValueError("Automatic editing of a symlinked .bashrc is unsupported")
    content = bashrc.read_text(encoding="utf-8") if bashrc.exists() else ""
    stripped = strip_block(content)
    if args.rollback:
        state = json.loads((bundle / "IDENTITY_INSTALL.json").read_text(encoding="utf-8"))
        if managed_block(content) != state["installed_block"]:
            raise ValueError("Active entry changed since this upgrade; refusing to replace another installation")
        atomic_write(bashrc, stripped.rstrip("\r\n") + "\n\n" + state["previous_block"])
        print("Previous XunChi launcher restored. Open a new terminal.")
        return
    verify(bundle)
    current = current_bundle(content, args.current_dir)
    if not current.is_dir() or current.is_symlink() or current == home or os.path.commonpath([str(home), str(current)]) != str(home):
        raise ValueError("Existing bundle must be a real directory inside your home")
    for name in ("start.sh", "opencode", "bin/opencode", "terminal_compat.py"):
        if not (current / name).is_file():
            raise ValueError("Existing package is incomplete: " + name)
    launcher = (current / "start.sh").read_text(encoding="utf-8")
    # Match only the two existing launcher families; never guess a new provider.
    if '"$ROOT/launch.py"' in launcher:
        mode = "managed"
        if not all((current / name).is_file() for name in ("launch.py", "connections.py")):
            raise ValueError("Existing connection launcher files are missing")
    elif '"$ROOT/opencode"' in launcher and "OPENCODE_CONFIG" in launcher:
        mode = "legacy"
    else:
        raise ValueError("Unrecognized launcher; existing files and .bashrc remain unchanged")
    destination = (home / ".local/opt" / FOLDER).resolve()
    if os.path.commonpath([str(home), str(destination)]) != str(home):
        raise ValueError("New installation must stay inside your home")
    if destination.exists():
        raise ValueError("This version is already present; no overwrite: " + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Copy the installed runtime and launcher, including local customizations.
    shutil.copytree(str(current), str(destination), symlinks=True)
    engine = bundle / "engines" / mode
    target = destination / "bin/opencode"
    if target.is_symlink():
        target.unlink()
    shutil.copy2(str(engine), str(target))
    os.chmod(str(target), 0o755)
    for name in ("install_identity.py", "install_common.py", "IDENTITY.md", "BUILD.identity.json"):
        shutil.copy2(str(bundle / name), str(destination / name))
    (destination / "patches").mkdir(exist_ok=True)
    for path in (bundle / "patches").glob("*.patch"):
        shutil.copy2(str(path), str(destination / "patches" / path.name))
    if (destination / "BUILD.json").exists():
        (destination / "BUILD.json").rename(str(destination / "BUILD.previous.json"))
    build = json.loads((bundle / "BUILD.identity.json").read_text(encoding="utf-8"))
    build["installed_variant"] = mode
    (destination / "BUILD.json").write_text(json.dumps(build, indent=2) + "\n", encoding="utf-8")
    # Avoid leaving the old installer offering an incorrect rollback/version.
    old_installer = destination / "install.py"
    if old_installer.exists():
        old_installer.rename(str(destination / "install.previous.py"))
    result = subprocess.run([str(destination / "opencode"), "--version"], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
    if result.returncode or result.stdout.strip() != "1.19.0":
        raise ValueError("New engine did not start; .bashrc was not changed. Files retained at " + str(destination))
    for name in ("start.sh", "terminal_compat.py", "opencode", "launch.py", "connections.py"):
        if (current / name).exists() and (current / name).read_bytes() != (destination / name).read_bytes():
            raise ValueError("Launcher preservation check failed: " + name)
    command = "bash " + shlex.quote(str(destination / "start.sh"))
    block = BEGIN + "\nalias xunchi-agent-centos7=" + shlex.quote(command) + "\n" + END + "\n"
    state = {"previous_bundle": str(current), "connection_workflow": mode,
             "previous_block": managed_block(content), "installed_block": block}
    (destination / "IDENTITY_INSTALL.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    # Replace the inherited manifest with hashes for the actual upgraded files.
    entries = []
    for path in sorted(destination.rglob("*")):
        if path.name == "FILES.json" or path.is_dir():
            continue
        rel = str(path.relative_to(destination))
        entries.append({"path": rel, "link": os.readlink(str(path))} if path.is_symlink() else
                       {"path": rel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (destination / "FILES.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    verify(destination)
    if bashrc.exists():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(str(bashrc), str(bashrc.with_name(".bashrc.before-xunchi-identity-" + stamp)))
    atomic_write(bashrc, stripped.rstrip("\r\n") + "\n\n" + block)
    print("INSTALLED=" + str(destination))
    print("CONNECTION_WORKFLOW_PRESERVED=" + mode)
    print("Open a new terminal, then run: xunchi-agent-centos7")
    print("Display: XunChi Agent 0.1.1. Existing config, credentials, history and Virtuoso processes were not changed.")
    print("Rollback: python3 " + shlex.quote(str(destination / "install_identity.py")) + " --rollback")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("INSTALL_FAILED: " + str(error), file=sys.stderr)
        sys.exit(2)
