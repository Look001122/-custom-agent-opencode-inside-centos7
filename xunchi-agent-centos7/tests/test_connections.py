import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
if os.name == "posix":
    spec = importlib.util.spec_from_file_location("connections", str(DEPLOY / "connections.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


@unittest.skipUnless(os.name == "posix", "Linux deployment required")
class ConnectionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xunchi-connections-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = module.Store(self.root / "config", self.root / "session")
        self.store.migrate()
        self.calls = []
        self.failure = 0
        self.bad_tool = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def response(self, body):
                if owner.failure:
                    self.send_response(owner.failure)
                    if owner.failure == 302:
                        self.send_header("Location", "http://127.0.0.1:1/do-not-follow")
                    self.end_headers()
                    self.wfile.write(b"untrusted error body must not be displayed")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def do_GET(self):
                owner.calls.append((self.path, dict(self.headers), None))
                self.response({"data": [{"id": "model-A"}, {"id": "model-B"}]})

            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.calls.append((self.path, dict(self.headers), request))
                name = "unexpected_tool" if owner.bad_tool else "xunchi_probe"
                if self.path.endswith("/chat/completions"):
                    message = {"content": "OK"}
                    if request.get("tools"):
                        message = {"tool_calls": [{"function": {"name": name, "arguments": '{"marker":"ok"}'}}]}
                    self.response({"choices": [{"message": message}]})
                elif self.path.endswith("/messages"):
                    self.response({"content": [{"type": "tool_use", "name": name, "input": {"marker": "ok"}}] if request.get("tools") else [{"type": "text", "text": "OK"}]})
                else:
                    self.response({"output": [{"type": "function_call", "name": name, "arguments": '{"marker":"ok"}'}] if request.get("tools") else [{"content": [{"type": "output_text", "text": "OK"}]}]})

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = "http://127.0.0.1:%s/v1" % self.server.server_port

    def save(self, **changes):
        request = {"name": "我的服务", "protocol": "chat", "baseURL": self.url,
                   "model": "model-A", "models": ["model-A"], "credential_mode": "saved",
                   "key": "fake-test-secret-not-real"}
        request.update(changes)
        return self.store.action("save", request)

    def test_saved_key_private_separate_and_restart_restores_default(self):
        state = self.save(default=True)
        ident = state["active"]
        self.assertNotIn("fake-test-secret-not-real", json.dumps(state))
        self.assertNotIn("fake-test-secret-not-real", self.store.path.read_text())
        self.assertNotIn("fake-test-secret-not-real", self.store.runtime.read_text())
        self.assertEqual(self.store.keys_path.stat().st_mode & 0o777, 0o600)
        other = module.Store(self.store.home, self.root / "restart")
        self.assertEqual(other.action("initialize", {})["active"], ident)
        self.assertEqual(other.key(other.load()["profiles"][0]), "fake-test-secret-not-real")

    def test_session_key_expires_and_no_key_service_is_supported(self):
        state = self.save(credential_mode="session")
        self.assertTrue(state["profiles"][0]["ready"])
        other = module.Store(self.store.home, self.root / "restart")
        self.assertFalse(other.state()["profiles"][0]["ready"])
        state = self.save(name="本机服务", key="", credential_mode="none")
        self.assertTrue(next(p for p in state["profiles"] if p["id"] == state["active"])["ready"])

    def test_switch_and_default_are_distinct_and_delete_removes_credentials(self):
        first = self.save(default=True)["active"]
        second = self.save(name="第二连接")["active"]
        self.assertEqual(self.store.state()["default"], first)
        self.store.action("select", {"id": first})
        self.assertEqual(self.store.state()["active"], first)
        self.store.action("default", {"id": second})
        self.store.action("delete", {"id": second})
        self.assertNotIn(second, self.store.keys_path.read_text())
        self.assertFalse((self.store.session / (second + ".key")).exists())
        self.assertEqual(self.store.state()["active"], first)

    def test_legacy_env_migration_does_not_require_key_or_change_source(self):
        base = {"provider": {"bailian": {"npm": "@ai-sdk/openai-compatible", "options": {"baseURL": self.url, "apiKey": "{env:XUNCHI_TEST_MISSING_ENV}"}, "models": {"model-A": {"name": "old"}}}}, "model": "bailian/model-A", "mcp": {"local": {"enabled": False}}}
        store = module.Store(self.root / "legacy", self.root / "legacy-session", base)
        result = store.action("initialize", {})
        self.assertFalse(result["profiles"][0]["ready"])
        self.assertEqual(json.loads(store.runtime.read_text())["enabled_providers"], [])
        self.assertEqual(base["provider"]["bailian"]["options"]["apiKey"], "{env:XUNCHI_TEST_MISSING_ENV}")
        self.assertIn("mcp", json.loads(store.runtime.read_text()))

    def test_protocol_model_listing_chat_and_structured_tool_validation(self):
        for protocol in ("chat", "responses", "anthropic"):
            ident = self.save(protocol=protocol)["active"]
            self.assertEqual(self.store.action("models", {"id": ident})["models"], ["model-A", "model-B"])
            self.assertTrue(self.store.action("test", {"id": ident, "kind": "chat"})["passed"])
            self.assertTrue(self.store.action("test", {"id": ident, "kind": "tools"})["passed"])
            self.bad_tool = True
            self.assertFalse(self.store.action("test", {"id": ident, "kind": "tools"})["passed"])
            self.bad_tool = False
        self.assertEqual(len(self.calls), 12)

    def test_auth_errors_and_redirects_do_not_display_remote_body(self):
        ident = self.save()["active"]
        for status in (401, 403, 404, 429, 500, 302):
            self.failure = status
            with self.assertRaises(module.ConnectionError) as caught:
                self.store.action("test", {"id": ident})
            self.assertNotIn("untrusted", str(caught.exception))
            self.assertNotIn("fake-test-secret-not-real", str(caught.exception))

    def test_invalid_edit_is_atomic_and_rejects_key_in_url(self):
        ident = self.save()["active"]
        before = self.store.path.read_bytes(), self.store.keys_path.read_bytes()
        with self.assertRaises(module.ConnectionError):
            self.save(id=ident, baseURL="https://user:secret@example.test/v1")
        self.assertEqual((self.store.path.read_bytes(), self.store.keys_path.read_bytes()), before)

    def test_launcher_never_prompts_and_cleans_runtime_credentials(self):
        home = self.root / "launch-home"
        home.mkdir()
        engine = self.root / "engine"
        engine.mkdir()
        for name in ("connections.py", "launch.py"):
            (engine / name).write_bytes((DEPLOY / name).read_bytes())
        result_path = self.root / "launch-result.json"
        program = engine / "opencode"
        program.write_text('#!/usr/bin/python3\nimport json, os, sys\nfrom pathlib import Path\np=Path(os.environ["OPENCODE_CONFIG"])\nPath(os.environ["TEST_RESULT"]).write_text(json.dumps({"runtime":str(p),"args":sys.argv[1:],"cwd":os.getcwd(),"config":json.loads(p.read_text())}))\nsys.exit(7)\n')
        program.chmod(0o755)
        env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), XDG_CACHE_HOME=str(home / "cache"), TEST_RESULT=str(result_path))
        for name in ("OPENCODE_CONFIG", "DASHSCOPE_API_KEY"):
            env.pop(name, None)
        process = subprocess.run([sys.executable, str(engine / "launch.py"), str(engine), "-c"], cwd=str(home), env=env, input=b"", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(process.returncode, 7, process.stderr)
        self.assertNotIn(b"API Key:", process.stdout + process.stderr)
        info = json.loads(result_path.read_text())
        self.assertEqual(info["args"], ["-c"])
        self.assertEqual(info["cwd"], str(home))
        self.assertEqual(info["config"]["enabled_providers"], [])
        self.assertFalse(Path(info["runtime"]).exists())


if __name__ == "__main__":
    unittest.main()
