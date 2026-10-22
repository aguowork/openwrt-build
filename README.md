# OpenWrt Build

通过 GitHub Actions 为 Redmi AX6、Redmi AX6000 编译并发布 OpenWrt 固件，可选编入 Passwall 或大鹅 Dashboard（含 dae）。

## 支持设备

| 构建目标 | 源码 | 镜像 |
| --- | --- | --- |
| `redmi_ax6_immwrt` | VIKINGYFY/immortalwrt | AX6 标准版、stock 版 |
| `redmi_ax6_libwrt` | LiBwrt/openwrt-6.x | AX6 标准版、stock 版 |
| `redmi_ax6000_immwrt` | padavanonly/immortalwrt-mt798x-6.6 | AX6000 ubootmod |

刷机前确认设备型号和分区布局与镜像匹配。

## 使用方法

1. Fork 本仓库并启用 Actions。
2. 在 **Settings → Secrets and variables → Actions** 中添加以下五项 Secrets，缺少任意一项都会导致构建失败。

   | Secret | 内容 |
   | --- | --- |
   | `DDNSTO_TOKEN` | DDNSTO Token |
   | `WXPUSHER_TOKEN` | WxPusher 应用 Token，以 `AT_` 开头 |
   | `WXPUSHER_UIDS` | 一个以 `UID_` 开头的 WxPusher UID |
   | `WECHATPUSH_SC3KEY` | 微信推送 sc3key |
   | `WECHATPUSH_SC3UID` | 微信推送 sc3uid |

   这些配置会写入固件。

3. 打开 **Actions → 构建并发布 OpenWrt → Run workflow**，选择设备，按需勾选 `passwall`、`daed`，然后运行。
4. 构建完成后到 **Releases** 下载固件。失败时查看 Actions 日志。

## 默认登录

- 地址：`http://192.168.169.1`
- 用户名：`root`
- 密码：`password`

首次登录后请修改密码；保留配置升级时，以原有设置为准。

## 常用修改

| 内容 | 位置 |
| --- | --- |
| 源码和分支 | `profiles/` |
| 公共插件和编译选项 | `configs/common.config` |
| 设备配置 | `configs/devices/` |
| Passwall、大鹅、NSS 配置 | `configs/features/` |
| 默认密码 | `configs/root-password.txt` |
| 第三方软件包 | `feeds/custom.conf` |
| 公共固件文件 | `files/common/` |
| 设备专用文件 | `files/ax6immwrt/`、`files/ax6libwrt/`、`files/ax6000/` |
| 补丁 | `patches/`，见 [补丁说明](patches/README.md) |
| 构建流程 | `.github/workflows/build.yml`、`.github/scripts/` |

`files/` 中的路径对应固件内路径，设备专用文件会覆盖同路径的公共文件。

## 下载说明

Release 包含固件、配套内核模块、编译配置和校验文件。内核模块须与同次构建的固件配套使用，可通过 `sha256sum --check SHA256SUMS` 校验下载文件。

## 来源与许可

基于 [ZqinKing/wrt_release](https://github.com/ZqinKing/wrt_release) 重构，采用 [GPLv3](LICENSE)；上游源码和软件包遵循各自许可证。
