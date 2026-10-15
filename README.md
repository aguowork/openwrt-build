# openwrt-build

通过 GitHub Actions 编译 OpenWrt，并把固件和配套内核模块发布到 GitHub Releases。

从 [aguowork/wrt_release](https://github.com/aguowork/wrt_release) 重构，保留三个构建目标、原设备配置、公共插件和主要默认设置。GitHub Actions 是唯一构建入口。

## 在 GitHub 上构建

1. 将本项目推送到自己的 GitHub 仓库默认分支，启用 Actions。
2. 打开 **Actions → 构建并发布 OpenWrt → Run workflow**。
3. 选择设备，按需勾选 **Passwall**、**大鹅 Dashboard**，然后运行。
4. 完成后到 **Releases** 下载固件；运行页面也保留 7 天的发布文件。

使用 GitHub 自动提供的 `GITHUB_TOKEN` 发布，无需额外配置 PAT 或 Secrets。工作流已为发布阶段声明 `contents: write`；组织仓库需要允许这一权限及所用的官方 Actions。

每次运行只构建一个目标。两个可选插件默认都不勾选，AX6 的 NSS 配置自动加载。

## 构建目标

| 目标 | 源码 / 分支 | 设备与镜像 |
| --- | --- | --- |
| `redmi_ax6_immwrt` | VIKINGYFY/immortalwrt · `main` | 红米 AX6，包含标准版和 stock 版 |
| `redmi_ax6_libwrt` | LiBwrt/openwrt-6.x · `25.12-nss` | 红米 AX6，包含标准版和 stock 版 |
| `redmi_ax6000_immwrt` | padavanonly/immortalwrt-mt798x-6.6 · `openwrt-24.10-6.6` | 红米 AX6000，**ubootmod 分区布局** |

刷机文件须匹配设备当前的分区布局，AX6 标准版、stock 版和 AX6000 ubootmod 镜像不能互换。

## 目录与维护位置

```text
.github/
  workflows/build.yml          唯一工作流：编译 → 打包 → 发布
  scripts/
    prepare.sh                 检出源码、组织各准备阶段
    feeds.sh                   更新 feeds、按清单同步插件
    customize.sh               当前设备和插件所需的兼容处理
    config.py                  合并配置、检查所选功能是否生效
    package.py                 校验产物、整理 Release
profiles/*.conf                各目标的源码、分支、设备配置及平台
configs/
  common.config                公共插件和编译选项
  devices/
    redmi_ax6_immwrt.config     AX6 · VIKINGYFY / ImmortalWrt
    redmi_ax6_libwrt.config     AX6 · LiBwrt
    redmi_ax6000.config         AX6000 · ImmortalWrt
  features/                    NSS、Passwall、大鹅配置
feeds/
  custom.conf                  第三方插件来源清单
  golang.conf                  Go 编译依赖的来源
files/
  common/                      所有设备的固件文件覆盖
  nss/                         AX6 的固件文件覆盖
  mt798x/                      AX6000 的固件文件覆盖
patches/                       有适用范围的源码、软件包补丁
```

配置合并顺序是 **设备 → 公共 → NSS（仅 AX6）→ 勾选的插件**。后面的同名选项覆盖前面的设置，再由 `make defconfig` 解析依赖。设备选择、明确启用的 LuCI 插件若未生效，构建会提前失败。

| 修改目的 | 修改位置 |
| --- | --- |
| 切换源码或分支 | 对应的 `profiles/*.conf`；`SOURCE_BRANCH` 支持分支名或标签 |
| 给所有设备增删插件 | `configs/common.config` |
| 修改某台设备的驱动、插件 | `configs/devices/*.config` |
| 添加上游没有的插件 | 先在 `feeds/custom.conf` 添加来源，再在配置中启用 |
| 修改默认 LAN 地址 | `files/common/etc/board.d/99-custom-network` |
| 修改 AX6 Wi-Fi 初始化设置 | `files/nss/etc/uci-defaults/992-wifi` |
| 修改主题和服务默认设置 | `files/common/etc/uci-defaults/` |
| 修复上游源码问题 | 按 [补丁说明](patches/README.md) 添加对应范围的补丁 |

两个 AX6 目标各有一份独立的设备配置，与对应 profile 同名，由 `DEVICE_CONFIG` 指定，可按上游分别调整驱动和插件。新增目标时，添加 profile 和对应配置，并在工作流的设备下拉选项中加入名称；同平台的构建步骤可以直接复用。

## 保留的固件配置

公共插件包括 AdGuard Home、ARP 绑定、自动重启、DDNSTO、OAF、TTYD、UPnP、微信推送、ZeroTier 和网络唤醒。设备专用插件仍由原设备配置选择，Passwall 和大鹅按勾选项编入。

- 默认 LAN 为 `192.168.169.1`，首次初始化或恢复出厂设置时生效；保留配置升级沿用原网络配置。
- 保留 Argon 主题，主色 `#6A89CC`、透明度 `0.3`。
- AX6 沿用原 Wi-Fi 初始化策略：对尚未设置加密的接口设置 `Redmi_AX6` / `Redmi_AX6_5G`，密码 `12345678`；已有加密配置不覆盖。AX6000 沿用其上游无线默认设置。
- 保留 AX6 的 NSS、IRQ 分配、硬件加速负载显示、温度脚本，以及 AX6000 的 HNAT 负载显示。
- 保留每天 03:15 的缓存清理任务、OAF 初始配置和 AdGuard Home 配置备份规则。
- 默认不预装 Docker、iStore、QuickStart、Lucky 等原配置已禁用的组件。

OAF 默认配置保持原行为，需要使用时在启动项中启用 `appfilter`。DDNSTO 需要在路由器页面中填写自己的 Token。两个可选代理插件可以同时编入，流量接管方式在设备上配置。

## 发布文件和失败处理

每个 Release 包含固件镜像、manifest、`profiles.json`、kmod 归档，以及：

- `build.config`：实际参与编译的完整配置。
- `requested.config`：依赖解析前的合并配置。
- `build-info.json`、`sources.lock`：构建信息、源码及各软件源的实际提交。
- `SHA256SUMS`：所有发布文件的 SHA-256 校验和。

打包按 `profiles.json` 校验所选设备的实际镜像，AX6 两种镜像配置都必须有产物。内核模块保留归档内的目录结构，同时支持 `.ipk` 和 `.apk`。缺少镜像、manifest、kmod，或镜像校验失败时，不进入发布阶段。

Release 先作为草稿创建，文件上传完成后才公开。发布阶段失败时，可以在 Actions 重跑失败的 job，复用已上传的固件。编译失败时，运行页面会保留准备日志、编译日志和配置文件，保留期同样是 7 天。

源码和 feeds 跟随所配置的分支更新。`sources.lock` 是本次构建的版本记录，不会自动锁定下一次构建；相同项目提交在不同日期构建可能使用不同的上游版本。上游变化导致补丁不匹配时，应按日志中的文件名更新补丁。

项目保留原项目的 [LICENSE](LICENSE) 及所迁移文件的作者声明，原项目基于 [ZqinKing/wrt_release](https://github.com/ZqinKing/wrt_release)。
