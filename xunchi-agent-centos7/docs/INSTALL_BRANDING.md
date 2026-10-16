# CentOS 7 安装启动页定制版

本说明用于已经构建成功的 `xunchi-IC-agent-0.1.0-brand.3.tar.gz`，不能用源码压缩包替代。

## 准备

使用普通 EDA 用户安装，不需要 sudo 或 su。将成品压缩包及同名 `.sha256` 文件放进 CentOS 可访问的同一目录，或通过 VMware 共享目录访问。

## 安装

若成品包与 `install-xunchi.sh` 都已放入共享目录的 `xunchi-branding-release` 子目录，推荐在 CentOS 普通终端执行一条命令：

```bash
bash /mnt/hgfs/VMwareShare/xunchi-branding-release/install-xunchi.sh
```

此路径取决于实际共享目录映射；脚本必须与成品压缩包和校验文件放在同一目录。脚本自动校验、在新的临时目录解压并安装。

也可以在成品包所在目录逐条执行：

```bash
sha256sum -c xunchi-IC-agent-0.1.0-brand.3.tar.gz.sha256
tar -xzf xunchi-IC-agent-0.1.0-brand.3.tar.gz
python3 xunchi-IC-agent-0.1.0-brand.3/install.py
```

校验失败时停止，不继续解压/安装。目录已存在时应先确认其来源，避免重复覆盖解压。

安装器验证文件、复制到新的用户目录、执行版本检查，通过后才备份并更新 `.bashrc` 中由它管理的 `xunchi-agent-centos7` 入口。已有同名旧 alias 保留在原位置，末尾的托管入口会覆盖它。

安装成功后，打开一个新的普通终端，输入：

```bash
xunchi-agent-centos7
```

页面蓝字为 `xunchi-IC-agent`。恢复会话可使用 `xunchi-agent-centos7 -c`，但检查新启动页时应先不带 `-c`，否则可能直接恢复到对话页面。

本次更新：主页窗口标题为 `XunChi`，进入已有会话后为 `XunChi | 会话名`；任务栏跟随窗口标题。退出摘要也改为 `XunChi`，恢复提示使用兼容启动命令。brand.3 增加旧终端兼容层，拦截不支持的探测并恢复退出状态；该修复已通过 WSL 测试，仍待 CentOS 7 实测。

已经安装 `brand.1` 或 `brand.2` 时，本安装器将 `brand.3` 放入新的目录并更新托管入口，不覆盖旧版。当前运行的旧进程仍是旧程序；安装后需正常退出，打开新终端再启动。

默认复用 `~/opencode-bailian-v1.json`；配置在其他位置时使用已有 `OPENCODE_CONFIG`。API Key 已在环境中时直接复用，否则会隐藏输入提示，不写入安装包或配置。

## 原版本和回退

`opencode-centos7` 的定义和原安装目录不变。现有 OpenCode 会话数据由上游管理，本包没有迁移或重写会话。

新版本仍需要实机检查 Logo、中文字符、输入、模型请求和会话恢复。发现问题时可继续用旧命令，并执行：

```bash
python3 "$HOME/.local/opt/xunchi-IC-agent-0.1.0-brand.3/install.py" --rollback
```

再打开新终端。该操作只移除托管启动入口，不删除安装文件，不停止 Virtuoso。

更新状态（2026-10-16）：用户已确认 CentOS 7 中退出不再出现乱码，且当前 agent 可以操控 Virtuoso。此反馈不替代系统剪贴板、完整工具封装或设计质量验收。内部包没有附于本次公开源码更新。
