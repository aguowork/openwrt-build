# OpenWrt Build

通过 GitHub Actions 管理多个 OpenWrt 上游和设备，在上游配置基础上叠加指定插件、自定义文件和统一登录信息，完成固件构建与 Releases 发布。

每个构建目标独立维护源码来源、设备配置和文件覆盖；公共插件与通用文件集中管理。Passwall、daed 两个开关独立生效，可关闭、单独启用或同时启用。

## 支持目标

| 构建目标 | 上游仓库 | 分支 | 镜像 |
| --- | --- | --- | --- |
| `redmi_ax6_immwrt` | [VIKINGYFY/immortalwrt](https://github.com/VIKINGYFY/immortalwrt) | `main` | AX6 标准版、stock 版 |
| `redmi_ax6_libwrt` | [LiBwrt/openwrt-6.x](https://github.com/LiBwrt/openwrt-6.x) | `25.12-nss` | AX6 标准版、stock 版 |
| `redmi_ax6000_immwrt` | [padavanonly/immortalwrt-mt798x-6.6](https://github.com/padavanonly/immortalwrt-mt798x-6.6) | `openwrt-24.10-6.6` | AX6000 ubootmod |

两个 AX6 目标由最小设备选择和 `make defconfig` 生成上游默认配置。AX6000 直接读取当次检出的上游 `defconfig/mt7986-ax6000_dae.config`，保留其 MTK 厂商无线驱动，并将设备选择限定为 ubootmod 型号。

刷机时请选择与设备型号、Bootloader 和分区布局匹配的镜像。

## 开始构建

### 1. 准备仓库与凭据

Fork 本仓库，并在 **Actions** 页面启用工作流。进入 **Settings → Secrets and variables → Actions → New repository secret**，添加以下五项 Secrets：

| Secret | 内容 |
| --- | --- |
| `DDNSTO_TOKEN` | DDNSTO Token |
| `WXPUSHER_TOKEN` | WxPusher 应用 Token，以 `AT_` 开头 |
| `WXPUSHER_UIDS` | 单个 WxPusher 用户 UID，以 `UID_` 开头 |
| `WECHATPUSH_SC3KEY` | 微信推送的 sc3key |
| `WECHATPUSH_SC3UID` | 微信推送的 sc3uid |

**五项 Secrets 在所有构建组合中均为必填。** 凭据会写入生成的固件；通过公开 Releases 分发前，请确认这些凭据适合随固件一起提供。

### 2. 运行工作流

1. 打开 **Actions → 构建并发布 OpenWrt → Run workflow**。
2. 选择构建目标，按需勾选 Passwall 和大鹅 Dashboard（daed）；两项默认关闭。
3. 运行后等待编译、镜像检查及发布完成。
4. 在 **Releases** 下载对应构建的固件及附件。

工作流运行在 Ubuntu 24.04。源码与软件源网络操作最多尝试三次；并行编译失败后会以单线程输出详细日志重试。进入编译阶段后，即使编译失败也会尝试保存已有的编译缓存。

失败时先查看运行日志；Actions 附件 `build-logs-<构建目标>-<尝试次数>` 保存实际配置、源码与软件源锁定信息及其他诊断文件，保留 7 天。准备、配置解析、下载和编译的完整文本日志可直接从运行页面下载。

## 默认设置与插件

首次刷入或恢复出厂设置后的登录信息：

| 项目 | 默认值 |
| --- | --- |
| 管理地址 | `http://192.168.169.1` |
| 用户名 | `root` |
| 密码 | `password` |

保留配置升级时继续使用已有网络配置和密码。首次登录后请修改默认密码。

### 公共插件

所有目标启用 LuCI 简体中文，并选择以下插件：

| 功能 | 软件包 | 来源 |
| --- | --- | --- |
| AdGuardHome 界面 | `luci-app-adguardhome` | [Kong](https://github.com/kongfl888/luci-app-adguardhome) |
| 应用过滤 OAF | `luci-app-oaf` | [small-package](https://github.com/kenzok8/small-package)，含配套后端 |
| ARP 绑定 | `luci-app-arpbind` | 上游 feeds |
| 自动重启 | `luci-app-autoreboot` | 上游 feeds |
| DDNSTO | `luci-app-ddnsto` | [linkease](https://github.com/linkease/ddnsto-openwrt-package) |
| 微信推送 | `luci-app-wechatpush` | [aguowork 分支](https://github.com/aguowork/luci-app-wechatpush) |
| 网络唤醒 | `luci-app-wol` | 上游 feeds |
| UPnP | `luci-app-upnp` | 上游 feeds |
| 网页终端 | `luci-app-ttyd` | 上游 feeds |

微信推送启用流量监控、主机信息检测和本地磁盘信息检测，配套 `wrtbwmon` 使用 [brvphoenix 的实现](https://github.com/brvphoenix/wrtbwmon)。AdGuardHome 使用 Kong 的 LuCI 界面，需要时在界面下载官方核心。

公共配置同时保留 `coreutils-shuf`、`coreutils-base64`，以及自定义脚本和网页需要的 Bash、curl、jq、jsonfilter、iwinfo、OpenSSL、RPCD 模块和 LuCI 兼容库。完整清单见 [configs/common.config](configs/common.config)。

### 可选插件

| 开关 | 启用后的配置 |
| --- | --- |
| Passwall | 使用 [作者主仓库](https://github.com/Openwrt-Passwall/openwrt-passwall) 与 [官方配套 packages](https://github.com/Openwrt-Passwall/openwrt-passwall-packages)，清除基线遗留的 Passwall 子选项，由插件决定默认核心和依赖 |
| 大鹅 Dashboard（daed） | 使用固件上游 feeds 中的 daed，包含 dae 后端及地理数据，并补齐所需 BTF、BPF、cgroup 内核能力 |

关闭时禁用对应插件和专用后端，共享依赖继续由上游和其他插件决定。AX6000 即使关闭 daed，也保留上游 `_dae.config` 自带的内核能力。

## 定制边界

配置以**上游基线与默认值 + 设备选择 + 公共插件 + 可选功能**合并，再由 `make defconfig` 解析依赖。本仓库维护三类叠加：

- 指定插件及其运行依赖；替换同名包的范围由 [feeds/custom.conf](feeds/custom.conf) 声明。
- `files/` 中的脚本、UCI 配置和网页；现有无线、中继、防火墙、主题偏好及定时任务等行为继续生效。
- 统一 LAN 地址、root 默认密码和五项必填凭据；密码与凭据写入固件覆盖文件。

框架对源码的改动限定在清单声明的插件包替换。其余采用上游提供的 feeds、补丁、工具链、驱动、NSS 等平台能力、主题、包管理器和系统版本信息。额外软件包是否预装由上游基线和依赖决定。遇到上游与指定插件不兼容时构建报错，由维护者调整来源版本。

文件按以下顺序覆盖，同路径文件以后者为准：

```text
上游已有 files → files/common → 当前目标文件目录 → 生成的登录与凭据文件
```

## 目录与维护

| 路径 | 用途 |
| --- | --- |
| [profiles/](profiles/) | 各构建目标的源码地址、分支、设备配置和文件目录 |
| [configs/devices/](configs/devices/) | 按上游独立维护的最小设备与镜像选择 |
| [configs/common.config](configs/common.config) | 公共插件、中文、运行依赖及构建缓存与镜像元数据选项 |
| [configs/features/](configs/features/) | Passwall、daed 可选配置 |
| [configs/root-password.txt](configs/root-password.txt) | 固件默认 root 密码 |
| [feeds/custom.conf](feeds/custom.conf) | 指定插件来源、分支和包替换范围 |
| [files/common/](files/common/) | 所有目标共用的文件 |
| [files/ax6immwrt/](files/ax6immwrt/) | VIKINGYFY AX6 文件覆盖 |
| [files/ax6libwrt/](files/ax6libwrt/) | LiBwrt AX6 文件覆盖 |
| [files/ax6000/](files/ax6000/) | AX6000 文件覆盖 |
| [.github/scripts/](.github/scripts/) | 源码准备、配置合并、文件与凭据生成、发布整理 |
| [.github/workflows/build.yml](.github/workflows/build.yml) | Actions 输入、编译、缓存和发布流程 |

**不同上游的设备配置和文件目录独立维护。** 即使当前内容相同，也可分别适配后续变化；明确通用的部分放入 `configs/common.config` 和 `files/common/`。

### 新增设备或上游

1. 在 `profiles/` 添加目标文件，填写 `SOURCE_URL`、`SOURCE_BRANCH`、`DEVICE_CONFIG` 和 `FILES_PROFILE`。
2. 在 `configs/devices/` 添加最小设备配置，在 `files/` 创建该目标需要的覆盖目录。
3. 若上游提供适用基线，在 Profile 中填写可选的 `BASE_CONFIG`；路径相对于上游源码根目录，未填写时采用设备 Kconfig 默认值。
4. 在工作流的 `device` 选项中登记目标，运行构建并验证设备功能。

例如，AX6000 的 Profile 为：

```bash
SOURCE_URL=https://github.com/padavanonly/immortalwrt-mt798x-6.6.git
SOURCE_BRANCH=openwrt-24.10-6.6
BASE_CONFIG=defconfig/mt7986-ax6000_dae.config
DEVICE_CONFIG=redmi_ax6000
FILES_PROFILE=ax6000
```

基线直接读取本次检出的上游文件，设备片段只保留必要选择，避免维护从旧固件复制的大量配置。发布目标路径由最终编译配置确定。

`openwrt/`、`.work/`、`dist/` 和 `__pycache__/` 均为本地生成目录，已由 Git 忽略；分别用于源码与编译、临时文件与日志、发布文件、Python 缓存，可按需清理，运行时会重新生成。

## 发布文件与排错

发布前自动检查设备选择、必需插件与依赖、已关闭的功能、固件镜像及校验和。首次启动、无线和插件的实际运行情况仍需在对应设备上验证。

| 文件 | 内容 |
| --- | --- |
| 固件镜像 | 当前目标输出的镜像 |
| `*.manifest` | 固件内的软件包及版本清单 |
| `profiles.json` | 设备镜像元数据 |
| `kmods-<构建目标>.tar.gz` | 本次构建的内核模块包，须与本次固件配套使用 |
| `baseline.config` | 本次上游原始基线，无基线时为空 |
| `required.config` | 本仓库要求的显式增量与功能开关 |
| `requested.config` | 基线与增量合并后的编译输入 |
| `build.config` | 上游 defconfig 解析后的实际配置 |
| `sources.lock` | 源码和 feeds 的实际提交 |
| `build-info.json` | 构建来源、基线路径与 SHA256、内核和插件信息 |
| `RELEASE.md` | 本次发布说明 |
| `SHA256SUMS` | 发布附件的 SHA256 校验和 |

在 Linux 等提供 `sha256sum` 的环境中，将附件下载到同一目录后执行：

```bash
sha256sum --check SHA256SUMS
```

排查问题时，对照 `required.config`、`build.config` 和 `*.manifest` 判断所需配置与软件包是否生效，再通过 `sources.lock` 定位本次使用的上游提交。

## 致谢与许可

项目基于 [ZqinKing/wrt_release](https://github.com/ZqinKing/wrt_release) 重构，感谢各固件上游和插件作者。

本仓库采用 [GPL-3.0](LICENSE)；上游源码和软件包遵循各自许可证。
