# 安装模型连接管理版

版本：`0.2.0-connections.1`。使用普通 IC/EDA 用户，无需 sudo 或 su。

将成品压缩包、同名 `.sha256` 和 `install-connections.sh` 放在同一目录。共享目录映射正确时，执行：

```bash
bash /mnt/hgfs/VMwareShare/xunchi-branding-release/install-connections.sh
```

安装器校验全部文件，将本版放入新的 `~/.local/opt/xunchi-IC-agent-0.2.0-connections.1`，引擎版本检查通过后备份 `.bashrc` 并更新托管入口。旧版目录、原 `opencode-centos7`、模型配置和设计文件不覆盖。

安装后正常退出旧程序，打开新终端运行：

```bash
xunchi-agent-centos7
```

不会再在普通 shell 中询问 Bailian API Key。没有连接时自动显示中文连接菜单，可按 Esc 返回首页。使用 `/connections` 或 `/connect` 添加、编辑、删除、切换连接及设置默认连接。

已有标准 JSON 配置会只读导入：优先已有 `OPENCODE_CONFIG`，其次 `~/opencode-bailian-v1.json`，否则尝试原生用户目录的 `opencode/opencode.json`。已有百炼连接若通过环境变量读取密钥，而当前变量未设置，会标记“需要配置密钥”。在连接菜单选择该连接 → 编辑连接/更新密钥 → 在本机记住密钥，保存一次即可；原配置文件不修改。

支持 OpenAI 兼容 Chat Completions、OpenAI Responses 和 Anthropic Messages。填写服务商提供的完整 Base URL 和准确模型 ID；保存后可获取模型列表或测试连接。测试会发送少量请求，工具测试不执行任何工具。

密钥可以在本机记住、仅本次运行或不使用。记住的密钥在个人私有文件中以 0600 权限明文保存，不是加密存储；临时密钥在正常退出时清理。不同员工使用各自 Linux 用户或虚拟机。

详细字段、导入限制和测试范围见 `CONNECTIONS.md`。本版仍保留旧终端兼容层。开发测试使用 WSL 和本机模拟模型服务，不能替代目标 CentOS、真实中转站及实际工具能力验收。

## 回退

新开终端使用 `opencode-centos7` 可继续原版本。移除新托管入口：

```bash
python3 "$HOME/.local/opt/xunchi-IC-agent-0.2.0-connections.1/install.py" --rollback
```

该操作不删除安装文件、已保存连接或凭据，不停止 Virtuoso。上一版仍可按实际路径直接启动，例如：

```bash
bash "$HOME/.local/opt/xunchi-IC-agent-0.1.0-brand.3/start.sh"
```