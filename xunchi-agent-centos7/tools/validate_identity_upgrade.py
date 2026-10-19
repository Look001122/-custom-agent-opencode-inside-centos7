#!/usr/bin/env python3
"""Install the final shared archive over each real prior package in isolated HOME."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("shared", type=Path)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    results = []
    for mode, old_name in (("legacy", "xunchi-IC-agent-0.1.0-brand.3"),
                           ("managed", "xunchi-IC-agent-0.2.0-connections.1")):
        root = Path(tempfile.mkdtemp(prefix="identity-final-" + mode + "-", dir=str(args.work)))
        home = root / "home"
        old_parent = home / ".local/opt"
        old_parent.mkdir(parents=True)
        with tarfile.open(str(ROOT / "dist" / (old_name + ".tar.gz"))) as archive:
            archive.extractall(str(old_parent))
        old = old_parent / old_name
        original = "# original shell settings\nalias opencode-centos7='original-command'\n\n# >>> xunchi IC branding managed entry >>>\nalias xunchi-agent-centos7=" + shlex.quote("bash " + shlex.quote(str(old / "start.sh"))) + "\n# <<< xunchi IC branding managed entry <<<\n"
        (home / ".bashrc").write_text(original)
        config = home / "opencode-bailian-v1.json"
        config.write_text('{"model":"preserve-existing-config"}\n')
        config_before = config.read_bytes()
        env = dict(os.environ, HOME=str(home))
        command = ["bash", str(args.shared / "install-xunchi-identity.sh")]
        installed = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   universal_newlines=True, timeout=120)
        (root / "install.out").write_text(installed.stdout + installed.stderr)
        assert installed.returncode == 0, installed.stdout + installed.stderr
        destination = old_parent / "xunchi-agent-0.1.1-identity.1"
        state = json.loads((destination / "IDENTITY_INSTALL.json").read_text())
        assert state["connection_workflow"] == mode
        assert (destination / "start.sh").read_bytes() == (old / "start.sh").read_bytes()
        assert config.read_bytes() == config_before
        (root / "bundle").symlink_to(destination, target_is_directory=True)
        result = subprocess.run([sys.executable, str(ROOT / "tools/inspect_identity_release.py"), str(root), "--mode", mode],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=180)
        (root / "acceptance.out").write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        assert config.read_bytes() == config_before
        rolled = subprocess.run([sys.executable, str(destination / "install_identity.py"), "--rollback"], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
        assert rolled.returncode == 0, rolled.stderr
        assert (home / ".bashrc").read_text().strip() == original.strip()
        results.append({"mode": mode, "work_directory": str(root), "install_rc": installed.returncode,
                        "rollback_rc": rolled.returncode, "old_launcher_bytes_preserved": True,
                        "existing_config_unchanged": True, "real_user_home_modified": False,
                        "selected_engine_sha256": hashlib.sha256((destination / "bin/opencode").read_bytes()).hexdigest(),
                        "installed_engine_acceptance": json.loads((root / "result.json").read_text())})
    record = {"environment": "WSL Ubuntu; CentOS target pending", "variants": results}
    (args.shared / "INSTALL_WSL_RESULT.identity.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
