#!/usr/bin/env python3
"""Apply the branding patch to a fixed upstream source and select musl only."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    lock = json.loads((ROOT / "upstream.lock.json").read_text(encoding="utf-8"))
    version = json.loads((source / "packages/opencode/package.json").read_text())["version"]
    if version != "1.19.0":
        raise SystemExit("Expected upstream 1.19.0")
    patch = ROOT / "patches/0002-xunchi-home-branding.patch"
    check = subprocess.run(["git", "-C", str(source), "apply", "--check", str(patch)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check.returncode == 0:
        subprocess.check_call(["git", "-C", str(source), "apply", str(patch)])
    else:
        subprocess.check_call(["git", "-C", str(source), "apply", "--reverse", "--check", str(patch)])
    identity = ROOT / "patches/0004-xunchi-terminal-identity.patch"
    check = subprocess.run(["git", "-C", str(source), "apply", "--check", str(identity)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check.returncode == 0:
        subprocess.check_call(["git", "-C", str(source), "apply", str(identity)])
    else:
        subprocess.check_call(["git", "-C", str(source), "apply", "--reverse", "--check", str(identity)])
    connections = ROOT / "patches/0005-xunchi-connections.patch"
    check = subprocess.run(["git", "-C", str(source), "apply", "--check", str(connections)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check.returncode == 0:
        subprocess.check_call(["git", "-C", str(source), "apply", str(connections)])
    else:
        subprocess.check_call(["git", "-C", str(source), "apply", "--reverse", "--check", str(connections)])
    build = source / "packages/opencode/script/build.ts"
    before = build.read_text(encoding="utf-8")
    start = "const targets = singleFlag"
    replacement = '''const targets = process.env.XUNCHI_BUILD_TARGET === "linux-x64-musl"
  ? allTargets.filter((item) => item.os === "linux" && item.arch === "x64" && item.abi === "musl" && item.avx2 !== false)
  : singleFlag'''
    if start in before:
        after = before.replace(start, replacement, 1)
        with build.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(after)
        diff = "diff --git a/packages/opencode/script/build.ts b/packages/opencode/script/build.ts\n"
        diff += "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile="a/packages/opencode/script/build.ts", tofile="b/packages/opencode/script/build.ts"))
        with (ROOT / "patches/0003-select-musl-build.patch").open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(diff)
    elif replacement not in before:
        raise SystemExit("Build selector does not match the pinned source")
    record = {
        "upstream_commit": lock["commit"], "upstream_version": version,
        "branding_patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
        "terminal_identity_patch_sha256": hashlib.sha256(identity.read_bytes()).hexdigest(),
        "connections_patch_sha256": hashlib.sha256(connections.read_bytes()).hexdigest(),
        "target": "linux-x64-musl", "clipboard_patch_applied": False,
        "note": "Homepage, terminal identity and connection manager; legacy terminal transport supplied by launcher",
    }
    (source / "XUNCHI_SOURCE.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("Branding applied. Explicit linux-x64-musl build selector prepared.")


if __name__ == "__main__":
    main()
