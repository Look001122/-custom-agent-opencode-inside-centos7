import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.name == "posix" and os.geteuid() != 0, "Normal Linux user required")
class IdentityUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xunchi-identity-install-")
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.old = self.home / ".local/opt/old version"
        (self.old / "bin").mkdir(parents=True)
        (self.old / "opencode").write_text('#!/bin/sh\nexec "$(dirname "$0")/bin/opencode" "$@"\n')
        (self.old / "opencode").chmod(0o755)
        (self.old / "terminal_compat.py").write_text("# previous transport\n")
        (self.old / "bin/opencode").write_text("previous engine\n")
        self.bundle = self.root / "bundle"
        (self.bundle / "engines").mkdir(parents=True)
        project = Path(__file__).resolve().parents[1]
        (self.bundle / "install_identity.py").write_bytes((project / "deploy/install_identity.py").read_bytes())
        (self.bundle / "install_common.py").write_bytes((project / "deploy/install.py").read_bytes())
        for name in ("IDENTITY.md", "BUILD.identity.json"):
            (self.bundle / name).write_text("{}\n")
        for mode in ("legacy", "managed"):
            p = self.bundle / "engines" / mode
            p.write_text("#!/bin/sh\n# " + mode + "\necho 1.19.0\n")
            p.chmod(0o755)
        self.original = "# company environment\nalias opencode-centos7='old-command'\n\n" + "# >>> xunchi IC branding managed entry >>>\nalias xunchi-agent-centos7=" + shlex.quote("bash " + shlex.quote(str(self.old / "start.sh"))) + "\n# <<< xunchi IC branding managed entry <<<\n"
        (self.home / ".bashrc").write_text(self.original)
        self.dest = self.home / ".local/opt/xunchi-agent-0.1.1-identity.1"
        self.config = self.home / "opencode-bailian-v1.json"
        self.config.write_text('{"model":"keep-existing"}\n')
        self.set_mode("legacy")

    def tearDown(self):
        self.temp.cleanup()

    def set_mode(self, mode):
        if mode == "managed":
            (self.old / "start.sh").write_text('#!/bin/bash\nROOT=original\nexec python3 "$ROOT/launch.py"\n')
            for name in ("launch.py", "connections.py"):
                (self.old / name).write_text("# keep existing " + name + "\n")
        else:
            (self.old / "start.sh").write_text('#!/bin/bash\n# preserve OPENCODE_CONFIG\nexec "$ROOT/opencode"\n')
        manifest = [{"path": str(p.relative_to(self.bundle)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in self.bundle.rglob("*") if p.is_file() and p.name != "FILES.json"]
        (self.bundle / "FILES.json").write_text(json.dumps(manifest))

    def install(self, *args, installed=False):
        script = (self.dest if installed else self.bundle) / "install_identity.py"
        return subprocess.run([sys.executable, str(script)] + list(args), env=dict(os.environ, HOME=str(self.home)),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def test_legacy_launch_bytes_and_config_preserved_and_rollback(self):
        before = {name: (self.old / name).read_bytes() for name in ("opencode", "start.sh", "terminal_compat.py", "bin/opencode")}
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name, body in before.items():
            self.assertEqual((self.old / name).read_bytes(), body)
            if name != "bin/opencode":
                self.assertEqual((self.dest / name).read_bytes(), body)
        self.assertEqual(self.config.read_text(), '{"model":"keep-existing"}\n')
        self.assertIn("# legacy", (self.dest / "bin/opencode").read_text())
        self.assertIn("alias opencode-centos7='old-command'", (self.home / ".bashrc").read_text())
        result = self.install("--rollback", installed=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / ".bashrc").read_text().strip(), self.original.strip())

    def test_managed_launch_and_backend_are_preserved(self):
        self.set_mode("managed")
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# managed", (self.dest / "bin/opencode").read_text())
        for name in ("launch.py", "connections.py", "start.sh"):
            self.assertEqual((self.old / name).read_bytes(), (self.dest / name).read_bytes())

    def test_bad_active_entry_does_not_mutate_shell(self):
        original = "alias xunchi-agent-centos7='unknown-wrapper'\n"
        (self.home / ".bashrc").write_text(original)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.dest.exists())
        self.assertEqual((self.home / ".bashrc").read_text(), original)

    def test_tampered_package_is_rejected(self):
        (self.bundle / "engines/legacy").write_text("tampered")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.dest.exists())
        self.assertEqual((self.home / ".bashrc").read_text(), self.original)

    def test_rollback_does_not_replace_newer_entry(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        newer = (self.home / ".bashrc").read_text().replace("0.1.1-identity.1", "newer")
        (self.home / ".bashrc").write_text(newer)
        result = self.install("--rollback", installed=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.home / ".bashrc").read_text(), newer)


if __name__ == "__main__":
    unittest.main()
