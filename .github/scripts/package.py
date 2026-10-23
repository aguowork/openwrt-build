"""将一次构建整理成完整的 Release 文件，缺少设备镜像、manifest 或 kmod 时失败。"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile

from config import FEATURE_PACKAGES, read_config, required_packages, selected_devices, verify_config


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def select_images(target_dir, final_config):
    profiles_path = target_dir / "profiles.json"
    profiles = json.loads(profiles_path.read_text(encoding="utf-8"))["profiles"]
    selected = selected_devices(read_config(final_config))
    if not selected:
        raise ValueError("最终配置没有选择设备。")
    images = {}
    for device in sorted(selected):
        entries = profiles.get(device, {}).get("images", [])
        if not entries:
            raise ValueError(f"设备 {device} 没有输出镜像，请检查镜像大小限制及构建日志。")
        for entry in entries:
            name = entry["name"]
            if Path(name).name != name or any(char in name for char in "\\\r\n"):
                raise ValueError(f"无效的镜像文件名：{name!r}")
            path = target_dir / name
            if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
                raise ValueError(f"镜像缺失或为空：{name}")
            digest = sha256(path)
            if digest != entry["sha256"]:
                raise ValueError(f"镜像与 profiles.json 的校验和不符：{name}")
            images[name] = path
    return images


def read_manifests(paths):
    kernels = set()
    applications = set()
    for path in paths:
        found_kernel = False
        for line in path.read_text(encoding="utf-8").splitlines():
            name, separator, version = line.partition(" - ")
            if not separator:
                continue
            if name == "kernel":
                kernels.add(version.strip())
                found_kernel = True
            if name.startswith("luci-app-"):
                applications.add(name)
        if not found_kernel:
            raise ValueError(f"{path.name} 缺少 kernel 版本。")
    if len(kernels) != 1:
        raise ValueError("固件 manifest 缺失或内核版本不一致。")
    return kernels.pop(), sorted(applications)


def verify_packages(manifests, required_config):
    options = read_config(required_config)
    required = required_packages(options)
    forbidden = {
        package for packages in FEATURE_PACKAGES.values() for package in packages
        if options.get(f"CONFIG_PACKAGE_{package}") == "n"
    }
    for path in manifests:
        installed = {line.partition(" - ")[0] for line in path.read_text(encoding="utf-8").splitlines()}
        missing = required - installed
        if missing:
            raise ValueError(f"{path.name} 缺少所选功能的软件包：{', '.join(sorted(missing))}")
        unexpected = forbidden & installed
        if unexpected:
            raise ValueError(f"{path.name} 编入了已关闭的功能：{', '.join(sorted(unexpected))}")


def package_release(root):
    root = Path(root).resolve()
    source = root / "openwrt"
    work = root / ".work"
    metadata = json.loads((work / "build.json").read_text(encoding="utf-8"))
    for name in ("baseline.config", "required.config", "requested.config", "sources.lock"):
        if not (work / name).is_file():
            raise ValueError(f"缺少构建记录：{name}")
    verify_config(work / "required.config", source / ".config", work / "baseline.config")
    actual = read_config(source / ".config")
    board = actual["CONFIG_TARGET_BOARD"].strip('"')
    subtarget = actual["CONFIG_TARGET_SUBTARGET"].strip('"')
    metadata["target"] = f"{board}/{subtarget}"
    target_dir = source / "bin" / "targets" / metadata["target"]
    images = select_images(target_dir, source / ".config")
    manifests = sorted(path for path in target_dir.glob("*.manifest") if path.name != "Packages.manifest")
    kernel, applications = read_manifests(manifests)
    verify_packages(manifests, work / "required.config")
    bin_dir = source / "bin"
    modules = sorted(
        path for path in bin_dir.rglob("kmod-*")
        if path.suffix in {".ipk", ".apk"} and path.is_file() and not path.is_symlink()
    )
    if not modules:
        raise ValueError("没有找到 kmod 包，停止发布。")
    output = root / "dist"
    output.mkdir(exist_ok=False)
    for path in [*images.values(), *manifests, target_dir / "profiles.json"]:
        shutil.copyfile(path, output / path.name)
    for name in ("config.buildinfo", "feeds.buildinfo", "version.buildinfo"):
        if (target_dir / name).is_file():
            shutil.copyfile(target_dir / name, output / name)
    shutil.copyfile(source / ".config", output / "build.config")
    for name in ("baseline.config", "required.config", "requested.config", "sources.lock"):
        shutil.copyfile(work / name, output / name)
    archive_name = f'kmods-{metadata["device"]}.tar.gz'
    with tarfile.open(output / archive_name, "w:gz") as archive:
        for path in modules:
            archive.add(path, arcname=path.relative_to(bin_dir).as_posix(), recursive=False)

    metadata.update({"kernel": kernel, "applications": applications, "kmod_count": len(modules)})
    (output / "build-info.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    repository = metadata["recipe"]["repository"]
    recipe_commit = metadata["recipe"]["commit"]
    source_url = metadata["source"]["url"].removesuffix(".git")
    source_commit = metadata["source"]["commit"]
    features = ", ".join(metadata["features"]) or "默认插件"
    base_config = metadata.get("base_config")
    base_label = base_config["path"] if base_config else "设备 Kconfig 默认值"
    default_password = (root / "configs/root-password.txt").read_text(encoding="utf-8").strip()
    notes = [
        f'# {metadata["device"]}',
        "",
        f'- 构建时间：{metadata["build_time"]}',
        f'- 源码：[{source_commit[:12]}]({source_url}/commit/{source_commit})（{metadata["source"]["branch"]}）',
        f'- 构建配置：[{recipe_commit[:12]}](https://github.com/{repository}/tree/{recipe_commit})',
        f'- 上游配置基线：{base_label}',
        f'- Kernel：`{kernel}`',
        f'- 可选插件：{features}',
        f'- 构建日志：{metadata["run_url"]}',
        "",
        "首次刷入或恢复出厂设置后的登录信息：",
        "",
        "- 管理地址：`http://192.168.169.1`",
        "- 用户名：`root`",
        f"- 默认密码：`{default_password}`",
        "",
        f'默认设置和设备说明见[本次构建的 README](https://github.com/{repository}/blob/{recipe_commit}/README.md)。',
        "",
        f'`{archive_name}` 包含本次构建的 {len(modules)} 个内核模块包；请与本次固件配套使用。',
        "",
        "`baseline.config` 是上游原始基线（无基线时为空）；`required.config` 是显式增量；",
        "`requested.config` 是合并后的输入；`build.config` 是实际配置；`sources.lock` 记录源码和 feeds 的提交。",
        "下载后可用 `sha256sum --check SHA256SUMS` 校验文件。",
        "",
        "LuCI 插件：",
        "",
        *[f'- {name}' for name in applications],
        "",
    ]
    (output / "RELEASE.md").write_text("\n".join(notes), encoding="utf-8")
    checksums = [f"{sha256(path)}  {path.name}\n" for path in sorted(output.iterdir())]
    (output / "SHA256SUMS").write_text("".join(checksums), encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(f'已整理 {len(images)} 个固件镜像、{len(modules)} 个 kmod 包，等待发布。\n')
    return output


if __name__ == "__main__":
    try:
        destination = package_release(Path(__file__).resolve().parents[2])
        print(f"发布文件：{destination}")
    except (OSError, ValueError, KeyError) as error:
        print(f"整理发布文件失败：{error}", file=sys.stderr)
        sys.exit(1)
