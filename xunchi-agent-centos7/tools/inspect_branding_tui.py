#!/usr/bin/env python3
"""Inspect a real compiled TUI in a private tmux server, without sending prompts."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("smoke_directory", type=Path)
    args = parser.parse_args()
    root = args.smoke_directory.resolve()
    env = json.loads((root / "env.json").read_text())
    socket = "xunchi-brand-" + str(os.getpid())
    base = ["tmux", "-L", socket]
    engine = root / "opencode-centos7-1.19.0-r1/opencode"
    command = " ".join(shlex.quote(value) for value in ["env", "-i"] + [key + "=" + value for key, value in env.items()] + [str(engine)])
    command += " 2>" + shlex.quote(str(root / "tui.stderr"))
    transcript = ""
    result = {"environment": "WSL Ubuntu; not CentOS 7", "prompts_submitted": 0, "brand_visible": False}
    try:
        subprocess.check_call(base + ["new-session", "-d", "-s", "home", "-x", "120", "-y", "40", "-c", str(root / "work"), command])
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            captured = subprocess.run(base + ["capture-pane", "-p", "-t", "home"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            if captured.returncode:
                result["capture_error"] = captured.stderr
                break
            transcript = captured.stdout
            if "xunchi-IC-agent" in transcript and "苏州迅驰信息科技有限公司" in transcript:
                result["brand_visible"] = True
                result["english_without_trailing_period"] = "Co., Ltd." not in transcript and "Co., Ltd" in transcript
                title = subprocess.check_output(base + ["display-message", "-p", "-t", "home", "#{pane_title}"], universal_newlines=True).strip()
                result["terminal_title"] = title
                result["terminal_title_passed"] = title == "XunChi"
                break
            time.sleep(1)
    finally:
        subprocess.run(base + ["kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (root / "tui-capture.txt").write_text(transcript, encoding="utf-8")
    (root / "tui-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    print(transcript)
    if not result["brand_visible"] or not result.get("terminal_title_passed"):
        error = root / "tui.stderr"
        if error.exists():
            print(error.read_text(encoding="utf-8", errors="replace")[-4000:])
        raise SystemExit(2)


if __name__ == "__main__":
    main()
