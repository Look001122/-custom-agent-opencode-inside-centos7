# 固定上游补丁

目标提交：`733b2c627e5aec39cb33cc22373bdce33053ef2c`（v1.19.0）。

`0001-opt-out-osc52.patch` 在 `writeOsc52()` 中添加 `XUNCHI_DISABLE_OSC52=1` 开关。未设置时保留上游行为；设置后跳过 OSC52 写出，但仍继续上游的本地复制路径。

此补丁针对旧终端出现 `52;c;...` 的问题。它没有修改本地复制失败时上游静默处理的行为，也不能保证本地剪贴板辅助程序可用。后续需补充失败提示、文件导出路径及真实终端验收。

对于上述 `0001` 剪贴板修复，目前只准备了源码补丁。它不是已修复的可执行文件，也不是通过在旧二进制旁设置环境变量就能生效的插件。

`0002-xunchi-home-branding.patch` 替换启动页 Logo 组件和任务示例；公司图形以双色半块字符显示，保留产品名并按宽度简化。生成来源、原图和预览见 `docs/BRANDING.md`。此补丁已构建进 Linux x64 musl 程序，通过 WSL 启动检查，用户已在 CentOS 7 确认显示生效。

`0003-select-musl-build.patch` 为固定版本构建脚本添加显式 Linux x64 musl 单目标选择，避免 `--single` 默认跳过 musl。

正式流程：检出锁定提交 → 检查并应用补丁 → 在构建机编译 musl 目标 → 组合兼容运行库 → 在 CentOS 7 上检查中文、复制、粘贴与回归任务 → 版本化发布。

`0004-xunchi-terminal-identity.patch` 将窗口标题、退出摘要和恢复入口改为 XunChi。brand.3 的终端修复位于 `deploy/terminal_compat.py`，复用 brand.2 引擎，无需再编译该兼容层。用户已确认退出不再出现乱码。
