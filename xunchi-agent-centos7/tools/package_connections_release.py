#!/usr/bin/env python3
"""Package a built musl engine with the previously verified compatibility runtime."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
# Local r1 archive, checked against its internal SHA256SUMS and source lock.
BASE_SHA = "22c756206202ee515f7203f707fd9fbc7b4e3349595714468946ebfd2ef263b0"
FOLDER = "xunchi-IC-agent-0.2.0-connections.1"


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--base-sha256", default=BASE_SHA,
                        help="Expected hash of a verified compatibility archive")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--build-record", type=Path, required=True)
    args = parser.parse_args()
    if sha(args.base) != args.base_sha256.lower():
        raise ValueError("Compatibility base package SHA mismatch")
    record = json.loads(args.build_record.read_text(encoding="utf-8"))
    if record.get("engine_sha256") != sha(args.engine) or record.get("release") != "0.2.0-connections.1":
        raise ValueError("Record this engine and release before packaging")
    engine = args.engine.read_bytes()
    if engine[:4] != b"\x7fELF" or engine[18:20] != b"\x3e\x00" or b"ld-musl-x86_64.so.1" not in engine:
        raise ValueError("Expected a Linux x64 musl ELF engine")
    if b"xunchi-IC-agent" not in engine:
        raise ValueError("Brand string is absent from the compiled engine")
    payload, links = {}, {}
    with tarfile.open(args.base, "r:gz") as archive:
        for item in archive.getmembers():
            name = item.name.split("/", 1)[-1]
            if name.startswith(("runtime/", "licenses/")) or name in ("opencode", "THIRD_PARTY_NOTICES.md", "sources.lock.json"):
                if item.issym():
                    links[name] = item.linkname
                elif item.isfile():
                    payload[name] = archive.extractfile(item).read()
    payload["bin/opencode"] = engine
    payload["start.sh"] = (ROOT / "deploy/start-connections.sh").read_bytes()
    payload["install.py"] = (ROOT / "deploy/install-connections.py").read_bytes()
    payload["terminal_compat.py"] = (ROOT / "deploy/terminal_compat.py").read_bytes()
    payload["connections.py"] = (ROOT / "deploy/connections.py").read_bytes()
    payload["launch.py"] = (ROOT / "deploy/launch.py").read_bytes()
    payload["company-logo.reference.png"] = (ROOT / "assets/company-logo.reference.png").read_bytes()
    payload["BUILD.json"] = args.build_record.read_bytes()
    payload["INSTALL.md"] = (ROOT / "docs/INSTALL_CONNECTIONS.md").read_bytes()
    payload["TERMINAL_COMPAT.md"] = (ROOT / "docs/TERMINAL_COMPAT.md").read_bytes()
    payload["CONNECTIONS.md"] = (ROOT / "docs/CONNECTIONS.md").read_bytes()
    payload["patches/0002-xunchi-home-branding.patch"] = (ROOT / "patches/0002-xunchi-home-branding.patch").read_bytes()
    payload["patches/0003-select-musl-build.patch"] = (ROOT / "patches/0003-select-musl-build.patch").read_bytes()
    payload["patches/0004-xunchi-terminal-identity.patch"] = (ROOT / "patches/0004-xunchi-terminal-identity.patch").read_bytes()
    payload["patches/0005-xunchi-connections.patch"] = (ROOT / "patches/0005-xunchi-connections.patch").read_bytes()
    payload["THIRD_PARTY_NOTICES.md"] = payload["THIRD_PARTY_NOTICES.md"].replace(b"\r\n", b"\n").replace(
        b"This kit keeps the upstream executable and runtime libraries unmodified.\nThe repository's MIT license covers the added scripts and documentation;\neach third-party component retains its upstream license.",
        b"This internal package contains a modified OpenCode executable and unmodified runtime libraries.\nEach third-party component retains its upstream license.\nCompany branding assets and new company code are not automatically covered by an open-source license."
    )
    payload["THIRD_PARTY_NOTICES.md"] += b"\nThis internal branding build modifies OpenCode homepage, terminal title and exit summary source.\nUpstream version: 1.19.0. Source commit and modifications: BUILD.json and patches/.\nCompany branding assets are not granted an open-source license by this package.\n"
    manifest = [{"path": name, "sha256": hashlib.sha256(body).hexdigest()} for name, body in sorted(payload.items())]
    manifest += [{"path": name, "link": target} for name, target in sorted(links.items())]
    payload["FILES.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / (FOLDER + ".tar.gz")
    with tarfile.open(target, "w:gz") as archive:
        for name, body in sorted(payload.items()):
            item = tarfile.TarInfo(FOLDER + "/" + name)
            item.size, item.mtime = len(body), int(time.time())
            item.mode = 0o755 if name in ("opencode", "start.sh") or name.startswith(("bin/", "runtime/")) else 0o644
            archive.addfile(item, io.BytesIO(body))
        for name, link in sorted(links.items()):
            item = tarfile.TarInfo(FOLDER + "/" + name)
            item.type, item.linkname, item.mode = tarfile.SYMTYPE, link, 0o777
            archive.addfile(item)
    checksum = sha(target)
    (target.parent / (target.name + ".sha256")).write_text(checksum + "  " + target.name + "\n", encoding="utf-8")
    print(json.dumps({"archive": str(target), "sha256": checksum, "bytes": target.stat().st_size}, indent=2))


if __name__ == "__main__":
    main()
