# xunchi-agent-centos7

面向公司内部工程师、运行在 CentOS 7 原生桌面中的 Virtuoso 助手。

**当前状态：基于固定 OpenCode 1.19.0 的 XunChi 定制开发。用户已在 CentOS 7 确认品牌界面、标题、中文交互和退出乱码修复，并反馈当前 agent 可以操控 Virtuoso。内部成品为 0.1.0-brand.3；公开目录提供源码和复现材料，完整产品及独立部署仍在开发。**

产品目标：工程师在 TUI 中输入任务，agent 自行确认工程、操作工作副本、执行导出和验证，并返回具体修改对象及实际报告。减少人工转抄命令、辨认版图版本和追查任务是否执行的时间。

## 这次建立了什么

- 独立的 `xunchi-agent-centos7` 启动入口，复用已有兼容内核和模型配置；转发 `-c` 等 OpenCode 参数，保留调用时的工作目录。
- 本地部署配置：引擎位置、工程身份、指定 PDK 堆栈和 EDA 环境脚本分别配置，不把个人模型地址或 Key 写进源码。
- 检查器：输出引擎、配置、中文环境及本地辅助程序的检查结果。文件存在不会被描述为功能通过。
- 执行记录原型：注册动作以独立进程运行，保存任务状态、实际退出码、日志、报告哈希及目标身份。查询结果不依赖模型记忆。
- 最小 LVS 报告适配器：区分 `completed + incorrect` 与 `completed + correct`；退出码为 0 不等于 LVS 一致。不认识的报告返回 `unknown`。
- 一份针对上游 1.19.0 的 OSC52 复制协议开关补丁。**现有二进制尚未包含此补丁；设置环境变量本身不会修好旧二进制。**
- 迅驰公司启动页的字符 Logo、`xunchi-IC-agent` 产品名和任务示例，已构建进 Linux x64 musl 程序，并准备独立安装和回退脚本。见 [品牌定制说明](docs/BRANDING.md)及[安装说明](docs/INSTALL_BRANDING.md)。

执行器当前只接收配置中声明 `mutates_design=false` 的动作。这是开发阶段的功能限制，并非文件系统沙箱：信任本地配置和脚本，不能据此保证任意程序不会修改设计。

## 尚未实现

OpenCode 自定义工具接入、bridge 身份认证/复用、真实 PDK 核对、CDL/GDS/Calibre 动作封装、版图修改事务及读回、DRC 解析、会话交接、完整产品部署流程、完整的多机回归、剪贴板源码补丁的编译和系统剪贴板实机验证。

目标机退出乱码已由用户确认解决；这不等于所有系统剪贴板路径已验收，也不代表 agent 已自主完成整个版图流程。后续建设顺序及验收条件见 [开发路线](docs/PRODUCT_PLAN.md)。

`brand.3` 的旧终端兼容模式在传输层屏蔽 OSC52 和不支持的探测，未将 `0001` 编译进程序。退出显示、中文输入和系统剪贴板的目标机验收应分别记录，见 [终端兼容说明](docs/TERMINAL_COMPAT.md)。

## 开发目录

```text
bin/                 新入口，不覆盖旧 opencode-centos7
src/xunchi.py        启动与环境检查
src/jobs.py          任务提交、独立执行、查询与最小 LVS 结果解析
config/              不含个人信息的部署模板
patches/             对固定版本的上游源码补丁
docs/                需求、架构、实机验收清单
tests/               不依赖 Cadence 的进程及结果语义测试
upstream.lock.json   上游版本与提交号
```

## 开发验证

项目使用 Python 3.6 标准库范围内的接口。开发机测试命令：

```sh
python3 -m unittest discover -s tests -v
```

POSIX 进程测试需要 Linux。WSL 测试只能验证进程机制，不能替代 CentOS 7、输入法或 Cadence 的实机验收。

将模板复制至用户自己的 `~/.config/xunchi-agent-centos7/deployment.json` 后，可通过开发底座入口的 `--doctor` 检查。底座入口尚未集成进品牌运行包；品牌运行包使用 `deploy/` 中的独立安装器，备份并更新托管 alias，保留 `opencode-centos7`。两者的功能范围不能混为一谈。

## 数据和分发

本目录按用户要求公开技术改造源码和说明；内部成品包没有随本次更新公开。实际部署配置、API Key、公司 PDK、原理图、版图和运行日志不随源码发布。`.gitignore` 只是降低误提交概率，不能替代发布前检查。

自研部分的权属及许可证由公司确认后补充。本目录没有为公司代码擅自指定开源许可。OpenCode 部分继续保留其 MIT 许可；运行时库、桥接组件和各依赖分别遵循其原许可，见 [第三方说明](THIRD_PARTY_NOTICES.md)。

代码许可沿用仓库根目录 LICENSE；品牌素材说明见 [第三方与品牌说明](THIRD_PARTY_NOTICES.md)。构建流程见 [BUILD.md](docs/BUILD.md)。
