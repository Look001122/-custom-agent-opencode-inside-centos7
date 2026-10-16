"""Detached process jobs with durable results; never equate exit 0 with LVS pass."""
from __future__ import print_function

import datetime
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(filename, value):
    fd, temporary = tempfile.mkstemp(prefix=".state-", dir=os.path.dirname(filename))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, filename)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read(filename):
    with open(filename, encoding="utf-8") as stream:
        return json.load(stream)


def digest(filename):
    result = hashlib.sha256()
    with open(filename, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def lvs_result(filename):
    if not os.path.isfile(filename):
        return "unknown"
    with open(filename, encoding="utf-8", errors="replace") as stream:
        text = stream.read()
    # Only inspect the overall section. Generic searches can match headings such
    # as INCORRECT OBJECTS even in unrelated diagnostics or hierarchical details.
    match = re.search(r"^\s*OVERALL COMPARISON RESULTS\s*$", text, re.M)
    if not match:
        return "unknown"
    section = text[match.end():].split("CELL COMPARISON RESULTS", 1)[0][:2500]
    tokens = set(re.findall(r"\b(?:INCORRECT|CORRECT)\b", section))
    return "incorrect" if tokens == {"INCORRECT"} else "correct" if tokens == {"CORRECT"} else "unknown"


def submit(profile, action_name):
    if os.name != "posix":
        raise ValueError("EDA jobs require a POSIX host")
    if not re.match(r"^[a-z][a-z0-9_-]{0,63}$", action_name):
        raise ValueError("Invalid action name")
    action = profile.get("actions", {}).get(action_name)
    if not isinstance(action, dict):
        raise ValueError("Action is not registered in the local profile: " + action_name)
    if action.get("mutates_design") is not False:
        raise ValueError("This development runner only supports actions declaring mutates_design=false")
    argv = action.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(x, str) for x in argv):
        raise ValueError("Action argv must be a nonempty string list")
    timeout = action.get("timeout_seconds", 1200)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
        raise ValueError("Action timeout_seconds must be a positive integer")
    kind = action.get("validation", "process")
    if kind not in ("process", "lvs"):
        raise ValueError("Only process and lvs result adapters are implemented")
    root = os.path.abspath(os.path.expanduser(profile["project"]["root"]))
    if not os.path.isdir(root):
        raise ValueError("Project directory does not exist")
    env_script = profile.get("eda_environment_script")
    if env_script:
        env_script = os.path.abspath(os.path.expanduser(env_script))
        if not os.path.isfile(env_script):
            raise ValueError("EDA environment script does not exist")
    store = os.path.abspath(os.path.expanduser(profile.get("job_store", "~/.local/state/xunchi-agent-centos7/jobs")))
    os.makedirs(store, mode=0o700, exist_ok=True)
    run_dir = tempfile.mkdtemp(prefix=action_name + "-", dir=store)
    values = {"{run_dir}": run_dir, "{project_root}": root}

    def expand(value):
        for key, replacement in values.items():
            value = value.replace(key, replacement)
        return value

    report = action.get("report", "lvs.report")
    if not isinstance(report, str) or os.path.isabs(report) or ".." in report.split("/"):
        raise ValueError("Action report must be a relative path inside the new job directory")
    request = {"action": action_name, "argv": [expand(x) for x in argv], "cwd": run_dir,
               "project": profile["project"], "environment_script": env_script,
               "timeout_seconds": timeout, "validation": kind, "report": report}
    save(os.path.join(run_dir, "request.json"), request)
    save(os.path.join(run_dir, "status.json"), {"state": "queued", "created_at": now()})
    worker_env = os.environ.copy()
    for name in profile.get("engine", {}).get("required_env", []):
        worker_env.pop(name, None)
    with open(os.path.join(run_dir, "worker.log"), "ab", buffering=0) as log:
        try:
            worker = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), "xunchi.py"), "--worker", run_dir],
                                      stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, env=worker_env)
        except OSError:
            save(os.path.join(run_dir, "status.json"), {"state": "failed", "reason": "worker_start_failed", "finished_at": now()})
            raise
    # Reap workers if this module is embedded in a long-lived tool host. A short
    # lived CLI can exit immediately; the detached worker is reparented by Linux.
    threading.Thread(target=worker.wait, daemon=True).start()
    save(os.path.join(run_dir, "worker.json"), {"pid": worker.pid})
    return {"job_directory": run_dir, "submitted": True, "worker_pid": worker.pid,
            "note": "Submission is not execution or validation success. Query --job."}


def work(run_dir):
    request = read(os.path.join(run_dir, "request.json"))
    status = {"state": "running", "worker_pid": os.getpid(), "started_at": now(),
              "project": request["project"], "design_modified": "not_verified",
              "validation": "not_tested"}
    state_file = os.path.join(run_dir, "status.json")
    save(state_file, status)
    argv = request["argv"]
    if request["environment_script"]:
        # Script is a trusted local deployment artifact, not model-generated env.
        argv = ["/bin/bash", "-c", 'set -e; source "$1" >/dev/null; shift; exec "$@"',
                "xunchi-eda", request["environment_script"]] + argv
    try:
        with open(os.path.join(run_dir, "process.log"), "wb", buffering=0) as log:
            process = subprocess.Popen(argv, cwd=request["cwd"], stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=log, start_new_session=True)
            status["child_pid"] = process.pid
            save(state_file, status)
            try:
                rc = process.wait(timeout=request["timeout_seconds"])
                status.update(state="completed" if rc == 0 else "failed", returncode=rc)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                status.update(state="timed_out", returncode=process.returncode)
        report = os.path.join(run_dir, request["report"])
        if request["validation"] == "lvs":
            # A partial or stale-looking report cannot pass a failed execution.
            status["validation"] = lvs_result(report) if status["state"] == "completed" else "unknown"
            if os.path.isfile(report):
                status["report"] = {"path": report, "sha256": digest(report)}
    except (OSError, ValueError) as error:
        status.update(state="failed", reason=str(error), validation="unknown")
    status["finished_at"] = now()
    save(state_file, status)
    return 0


def poll(run_dir):
    status = read(os.path.join(run_dir, "status.json"))
    if status["state"] in ("queued", "running"):
        worker_file = os.path.join(run_dir, "worker.json")
        if os.path.exists(worker_file):
            pid = read(worker_file)["pid"]
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                status.update(state="unknown", reason="worker_missing_without_final_result")
    return status
