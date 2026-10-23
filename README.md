# OpenWrt Build

通过 GitHub Actions 编译 Redmi AX6 / AX6000 固件，可选 Passwall、大鹅 Dashboard（含 dae）。

## 支持设备

| 构建目标 | 源码 | 镜像 |
| --- | --- | --- |
| `redmi_ax6_immwrt` | VIKINGYFY/immortalwrt | AX6 标准版、stock 版 |
| `redmi_ax6_libwrt` | LiBwrt/openwrt-6.x | AX6 标准版、stock 版 |
| `redmi_ax6000_immwrt` | padavanonly/immortalwrt-mt798x-6.6 | AX6000 ubootmod |

## 开始构建

1. Fork 本仓库并启用 Actions。
2. 在 **Settings → Secrets and variables → Actions** 添加五项必填 Secrets（会写入固件）：

   | Secret | 内容 |
   | --- | --- |
   | `DDNSTO_TOKEN` | DDNSTO Token |
   | `WXPUSHER_TOKEN` | WxPusher Token，`AT_` 开头 |
   | `WXPUSHER_UIDS` | 一个 WxPusher UID，`UID_` 开头 |
   | `WECHATPUSH_SC3KEY` | 微信推送 sc3key |
   | `WECHATPUSH_SC3UID` | 微信推送 sc3uid |

3. 打开 **Actions → 构建并发布 OpenWrt → Run workflow**，选择设备和可选插件后运行。
4. 到 **Releases** 下载固件；构建失败时查看 Actions 日志。

构建会检查设备和所选插件，并在发布前核对固件清单中的可选功能。内核模块和底层库允许由上游自动解析依赖，配置差异会写入日志；禁用的应用或服务被重新启用时仍会报错。编译失败也会保留已生成的编译缓存，修复脚本后重跑可继续复用。

源码、feeds 和第三方仓库遇到网络故障时最多尝试三次，克隆重试会清理本次失败的残留目录。选中大鹅时，构建会检查 BTF、BPF、cgroup 等必需内核配置。`sources.lock` 记录本次实际使用的提交；后续构建仍跟随配置中的分支。

刷机时确认型号和分区布局匹配，内核模块须与同次构建的固件配套使用。

## 使用说明

默认登录：`http://192.168.169.1` · 用户名 `root` · 密码 `password`

首次登录后请修改密码；保留配置升级时，以原有设置为准。

AdGuardHome 使用 [Kong 的 LuCI 界面](https://github.com/kongfl888/luci-app-adguardhome)，首次使用需联网下载官方核心，建议选择“作为 dnsmasq 的上游服务器”模式。

## 目录结构

```text
.
├── profiles/                 # 各设备的源码、分支和构建目标
├── configs/
│   ├── common.config         # 公共插件和编译选项
│   ├── devices/              # 设备配置
│   ├── features/             # Passwall、大鹅、NSS 配置
│   └── root-password.txt     # 默认密码
├── feeds/
│   ├── custom.conf           # 第三方软件包来源与替换策略
│   └── golang.conf           # Go 编译器来源
├── files/                    # 写入固件的文件
│   ├── common/               # 所有设备共用
│   ├── ax6immwrt/            # AX6 ImmortalWrt
│   ├── ax6libwrt/            # AX6 LiBwrt
│   └── ax6000/               # AX6000
├── patches/                  # 源码与软件包补丁
└── .github/
    ├── workflows/build.yml   # Actions 构建入口
    └── scripts/              # 源码准备、定制与打包脚本
```

`files/` 内路径对应固件根目录，设备文件覆盖同路径的公共文件。补丁用法见 [补丁说明](patches/README.md)。

## 来源与许可

基于 [ZqinKing/wrt_release](https://github.com/ZqinKing/wrt_release) 重构，采用 [GPLv3](LICENSE)；上游源码和软件包遵循各自许可证。