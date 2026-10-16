# 构建 XunChi 定制版本

公开目录是源码、补丁和测试，不含可运行的 brand.3 成品。旧的 r1 Release 不包含公司品牌或新的 PTY 兼容层。已有内部成品的使用者见 `INSTALL_BRANDING.md`；该说明中的共享目录不是 GitHub 下载地址。

## 开发环境

在现代 Linux x86_64 构建机准备 Git、Python 3、Bun **1.3.14** 和上游构建依赖。Bun/Node/C++ 构建工具只在构建机使用；CentOS 用户运行成品需要 Python 3.6+，不需要在 EDA 机器编译。

检出固定上游源码，不能只下载本仓库后直接运行 OpenCode：

```bash
git clone https://github.com/anomalyco/opencode.git opencode-xunchi-source
git -C opencode-xunchi-source checkout 733b2c627e5aec39cb33cc22373bdce33053ef2c
```

从本仓库根目录执行，`SOURCE` 使用刚检出的绝对路径：

```bash
SOURCE=/absolute/path/to/opencode-xunchi-source
bash xunchi-agent-centos7/tools/build_branding_linux.sh "$SOURCE" "$(command -v bun)"
```

脚本检查 Bun 版本，应用 `0002` 和 `0004`，准备 `0003` 的 musl 目标选择，安装固定依赖，在 TUI 包内执行类型检查，最后构建 Linux x64 musl。没有应用 `0001` 剪贴板补丁；brand.3 在传输层禁用旧终端不支持的协议。

输出程序为 `$SOURCE/packages/opencode/dist/opencode-linux-x64-musl/bin/opencode`。构建包含模型目录/前端资源等输入；本仓库保存历史构建摘要，不承诺在不同网络快照和构建环境中获得逐字节相同程序。

如果要重新生成公司字符 Logo，先在**未应用品牌补丁**的固定上游源码上运行 `tools/build_branding.py --upstream "$SOURCE"`，需要开发依赖 Pillow。直接应用已提交的补丁不需要 Pillow。静态浏览器预览仅用于布局检查，不能代替真实 TUI 验收。

## 组合兼容运行库

需要已校验的原 r1 兼容包，或从仓库根目录运行 `python3 scripts/build_bundle.py` 生成。保留其 `.sha256`、`sources.lock.json` 和全部许可证，并先执行：

```bash
python3 scripts/verify_bundle.py /absolute/path/to/opencode-centos7-1.19.0-r1.tar.gz
```

不同构建时间的压缩包 SHA 可以不同。`--base-sha256` 必须使用已验证来源的实际归档摘要；不能把历史内部归档的默认 SHA 当作所有下载文件的摘要。

记录本次新引擎的真实 SHA，不将历史测试结果自动移植到新构建：

```bash
ENGINE="$SOURCE/packages/opencode/dist/opencode-linux-x64-musl/bin/opencode"
python3 - "$ENGINE" > BUILD.local.json <<'PY'
import hashlib, json, sys
from pathlib import Path
p = Path(sys.argv[1])
print(json.dumps({
    "product": "xunchi-IC-agent",
    "release": "0.1.0-brand.3",
    "upstream_commit": "733b2c627e5aec39cb33cc22373bdce33053ef2c",
    "target": "linux-x64-musl",
    "engine_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
    "validation": "New build; runtime and target acceptance must be recorded separately"
}, indent=2))
PY
```

打包命令（替换两个占位值，不向 Git 提交本地路径或凭据）：

```bash
python3 xunchi-agent-centos7/tools/package_branding_release.py \
  --engine "$ENGINE" \
  --base /absolute/path/to/opencode-centos7-1.19.0-r1.tar.gz \
  --base-sha256 REPLACE_WITH_VERIFIED_ARCHIVE_SHA256 \
  --build-record BUILD.local.json
```

输出位于 `xunchi-agent-centos7/dist/`。将成品、同名 `.sha256` 和 `deploy/install-xunchi.sh` 放到同一目录后，才可使用安装脚本。`dist/` 和 `BUILD.local.json` 不应提交到源码仓库。

## 测试与验收

```bash
python3 -m unittest discover -s xunchi-agent-centos7/tests -v
```

测试需要普通 Linux 用户及 PTY；开发检查应记录实际跳过项。修改 TUI 源码还要在上游 TUI 包执行 `bun run typecheck`，真实 TUI 用独立 tmux 会话检查并在结束后停止该会话。安装器、版本、中文输入/粘贴、退出、模型调用和目标 EDA 操作需要分别验收。

`build-records/0.1.0-brand.3.json` 是已交付内部包的历史记录；用户随后确认的 CentOS 结果见 `docs/VALIDATION.md`，不能把该记录直接用于另一份二进制。
