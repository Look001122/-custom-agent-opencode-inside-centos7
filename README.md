# OpenCode inside CentOS 7

在 CentOS 7 中运行 OpenCode 1.19.0，并通过阿里云百炼接入 DeepSeek LLM。

仓库保留原有 **r1 兼容适配工具包**：使用上游原始 musl 二进制、独立运行库和启动脚本；r1 的二进制保持不变。另新增基于固定版本源码定制的 **XunChi 开发目录**。上游项目：[anomalyco/opencode](https://github.com/anomalyco/opencode)。

## 2026-10-16 更新：XunChi

新增 [xunchi-agent-centos7](xunchi-agent-centos7/)：公司启动页、`XunChi` 窗口标题和退出摘要、`xunchi-agent-centos7` 启动入口、旧终端协议过滤、用户级安装/校验/备份/回退，以及相关测试和构建补丁。

用户已在目标 CentOS 7 确认：公司启动页和标题生效、退出后不再出现乱码，并可通过 agent 操控现有 Virtuoso 环境。开发环境全部 23 项 Python 测试通过，真实 TUI 中文粘贴及退出恢复检查通过。证据和边界见 [2026-10-16 更新记录](docs/UPDATES_20261016.md)。

本次公开的是源码、补丁、测试、模板和说明。公司内部品牌成品包没有附在本次 GitHub 更新中，`brand.3` 不在旧 r1 Release 里。已有内部包按 [安装说明](xunchi-agent-centos7/docs/INSTALL_BRANDING.md) 更新；源码开发见 [构建说明](xunchi-agent-centos7/docs/BUILD.md)。

## 已验证的目标环境

| 项目 | 已验证配置 |
|---|---|
| 系统 | CentOS Linux 7.7.1908 |
| 内核 | 3.10.0-1062.el7.x86_64 |
| 系统 glibc | 2.17 |
| CPU | x86_64，Intel i9-14900HX，支持 AVX2 |
| OpenCode | 1.19.0 官方 linux-x64-musl 构建 |
| LLM | 百炼 `deepseek-v4.1-flash` |

已在上述目标机验证版本命令、TUI、乱码修复、真实模型请求和 Bash 工具调用；2026-10-14 用户进一步确认 TUI 中文输入已解决，`Ctrl+Shift+V` 可以粘贴。这不是所有 CentOS 7 配置的兼容性保证。具体证据范围见 [验证记录](docs/VALIDATION.md)。

## 给另一位实习生：下载与启动

1. 打开本仓库的 [Releases](https://github.com/Look001122/-custom-agent-opencode-inside-centos7/releases)。
2. 下载 `opencode-centos7-1.19.0-r1.tar.gz` 和同名 `.sha256` 文件。GitHub 的 `Source code.zip` 是脚本源码，不包含可执行文件及运行库。
3. 将这两个文件放到自己的 CentOS 用户主目录，逐条执行：

```bash
cd "$HOME"
sha256sum -c opencode-centos7-1.19.0-r1.tar.gz.sha256
tar -xzf opencode-centos7-1.19.0-r1.tar.gz
cd opencode-centos7-1.19.0-r1
sha256sum -c SHA256SUMS
bash doctor.sh
bash start.sh
```

如果解压目录已存在，请选择一个新的空目录，避免覆盖已有安装。

`start.sh` 会提示输入两项：

- **Base URL**：从自己的百炼控制台“API 代码示例”复制完整 `base_url`，例如 `https://YOUR_WORKSPACE_ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`。
- **API Key**：使用自己的百炼 Key。输入时不显示字符是正常的。Key 只交给本次 OpenCode 进程，不写入安装包或仓库。

联网和模型服务访问需由接收者自己的环境提供；包内不包含可用的模型凭据。

启动后发送：

```text
Please reply with "Bailian connection successful". Do not call tools.
```

然后测试工具调用：

```text
Use Bash to run pwd and python3 --version. Report the actual outputs. Do not change files.
```

支持通过环境变量预先设置 `BAILIAN_BASE_URL` 和 `DASHSCOPE_API_KEY`，已设置时不再提示输入。不要把 Key 作为命令行参数或提交到 GitHub。

## 下次启动与恢复对话

在任何工作目录运行：

```bash
bash "$HOME/opencode-centos7-1.19.0-r1/start.sh" --continue
```

不带 `--continue` 则按 OpenCode 的默认方式启动。工作目录保持为你执行命令时所在的目录。

### 设置短命令 opencode-centos7

使用本仓库 r1 交接包时，在 **CentOS 普通 Bash 终端**执行一次：

```bash
cat >> "$HOME/.bashrc" <<'EOF'
alias opencode-centos7='bash "$HOME/opencode-centos7-1.19.0-r1/start.sh"'
EOF
source "$HOME/.bashrc"
```

如果已经设置过同名 alias，请在 `~/.bashrc` 中修改原定义，避免重复追加。安装位置不同时，应将 alias 内的路径改为自己的实际安装目录。

以后启动和恢复最近的对话只需：

```bash
opencode-centos7
opencode-centos7 -c
```

上面两条是分别使用的命令；恢复对话时执行第二条。alias 保留执行时的工作目录，只缩短启动命令；Base URL 和 API Key 的输入规则仍由 `start.sh` 管理。

本次用户的早期安装目录是 `~/opencode-centos7-1.19.0`，且已配置好百炼连接，使用的短命令定义为：

```bash
alias opencode-centos7='OPENTUI_FORCE_EXPLICIT_WIDTH=0 "$HOME/opencode-centos7-1.19.0/opencode"'
```

该定义复用现有 OpenCode 配置，不自动使用 r1 包的百炼模板。接收者应按自己安装的版本选择相应定义。

## 适配方法

- 在包内提供 musl、libgcc、libstdc++，通过包内加载器启动上游二进制。
- 默认设置 `OPENTUI_FORCE_EXPLICIT_WIDTH=0`，解决旧版终端出现 `66;w=1;` 等乱码的问题。无需每次手动加该变量。
- 无需安装 Node.js、Bun 或新的 Python 来运行这个成品包，也不需要 sudo。
- 启动器在 OpenCode 进程及其子进程中清除 `LD_LIBRARY_PATH`、`LD_PRELOAD`，避免混用 Cadence 的库环境。原 shell 和已运行的 Virtuoso 不受影响。以后若通过 agent 启动 Cadence 程序，需要在对应工具脚本中单独加载它的运行环境。
- 固定版本并关闭自动更新，升级时应重新验证配套运行库。

仅启动界面、不配置百炼时可以执行 `./opencode`。要使用包内百炼配置，请使用 `bash start.sh`。

## 网络与输入问题

虚拟机需要具备公网访问能力、默认路由和可用 DNS。VMware 的仅主机网络不能单独提供公网访问；可以添加 NAT 网卡，让已有仅主机网卡继续用于本机通信。网关和 DNS 必须按接收者自己的虚拟机配置确定。

本次目标机已确认：普通终端和 OpenCode TUI 输入框都可以通过 `Ctrl+Shift+V` 粘贴。中文输入需先在 CentOS 本机配置输入法；GNOME 中可添加 `Chinese (Intelligent Pinyin)`，先在 gedit 测试，再在 OpenCode 测试。输入法的配置说明见 [中文输入与粘贴](docs/TROUBLESHOOTING.md#5-粘贴和中文输入)。

这些设置在 CentOS 本机完成，不需要通过 Windows 浏览器输入。暂时不能直接输入中文时，也可把任务保存为 UTF-8 文件，再让 OpenCode 读取，例如本包的 `prompts/check-tools.txt`。

中文输入法属于桌面环境依赖，不随本成品包提供；缺少相关软件包时，安装它们需要系统包管理权限。

完整排查步骤见 [故障排查](docs/TROUBLESHOOTING.md)。

## 源码目录与本地打包

仓库保存启动脚本、通用配置、构建脚本、许可证和说明；大体积成品包放在 Release。

2026-10-14 的更新为使用文档和验证记录修订。已发布的 r1 Release 资产保持原样；下载旧包后，请同时参考仓库中最新的 README 和故障排查说明。

在有网络的构建机上，使用 Python 3.6+：

```bash
python3 scripts/build_bundle.py
```

构建脚本下载固定版本的官方文件，检查 SHA256，然后输出到 `dist/`。脚本只从允许的来源打包文件，不收集用户 HOME、会话历史、密钥、Virtuoso/PDK 或设计文件。

GitHub Actions 在发布工作流首次上传时自动构建，并发布 `v1.19.0-centos7.1`。也可在 Actions 中手动运行。工作流会先在 Linux runner 上验证启动器和配置，再上传成品包及校验文件；这不替代 CentOS 7 目标机验证。

## 当前范围

原 r1 包交付 OpenCode、终端兼容设置和百炼模板。2026-10-16 用户已确认其现有 agent 环境可操控 Virtuoso；这项反馈不代表本仓库已打包或自动配置 bridge、Cadence、Calibre、PDK、许可证服务或设计工程，也不代表任意版图任务均通过 DRC/LVS。新接收者仍需单独配置自己的 EDA 环境。

## 许可证与来源

本仓库新增脚本使用 [MIT](LICENSE)。随包提供的第三方程序和运行库保留各自许可证，见 [第三方说明](THIRD_PARTY_NOTICES.md)、`licenses/` 和 [固定来源清单](sources.lock.json)。
