# CentOS 7 旧终端兼容模式

日期：2026-10-16。随 `0.1.0-brand.3` 提供，复用 brand.2 的品牌程序，不需要在 CentOS 编译。

## 证据与边界

用户截图确认 brand.2 标题 `XunChi` 已生效，但退出后仍有 `>0q`、`?2026$p`、`?u`、`opentui-notifications` 等序列。它们与 OpenTUI 0.4.5 的终端探测定义相符，不是中文文本的编码结果。

上游定义：[ansi.zig](https://github.com/anomalyco/opentui/blob/v0.4.5/packages/core/src/zig/ansi.zig) 的 `xtversion`、`capabilityQueries`、`notificationQueries`；[terminal.zig](https://github.com/anomalyco/opentui/blob/v0.4.5/packages/core/src/zig/terminal.zig) 的 `queryTerminalSend` 和环境开关实现。

仅凭截图，不能确定每一条序列的具体泄漏时刻，也没有实测目标 VTE 版本。本修复在传输层阻止这些协议到达旧终端，并恢复退出状态；不将 WSL 测试写成 CentOS 实机修复成功。

## 实现

`start.sh` 在交互式终端默认使用 Python 3.6 标准库的 `terminal_compat.py`，通过独立 PTY 运行现有程序。当前目录、环境配置和启动参数保持传递，不记录提示词、凭据或对话。

- 按完整 escape record 解析输出，支持一个序列跨多次读取；中文 UTF-8 普通字节不解码、不改写。
- 拦截现代 DECRQM/XTVERSION/Kitty 键盘探测、同步输出模式、DCS/APC/PM 以及 OSC 22/52/66/99/1337。旧终端不提供对应协议能力，不能再将这些协议当作可用功能。
- 关闭 OpenTUI 已有的图形、通知和显式字符宽度探测。没有虚构环境变量，也没有改第三方二进制。
- 保留窗口标题、颜色和光标绘制。保留传统按键及 SGR 鼠标序列。显式开启 bracketed paste，避免探测被拦截后丢失多行粘贴的边界。
- 传递尺寸变化，支持子进程暂停后恢复；正常退出、子程序异常结束或外部 SIGTERM 时恢复原 tty 属性，关闭鼠标/焦点/粘贴模式，恢复主屏和窗口标题。不通过清屏隐藏问题。
- 非交互式输入/输出直接执行原程序，不过滤管道或机器可读输出。返回原程序的退出码。

OSC52 被禁用，不等于已经验证系统剪贴板复制成功；原生 clipboardy/xclip 等路径仍需目标机验收。图片终端协议不属于旧终端模式的功能。

## 切换与回退

默认无需输入额外参数，仍使用 `xunchi-agent-centos7`。

排查时可对一次启动设置 `XUNCHI_TERMINAL_PROFILE=native`，跳过兼容层。只用于对照，不表示旧终端问题已解决。

旧 brand.1/brand.2 安装目录和 `opencode-centos7` 保留，完整回退方式见 `INSTALL_BRANDING.md`。不要修改 PDK、模型配置或 Virtuoso 来解决终端显示问题。

## 已验证

- 五项 Linux 测试：分片序列过滤、超长/截断控制记录不泄漏、真实 PTY 中文及多行粘贴往返/尺寸变化/退出码/属性恢复、外部 SIGTERM 的退出与恢复、非交互输出保持。
- 真实 brand.2 TUI 加兼容层，在 WSL 独立 tmux/HOME 中：主页和 `XunChi` 标题可见，中文粘贴到输入框可见，未提交模型提示；正常退出后 tty 属性与启动前一致，原始输出中未发现上述关键探测序列。
- Python 3.6 语法检查不等于已经在目标 Python 3.6 运行通过。

## 待目标机验收

在新终端中安装 brand.3，启动后检查中文输入、Ctrl+Shift+V、滚动、窗口调整，再正常退出并观察新产生的输出。旧终端里已经留下的乱码不会被追溯删除，可新开终端检查。仍需确认输入法、鼠标、系统剪贴板复制、会话恢复及 DeepSeek 请求。

更新状态（2026-10-16）：用户已确认 CentOS 7 中退出不再出现乱码，且当前 agent 可以操控 Virtuoso。此反馈不替代系统剪贴板、完整工具封装或设计质量验收。内部包没有附于本次公开源码更新。
