#!/usr/bin/env python3
"""Build the handoff bundle from pinned official files (Python 3.6+)."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = (
    "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "sources.lock.json",
    "opencode", "start.sh", "doctor.sh", "config/bailian.json",
    "prompts/check-tools.txt", "docs/TROUBLESHOOTING.md",
    "docs/VALIDATION.md", "docs/RELEASE_NOTES.md", "scripts/build_bundle.py",
    "scripts/verify_bundle.py",
)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def fetch(item, cache):
    target = cache / item["url"].rsplit("/", 1)[1]
    if target.is_file() and digest(target) == item["sha256"]:
        return target
    print("Download:", item["name"], item["version"], flush=True)
    request = urllib.request.Request(item["url"], headers={"User-Agent": "opencode-centos7-kit"})
    temp = target.with_name(target.name + ".partial")
    with urllib.request.urlopen(request, timeout=120) as response, temp.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    if digest(temp) != item["sha256"]:
        raise ValueError("SHA256 mismatch for " + item["name"])
    os.replace(str(temp), str(target))
    return target


def build(output):
    lock = json.loads((ROOT / "sources.lock.json").read_text(encoding="utf-8"))
    version = lock["upstream_version"]
    revision = lock["package_revision"]
    folder = "opencode-centos7-" + version + "-" + revision
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in PAYLOAD:
        files[name] = (ROOT / name).read_bytes()
    for path in sorted((ROOT / "licenses").glob("*.txt")):
        files["licenses/" + path.name] = path.read_bytes()
    if len([name for name in files if name.startswith("licenses/")]) != 4:
        raise ValueError("All four third-party license files must be present")
    for item in lock["sources"]:
        path = fetch(item, cache)
        with tarfile.open(str(path), mode="r:gz") as archive:
            names = ["opencode"] if item["name"] == "opencode" else item["files"]
            for name in names:
                candidates = [entry for entry in archive.getmembers()
                              if entry.isfile() and (entry.name == name or Path(entry.name).name == name)]
                if len(candidates) != 1:
                    raise ValueError("Expected exactly one payload file: " + name)
                prefix = "bin/" if item["name"] == "opencode" else "runtime/"
                files[prefix + Path(name).name] = archive.extractfile(candidates[0]).read()
    sources = {
        "upstream_version": version, "package_revision": revision,
        "binary_modified": False, "sources": lock["sources"],
        "validation_record": "docs/VALIDATION.md",
        "publication_scope": "No user credentials, workspace endpoint, sessions, EDA software or designs",
    }
    files["SOURCES.json"] = (json.dumps(sources, indent=2) + "\n").encode("utf-8")
    sums = "".join(hashlib.sha256(body).hexdigest() + "  " + name + "\n"
                   for name, body in sorted(files.items()))
    files["SHA256SUMS"] = sums.encode("utf-8")
    target = output / (folder + ".tar.gz")
    timestamp = int(time.time())
    with tarfile.open(str(target), "w:gz", compresslevel=6) as archive:
        for name, body in sorted(files.items()):
            info = tarfile.TarInfo(folder + "/" + name)
            info.mode = 0o755 if name in ("opencode", "start.sh", "doctor.sh") or name.startswith(("bin/", "runtime/")) else 0o644
            info.mtime = timestamp
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
        for name, link in (("libc.musl-x86_64.so.1", "ld-musl-x86_64.so.1"),
                           ("libstdc++.so.6", "libstdc++.so.6.0.33")):
            info = tarfile.TarInfo(folder + "/runtime/" + name)
            info.type = tarfile.SYMTYPE
            info.linkname = link
            info.mode = 0o777
            info.mtime = timestamp
            archive.addfile(info)
    checksum = digest(target)
    (output / (target.name + ".sha256")).write_text(checksum + "  " + target.name + "\n", encoding="utf-8")
    print(json.dumps({"archive": str(target), "bytes": target.stat().st_size,
                      "sha256": checksum, "payload_files": len(files)}, indent=2))
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    build(args.output)
