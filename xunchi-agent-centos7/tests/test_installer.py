import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.name == "posix" and os.geteuid() != 0, "Normal Linux user required")
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xunchi-install-test-")
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        self.original = "# existing setup\nalias xunchi-agent-centos7='opencode-centos7'\nopencode-centos7() { echo original; }\n"
        (self.home / ".bashrc").write_text(self.original)
        self.installer = Path(__file__).resolve().parents[1] / "deploy/install.py"
        self.make_bundle("1.19.0")

    def tearDown(self):
        self.temp.cleanup()

    def make_bundle(self, version):
        (self.bundle / "install.py").write_bytes(self.installer.read_bytes())
        engine = self.bundle / "opencode"
        engine.write_text("#!/bin/sh\nprintf '%s\\n' '" + version + "'\n")
        engine.chmod(0o755)
        (self.bundle / "start.sh").write_text("#!/bin/bash\nexit 0\n")
        manifest = [{"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in self.bundle.iterdir() if p.name != "FILES.json"]
        (self.bundle / "FILES.json").write_text(json.dumps(manifest))

    def run_installer(self, *args):
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        return subprocess.run([sys.executable, str(self.bundle / "install.py")] + list(args),
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def test_install_and_rollback_preserve_old_entry(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        bashrc = (self.home / ".bashrc").read_text()
        self.assertIn(self.original.rstrip(), bashrc)
        self.assertIn("# >>> xunchi IC branding managed entry >>>", bashrc)
        self.assertEqual(len(list(self.home.glob(".bashrc.before-xunchi-*"))), 1)
        result = self.run_installer("--rollback")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / ".bashrc").read_text().strip(), self.original.strip())

    def test_version_failure_does_not_change_startup(self):
        self.make_bundle("unexpected")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.home / ".bashrc").read_text(), self.original)

    def test_tamper_is_rejected_before_install(self):
        (self.bundle / "start.sh").write_text("tampered\n")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / ".local").exists())
        self.assertEqual((self.home / ".bashrc").read_text(), self.original)

    def test_existing_destination_is_not_overwritten(self):
        target = self.home / ".local/opt/xunchi-IC-agent-0.1.0-brand.3"
        target.mkdir(parents=True)
        (target / "keep.txt").write_text("preserve")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((target / "keep.txt").read_text(), "preserve")
        self.assertEqual((self.home / ".bashrc").read_text(), self.original)


if __name__ == "__main__":
    unittest.main()
