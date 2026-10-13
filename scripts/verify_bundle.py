#!/usr/bin/env python3
"""Exercise the delivered launcher and config on a Linux build/test host."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile


def verify(archive):
    if os.name != "posix":
        raise SystemExit("Run verification on Linux")
    base = Path(tempfile.mkdtemp(prefix="opencode-handoff-check-"))
    with tarfile.open(str(archive), "r:gz") as source:
        members = source.getmembers()
        for item in members:
            path = Path(item.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Invalid archive path")
            if item.issym() and (Path(item.linkname).is_absolute() or ".." in Path(item.linkname).parts):
                raise ValueError("Invalid archive link")
            if not (item.isfile() or item.isdir() or item.issym()):
                raise ValueError("Unexpected archive member")
        source.extractall(str(base))
    roots = [item for item in base.iterdir() if item.is_dir()]
    if len(roots) != 1:
        raise ValueError("Expected one bundle directory")
    root = roots[0]
    env = dict(os.environ)
    for key, folder in (("HOME", "home"), ("XDG_CONFIG_HOME", "config"),
                        ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache"),
                        ("XDG_STATE_HOME", "state")):
        dest = base / ("test-" + folder)
        dest.mkdir()
        env[key] = str(dest)
    env["OPENCODE_DISABLE_MODELS_FETCH"] = "1"
    env["BAILIAN_BASE_URL"] = "https://example.invalid/compatible-mode/v1"
    env["DASHSCOPE_API_KEY"] = "local-validation-placeholder"
    commands = (("sh", "-n", str(root / "opencode")),
                ("bash", "-n", str(root / "start.sh")),
                ("bash", "-n", str(root / "doctor.sh")),
                ("sha256sum", "-c", "SHA256SUMS"),
                (str(root / "opencode"), "--version"))
    for command in commands:
        result = subprocess.run(command, cwd=str(root), env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
        if result.returncode:
            raise RuntimeError("Check failed: " + str(command) + "\n" + result.stderr)
        if command[-1] == "--version" and result.stdout.strip() != "1.19.0":
            raise ValueError("Unexpected version")
        print("PASS:", " ".join(command), flush=True)
    result = subprocess.run(("bash", str(root / "start.sh"), "debug", "config"),
                            cwd=str(root), env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, timeout=45)
    if result.returncode:
        raise RuntimeError("Configuration check failed: " + result.stderr)
    config = json.loads(result.stdout)
    provider = config["provider"]["bailian"]
    if config["model"] != "bailian/deepseek-v4.1-flash" or provider["options"]["baseURL"] != env["BAILIAN_BASE_URL"]:
        raise ValueError("Configuration did not resolve correctly")
    print("PASS: launch script resolves the portable Bailian config", flush=True)
    print("Linux package verification passed; this is not a CentOS 7 or live LLM acceptance test.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    verify(parser.parse_args().archive)
