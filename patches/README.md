# 补丁

- `source/common/`：所有目标；`source/<platform>/`：平台目标；`source/<device>/`：指定设备。按 common、平台、设备顺序应用，目录内按文件名排序。
- `packages/<package>/`：软件包补丁，需在 `.github/scripts/customize.sh` 中配置安装路径。

源码补丁相对于 OpenWrt 根目录。构建时先检查并应用；若上游已包含补丁则跳过，否则报错。

| 补丁 | 作用 |
| --- | --- |
| `source/common/100-luci-cpuusage.patch` | LuCI 优先使用 `/sbin/cpuusage`。 |
| `source/redmi_ax6_immwrt/110-netfilter-dependency.patch` | 调整 AX6 ImmortalWrt 的 iptables 依赖。 |
| `packages/opkg/001-fix-provides-version-parsing.patch` | 修复 opkg 的 `Provides` 版本解析。 |
| `packages/miniupnpd/999-default-leaseduration.patch` | 调整 UPnP 端口映射租期。 |
