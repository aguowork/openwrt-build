"""合并 Kconfig，并检查 defconfig 是否保留了所选设备和插件。仅使用标准库。"""

import argparse
from pathlib import Path
import re
import sys


REQUIRED_PACKAGES = {
    "bash", "curl", "iwinfo", "jq", "jsonfilter", "luci-compat", "rpcd-mod-iwinfo",
}
DAED_KERNEL_OPTIONS = {
    "CONFIG_KERNEL_DEBUG_INFO", "CONFIG_KERNEL_DEBUG_INFO_BTF",
    "CONFIG_KERNEL_BPF_EVENTS", "CONFIG_KERNEL_BPF_STREAM_PARSER",
    "CONFIG_KERNEL_CGROUPS", "CONFIG_KERNEL_CGROUP_BPF", "CONFIG_KERNEL_XDP_SOCKETS",
}


def is_luci_feature(key):
    return re.fullmatch(r"CONFIG_PACKAGE_luci-(?:app|theme|proto)-[\w.-]+", key) is not None


def read_config(path):
    options = {}
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        # OpenWrt 包名可包含点号，例如 libusb-1.0。
        enabled = re.fullmatch(r"(CONFIG_\w[\w.-]*)=(.+)", line)
        disabled = re.fullmatch(r"# (CONFIG_\w[\w.-]*) is not set", line)
        if enabled:
            options[enabled[1]] = enabled[2]
        elif disabled:
            options[disabled[1]] = "n"
        elif line and not line.startswith("#"):
            raise ValueError(f"{path}:{number}: 无法识别的配置：{line}")
    return options


def merge_configs(paths):
    options = {}
    for path in paths:
        options.update(read_config(path))
    return "".join(
        f"# {key} is not set\n" if value == "n" else f"{key}={value}\n"
        for key, value in options.items()
    )


def verify_config(requested_path, actual_path):
    requested = read_config(requested_path)
    actual = read_config(actual_path)
    errors = []
    differences = []
    for key, value in requested.items():
        resolved = actual.get(key, "n")
        if value == resolved or (value == "m" and resolved == "y"):
            continue
        differences.append(f"{key}: {value} -> {resolved}")
        # 各源码支持的底层选项不同；设备选择和顶层插件缺失必须报错。
        required = (
            key.startswith("CONFIG_TARGET_")
            or key in {"CONFIG_CCACHE", "CONFIG_JSON_OVERVIEW_IMAGE_INFO"}
            or key.removeprefix("CONFIG_PACKAGE_") in REQUIRED_PACKAGES
            or (is_luci_feature(key) and "_" not in key.removeprefix("CONFIG_PACKAGE_"))
        )
        if required and value == "y":
            errors.append(f"所选设备或插件未生效：{key}")
        # 内核模块和底层库允许随依赖调整，禁用的应用和服务仍须保持禁用。
        dependency = key.startswith(("CONFIG_PACKAGE_kmod-", "CONFIG_PACKAGE_lib"))
        if key.startswith("CONFIG_PACKAGE_") and not dependency and value == "n" and resolved == "y":
            errors.append(f"已禁用的软件包被依赖重新启用：{key}")
    if requested.get("CONFIG_PACKAGE_luci-app-daed") == "y":
        for key in sorted(DAED_KERNEL_OPTIONS):
            if actual.get(key, "n") != "y":
                errors.append(f"大鹅缺少必需的内核配置：{key}=y")
        if actual.get("CONFIG_KERNEL_DEBUG_INFO_REDUCED", "n") == "y":
            errors.append("大鹅需要完整调试信息：CONFIG_KERNEL_DEBUG_INFO_REDUCED 必须禁用")
    if differences:
        print("上游依赖解析调整了以下配置（完整配置随 Release 发布）：")
        print("\n".join(differences))
    if errors:
        raise ValueError("\n".join(errors) + "\n请检查软件源、包名及依赖，不发布缺少所选功能的固件。")
    print("设备与插件配置检查通过。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    merge = commands.add_parser("merge")
    merge.add_argument("paths", nargs="+", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("requested", type=Path)
    verify.add_argument("actual", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "merge":
            print(merge_configs(args.paths), end="")
        else:
            verify_config(args.requested, args.actual)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
