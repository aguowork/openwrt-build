"""合并上游基线和显式增量，只校验本项目承诺的设备、插件及功能。"""

import argparse
from pathlib import Path
import re
import sys


FEATURE_PACKAGES = {
    "passwall": {"luci-app-passwall"},
    "daed": {"luci-app-daed", "daed", "daed-geoip", "daed-geosite"},
}
TARGET_MODES = {
    "CONFIG_TARGET_MULTI_PROFILE", "CONFIG_TARGET_ALL_PROFILES",
    "CONFIG_TARGET_PER_DEVICE_ROOTFS",
}
# 上游 MTK 基线的关键驱动必须保留；其余基线选项仍由 defconfig 解析。
VENDOR_DRIVER_OPTIONS = {
    "CONFIG_MTK_WIFI_DRIVER", "CONFIG_PACKAGE_kmod-mt_wifi",
    "CONFIG_PACKAGE_mtwifi-cfg", "CONFIG_PACKAGE_luci-app-mtwifi-cfg",
}


def read_config(path):
    options = {}
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        enabled = re.fullmatch(r"(CONFIG_\w[\w.-]*)=(.+)", line)
        disabled = re.fullmatch(r"# (CONFIG_\w[\w.-]*) is not set", line)
        if enabled:
            options[enabled[1]] = enabled[2]
        elif disabled:
            options[disabled[1]] = "n"
        elif line and not line.startswith("#"):
            raise ValueError(f"{path}:{number}: 无法识别的配置：{line}")
    return options


def format_config(options):
    return "".join(
        f"# {key} is not set\n" if value == "n" else f"{key}={value}\n"
        for key, value in options.items()
    )


def is_target_selection(key):
    return (
        re.match(r"CONFIG_TARGET_[a-z0-9]", key) is not None
        or key.startswith("CONFIG_TARGET_DEVICE_")
        or key in TARGET_MODES
        or key in {"CONFIG_TARGET_BOARD", "CONFIG_TARGET_SUBTARGET",
                   "CONFIG_TARGET_PROFILE", "CONFIG_TARGET_ARCH_PACKAGES"}
    )


def selected_devices(options):
    return {
        key.rsplit("_DEVICE_", 1)[1]
        for key, value in options.items()
        if re.fullmatch(r"CONFIG_TARGET_(?:DEVICE_)?[a-z0-9_]+_DEVICE_[\w.-]+", key)
        and value == "y"
    }


def merge_configs(paths, base=None, passwall=False, daed=False):
    options = read_config(base) if base is not None else {}
    options = {
        key: value for key, value in options.items()
        if not is_target_selection(key)
        and not (passwall and key.startswith("CONFIG_PACKAGE_luci-app-passwall_"))
    }
    overrides = {}
    for path in paths:
        overrides.update(read_config(path))
    if selected_devices(overrides):
        # 基线的多设备模式不能令单设备选择失效，也不允许 BUILDBOT 默认选中全部设备。
        options.update(dict.fromkeys(sorted(TARGET_MODES), "n"))
    options.update(overrides)
    for feature, enabled in (("passwall", passwall), ("daed", daed)):
        for package in sorted(FEATURE_PACKAGES[feature]):
            options[f"CONFIG_PACKAGE_{package}"] = "y" if enabled else "n"
    return format_config(options)


def required_packages(options):
    return {
        key.removeprefix("CONFIG_PACKAGE_")
        for key, value in options.items()
        if key.startswith("CONFIG_PACKAGE_") and value == "y"
        and not key.startswith("CONFIG_PACKAGE_luci-app-wechatpush_")
    }


def verify_config(required_path, actual_path, base=None):
    required = read_config(required_path)
    actual = read_config(actual_path)
    errors = []
    for key, value in required.items():
        resolved = actual.get(key, "n")
        if value == resolved or (value == "m" and resolved == "y"):
            continue
        # m 只生成独立软件包，不会编入固件；关闭的应用不得成为内置包。
        if value == "n" and resolved != "y":
            continue
        errors.append(f"显式配置未生效：{key}: {value} -> {resolved}")
    wanted = selected_devices(required)
    selected = selected_devices(actual)
    if wanted != selected:
        errors.append(f"镜像设备不符：期望 {sorted(wanted)}，实际 {sorted(selected)}")
    if base is not None:
        baseline = read_config(base)
        for key in sorted(VENDOR_DRIVER_OPTIONS):
            if baseline.get(key) == "y" and actual.get(key) != "y":
                errors.append(f"上游基线的厂商无线驱动未保留：{key}=y")
    if errors:
        raise ValueError("\n".join(errors) + "\n请检查上游与插件版本的兼容性，不自动修改源码。")
    print("设备、指定插件和功能配置检查通过。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    merge = commands.add_parser("merge")
    merge.add_argument("--base", type=Path, help="上游原始配置；不提供时使用 Kconfig 默认值")
    merge.add_argument("--passwall", action="store_true")
    merge.add_argument("--daed", action="store_true")
    merge.add_argument("paths", nargs="+", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--base", type=Path, help="校验厂商无线驱动是否保留")
    verify.add_argument("required", type=Path, help="不含上游基线的显式增量")
    verify.add_argument("actual", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "merge":
            print(merge_configs(args.paths, args.base, args.passwall, args.daed), end="")
        else:
            verify_config(args.required, args.actual, args.base)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
