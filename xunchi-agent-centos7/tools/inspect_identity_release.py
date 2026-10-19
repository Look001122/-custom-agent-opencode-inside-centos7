#!/usr/bin/env python3
"""Exercise compiled engines against a local fixture and inspect the real TUI.

The fixture cannot validate a real model's answer. It captures outgoing system
instructions and implements one harmless read-tool round trip on a test file.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import threading
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--mode", choices=("legacy", "managed"), required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    home, work, bundle = root / "home", root / "work", root / "bundle"
    home.mkdir(exist_ok=True)
    work.mkdir(exist_ok=True)
    if (home / "config/xunchi-agent-centos7/connections.json").exists():
        raise ValueError("Use a fresh isolated HOME; saved profiles intentionally retain their existing service address")
    marker = work / "read-only-marker.txt"
    marker.write_text("XUNCHI_READ_ONLY_MARKER\n")
    marker_hash = hashlib.sha256(marker.read_bytes()).hexdigest()
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(value)
            user = json.dumps([m for m in value.get("messages", []) if m["role"] == "user"])
            read_available = any(t["function"]["name"] == "read" for t in value.get("tools", []))
            tool_call = "READ_TOOL_PROBE" in user and read_available and not any(m["role"] == "tool" for m in value.get("messages", []))
            delta = {"role": "assistant", "content": "Fixture response: XunChi Agent."}
            finish = "stop"
            if tool_call:
                assert any(t["function"]["name"] == "read" for t in value.get("tools", [])), "Read tool disappeared"
                delta = {"role": "assistant", "tool_calls": [{"index": 0, "id": "read-probe", "type": "function", "function": {"name": "read", "arguments": json.dumps({"filePath": str(marker)})}}]}
                finish = "tool_calls"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for part, reason in ((delta, None), ({}, finish)):
                chunk = {"id": "identity-fixture", "object": "chat.completion.chunk", "created": 1,
                         "model": value["model"], "choices": [{"index": 0, "delta": part, "finish_reason": reason}]}
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = dict(os.environ, HOME=str(home), PATH="/usr/bin:/bin", LANG="C.UTF-8", TERM="xterm-256color",
               XDG_DATA_HOME=str(home / "data"), XDG_CONFIG_HOME=str(home / "config"),
               XDG_CACHE_HOME=str(home / "cache"), XDG_STATE_HOME=str(home / "state"),
               OPENCODE_DISABLE_AUTOUPDATE="true", OPENCODE_DISABLE_MODELS_FETCH="true",
               OPENCODE_DISABLE_PROJECT_CONFIG="true", DASHSCOPE_API_KEY="LOCAL-FIXTURE-ONLY")
    config = home / "fixture.json"
    value = {"model": "fixture/deepseek-fixture", "small_model": "fixture/deepseek-fixture",
             "enabled_providers": ["fixture"],
             "provider": {"fixture": {"npm": "@ai-sdk/openai-compatible", "name": "Local Fixture",
                          "options": {"baseURL": "http://127.0.0.1:%s/v1" % server.server_port, "apiKey": "LOCAL-FIXTURE-ONLY"},
                          "models": {name: {"name": name, "limit": {"context": 64000, "output": 4096}}
                                     for name in ("deepseek-fixture", "gemini-fixture", "claude-fixture")}}},
             "agent": {"custom-probe": {"mode": "primary", "prompt": "CUSTOM_AGENT_TASK: assist with resistor inspection."}}}
    config.write_text(json.dumps(value))
    env["OPENCODE_CONFIG"] = str(config)
    env_file = root / "test-env.json"
    env_file.write_text(json.dumps({k: v for k, v in env.items() if k in (
        "HOME", "PATH", "LANG", "TERM", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME",
        "OPENCODE_CONFIG", "DASHSCOPE_API_KEY", "OPENCODE_DISABLE_AUTOUPDATE", "OPENCODE_DISABLE_MODELS_FETCH", "OPENCODE_DISABLE_PROJECT_CONFIG")}))
    report = {"environment": "WSL Ubuntu / tmux; CentOS 7 not tested", "mode": args.mode,
              "external_model_requests": 0, "real_model_answer_validated": False}
    socket = ["tmux", "-L", "xunchi-identity-" + str(os.getpid())]
    capture = ""
    session = None

    def run_cli(agent, model, text, resume=None):
        command = ["bash", str(bundle / "start.sh"), "run", "--format", "json", "--agent", agent,
                   "--model", "fixture/" + model]
        if resume:
            command += ["--session", resume]
        process = subprocess.Popen(command + [text], cwd=str(work), env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                   universal_newlines=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        assert result.returncode == 0, result.stderr[-2000:]
        events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        assert not any(event.get("type") == "error" for event in events), events
        found = [event.get("sessionID") for event in events if event.get("sessionID")]
        assert found, result.stdout
        return found[0], events

    def tmux(*values):
        return subprocess.check_output(socket + list(values), universal_newlines=True)

    def wait(text):
        nonlocal capture
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            capture = tmux("capture-pane", "-p", "-t", "ui")
            if text in capture:
                return
            time.sleep(0.2)
        raise AssertionError("Missing " + text + "\n" + capture)

    def launch(resume=None):
        test_env = json.loads(env_file.read_text())
        command = ["env", "-i"] + [k + "=" + v for k, v in test_env.items()] + ["bash", str(bundle / "start.sh")]
        if resume:
            command += ["-s", resume]
        script = root / "test-launch.sh"
        script.write_text("stty -g > " + shlex.quote(str(root / "before")) + "\n" +
                          " ".join(shlex.quote(part) for part in command) +
                          '\nprintf "AFTER_EXIT:%s\\n" "$?"\nstty -g > ' + shlex.quote(str(root / "after")) + "\nsleep 30\n")
        tmux("new-session", "-d", "-s", "ui", "-x", "150", "-y", "45", "-c", str(work), "bash " + shlex.quote(str(script)))

    def command(text):
        tmux("send-keys", "-t", "ui", "-l", text)
        time.sleep(0.2)
        tmux("send-keys", "-t", "ui", "Enter")

    try:
        help_result = subprocess.run(["bash", str(bundle / "start.sh"), "--help"], cwd=str(work), env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                     universal_newlines=True, timeout=30)
        assert help_result.returncode == 0
        assert "XunChi Agent 0.1.1" in help_result.stdout + help_result.stderr
        assert "xunchi-agent-centos7" in help_result.stdout + help_result.stderr
        report["cli_help_product_brand"] = True
        for agent, model in (("build", "deepseek-fixture"), ("plan", "gemini-fixture"), ("custom-probe", "claude-fixture")):
            start = len(calls)
            sid, events = run_cli(agent, model, "IDENTITY_PROBE_" + agent)
            assert calls[start:], "No real engine request captured"
            systems = ["\n".join(str(m["content"]) for m in call["messages"] if m["role"] == "system") for call in calls[start:]]
            assert all("<product_identity>" in system and "You are XunChi Agent" in system for system in systems)
            assert all("You are opencode" not in system and "You are OpenCode" not in system for system in systems)
            if agent == "custom-probe":
                assert any("CUSTOM_AGENT_TASK" in system for system in systems)
            if agent == "build":
                session = sid
                assert any(len(call.get("tools", [])) > 0 for call in calls[start:])
        report["build_plan_custom_agent_and_model_prompt_identity"] = True
        run_cli("build", "deepseek-fixture", "IDENTITY_RESUME", session)
        report["resumed_session_system_identity"] = "<product_identity>" in json.dumps(calls[-1])
        start = len(calls)
        run_cli("build", "deepseek-fixture", "READ_TOOL_PROBE")
        assert any(m.get("role") == "tool" and "XUNCHI_READ_ONLY_MARKER" in json.dumps(m) for c in calls[start:] for m in c["messages"])
        assert hashlib.sha256(marker.read_bytes()).hexdigest() == marker_hash
        report["actual_read_tool_roundtrip_and_file_unchanged"] = True
        launch()
        wait("XunChi Agent")
        wait("0.1.1")
        assert "xunchi-IC-agent" not in capture
        assert tmux("display-message", "-p", "-t", "ui", "#{pane_title}").strip() == "XunChi Agent"
        report["home_product_version_and_title"] = True
        command("/about")
        wait("关于 XunChi Agent")
        wait("OpenCode 1.19.0")
        wait("fixture/deepseek-fixture")
        report["about_provenance_and_actual_model"] = True
        tmux("send-keys", "-t", "ui", "Escape")
        time.sleep(0.4)
        command("/help")
        wait("XunChi Agent 帮助")
        tmux("send-keys", "-t", "ui", "Escape")
        time.sleep(0.4)
        tmux("set-buffer", "中文输入与粘贴检查")
        tmux("paste-buffer", "-p", "-t", "ui")
        wait("中文输入与粘贴检查")
        tmux("send-keys", "-t", "ui", "C-u")
        tmux("send-keys", "-t", "ui", "C-d")
        wait("AFTER_EXIT:0")
        assert (root / "before").read_bytes() == (root / "after").read_bytes()
        report["help_chinese_paste_exit_and_tty_restore"] = True
        tmux("kill-session", "-t", "ui")
        launch(session)
        wait("XunChi Agent 0.1.1")
        assert "OpenCode 1.19.0" not in capture
        report["restored_session_sidebar_brand"] = True
        tmux("send-keys", "-t", "ui", "C-d")
        wait("AFTER_EXIT:0")
        assert "Continue" in capture and "xunchi-agent-centos7" in capture and "XunChi Agent" in capture
        report["exit_brand_and_resume_command"] = True
        report["loopback_requests"] = len(calls)
    finally:
        (root / "last-screen.txt").write_text(capture)
        (root / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        subprocess.run(socket + ["kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        server.shutdown()
        server.server_close()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
