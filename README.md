# OpenWrt Build

使用 GitHub Actions 编译 OpenWrt，并自动将固件、内核模块和构建记录发布到 GitHub Releases。

## 开始构建

1. 将仓库推送到 GitHub，并在仓库设置中启用 Actions。
2. 在 **Actions → 构建并发布 OpenWrt → Run workflow** 选择设备。
3. 按需勾选 Passwall 或大鹅 Dashboard，然后运行。每次运行构建一个设备目标。
4. 从 **Releases** 下载固件；Actions 运行产物保留 7 天。

工作流使用 GitHub 自动提供的 `GITHUB_TOKEN`。发布 job 已申请 `contents: write`，无需另设 PAT 或 Secrets；仓库策略须允许该权限。

## 构建目标

| 工作流选项 | 固件源码 | 设备与镜像 |
| --- | --- | --- |
| `redmi_ax6_immwrt` | [VIKINGYFY/immortalwrt](https://github.com/VIKINGYFY/immortalwrt)，`main` | Redmi AX6：标准版与 stock 版 |
| `redmi_ax6_libwrt` | [LiBwrt/openwrt-6.x](https://github.com/LiBwrt/openwrt-6.x)，`25.12-nss` | Redmi AX6：标准版与 stock 版 |
| `redmi_ax6000_immwrt` | [padavanonly/immortalwrt-mt798x-6.6](https://github.com/padavanonly/immortalwrt-mt798x-6.6)，`openwrt-24.10-6.6` | Redmi AX6000：ubootmod 分区布局 |

刷机前确认设备及分区布局。AX6 标准版、stock 版和 AX6000 ubootmod 镜像不能互刷。AX6 自动启用 NSS 配置。

## 目录结构

```text
.
├── .github/
│   ├── workflows/build.yml       # GitHub Actions 构建与发布
│   └── scripts/                  # 源码准备、配置校验与产物打包
├── profiles/                     # 构建目标、源码分支与平台定义
├── configs/
│   ├── common.config             # 所有设备共用的编译配置
│   ├── devices/                  # 设备专属配置
│   └── features/                 # NSS、Passwall、大鹅等可选配置
├── feeds/                        # 第三方软件源
├── files/                        # 固件默认文件；设备专属目录按需添加
│   ├── common/                   # 所有设备共用
│   ├── ax6immwrt/                 # AX6 · ImmortalWrt 固件文件
│   ├── ax6libwrt/                 # AX6 · LiBwrt 固件文件
│   └── ax6000/                   # AX6000 固件文件
└── patches/                      # 上游源码和软件包补丁
```

## 默认配置

- 默认 LAN 地址为 `192.168.169.1`，仅在首次初始化或恢复出厂设置时写入。
- 包含常用网络与系统插件、Argon 主题，以及设备配置中启用的驱动和功能。Passwall 与大鹅 Dashboard（含 dae）由工作流选项控制，默认关闭。
- AX6 首次初始化时为尚未设置加密的无线接口设置 `Redmi_AX6` / `Redmi_AX6_5G`，密码为 `12345678`；已有加密设置不会覆盖。AX6000 使用上游无线默认值。
- AX6 保留 NSS 及相关性能配置；AX6000 保留 HNAT 负载显示。

## 修改配置

| 目的 | 文件 |
| --- | --- |
| 修改源码仓库或分支 | `profiles/*.conf` |
| 调整所有设备共用的软件包 | `configs/common.config` |
| 调整设备专属配置 | `configs/devices/*.config` |
| 调整 NSS、Passwall 或大鹅 | `configs/features/*.config` |
| 添加第三方软件源 | `feeds/custom.conf` |
| 修改固件默认文件与初始化设置 | `files/common/` 或对应目标的 `files/ax6immwrt/`、`files/ax6libwrt/`、`files/ax6000/` |
| 修复上游源码或软件包 | 参见 [`patches/README.md`](patches/README.md) |

配置按设备、公共配置、平台功能、所选可选功能的顺序合并，再由 `make defconfig` 解析；关键设备和功能选项若未生效，构建会失败。

## 发布内容

Release 包含设备镜像、manifest、`profiles.json`、配套内核模块归档及构建记录：

- `build.config`：依赖解析后的实际编译配置；`requested.config`：合并后的配置输入。
- `build-info.json` 与 `sources.lock`：构建参数及源码、软件源提交记录。
- `SHA256SUMS`：发布文件校验和，可用 `sha256sum --check SHA256SUMS` 验证。

每次构建记录实际使用的上游提交，但不会锁定后续构建的版本；同一仓库提交在不同日期构建可能使用不同的上游代码。构建失败时，可从 Actions 运行记录下载日志和配置文件（保留 7 天）。

## 来源与许可

本项目从 [aguowork/wrt_release](https://github.com/aguowork/wrt_release) 重构，保留原项目许可及迁移文件中的作者声明。详见 [LICENSE](LICENSE)。
