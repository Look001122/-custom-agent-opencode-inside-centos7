# XunChi Agent 0.1.1：品牌与助手身份统一

本版本是现有 CentOS 7 安装的品牌升级。产品名称统一为 **XunChi Agent**；产品版本为 **0.1.1**，上游引擎仍为 **OpenCode 1.19.0**。

本仓库公开源码、补丁和历史构建记录，没有附带此版公司内部二进制。下方共享目录安装命令仅适用于已经获得完整内部包的环境，不是 GitHub 下载地址；自行构建见 [BUILD.md](BUILD.md)。旧 r1 Release 不包含此升级。

## 修改范围

- 首页、侧栏（包括内置插件）、窗口标题、TUI 帮助、命令行帮助标识、退出提示统一名称。`--version` 保留引擎版本号，产品版本在界面和 `/about` 展示。
- `/about` 展示公司、产品版本、OpenCode 来源及 MIT 许可证、当前服务商和模型 ID。
- 系统提示词加入产品身份。各模型默认提示词的开头同步修改，保留任务、工具、规划和权限规则。
- 通用身份说明进入每次请求的系统提示，包括自定义 agent；恢复旧会话时不改写历史消息。
- 产品身份与模型身份分开。实际模型、服务商继续由当前配置决定。

## 保留连接方式

安装器识别 `.bashrc` 中现有 `xunchi-agent-centos7` 的启动目录，把现有运行库、启动脚本和终端兼容层复制到独立新目录，再替换引擎。启动脚本会按字节核对，配置、密钥和会话文件不修改。

安装包包含两个引擎：原启动方式使用 legacy 引擎；已经启用连接管理器的安装使用 managed 引擎，保留原来的管理界面。安装器不会把一种连接方式切换成另一种。`opencode-centos7` 保留。

本升级不包含 PDK、原理图、版图、个人配置、密钥或私有模型地址。不会启动、停止或修改 Virtuoso。

## 安装

把整个发布目录放到 VMware 共享目录后，在普通 CentOS 用户终端执行：

```bash
bash /mnt/hgfs/VMwareShare/xunchi-branding-release/install-xunchi-identity.sh
```

成功后新开终端，运行原命令 `xunchi-agent-centos7`。不要同时运行旧的 `install-xunchi.sh`，那个入口属于连接管理器开发版本。

若启动命令没有使用标准 alias，自动识别会停止且不修改 `.bashrc`。可根据 `type xunchi-agent-centos7` 显示的安装目录指定：

```bash
bash /mnt/hgfs/VMwareShare/xunchi-branding-release/install-xunchi-identity.sh --current-dir /你的现有安装目录
```

回退到升级前的启动入口：

```bash
python3 "$HOME/.local/opt/xunchi-agent-0.1.1-identity.1/install_identity.py" --rollback
```

## 验证范围

构建检查、WSL 内的真实编译程序、隔离安装/回退测试及本机模拟接口请求证据记入 `BUILD.identity.json` 和对应验证记录。本机模拟接口验证系统提示和传输路径，不代表真实 DeepSeek 的回答验收。

CentOS 7 实机的启动、输入、退出和 Virtuoso 连接仍需目标机器验收。已有品牌版本的成功结果不能替代本版本实测。提示词会引导身份回答，但不能保证任意模型的每次回答均符合要求。

## 重建

固定上游 commit：`733b2c627e5aec39cb33cc22373bdce33053ef2c`，Bun 1.3.14。

legacy 源码按顺序应用补丁 0002、0003、0004、0006；managed 在此基础上应用 0005。可在具有完整固定依赖的全新源码目录运行 `tools/build_identity_linux.sh SOURCE BUN legacy`（或 `managed`）。两者分别在包目录执行类型检查，再设置 `OPENCODE_VERSION=1.19.0`、`OPENCODE_CHANNEL=latest`、`XUNCHI_BUILD_TARGET=linux-x64-musl` 构建。不修改上游协议版本号。引擎哈希与构建记录一致后，由 `tools/package_identity_release.py` 打包。
