# 构建 XunChi Agent 0.1.1

公开仓库只有源码、补丁、模板、测试和历史构建摘要，没有此版内部二进制。旧 r1 Release 不包含身份升级。以下工作在现代 Linux x86_64 构建机完成，CentOS 用户不需要编译。

## 两种引擎

准备两个独立的上游源码目录，均检出 `733b2c627e5aec39cb33cc22373bdce33053ef2c`，在各自目录使用 Bun **1.3.14** 执行 `bun install --frozen-lockfile`。构建机需要上游的 Node/C++ 等构建依赖。

从本仓库根目录执行：

```bash
bash xunchi-agent-centos7/tools/build_identity_linux.sh /absolute/path/to/fresh-legacy-source "$(command -v bun)" legacy
bash xunchi-agent-centos7/tools/build_identity_linux.sh /absolute/path/to/fresh-managed-source "$(command -v bun)" managed
```

脚本要求全新且尚未应用品牌补丁的源码，并预先安装完整依赖，内部使用 `--skip-install`。legacy 应用 0002/0003/0004/0006，managed 再应用 0005。脚本在包目录运行类型检查并构建 musl 引擎。不要同时对同一源码目录构建两个变体。

模型目录由上游构建获取；如有已验证的本地快照，可设置 `MODELS_DEV_API_JSON` 为绝对路径。公开仓库不含内部 vendor。不同环境的新构建不保证和历史摘要逐字节相同。

## 升级包

将两个目录中的 `packages/opencode/dist/opencode-linux-x64-musl/bin/opencode` 分别复制到自己的构建目录 `identity-engines/legacy` 和 `identity-engines/managed`。记录本次真实引擎 SHA：

```bash
python3 - /absolute/path/to/identity-engines > BUILD.local.json <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
print(json.dumps({
    "product": "XunChi Agent", "product_version": "0.1.1",
    "release": "0.1.1-identity.1", "engine_version": "1.19.0",
    "upstream_commit": "733b2c627e5aec39cb33cc22373bdce33053ef2c",
    "target": "linux-x64-musl",
    "engines": {mode: hashlib.sha256((root / mode).read_bytes()).hexdigest()
                for mode in ("legacy", "managed")},
    "validation": "New build; runtime and target acceptance pending"
}, indent=2))
PY
```

依赖许可材料来自已经校验的 r1 兼容归档或内部 brand.3 归档。r1 可通过旧 Release 或根目录 `scripts/build_bundle.py` 获取；先运行 `scripts/verify_bundle.py`。使用可信同名校验文件里的 SHA，不能把不同归档的历史 SHA 混用。

```bash
python3 xunchi-agent-centos7/tools/package_identity_release.py \
  --engines /absolute/path/to/identity-engines \
  --record BUILD.local.json \
  --licenses-from /absolute/path/to/verified-compatibility.tar.gz \
  --base-sha256 REPLACE_WITH_VERIFIED_ARCHIVE_SHA256
```

升级包复用目标机已有运行库、启动脚本和终端兼容层。将生成的归档、同名 `.sha256` 和 `deploy/install-xunchi-identity.sh` 放在一起，已有匹配安装的用户才能升级。条件和回退见 [IDENTITY.md](IDENTITY.md)。历史 `build-records/0.1.1-identity.1.json` 不替代新构建验收。

## 可选连接管理开发分支

独立入口为 `build_connections_linux.sh`、`prepare_connections_source.py`、`package_connections_release.py`，以及 `deploy/start-connections.sh`、`install-connections.py`、`install-connections.sh`。

构建脚本接受全新上游源码和 Bun 路径，应用 0002/0003/0004/0005。打包器接受 `--engine`、`--base`、`--base-sha256`、`--build-record`，记录需包含真实 `engine_sha256` 和 `release=0.2.0-connections.1`。它采用新的连接流程，不是本次“保留既有连接方式”的必选升级。

## 验证

普通源码测试：`python3 -m unittest discover -s xunchi-agent-centos7/tests -v`。Python 部署语法按 3.6 检查；TUI 修改在对应上游包内类型检查。

`inspect_identity_release.py` 和 `inspect_connections_tui.py` 使用真实程序、隔离 HOME/tmux 及本机模拟服务。`validate_identity_upgrade.py` 还要求开发者自备两个历史内部包，这些包未随源码提供。普通源码 CI 不假装执行缺少二进制的验收。新版本的真实模型、CentOS 和 Virtuoso 仍需分别检查。
