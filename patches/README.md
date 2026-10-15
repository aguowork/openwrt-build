# 补丁维护

`source/` 下的补丁相对于 OpenWrt 源码根目录，按 **common → 平台 → 构建目标** 的顺序执行，每个目录内按文件名排序。

| 补丁 | 适用范围 | 用途 |
| --- | --- | --- |
| `source/common/100-luci-cpuusage.patch` | 三个目标 | LuCI 优先调用固件内的 CPU / 硬件加速负载脚本 |
| `source/nss/100-netfilter-legacy.patch` | 两个 AX6 目标 | 按 Linux 6.12 前后区分 legacy iptables 模块 |
| `source/redmi_ax6_immwrt/110-netfilter-dependency.patch` | AX6 ImmortalWrt | 调整 Linux 6.18 下重复的 iptables 依赖 |
| `packages/opkg/001-fix-provides-version-parsing.patch` | 源码包含 opkg 时 | 保留原项目的 Provides 版本解析修正 |
| `packages/miniupnpd/999-default-leaseduration.patch` | UPnP 包 | 保留原项目的端口映射租期设置 |

源码补丁先执行 `git apply --check`，上游已经应用的补丁会通过反向检查识别并跳过。两种检查都失败时停止构建，并在日志中给出补丁路径。

软件包补丁放入对应包的 `patches/`，在 OpenWrt 下载、准备软件包时应用。它们与 `source/` 补丁的执行阶段不同，包版本升级后需要检查补丁是否仍适用。
