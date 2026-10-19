#!/usr/bin/env python3
"""Private per-user connection store and explicit capability probes. Python 3.6+."""
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import ssl
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid

ADAPTERS = {"chat": "@ai-sdk/openai-compatible", "responses": "@ai-sdk/openai", "anthropic": "@ai-sdk/anthropic"}


class ConnectionError(Exception):
    pass


def read_json(path, default):
    if not path.exists():
        return copy.deepcopy(default)
    if path.is_symlink():
        raise ConnectionError("配置文件不能是符号链接")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise ConnectionError("配置文件不是有效 JSON；原文件未修改")


def private_dir(path):
    if path.is_symlink():
        raise ConnectionError("私有目录不能是符号链接")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_uid != os.getuid():
        raise ConnectionError("配置目录不属于当前用户")
    path.chmod(0o700)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def atomic_bytes(path, value):
    private_dir(path.parent)
    if path.is_symlink():
        raise ConnectionError("拒绝覆盖符号链接")
    fd, temp = tempfile.mkstemp(prefix=".write-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def clean(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024 or re.search(r"[\x00-\x1f\x7f]", value):
        raise ConnectionError(label + "不能为空或包含控制字符")
    return value.strip()


def address(value):
    value = clean(value, "API 地址").rstrip("/")
    parts = urllib.parse.urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ConnectionError("请填写不含凭据、查询参数的完整 HTTP(S) Base URL")
    if parts.scheme == "http" and parts.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ConnectionError("远程连接请使用 HTTPS；HTTP 仅允许本机模型服务")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ConnectionError("服务地址发生跳转；请填写最终 API 地址后重试")


class Store:
    def __init__(self, home, session, base=None):
        self.home, self.session = Path(home), Path(session)
        private_dir(self.home)
        private_dir(self.session)
        self.base = base or {}
        self.path = self.home / "connections.json"
        self.keys_path = self.home / "credentials.json"
        self.session_path = self.session / "state.json"
        self.runtime = self.session / "opencode.json"

    def load(self):
        data = read_json(self.path, {"version": 1, "default": None, "profiles": []})
        if data.get("version") != 1 or not isinstance(data.get("profiles"), list):
            raise ConnectionError("不支持的连接配置版本")
        return data

    def migrate(self):
        if self.path.exists():
            return
        data = self.load()
        keys = {}
        for ident, provider in self.base.get("provider", {}).items():
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", ident):
                continue
            options = provider.get("options", {})
            models = provider.get("models", {})
            if not options.get("baseURL") or not models:
                continue
            npm = provider.get("npm", "@ai-sdk/openai-compatible")
            protocol = next((key for key, value in ADAPTERS.items() if value == npm), None)
            if not protocol:
                continue
            key = options.get("apiKey", "")
            env = re.fullmatch(r"\{env:([A-Za-z_][A-Za-z0-9_]*)\}", key) if isinstance(key, str) else None
            credential = {"mode": "env", "env": env.group(1)} if env else {"mode": "saved" if key else "none"}
            if key and not env:
                keys[ident] = key
            chosen = self.base.get("model", "")[len(ident)+1:] if self.base.get("model", "").startswith(ident + "/") else ""
            if chosen not in models:
                chosen = next(iter(models))
            data["profiles"].append({"id": ident, "name": provider.get("name", ident), "protocol": protocol,
                                     "baseURL": options["baseURL"], "models": list(models), "model": chosen,
                                     "credential": credential, "model_options": models,
                                     "extra_options": {k: v for k, v in options.items() if k != "apiKey"}})
            if self.base.get("model", "").startswith(ident + "/"):
                data["default"] = ident
        if data["profiles"] and not data["default"]:
            data["default"] = data["profiles"][0]["id"]
        atomic_json(self.keys_path, keys)
        atomic_json(self.path, data)

    def key(self, profile):
        credential = profile["credential"]
        if credential["mode"] == "none":
            return ""
        if credential["mode"] == "env":
            return os.environ.get(credential["env"], "")
        source = self.keys_path if credential["mode"] == "saved" else self.session / "credentials.json"
        return read_json(source, {}).get(profile["id"], "")

    def state(self):
        self.migrate()
        data = self.load()
        active = read_json(self.session_path, {}).get("active", data["default"])
        profiles = []
        for profile in data["profiles"]:
            public = {k: profile[k] for k in ("id", "name", "protocol", "baseURL", "models", "model")}
            public["credential_mode"] = profile["credential"]["mode"]
            public["ready"] = profile["credential"]["mode"] == "none" or bool(self.key(profile))
            profiles.append(public)
        return {"profiles": profiles, "default": data["default"], "active": active}

    def render(self):
        data, public = self.load(), self.state()
        config = copy.deepcopy(self.base)
        providers = config.setdefault("provider", {})
        ready = []
        active = None
        for profile in data["profiles"]:
            ident = profile["id"]
            key = self.key(profile)
            path = self.session / (ident + ".key")
            atomic_bytes(path, key.encode("utf-8"))
            options = dict(profile.get("extra_options", {}), baseURL=profile["baseURL"], apiKey="{file:" + str(path) + "}")
            providers[ident] = {"npm": ADAPTERS[profile["protocol"]], "name": profile["name"], "options": options,
                                "models": {model: dict(profile.get("model_options", {}).get(model, {}), name=model) for model in profile["models"]}}
            if key or profile["credential"]["mode"] == "none":
                ready.append(ident)
            if ident == public["active"]:
                active = profile
        # Never fall back to an unrelated free/paid provider after an auth error.
        config["enabled_providers"] = ready
        if active and active["id"] in ready:
            config["model"] = config["small_model"] = active["id"] + "/" + active["model"]
        else:
            config.pop("model", None)
            config.pop("small_model", None)
        atomic_json(self.runtime, config)
        return public

    def save(self, request):
        data = self.load()
        ident = request.get("id") or "xunchi-" + uuid.uuid4().hex[:12]
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", ident):
            raise ConnectionError("连接标识无效")
        old = next((p for p in data["profiles"] if p["id"] == ident), None)
        protocol = request.get("protocol", "chat")
        if protocol not in ADAPTERS:
            raise ConnectionError("不支持的接口类型")
        models = list(dict.fromkeys(clean(m, "模型 ID") for m in request.get("models", [])))
        model = clean(request.get("model"), "默认模型 ID")
        if model not in models:
            models.insert(0, model)
        mode = request.get("credential_mode", "saved")
        if mode not in ("saved", "session", "none", "keep"):
            raise ConnectionError("密钥保存方式无效")
        key = request.get("key", "")
        if key and (not isinstance(key, str) or re.search(r"[\x00-\x20\x7f]", key)):
            raise ConnectionError("API Key 不能包含空白或控制字符")
        credential = copy.deepcopy(old["credential"]) if mode == "keep" and old else {"mode": mode}
        if mode == "keep" and not old:
            raise ConnectionError("新连接需要指定密钥保存方式")
        if mode in ("saved", "session") and not key:
            raise ConnectionError("请输入 API Key，或选择无需密钥的本机服务")
        profile = {"id": ident, "name": clean(request.get("name"), "连接名称"), "protocol": protocol,
                   "baseURL": address(request.get("baseURL")), "models": models, "model": model, "credential": credential}
        if old:
            profile.update({k: old[k] for k in ("model_options", "extra_options") if k in old})
        for filename, target_mode in ((self.keys_path, "saved"), (self.session / "credentials.json", "session")):
            keys = read_json(filename, {})
            if mode != "keep":
                keys.pop(ident, None)
                if mode == target_mode:
                    keys[ident] = key
            atomic_json(filename, keys)
        data["profiles"] = [p for p in data["profiles"] if p["id"] != ident] + [profile]
        if request.get("default") or not data["default"]:
            data["default"] = ident
        atomic_json(self.path, data)
        atomic_json(self.session_path, {"active": ident})
        return self.render()

    def action(self, action, request):
        self.migrate()
        if action in ("initialize", "state"):
            return self.render() if action == "initialize" else self.state()
        if action == "save":
            return self.save(request)
        data = self.load()
        profile = next((p for p in data["profiles"] if p["id"] == request.get("id")), None)
        if not profile:
            raise ConnectionError("连接不存在")
        if action in ("select", "default"):
            if action == "default":
                data["default"] = profile["id"]
                atomic_json(self.path, data)
            atomic_json(self.session_path, {"active": profile["id"]})
            return self.render()
        if action == "delete":
            data["profiles"] = [p for p in data["profiles"] if p["id"] != profile["id"]]
            if data["default"] == profile["id"]:
                data["default"] = data["profiles"][0]["id"] if data["profiles"] else None
            atomic_json(self.path, data)
            for path in (self.keys_path, self.session / "credentials.json"):
                keys = read_json(path, {}); keys.pop(profile["id"], None); atomic_json(path, keys)
            (self.session / (profile["id"] + ".key")).unlink() if (self.session / (profile["id"] + ".key")).exists() else None
            atomic_json(self.session_path, {"active": data["default"]})
            return self.render()
        if action in ("models", "test"):
            return self.probe(profile, request, action)
        raise ConnectionError("未知连接操作")

    def probe(self, profile, request, action):
        key = self.key(profile)
        if not key and profile["credential"]["mode"] != "none":
            raise ConnectionError("此连接尚未配置密钥；请在连接设置中添加")
        protocol = profile["protocol"]
        headers = {"Content-Type": "application/json"}
        if key:
            headers["x-api-key" if protocol == "anthropic" else "Authorization"] = key if protocol == "anthropic" else "Bearer " + key
        if protocol == "anthropic":
            headers["anthropic-version"] = "2023-06-01"
        tool = request.get("kind") == "tools"
        endpoint = "models"
        body = None
        if action == "test":
            schema = {"type": "object", "properties": {"marker": {"type": "string", "enum": ["ok"]}}, "required": ["marker"], "additionalProperties": False}
            instruction = 'Call xunchi_probe with marker="ok".' if tool else 'Reply exactly OK.'
            body = {"model": profile["model"], "max_tokens": 64, "messages": [{"role": "user", "content": instruction}]}
            endpoint = "messages" if protocol == "anthropic" else "chat/completions"
            if protocol == "responses":
                endpoint = "responses"
                body = {"model": profile["model"], "max_output_tokens": 128, "input": instruction}
            if tool and protocol == "anthropic":
                body.update(tools=[{"name": "xunchi_probe", "description": "Connection test only; never executed", "input_schema": schema}], tool_choice={"type": "tool", "name": "xunchi_probe"})
            elif tool and protocol == "responses":
                body.update(tools=[{"type": "function", "name": "xunchi_probe", "description": "Connection test only; never executed", "parameters": schema}], tool_choice={"type": "function", "name": "xunchi_probe"})
            elif tool:
                body.update(tools=[{"type": "function", "function": {"name": "xunchi_probe", "parameters": schema}}], tool_choice={"type": "function", "function": {"name": "xunchi_probe"}})
        req = urllib.request.Request(address(profile["baseURL"]) + "/" + endpoint, headers=headers,
                                     data=json.dumps(body).encode("utf-8") if body else None)
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=20) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise ConnectionError("服务响应过大；请检查接口地址")
                result = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as error:
            if action == "models" and error.code == 404:
                raise ConnectionError("此服务不提供模型列表；请通过编辑连接手动填写模型 ID")
            messages = {401: "鉴权失败，请检查密钥", 403: "服务拒绝访问，请检查权限", 404: "接口或模型不存在，请检查协议和地址", 429: "请求受限或额度不足"}
            raise ConnectionError(messages.get(error.code, "服务请求失败，HTTP " + str(error.code)))
        except urllib.error.URLError as error:
            if isinstance(error.reason, socket.gaierror):
                raise ConnectionError("DNS 解析失败；请检查服务域名和系统 DNS")
            if isinstance(error.reason, ssl.SSLError):
                raise ConnectionError("TLS 证书验证失败；请检查服务证书和系统时间")
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                raise ConnectionError("连接超时；请检查网络和服务状态")
            raise ConnectionError("无法连接模型服务；请检查网络、代理和服务地址")
        except (socket.timeout, TimeoutError):
            raise ConnectionError("连接超时；请检查网络和服务状态")
        except (ValueError, UnicodeError):
            raise ConnectionError("服务返回的不是有效 JSON；请检查 Base URL")
        if action == "models":
            return {"models": [clean(item["id"], "模型 ID") for item in result.get("data", []) if isinstance(item, dict) and isinstance(item.get("id"), str)][:300]}
        try:
            if protocol == "chat":
                message = result["choices"][0]["message"]
                calls = [{"name": c["function"]["name"], "input": json.loads(c["function"]["arguments"])} for c in message.get("tool_calls", [])]
                text = message.get("content")
            elif protocol == "anthropic":
                calls = [c for c in result.get("content", []) if c.get("type") == "tool_use"]
                text = "".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
            else:
                calls = [{"name": c["name"], "input": json.loads(c["arguments"])} for c in result.get("output", []) if c.get("type") == "function_call"]
                text = "".join(t.get("text", "") for c in result.get("output", []) for t in c.get("content", []) if t.get("type") == "output_text")
            passed = any(c.get("name") == "xunchi_probe" and c.get("input") == {"marker": "ok"} for c in calls) if tool else bool(isinstance(text, str) and text.strip())
        except (KeyError, IndexError, TypeError, ValueError):
            passed = False
        return {"passed": passed, "kind": "tools" if tool else "chat", "message": ("工具调用格式测试通过（未执行任何工具）" if tool else "普通对话测试通过") if passed else "响应不符合测试要求；不能据此确认模型能力"}


def main():
    import sys
    try:
        base = read_json(Path(os.environ["XUNCHI_SESSION_DIR"]) / "base.json", {})
        store = Store(os.environ["XUNCHI_CONNECTIONS_HOME"], os.environ["XUNCHI_SESSION_DIR"], base)
        lock_path = store.home / ".lock"
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            request = json.loads(sys.stdin.read() or "{}")
            result = store.action(sys.argv[1], request)
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False))
    except ConnectionError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
    except Exception:
        # Provider bodies, request payloads and key values must never reach logs.
        print(json.dumps({"ok": False, "error": "连接操作失败；请检查私有配置目录和配置格式"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
