# 启动页品牌定制

这轮将“迅驰公司 Logo 和产品身份”调整为产品开发的首个可见交付项。

## 设计

- 公司名称：苏州迅驰信息科技有限公司。
- 启动页产品名：`xunchi-IC-agent`；启动命令保持为 `xunchi-agent-centos7`。
- 蓝色标志：依据用户提供的 Logo 左侧图形生成双色半块字符近似；不是重新设计公司标志。
- 宽终端展示英文公司名称；较窄终端隐藏英文，再隐藏图形，保留产品名。
- 启动页任务示例改为工程环境检查、器件参数核对和验证报告总结。

原图原样保存在 `assets/company-logo.reference.png`，其哈希记录在 `branding/provenance.json`。原图只读，没有覆盖、裁剪或重新编码该文件。字符近似的采样区域和颜色配置记录在 `branding/brand.json`。

## 为什么使用字符版本

目标是现有 CentOS 7 终端，不依赖 Kitty/Sixel 等终端图片协议。字符版本沿用上游 Logo 已使用的半块字符方案。字体、中文字符宽度和颜色仍需实机测试，不能仅依据浏览器预览认定适配成功。

## 修改范围

补丁 `patches/0002-xunchi-home-branding.patch` 针对锁定的上游提交，修改：

1. `packages/tui/src/component/logo.tsx`：替换启动页 Logo 组件。
2. `packages/tui/src/routes/home.tsx`：替换三个启动页任务示例。

补丁 `patches/0004-xunchi-terminal-identity.patch` 继续修改：

1. `packages/tui/src/app.tsx`：首页终端窗口标题为 `XunChi`；已有会话为 `XunChi | 会话名`；插件页面使用相同前缀。桌面任务栏通常跟随终端窗口标题。
2. `packages/tui/src/util/presentation.ts`：退出摘要显示 `XunChi`，会话恢复提示使用 `xunchi-agent-centos7 -s ...`，没有会话 ID 时使用 `-c`。
3. 同步已有退出摘要测试中的恢复命令。

没有修改 agent 能力、模型实现或底层 CLI 命令名称。第三方许可中的上游来源继续保留。此补丁不修改终端能力探测，也不代表退出乱码已经解决。

## 开发预览与复现

`branding/startup-preview.html` 是静态布局预览。它没有连接模型、Virtuoso 或实际 OpenCode；图片中的交互、底部状态和版本位置为布局示意，不是当前 TUI 的实际运行截图。

`tools/build_branding.py` 需要开发环境中的 Pillow；读取原图和固定版本源文件，生成终端 Logo 源码、补丁和静态 HTML。生成后的 TUI 组件不依赖 Pillow 或图片解码器。

`tools/render_branding_preview.cjs` 使用开发环境 Playwright 生成不同宽度的预览截图，检查页面错误和横向溢出。它不能代替真正的 TUI 测试。

## 生效条件

首版 `0.1.0-brand.1` 已完成 WSL 构建与启动检查；用户后续提供的 CentOS 7 截图确认首页公司 Logo 和产品名已显示，但窗口标题和退出摘要仍是上游标识。`0.1.0-brand.2` 补上上述两处身份，并使用独立目录安装。具体构建和验证结果见 `VALIDATION.md`，安装见 `INSTALL_BRANDING.md`。

安装器将新版本放入独立目录，版本检查通过后添加 `xunchi-agent-centos7` 的托管入口，提供回退命令。随后在 CentOS 7 检查启动、窄窗口、低窗口高度、中文、输入框、模型请求和恢复会话；`opencode-centos7` 保留原有运行版本作为回退。

## 发布边界

公司 Logo 不是因 OpenCode 使用 MIT 许可就自动成为开源资源。当前资产保存在本地内部开发目录，未上传原公开仓库；后续对外发布由公司确定品牌资产的使用范围。

更新状态（2026-10-16）：用户已确认 CentOS 7 中退出不再出现乱码，且当前 agent 可以操控 Virtuoso。此反馈不替代系统剪贴板、完整工具封装或设计质量验收。内部包没有附于本次公开源码更新。
