#!/usr/bin/env python3
"""Package an engine-only identity upgrade, with no provider configuration."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
FOLDER = "xunchi-agent-0.1.1-identity.1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engines", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--licenses-from", type=Path,
                        help="Verified compatibility archive providing dependency license notices")
    parser.add_argument("--base-sha256",
                        help="Expected SHA256 of --licenses-from; required when that option is used")
    args = parser.parse_args()
    record = json.loads(args.record.read_text(encoding="utf-8"))
    payload = {}
    base = args.licenses_from or ROOT / "dist/xunchi-IC-agent-0.1.0-brand.3.tar.gz"
    expected = args.base_sha256 if args.licenses_from else "8cbcd4ec7cb8501c7b603fc15a9fb25ac8ab4e01badaefbe681deb521c733a09"
    if not expected or hashlib.sha256(base.read_bytes()).hexdigest() != expected.lower():
        raise ValueError("License reference package checksum mismatch")
    with tarfile.open(str(base), "r:gz") as archive:
        for item in archive.getmembers():
            name = item.name.split("/", 1)[-1]
            if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
                raise ValueError("Unsafe license archive path")
            if item.isfile() and name.startswith("licenses/"):
                payload[name] = archive.extractfile(item).read()
    for mode in ("legacy", "managed"):
        body = (args.engines / mode).read_bytes()
        if body[:4] != b"\x7fELF" or body[18:20] != b"\x3e\x00" or b"ld-musl-x86_64.so.1" not in body:
            raise ValueError("Expected a Linux x64 musl engine")
        if hashlib.sha256(body).hexdigest() != record["engines"][mode]:
            raise ValueError("Engine does not match the build record")
        payload["engines/" + mode] = body
    payload["install_identity.py"] = (ROOT / "deploy/install_identity.py").read_bytes()
    payload["install_common.py"] = (ROOT / "deploy/install.py").read_bytes()
    payload["IDENTITY.md"] = (ROOT / "docs/IDENTITY.md").read_bytes()
    payload["BUILD.identity.json"] = args.record.read_bytes()
    payload["licenses/OpenCode-LICENSE.txt"] = (ROOT / "licenses/OpenCode-LICENSE.txt").read_bytes()
    payload["THIRD_PARTY_NOTICES.md"] = ("# XunChi Agent identity upgrade\n\n"
        "This archive contains modified OpenCode 1.19.0 Linux x64 musl engines, source patches, and upgrade scripts. "
        "Upstream OpenCode copyright and MIT terms are retained in licenses/. "
        "Dependency notices from the compatibility reference package are retained. "
        "The installer reuses the existing installation's runtime libraries and license files. "
        "Product branding does not grant trademark rights. See BUILD.identity.json for source provenance.\n").encode()
    for name in ("0002-xunchi-home-branding.patch", "0003-select-musl-build.patch", "0004-xunchi-terminal-identity.patch", "0005-xunchi-connections.patch", "0006-xunchi-product-identity.patch"):
        payload["patches/" + name] = (ROOT / "patches" / name).read_bytes()
    payload["FILES.json"] = (json.dumps([{"path": name, "sha256": hashlib.sha256(body).hexdigest()} for name, body in sorted(payload.items())], indent=2) + "\n").encode()
    target = ROOT / "dist" / (FOLDER + ".tar.gz")
    with tarfile.open(str(target), "w:gz") as archive:
        for name, body in sorted(payload.items()):
            item = tarfile.TarInfo(FOLDER + "/" + name)
            item.size, item.mtime = len(body), int(time.time())
            item.mode = 0o755 if name.startswith("engines/") else 0o644
            archive.addfile(item, io.BytesIO(body))
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_name(target.name + ".sha256").write_text(checksum + "  " + target.name + "\n", encoding="utf-8")
    print(json.dumps({"file": str(target), "bytes": target.stat().st_size, "sha256": checksum}, indent=2))


if __name__ == "__main__":
    main()
