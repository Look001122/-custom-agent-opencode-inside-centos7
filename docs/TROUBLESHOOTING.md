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

- GNOME Terminal 使用 `Ctrl+Shift+V` 或菜单 Edit > Paste。
- 先在 CentOS 文本编辑器中复制 `hello` 再尝试粘贴，以区分终端问题和 Windows/VMware 跨系统剪贴板问题。
- OpenCode 能接受 UTF-8 中文任务；输入法不可用时，把任务写入文件并输入 `Read /path/to/task.txt and follow its instructions.`。

参见 [GNOME Terminal](https://help.gnome.org/gnome-terminal/txt-copy-paste.html) 与 [OpenCode TUI](https://opencode.ai/docs/tui/)。

## 6. 排查日志与计费显示

```bash
bash "$HOME/opencode-centos7-1.19.0-r1/start.sh" --print-logs
```

日志与截图留在本机，分享前确认不含 Key 或私有任务内容。
自定义模型没有配置完整价格和上下文元数据时，侧栏的 `$0.00` 或 `0%` 不能作为费用或模型容量的依据；费用以百炼账单为准。
