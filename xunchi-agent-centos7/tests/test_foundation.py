import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import jobs
import xunchi


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xunchi-tests-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def profile(self, code, **extra):
        action = {"argv": [sys.executable, "-c", code], "timeout_seconds": 10,
                  "validation": "process", "mutates_design": False}
        action.update(extra)
        return {"schema_version": 1, "engine": {"launcher": sys.executable, "config": str(self.root / "config.json")},
                "project": {"root": str(self.root), "target": {"library": "TEST", "cell": "TEST", "view": "layout"}},
                "actions": {"check": action}, "job_store": str(self.root / "jobs")}

    def wait(self, result):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            state = jobs.poll(result["job_directory"])
            if state["state"] not in ("queued", "running"):
                return state
            time.sleep(0.05)
        self.fail("worker did not finish")

    def test_profile_schema_rejected(self):
        file = self.root / "profile.json"
        file.write_text('{"schema_version": 2}')
        with self.assertRaises(ValueError):
            xunchi.load_profile(str(file))

    def test_doctor_does_not_echo_credentials_or_claim_eda_acceptance(self):
        profile = self.profile("pass")
        profile["engine"]["required_env"] = ["DASHSCOPE_API_KEY"]
        with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-secret-value"}):
            result = xunchi.doctor(profile)
        self.assertNotIn("test-secret-value", json.dumps(result))
        self.assertEqual(result["eda_acceptance"], "not_tested")

    @unittest.skipUnless(os.name == "posix", "Linux process test")
    def test_launcher_preserves_arguments_cwd_and_isolates_engine_libraries(self):
        profile = self.profile("pass")
        Path(profile["engine"]["config"]).write_text("{}")
        cwd = os.getcwd()
        with mock.patch.dict(os.environ, {"LD_LIBRARY_PATH": "cadence-only", "LD_PRELOAD": "cadence-only"}):
            with mock.patch("os.execve") as execute:
                xunchi.launch(profile, ["-c", "directory with spaces"])
            argv = execute.call_args[0][1]
            env = execute.call_args[0][2]
            self.assertNotIn("LD_LIBRARY_PATH", env)
            self.assertNotIn("LD_PRELOAD", env)
            self.assertEqual(os.environ["LD_LIBRARY_PATH"], "cadence-only")
        self.assertEqual(argv[1:], ["-c", "directory with spaces"])
        self.assertEqual(os.getcwd(), cwd)

    @unittest.skipUnless(os.name == "posix", "Linux process test")
    def test_detached_job_writes_durable_log_in_unique_directory(self):
        profile = self.profile('print("中文执行记录")')
        first, second = jobs.submit(profile, "check"), jobs.submit(profile, "check")
        for result in (first, second):
            status = self.wait(result)
            self.assertEqual(status["state"], "completed")
            self.assertEqual(status["returncode"], 0)
            log = Path(result["job_directory"]) / "process.log"
            self.assertIn("中文执行记录", log.read_text(encoding="utf-8"))
            self.assertEqual(status["project"]["target"]["library"], "TEST")
            self.assertEqual(status["design_modified"], "not_verified")
        self.assertNotEqual(first["job_directory"], second["job_directory"])

    @unittest.skipUnless(os.name == "posix", "Linux process test")
    def test_lvs_incorrect_is_not_pass_even_with_exit_zero(self):
        code = 'open("lvs.report", "w").write("OVERALL COMPARISON RESULTS\\n# INCORRECT #\\n")'
        result = jobs.submit(self.profile(code, validation="lvs"), "check")
        status = self.wait(result)
        self.assertEqual(status["returncode"], 0)
        self.assertEqual(status["validation"], "incorrect")
        self.assertEqual(len(status["report"]["sha256"]), 64)

    @unittest.skipUnless(os.name == "posix", "Linux process test")
    def test_failed_execution_cannot_pass_using_correct_report(self):
        code = 'open("lvs.report", "w").write("OVERALL COMPARISON RESULTS\\n# CORRECT #\\n"); raise SystemExit(9)'
        status = self.wait(jobs.submit(self.profile(code, validation="lvs"), "check"))
        self.assertEqual(status["state"], "failed")
        self.assertEqual(status["returncode"], 9)
        self.assertEqual(status["validation"], "unknown")

    @unittest.skipUnless(os.name == "posix", "Linux process test")
    def test_timeout_has_explicit_state(self):
        profile = self.profile('import time; time.sleep(20)', timeout_seconds=1)
        status = self.wait(jobs.submit(profile, "check"))
        self.assertEqual(status["state"], "timed_out")
        self.assertNotEqual(status["returncode"], 0)

    @unittest.skipUnless(os.name == "posix", "Linux process test")
    def test_eda_environment_script_is_applied_only_in_job(self):
        script = self.root / "environment with spaces.sh"
        script.write_text('export XUNCHI_TEST_EDA_VALUE="eda child"\n')
        profile = self.profile('import os; print(os.environ["XUNCHI_TEST_EDA_VALUE"])')
        profile["eda_environment_script"] = str(script)
        result = jobs.submit(profile, "check")
        self.assertEqual(self.wait(result)["state"], "completed")
        self.assertIn("eda child", (Path(result["job_directory"]) / "process.log").read_text())
        self.assertNotIn("XUNCHI_TEST_EDA_VALUE", os.environ)

    @unittest.skipUnless(os.name == "posix", "Linux process test")
    def test_design_mutation_is_not_supported_in_first_runner(self):
        profile = self.profile("pass", mutates_design=True)
        with self.assertRaises(ValueError):
            jobs.submit(profile, "check")

    def test_report_without_overall_section_is_unknown(self):
        report = self.root / "sample.report"
        report.write_text("CELL COMPARISON RESULTS\nCORRECT\n")
        self.assertEqual(jobs.lvs_result(str(report)), "unknown")

    @unittest.skipUnless(os.name == "posix", "Linux process test")
    def test_engine_credentials_are_not_forwarded_to_eda_worker(self):
        profile = self.profile('import os; print("key-present=" + str("DASHSCOPE_API_KEY" in os.environ))')
        profile["engine"]["required_env"] = ["DASHSCOPE_API_KEY"]
        with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "secret-test-value"}):
            result = jobs.submit(profile, "check")
        self.assertEqual(self.wait(result)["state"], "completed")
        self.assertIn("key-present=False", (Path(result["job_directory"]) / "process.log").read_text())

    @unittest.skipUnless(os.name == "posix", "Linux process test")
    def test_disappeared_worker_is_unknown_not_claimed_rollback(self):
        jobs.save(str(self.root / "status.json"), {"state": "running"})
        jobs.save(str(self.root / "worker.json"), {"pid": 99999999})
        self.assertEqual(jobs.poll(str(self.root))["state"], "unknown")

    @unittest.skipUnless(os.name == "posix", "Linux process test")
    def test_worker_survives_submitting_cli_exit_and_other_cli_can_query(self):
        profile = self.profile('import time; time.sleep(0.3); print("finished after client exit")')
        filename = self.root / "deployment.json"
        filename.write_text(json.dumps(profile))
        entry = str(Path(xunchi.__file__))
        output = subprocess.check_output([sys.executable, entry, "--profile", str(filename), "--run", "check"])
        result = json.loads(output.decode("utf-8"))
        self.assertEqual(self.wait(result)["state"], "completed")
        output = subprocess.check_output([sys.executable, entry, "--job", result["job_directory"]])
        self.assertEqual(json.loads(output.decode("utf-8"))["state"], "completed")

    def test_overall_correct_report(self):
        report = self.root / "sample.report"
        report.write_text("OVERALL COMPARISON RESULTS\n# CORRECT #\nCELL COMPARISON RESULTS\n")
        self.assertEqual(jobs.lvs_result(str(report)), "correct")


if __name__ == "__main__":
    unittest.main()
