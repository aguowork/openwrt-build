# OpenWrt Build

使用 GitHub Actions 为 Redmi AX6 和 Redmi AX6000 构建 OpenWrt 固件，并将设备镜像、配套内核模块和构建记录发布到 GitHub Releases。

每次运行选择一个构建目标，可按需编入 Passwall 或大鹅 Dashboard（含 dae）。

## 导航

- [默认登录信息](#默认登录信息)
- [支持的设备](#支持的设备)
- [开始构建](#开始构建)
- [目录结构](#目录结构)
- [修改与定制](#修改与定制)
- [发布文件与构建记录](#发布文件与构建记录)
- [来源与许可](#来源与许可)

## 默认登录信息

| 项目 | 默认值 |
| --- | --- |
| 管理地址 | `http://192.168.169.1` |
| 用户名 | `root` |
| root 密码 | `password` |

默认密码公开保存在 [`configs/root-password.txt`](configs/root-password.txt)，构建时生成 SHA-512 crypt 哈希写入固件，无需配置 root 密码 Secret。每次 Release 说明也会列出管理地址、用户名和默认密码，登录后请修改密码。

上述设置适用于首次初始化或恢复出厂设置；保留配置升级时，以设备原有设置为准。无线名称、无线密码和 `wwan` 初始设置由各目标的 `etc/uci-defaults/` 脚本配置，修改入口见下文。

## 支持的设备

| 工作流选项 | 上游源码 | 分支 | 设备与镜像 |
| --- | --- | --- | --- |
| `redmi_ax6_immwrt` | [VIKINGYFY/immortalwrt](https://github.com/VIKINGYFY/immortalwrt) | `main` | Redmi AX6，标准版与 stock 版 |
| `redmi_ax6_libwrt` | [LiBwrt/openwrt-6.x](https://github.com/LiBwrt/openwrt-6.x) | `25.12-nss` | Redmi AX6，标准版与 stock 版 |
| `redmi_ax6000_immwrt` | [padavanonly/immortalwrt-mt798x-6.6](https://github.com/padavanonly/immortalwrt-mt798x-6.6) | `openwrt-24.10-6.6` | Redmi AX6000，ubootmod 分区布局 |

刷机前确认设备型号、分区布局和镜像用途，AX6 标准版、stock 版及 AX6000 ubootmod 镜像须与设备实际布局匹配。两个 AX6 目标自动合并 NSS 配置；AX6000 使用 MT798x 平台配置，并提供 CPU 使用率与 HNAT 表项数量显示脚本。

目标、编译配置和固件文件目录的对应关系如下：

| 构建目标 | 设备编译配置 | 固件文件目录 |
| --- | --- | --- |
| `redmi_ax6_immwrt` | `configs/devices/redmi_ax6_immwrt.config` | `files/ax6immwrt/` |
| `redmi_ax6_libwrt` | `configs/devices/redmi_ax6_libwrt.config` | `files/ax6libwrt/` |
| `redmi_ax6000_immwrt` | `configs/devices/redmi_ax6000.config` | `files/ax6000/` |

## 开始构建

### 仓库设置

1. Fork 本仓库或推送到自己的 GitHub 仓库，并启用 Actions。
2. 在 **Settings → Secrets and variables → Actions → New repository secret** 中添加下表的五项 Secrets。
3. 确认仓库或组织策略允许工作流申请 `contents: write` 权限，用于发布 Release。工作流使用 GitHub 自动提供的 `GITHUB_TOKEN`。

| Secret | 用途与格式 |
| --- | --- |
| `DDNSTO_TOKEN` | 写入 DDNSTO 配置并启用服务 |
| `WXPUSHER_TOKEN` | WxPusher 应用 Token，以 `AT_` 开头 |
| `WXPUSHER_UIDS` | WxPusher 接收用户，当前脚本接受一个以 `UID_` 开头的 UID |
| `WECHATPUSH_SC3KEY` | 写入微信推送插件的 `sc3key` |
| `WECHATPUSH_SC3UID` | 写入微信推送插件的 `sc3uid` |

当前构建流程要求五项均非空，缺少任何一项都会在源码准备阶段停止。配置由 `inject_secrets.py` 写入本次构建的源码树，并随固件发布。

### 运行工作流

1. 打开 **Actions → 构建并发布 OpenWrt → Run workflow**。
2. 选择分支和构建目标 `device`；默认目标为 `redmi_ax6000_immwrt`。
3. 按需勾选 `passwall` 或 `daed`，两者默认均不勾选。
4. 运行工作流，完成后从 **Releases** 下载对应设备镜像；发布说明包含本次固件的登录信息和构建日志入口。

工作流依次准备环境、拉取源码与软件源、应用补丁和固件文件、注入配置、解析编译选项、下载依赖、编译并打包发布。并行编译失败时，会自动以单线程详细日志模式重试。

## 目录结构

### 构建配置与脚本

```text
.
├── .github/
│   ├── workflows/
│   │   └── build.yml                  # 手动构建、缓存、产物上传和 Release 发布
│   └── scripts/
│       ├── prepare.sh                 # 准备阶段入口，串联源码、软件源和配置处理
│       ├── feeds.sh                   # 更新上游 feeds，导入第三方包并替换 Go 工具链
│       ├── customize.sh               # 设置默认密码、构建标识，应用补丁和源码定制
│       ├── inject_secrets.py          # 注入 DDNSTO、WxPusher 和微信推送配置
│       ├── config.py                  # 合并 Kconfig 片段，校验依赖解析结果
│       └── package.py                 # 校验镜像，整理固件、kmod、发布说明和校验和
├── profiles/
│   ├── redmi_ax6_immwrt.conf           # AX6 ImmortalWrt 源码、分支、平台和目录映射
│   ├── redmi_ax6_libwrt.conf           # AX6 LiBwrt 源码、分支、平台和目录映射
│   └── redmi_ax6000_immwrt.conf         # AX6000 源码、分支、平台和目录映射
├── configs/
│   ├── common.config                  # 公共插件、主题、依赖与编译选项
│   ├── root-password.txt              # 公开默认 root 密码，单行文本
│   ├── devices/
│   │   ├── redmi_ax6_immwrt.config     # AX6 ImmortalWrt 设备选择和专属配置
│   │   ├── redmi_ax6_libwrt.config     # AX6 LiBwrt 设备选择和专属配置
│   │   └── redmi_ax6000.config         # AX6000 设备选择和专属配置
│   └── features/
│       ├── nss.config                 # AX6 自动启用的 NSS 平台配置
│       ├── passwall.config            # Passwall 可选配置
│       └── daed.config                # 大鹅 Dashboard 与 BTF 等编译配置
├── feeds/
│   ├── custom.conf                    # 第三方包来源、分支、导入条件和替换策略
│   └── golang.conf                    # Go 工具链来源与分支
├── files/                             # 固件根文件系统覆盖文件，详见下一节
├── patches/
│   ├── README.md                      # 补丁规则和用途说明
│   ├── source/
│   │   ├── common/
│   │   │   └── 100-luci-cpuusage.patch
│   │   └── redmi_ax6_immwrt/
│   │       └── 110-netfilter-dependency.patch
│   └── packages/
│       ├── opkg/
│       │   └── 001-fix-provides-version-parsing.patch
│       └── miniupnpd/
│           └── 999-default-leaseduration.patch
├── .gitattributes                     # 文本文件换行规则
├── .gitignore                         # 忽略源码树、构建输出和 Python 缓存
├── LICENSE                            # GPLv3 许可证
└── README.md                          # 构建与维护说明
```

### 固件文件

`files/` 中的相对路径对应固件内的绝对路径。例如，`files/common/etc/wx/wx_settings.conf` 会安装为 `/etc/wx/wx_settings.conf`。

```text
files/
├── common/                            # 所有目标共用
│   ├── etc/
│   │   ├── board.d/
│   │   │   └── 99-custom-network      # 首次生成网络配置时设置 LAN 地址
│   │   ├── config/
│   │   │   └── wechatpush             # 微信推送插件的 UCI 配置
│   │   ├── init.d/
│   │   │   └── custom_task            # 启动时维护定时任务
│   │   ├── uci-defaults/
│   │   │   ├── 990-argon              # Argon 主题默认样式
│   │   │   ├── 991-system             # 系统连接跟踪及 Dropbear 设置
│   │   │   └── 993-services           # 服务启用与停用设置
│   │   ├── JiaoBen/
│   │   │   ├── wxpusher.conf          # 共用脚本的 WxPusher 配置
│   │   │   ├── qdts.sh                # 启动推送脚本
│   │   │   ├── llts.sh                # 流量推送脚本
│   │   │   └── rz.sh                  # 启用 OAF 测试模式并读取内核日志
│   │   ├── wx/
│   │   │   ├── wifi-config.json       # 共用 Wi-Fi 列表与自动切换计数初值
│   │   │   ├── wx_settings.conf       # 无线管理、连通性检测和推送设置
│   │   │   └── uninstall.sh           # wx 无线管理卸载脚本
│   │   └── rc.local                   # 开机调用权限设置和启动推送
│   ├── usr/
│   │   ├── libexec/rpcd/
│   │   │   └── wx-wireless            # 无线管理后端，提供 ubus RPC 接口
│   │   └── share/rpcd/acl.d/
│   │       └── wx-wireless.json       # RPC 接口访问权限定义
│   └── www/
│       ├── cgi-bin/
│       │   └── wx-auth.sh             # wx 管理页面的认证入口
│       └── wx/                        # 无线管理前端
│           ├── index.html             # 页面入口
│           ├── autoswitch.html        # 自动切换页面
│           ├── connect.html           # 连接页面
│           ├── manage.html            # 热点管理页面
│           ├── status.html            # 状态页面
│           ├── wifi.html              # 无线设置页面
│           ├── css/                   # 页面和组件样式
│           ├── js/                    # 页面逻辑、组件及依赖资源
│           └── .ver                   # 前端版本标识
├── ax6immwrt/                         # AX6 ImmortalWrt 专用
│   └── etc/
│       ├── crontabs/root              # root 定时任务
│       ├── JiaoBen/wx-permissions.sh  # wx 文件和接口权限设置
│       ├── uci-defaults/AX6           # 无线、wwan、防火墙与自动重启初始设置
│       └── wx/wifi-config.json        # 此目标的预置 Wi-Fi 列表
├── ax6libwrt/                         # AX6 LiBwrt 专用
│   └── etc/
│       ├── crontabs/root
│       ├── JiaoBen/wx-permissions.sh
│       ├── uci-defaults/AX6
│       └── wx/wifi-config.json
└── ax6000/                            # AX6000 专用
    ├── etc/
    │   ├── config/
    │   │   ├── wbzt                   # 微博相关任务配置
    │   │   └── xhszt                  # 小红书相关任务配置
    │   ├── crontabs/root              # root 定时任务
    │   ├── JiaoBen/
    │   │   ├── wx-permissions.sh      # wx 文件和接口权限设置
    │   │   ├── fcjh.sh                # 彩票信息查询与推送脚本
    │   │   ├── jd_monitor.sh          # 京东商品重新上架监控与推送
    │   │   ├── wbzt.sh                # 微博相关任务脚本
    │   │   └── xhszt.sh               # 小红书相关任务脚本
    │   ├── uci-defaults/AX6000        # 无线、wwan、防火墙与自动重启初始设置
    │   └── wx/wifi-config.json        # 此目标的预置 Wi-Fi 列表
    └── sbin/cpuusage                  # CPU 使用率与 HNAT 表项数量显示
```

构建时先将 `files/common/` 合并到源码树的 `openwrt/files/`，再合并当前目标目录；同路径文件以目标目录为准。例如，构建 AX6 LiBwrt 时，预置 Wi-Fi 列表使用 `files/ax6libwrt/etc/wx/wifi-config.json`。

### 构建时生成的目录

| 目录 | 内容 |
| --- | --- |
| `openwrt/` | 拉取的上游源码、feeds、合并后的固件文件、最终 `.config` 和编译输出 |
| `.work/` | 构建元数据、源码提交记录、输入配置以及准备、下载、编译日志 |
| `dist/` | 整理后的 Release 文件，供上传与发布使用 |

这三个目录均已在 `.gitignore` 中排除。

## 修改与定制

### 常见修改入口

| 修改内容 | 文件或目录 |
| --- | --- |
| 上游源码、分支、平台和文件目录映射 | `profiles/*.conf` |
| 所有设备的插件、主题和编译选项 | `configs/common.config` |
| 指定设备的镜像选择、驱动和专属配置 | `configs/devices/*.config` |
| 默认 root 密码 | `configs/root-password.txt`，同时更新本文的默认登录信息 |
| 默认 LAN 地址 | `files/common/etc/board.d/99-custom-network`，同时更新本文及 `package.py` 中的发布说明地址 |
| Passwall、大鹅或 NSS 配置 | `configs/features/*.config` |
| 第三方包来源与替换策略 | `feeds/custom.conf` |
| Go 工具链来源 | `feeds/golang.conf` |
| 无线名称、密码、wwan 和设备初始化设置 | 对应目标的 `etc/uci-defaults/AX6` 或 `etc/uci-defaults/AX6000` |
| 已知 Wi-Fi 列表和自动切换计数初值 | 对应目标的 `etc/wx/wifi-config.json` |
| 无线管理公共设置、前后端和权限 | `files/common/etc/wx/`、`files/common/usr/`、`files/common/www/` |
| 定时任务与设备脚本 | 对应目标的 `etc/crontabs/root` 和 `etc/JiaoBen/` |
| 开机操作与公共服务设置 | `files/common/etc/rc.local`、`files/common/etc/init.d/` 和 `files/common/etc/uci-defaults/` |
| 构建流程、默认值和上传设置 | `.github/workflows/build.yml` 与 `.github/scripts/` |
| 源码或软件包补丁 | `patches/`，规则见 [补丁说明](patches/README.md) |

### 编译配置合并顺序

同名选项由后面的配置覆盖，顺序为：

1. 当前目标的 `configs/devices/*.config`。
2. `configs/common.config`。
3. AX6 目标的 `configs/features/nss.config`。
4. 勾选 Passwall 时的 `configs/features/passwall.config`。
5. 勾选大鹅时的 `configs/features/daed.config`。

合并结果保存为 `.work/requested.config`，再由 `make defconfig` 解析依赖生成最终配置。所选设备、关键插件或必要工具未生效，以及明确禁用的软件包被依赖重新启用时，校验会报错；实际配置随 Release 的 `build.config` 发布。

### 软件源与补丁规则

`feeds/custom.conf` 每行按 `条件|策略|仓库|分支|包映射` 定义来源。`always` 表示始终导入，`passwall` 表示仅在勾选 Passwall 时导入；`replace` 替换同名包，`missing` 仅在上游缺少时补充。

源码补丁按 `common → 平台 → 设备` 的顺序应用，同一目录内按文件名排序。软件包补丁需由 `customize.sh` 安装到对应包的补丁目录，具体路径和现有补丁用途见 [`patches/README.md`](patches/README.md)。

## 发布文件与构建记录

| 文件 | 用途 |
| --- | --- |
| 设备固件镜像 | 按设备和分区布局选择，文件名与格式由上游构建结果决定 |
| `*.manifest` | 固件内软件包及版本清单 |
| `profiles.json` | 设备镜像清单、镜像类型与校验信息 |
| `kmods-<构建目标>.tar.gz` | 本次构建的内核模块包，须与本次固件配套使用 |
| `build.config` | 依赖解析后的实际编译配置 |
| `requested.config` | 合并后、依赖解析前的输入配置 |
| `build-info.json` | 目标、构建时间、源码提交、可选功能、内核及插件信息 |
| `sources.lock` | 本次源码、feeds、第三方包和工具链的来源与提交记录 |
| `config.buildinfo`、`feeds.buildinfo`、`version.buildinfo` | 上游生成时一并附带的构建信息 |
| `RELEASE.md` | 发布说明，包含默认登录信息、源码和构建日志入口 |
| `SHA256SUMS` | 发布文件的 SHA-256 校验和 |

下载文件后，在同一目录执行：

```sh
sha256sum --check SHA256SUMS
```

每次构建会记录实际使用的源码提交，但后续运行仍会拉取所配置分支的源码；`sources.lock` 用于记录本次来源，不会自动锁定下一次构建。因此，同一仓库提交在不同时间构建，产物可能不同。

Actions 中的 `release-files` 产物保留 7 天。构建失败时会尝试上传 `build-logs-<构建目标>-<运行次数>`，包含已有日志、配置和构建记录，同样保留 7 天。若配置校验、镜像校验、manifest 或内核模块收集失败，工作流会停止发布，可先查看对应步骤日志。

## 来源与许可

本项目从 [ZqinKing/wrt_release](https://github.com/ZqinKing/wrt_release) 重构，仓库内容采用 GPLv3；上游源码和软件包遵循各自许可证。详见 [LICENSE](LICENSE)。
