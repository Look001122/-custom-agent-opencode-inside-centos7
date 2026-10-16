# 架构与开发接口

```text
工程师（CentOS 原生 TUI）
  → xunchi 启动器 / 项目配置
  → 固定版本 OpenCode + DeepSeek
  → xunchi 自定义工具【待接入】
       → bridge 适配器【待实现】 → 现有 Virtuoso 会话
       → 任务执行器【已有原型】 → EDA 环境脚本 → CDL/GDS/Calibre
       → 结果与修改记录【部分原型】
```

## 内核和自研能力

第一阶段保留已验证的 musl 兼容内核，自研能力放在启动、工具、执行和报告层。内核源码修改仅处理确有需要的 TUI 行为，例如剪贴板和产品展示。每次上游升级均重新测试，不自动跟随最新版本。

`upstream.lock.json` 固定 v1.19.0 的提交。品牌补丁已有 Linux musl 构建和 WSL 启动检查，剪贴板补丁仍未编译；品牌和退出兼容层已由用户在 CentOS 7 确认，系统剪贴板与更完整的多机回归仍需单独验收。

## 环境边界

启动器仅在 OpenCode 子进程环境中清除 `LD_LIBRARY_PATH` 和 `LD_PRELOAD`。不会在用户登录 shell 中覆盖它们。

EDA 动作在独立进程中显式加载公司配置的环境脚本。脚本属于受信任部署资产；不把 `/proc/PID/environ` 简单转成可执行 shell，也不打印整份环境。API Key 通过环境传入引擎，不能作为动作命令行参数，以免进入进程列表和运行记录。

原型没有实现日志自动脱敏和认证隔离。任务记录默认放在用户私有目录；正式内部部署需检查日志访问范围，且不要在动作输出中主动打印凭据。

## 原型动作配置

`actions` 由部署者配置，agent 后续只提交动作名及受约束的参数，不自行改写动作注册表。当前只有开发接口，尚无 agent 工具注册与强制约束。

示意动作（不代表真实 EDA 动作已实现）：

```json
{
  "actions": {
    "check-runtime": {
      "argv": ["/usr/bin/python3", "-c", "print('runner ready')"],
      "timeout_seconds": 10,
      "mutates_design": false,
      "validation": "process"
    }
  }
}
```

动作以参数数组执行，不通过临时拼接的 shell 命令。支持 `{run_dir}` 和 `{project_root}` 路径占位符。工作目录始终是新的任务目录；真实 EDA 动作需要显式指定工程的 `cds.lib` 和全部输入绝对路径。

`--run ACTION` 立即返回新任务目录；`--job DIRECTORY` 查询状态。正式 agent 工具需直接调用这些接口，避免把这两条命令交给工程师代跑。

任务目录包含 `request.json`、`status.json`、`worker.json`、`worker.log` 和 `process.log`。任务设置独立进程会话，工具客户端退出不会直接发送终端挂断信号；机器重启、进程被杀等情况不保证继续执行。工作进程消失且没有最终状态时，查询返回 `unknown`。

工作进程使用超时控制，并在超时后终止该动作的进程组。自行再次脱离进程组的外部程序仍需专门的管理方案。请求文件和动作脚本均不应含密钥。

## 结果语义

| 字段 | 含义 |
|---|---|
| state=queued/running | 尚未结束 |
| state=completed | 进程退出码为 0，不代表设计通过 |
| state=failed | 启动或执行失败 |
| state=timed_out | 执行器确实触发了超时终止 |
| state=unknown | 无法确认最终运行状态 |
| validation=correct/incorrect | 受支持格式的 LVS 总结结果 |
| validation=unknown/not_tested | 缺少有效报告，或没有进行该类验证 |
| design_modified=not_verified | 当前通用执行器无法验证设计未变化 |

目前 LVS 适配器只是保守的文本解析原型，适用于含 `OVERALL COMPARISON RESULTS` 的格式；并非所有 Calibre 版本/层级报告的完整解析器。不能识别时明确返回 unknown。DRC 总结果数解析尚未实现。

## 下一个必须完成的接口

1. OpenCode 工具适配器：提交/查询 job，接口错误原样可追踪，不由模型编造成功。
2. bridge 适配器：认证、会话 PID、cellview、实际 PDK 目录读回。
3. EDA 动作：输入可读性、哈希、层映射、源/版图顶层名与规则入口检查。
4. 修改接口：完整目标身份、备份/工作副本、前后差异、保存及独立读回。
5. 完整验证器：报告完成标志、顶层比较、器件/端口/网络/参数差异、输入前后校验。

目标是用工具输出形成事实，再让模型解释事实；仅添加提示词不能替代这些接口。

## 用户现有 Virtuoso 环境

用户已确认当前 agent 可操控 Virtuoso；上图“待实现”指本目录独立封装的 bridge 工具适配器，并非否认用户现有桥接通道可用。本公开目录未捆绑该通道及其环境，不能直接据此完成全新 EDA 机器部署。

更新状态（2026-10-16）：用户已确认 CentOS 7 中退出不再出现乱码，且当前 agent 可以操控 Virtuoso。此反馈不替代系统剪贴板、完整工具封装或设计质量验收。内部包没有附于本次公开源码更新。
