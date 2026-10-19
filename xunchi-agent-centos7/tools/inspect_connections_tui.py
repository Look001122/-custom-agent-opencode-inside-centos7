#!/usr/bin/env python3
"""Real compiled TUI acceptance with a loopback fixture; never real credentials."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


def main(root):
    root = Path(root)
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            calls.append("models")
            self.send_response(200); self.end_headers()
            self.wfile.write(b'{"data":[{"id":"model-A"},{"id":"model-B"}]}')
        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            probe_tool = value.get("tool_choice", {}).get("function", {}).get("name") == "xunchi_probe" if isinstance(value.get("tool_choice"), dict) else False
            calls.append("agent-stream" if value.get("stream") else "tools" if probe_tool else "chat")
            if value.get("stream"):
                assert self.headers.get("Authorization") == "Bearer TEST-ONLY-KEY-123456"
                self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
                for delta, finish in (({"role": "assistant", "content": "OK"}, None), ({}, "stop")):
                    chunk = {"id": "fixture-chat", "object": "chat.completion.chunk", "created": 1, "model": value["model"], "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                    self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
                return
            message = {"content": "OK"}
            if probe_tool:
                message = {"tool_calls": [{"id": "test-call", "type": "function", "function": {"name": "xunchi_probe", "arguments": '{"marker":"ok"}'}}]}
            body = {"id": "test-message", "object": "chat.completion", "created": 1, "model": value["model"], "choices": [{"index": 0, "message": dict(role="assistant", **message), "finish_reason": "tool_calls" if value.get("tools") else "stop"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps(body).encode())
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = ["tmux", "-L", "xunchi-connections-test-" + str(os.getpid())]
    home = root / "home"
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TERM": "xterm-256color",
           "OPENCODE_DISABLE_AUTOUPDATE": "true", "OPENCODE_DISABLE_MODELS_FETCH": "true", "OPENCODE_DISABLE_PROJECT_CONFIG": "true",
           "XDG_DATA_HOME": str(home / "data"), "XDG_CONFIG_HOME": str(home / "config"), "XDG_CACHE_HOME": str(home / "cache"), "XDG_STATE_HOME": str(home / "state")}
    command = " ".join(shlex.quote(v) for v in ["env", "-i"] + [k + "=" + v for k, v in env.items()] + ["bash", str(root / "bundle/start.sh")])
    script = root / "launch-test.sh"
    script.write_text("sleep 0.5\nstty -g > " + str(root / "before") + "\n" + command + '\nprintf "AFTER_EXIT:%s\\n" "$?"\nstty -g > ' + str(root / "after") + "\nsleep 20\n")
    report = {"environment": "WSL tmux; CentOS 7 pending", "external_model_requests": 0}
    capture = ""
    def run(*args):
        return subprocess.check_output(base + list(args), text=True)
    def wait(text):
        nonlocal capture
        for attempt in range(80):
            capture = run("capture-pane", "-p", "-t", "ui")
            if text in capture:
                return
            time.sleep(0.15)
        raise AssertionError("Missing UI text: " + text + "\n" + capture)
    def keys(*values):
        run("send-keys", "-t", "ui", *values)
        time.sleep(0.15)
    def text(value):
        run("send-keys", "-t", "ui", "-l", value)
        time.sleep(0.1)
    try:
        run("new-session", "-d", "-s", "ui", "-x", "120", "-y", "45", "-c", str(root / "work"), "bash " + str(script))
        run("pipe-pane", "-t", "ui", "cat > " + str(root / "terminal.raw"))
        wait("XunChi · 模型连接")
        report["first_run_without_key_prompt"] = True
        keys("Enter"); wait("连接名称"); text("测试中转A"); keys("Enter")
        wait("选择接口类型"); keys("Enter")
        wait("API 地址"); text("http://127.0.0.1:%s/v1" % server.server_port); keys("Enter")
        wait("密钥保存方式"); keys("Enter")
        wait("输入 API Key")
        secret = "TEST-ONLY-KEY-123456"
        # Paste through the actual terminal's bracketed-paste path.
        run("set-buffer", secret); run("paste-buffer", "-p", "-t", "ui")
        time.sleep(0.3)
        wait("已输入 20 个字符" if len(secret) == 20 else "已输入 %s 个字符" % len(secret))
        assert secret not in capture
        assert secret.encode() not in (root / "terminal.raw").read_bytes()
        report["secret_not_rendered"] = True
        keys("Enter"); wait("默认模型 ID"); text("model-A"); keys("Enter")
        wait("保存连接"); keys("Enter"); wait("XunChi · 模型连接")
        wait("测试中转A")
        profile_path = home / "config/xunchi-agent-centos7/connections.json"
        profiles = json.loads(profile_path.read_text())
        credential_path = profile_path.with_name("credentials.json")
        assert list(json.loads(credential_path.read_text()).values()) == [secret]
        assert credential_path.stat().st_mode & 0o777 == 0o600
        report["saved_default_and_private_key"] = True
        keys("Escape"); wait("model-A")
        assert "测试中转A" in capture
        report["configured_model_visible"] = True
        text("Say the two-letter acknowledgement only. Do not call tools."); keys("Enter")
        wait("OK")
        report["actual_agent_loopback_stream_and_auth"] = True
        for action, outcome in (("测试普通对话", "普通对话测试通过"), ("测试工具调用格式", "工具调用格式测试通过")):
            text("/connections"); keys("Enter"); wait("XunChi · 模型连接")
            keys("Down", "Enter"); wait("使用此连接")
            text(action); keys("Enter"); wait(outcome)
            keys("Enter"); wait("XunChi · 模型连接"); keys("Escape")
            wait("model-A")
        report["ui_chat_and_tool_tests"] = True
        assert "agent-stream" in calls and "chat" in calls and "tools" in calls, calls
        keys("C-d"); wait("AFTER_EXIT:0")
        assert (root / "before").read_bytes() == (root / "after").read_bytes()
        assert secret.encode() not in (root / "terminal.raw").read_bytes()
        assert not list((home / "cache/xunchi-agent-centos7").glob("session-*"))
        report["exit_tty_and_session_cleanup"] = True
        report["loopback_requests"] = calls
        # Restart the actual launcher with the same user config, without key env.
        run("kill-session", "-t", "ui")
        run("new-session", "-d", "-s", "ui", "-x", "120", "-y", "45", "-c", str(root / "work"), "bash " + str(script))
        wait("xunchi-IC-agent"); wait("model-A")
        assert "XunChi · 模型连接" not in capture
        report["restart_uses_saved_default_without_prompt"] = True
        keys("C-d"); wait("AFTER_EXIT:0")
    finally:
        (root / "last-screen.txt").write_text(capture)
        (root / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        subprocess.run(base + ["kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        server.shutdown(); server.server_close()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
