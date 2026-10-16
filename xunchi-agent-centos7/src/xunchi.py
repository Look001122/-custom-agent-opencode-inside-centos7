#!/usr/bin/env python3
"""Internal product foundation. Python 3.6+; no third-party dependencies."""
from __future__ import print_function

import argparse
import getpass
import json
import os
import platform
import shutil
import subprocess
import sys

from jobs import poll, submit, work

VERSION = "0.1.0-dev.1"


def path(value):
    return os.path.abspath(os.path.expanduser(value))


def load_profile(filename):
    with open(filename, encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("schema_version") != 1:
        raise ValueError("profile schema_version must be 1")
    engine = data.get("engine", {})
    for field in ("launcher", "config"):
        if not isinstance(engine.get(field), str) or not engine[field]:
            raise ValueError("engine.%s is required" % field)
    required = engine.get("required_env", [])
    if not isinstance(required, list) or any(not isinstance(x, str) for x in required):
        raise ValueError("engine.required_env must be a list of variable names")
    return data


def doctor(profile):
    engine = profile["engine"]
    checks = []

    def add(name, ok, detail, warning=False):
        checks.append({"name": name, "status": "pass" if ok else "warning" if warning else "fail", "detail": detail})

    add("os", platform.system() == "Linux" and platform.machine() == "x86_64", "Linux x86_64 required")
    add("python", sys.version_info >= (3, 6), platform.python_version())
    launcher = path(engine["launcher"])
    add("engine_launcher", os.path.isfile(launcher) and os.access(launcher, os.X_OK), launcher)
    config = path(engine["config"])
    add("engine_config", os.path.isfile(config) and os.access(config, os.R_OK), config)
    # Never print config content, credentials, or the full process environment.
    for name in engine.get("required_env", []):
        add("credential_environment", bool(os.environ.get(name)), "%s: %s" % (name, "set" if os.environ.get(name) else "missing"), True)
    add("utf8_locale", "utf" in os.environ.get("LC_ALL", os.environ.get("LANG", "")).lower(), "Native desktop input method still needs a manual input test", True)
    add("native_clipboard", bool(shutil.which("xclip") or shutil.which("xsel") or shutil.which("wl-copy")), "Helper presence does not prove clipboard works; upstream OSC52 is not fixed in the existing binary", True)
    env_script = profile.get("eda_environment_script")
    add("eda_environment_script", bool(env_script and os.path.isfile(path(env_script))), "Configured script presence only; no script was executed", True)
    project = profile.get("project", {})
    root = project.get("root")
    add("project_directory", bool(root and os.path.isdir(path(root))), "Project presence only; PDK and bridge identity require live verification", True)
    return {"product": "xunchi-agent-centos7", "version": VERSION, "checks": checks,
            "ready_to_attempt_launch": not any(x["status"] == "fail" for x in checks),
            "eda_acceptance": "not_tested", "model_connectivity": "not_tested"}


def launch(profile, arguments):
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("The TUI runtime requires Linux x86_64")
    engine = profile["engine"]
    launcher, config = path(engine["launcher"]), path(engine["config"])
    if not os.path.isfile(launcher) or not os.access(launcher, os.X_OK):
        raise ValueError("Engine launcher is missing or not executable: " + launcher)
    if not os.path.isfile(config) or not os.access(config, os.R_OK):
        raise ValueError("Engine config is missing or unreadable: " + config)
    child_env = os.environ.copy()
    for name in engine.get("required_env", []):
        if not child_env.get(name):
            if not sys.stdin.isatty():
                raise ValueError("Missing credential environment variable: " + name)
            child_env[name] = getpass.getpass(name + ": ")
            if not child_env[name]:
                raise ValueError("Credential must not be empty")
    child_env.pop("LD_LIBRARY_PATH", None)
    child_env.pop("LD_PRELOAD", None)
    child_env["OPENCODE_CONFIG"] = config
    child_env["OPENTUI_FORCE_EXPLICIT_WIDTH"] = "0"
    child_env["OPENCODE_DISABLE_AUTOUPDATE"] = "true"
    # This flag only takes effect after the source patch is built into the engine.
    child_env["XUNCHI_DISABLE_OSC52"] = "1"
    os.execve(launcher, [launcher] + arguments, child_env)


def main(arguments=None):
    parser = argparse.ArgumentParser(description="xunchi-agent-centos7 development entry")
    parser.add_argument("--profile", default=os.environ.get("XUNCHI_PROFILE", "~/.config/xunchi-agent-centos7/deployment.json"))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--product-version", action="store_true")
    group.add_argument("--doctor", action="store_true")
    group.add_argument("--run", metavar="ACTION")
    group.add_argument("--job", metavar="DIRECTORY")
    group.add_argument("--worker", metavar="DIRECTORY", help=argparse.SUPPRESS)
    args, remaining = parser.parse_known_args(arguments)
    if args.product_version:
        print("xunchi-agent-centos7 " + VERSION)
        return 0
    if args.worker:
        return work(path(args.worker))
    if args.job:
        print(json.dumps(poll(path(args.job)), ensure_ascii=False, indent=2))
        return 0
    profile = load_profile(path(args.profile))
    if args.doctor:
        result = doctor(profile)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ready_to_attempt_launch"] else 2
    if args.run:
        print(json.dumps(submit(profile, args.run), ensure_ascii=False, indent=2))
        return 0
    if remaining and remaining[0] == "--":
        remaining = remaining[1:]
    launch(profile, remaining)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print("xunchi: " + str(error), file=sys.stderr)
        sys.exit(2)
