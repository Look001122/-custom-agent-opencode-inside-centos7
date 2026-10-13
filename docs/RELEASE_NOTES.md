# OpenCode 1.19.0 / CentOS 7 handoff r1

适用于把已验证的 CentOS 7 OpenCode 环境交接给另一位使用者。

- 官方 linux-x64-musl 二进制，配套独立 musl、libgcc 和 libstdc++。
- 默认关闭旧终端有问题的显式字符宽度协议。
- 交互式百炼配置，默认模型 deepseek-v4.1-flash。
- 无需 sudo；无需修改系统库；模型 Key 由接收者自己输入。
- 附完整来源记录、许可证、诊断步骤及 SHA256 校验。

下载 `opencode-centos7-1.19.0-r1.tar.gz` 和同名 `.sha256`，按仓库 README 启动。
原始二进制和适配方法已经在 CentOS 7.7 / glibc 2.17 目标机通过版本、TUI、模型请求和 Bash 工具调用验证。修订脚本和交接包另经 Linux 启动验证，不代表全部 CentOS 7 环境均兼容。

本版本不包含个人 API Key、业务空间地址、账号文件、会话数据、Virtuoso、PDK 或设计文件，也未包含 Virtuoso bridge 安装。
