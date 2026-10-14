# 故障排查

## 1. 解压或进入目录失败

确认下载文件的实际位置。`.tar.gz` 是压缩文件，不能直接执行，也不能 `cd` 进入；先解压，再进入目录。

```bash
ls -l "$HOME/opencode-centos7-1.19.0-r1.tar.gz"
```

新版打包设置了正常文件时间，修正早期包的 1970 年时间戳警告。

## 2. 界面出现 66;w=1; 等乱码

本包启动器已默认关闭显式字符宽度协议。如果之前在终端手动设置过该选项，可以显式覆盖：

```bash
OPENTUI_FORCE_EXPLICIT_WIDTH=0 bash "$HOME/opencode-centos7-1.19.0-r1/start.sh"
```

参见上游 [OpenTUI issue #1383](https://github.com/anomalyco/opentui/issues/1383)。

## 3. Cannot connect to API

先查看路由和 DNS：

```bash
ip route
cat /etc/resolv.conf
```

`ip route` 应包含有效的 `default via ...`。若缺失，应先修复虚拟机联网。
`Resolving timed out` 表示解析阶段超时；`Network is unreachable` 表示当前没有可用路由。

从百炼控制台复制正确的 Base URL，在下面命令中替换示例地址。测试不发送 Key：

```bash
curl -4 -I --connect-timeout 10 --max-time 20 \
"https://YOUR_WORKSPACE_ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions"
```

收到 HTTP 响应说明 HTTP 连接已经建立。未携带 Key 时返回 `401` 属于预期；这不证明实际模型调用已经成功。

不要照抄别人的网关、DNS 或固定服务器 IP。按自己的 VMware NAT/DHCP 配置确定。
参见 [百炼错误码](https://help.aliyun.com/zh/model-studio/error-code)。

## 4. 401 / 403 / 模型不存在

检查 Key、业务空间、地域、Base URL 与模型是否匹配。
本包默认模型是 `deepseek-v4.1-flash`。接收者需要确认自己的百炼账号提供这个模型。

## 5. 粘贴和中文输入

### 5.1 已验证的粘贴方法

2026-10-14 用户在目标机确认：普通终端能粘贴 `hello`，OpenCode TUI 输入框使用 **`Ctrl+Shift+V`** 也能粘贴。GNOME Terminal 还可使用菜单 Edit > Paste。

排查时，先在 **CentOS 本机文本编辑器**中输入并复制 `hello`，再分别粘贴到普通终端与 OpenCode 输入框。这样可以区分本机粘贴和 Windows/VMware 跨系统剪贴板问题。普通终端中的测试文字不需要执行，按 `Ctrl+C` 清空即可。

其他环境可检查 `command -v xclip xsel`；OpenCode 官方列出了 X11 剪贴板工具，但本次未取得这些工具的最终安装状态，不能据此认定目标机的成功依赖某个特定工具。

### 5.2 定位中文输入问题

在 **CentOS 普通终端**执行：

```bash
rpm -q ibus ibus-libpinyin ibus-gtk3 gnome-terminal
locale charmap
ibus engine
command -v xclip xsel gedit
printf 'GTK_IM_MODULE=%s\nXMODIFIERS=%s\nDISPLAY=%s\n' \
  "$GTK_IM_MODULE" "$XMODIFIERS" "$DISPLAY"
```

`locale charmap` 应显示 UTF-8 编码。保留包未安装、IBus 无法连接等错误，按实际结果处理。

打开 `gedit`，先测试中文输入：

- gedit 也不能输入中文：先检查输入法是否已安装、启用，并选择了中文引擎。
- gedit 可以、普通终端不可以：检查终端与输入法的配合。
- gedit 和普通终端都可以、OpenCode 不可以：继续检查 TUI 输入，不要重复安装输入法来代替定位。

### 5.3 在 GNOME 配置中文拼音

检查 `rpm -q ibus ibus-libpinyin`。仅当所需软件包缺失时安装：

```bash
sudo yum install ibus ibus-libpinyin
```

如果软件源、依赖或权限报错，应先解决该错误。软件包已经安装时无需重复安装。

打开输入源设置：

```bash
gnome-control-center region
```

在 **Region & Language > Input Sources** 点击 `+`，找到 Chinese / Chinese (China)，添加 **Chinese (Intelligent Pinyin)**。保留现有英文输入源。通过桌面输入源菜单选择中文，或使用 GNOME 默认的 `Super`（Windows 键）`+Space` 切换。若该按键被虚拟机宿主机截获，使用 CentOS 桌面菜单切换。

在 gedit 中输入 `nihao`，选择候选词“你好”；成功后再启动 `opencode-centos7`，点击输入框，用相同方式测试。若拼音引擎处于英文模式，需通过输入法菜单切换到中文模式。

本次用户先反馈 gedit 不能输入中文，后确认中文输入问题已解决。以上为复现指导；用户没有提供最终包版本、引擎状态或每一步执行记录，不能把全部步骤都列为已执行。验收应以目标机能实际输入中文为准。

### 5.4 临时备用方法

OpenCode 能读取 UTF-8 中文任务；暂时无法直接输入时，可以把任务写入文件，并输入 `Read /path/to/task.txt and follow its instructions.`。该方法是备用入口，不等同于直接中文输入已经修复。

参见 [GNOME Terminal](https://help.gnome.org/gnome-terminal/txt-copy-paste.html)、[OpenCode 粘贴排查](https://opencode.ai/docs/troubleshooting/#copypaste-not-working-on-linux) 与 [RHEL 7 GNOME 输入法配置](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/7/html/desktop_migration_and_administration_guide/internationalization)。

## 6. 排查日志与计费显示

```bash
bash "$HOME/opencode-centos7-1.19.0-r1/start.sh" --print-logs
```

日志与截图留在本机，分享前确认不含 Key 或私有任务内容。
自定义模型没有配置完整价格和上下文元数据时，侧栏的 `$0.00` 或 `0%` 不能作为费用或模型容量的依据；费用以百炼账单为准。
