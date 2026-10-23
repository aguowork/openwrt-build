#!/usr/bin/env bash
# Actions 准备阶段：上游基线 + 显式配置 + 固件覆盖文件。
set -Eeuo pipefail
trap 'echo "::error file=${BASH_SOURCE[0]},line=$LINENO::源码准备失败"' ERR

[[ ${GITHUB_ACTIONS:-} == true ]] || { echo '此脚本由 GitHub Actions 调用。' >&2; exit 1; }
: "${GITHUB_WORKSPACE:?}" "${GITHUB_OUTPUT:?}"
: "${GITHUB_RUN_ID:?}" "${GITHUB_RUN_ATTEMPT:?}" "${DEVICE:?}"
export RECIPE_ROOT="$GITHUB_WORKSPACE"
export SOURCE_DIR="$RECIPE_ROOT/openwrt"
# shellcheck source=.github/scripts/network.sh
source "$RECIPE_ROOT/.github/scripts/network.sh"
export INCLUDE_PASSWALL=${INCLUDE_PASSWALL:-false}
export INCLUDE_DAED=${INCLUDE_DAED:-false}

[[ $DEVICE =~ ^[a-z0-9_]+$ && -f "$RECIPE_ROOT/profiles/$DEVICE.conf" ]] || {
    echo "不支持的构建目标：$DEVICE" >&2
    exit 1
}
for value in "$INCLUDE_PASSWALL" "$INCLUDE_DAED"; do
    [[ $value == true || $value == false ]] || { echo "无效的布尔值：$value" >&2; exit 1; }
done
# shellcheck source=/dev/null
source "$RECIPE_ROOT/profiles/$DEVICE.conf"
: "${SOURCE_URL:?}" "${SOURCE_BRANCH:?}" "${DEVICE_CONFIG:?}" "${FILES_PROFILE:?}"
export BASE_CONFIG=${BASE_CONFIG:-}
[[ $FILES_PROFILE =~ ^[a-z0-9_]+$ ]] || { echo '无效的固件文件配置目录：FILES_PROFILE' >&2; exit 1; }
secret_names=(DDNSTO_TOKEN WXPUSHER_TOKEN WXPUSHER_UIDS WECHATPUSH_SC3KEY WECHATPUSH_SC3UID)
for name in "${secret_names[@]}"; do
    [[ -n ${!name:-} ]] || { echo "缺少 GitHub Secret：$name" >&2; exit 1; }
done
[[ $WXPUSHER_TOKEN =~ ^AT_[A-Za-z0-9_-]+$ ]] || { echo 'GitHub Secret WXPUSHER_TOKEN 格式无效。' >&2; exit 1; }
[[ $WXPUSHER_UIDS =~ ^UID_[A-Za-z0-9_-]+$ ]] || { echo 'GitHub Secret WXPUSHER_UIDS 格式无效。' >&2; exit 1; }
for name in "${secret_names[@]}"; do
    export -n "$name"
done
export SOURCE_URL SOURCE_BRANCH DEVICE
cd "$RECIPE_ROOT"
mkdir -p .work
exec > >(tee .work/prepare.log) 2>&1

echo '::group::检出固件源码与上游基线'
git_clone "$SOURCE_DIR" --depth 1 --single-branch --branch "$SOURCE_BRANCH" -- "$SOURCE_URL"
SOURCE_COMMIT=$(git -C "$SOURCE_DIR" rev-parse HEAD)
BUILD_TIME=$(date --iso-8601=seconds)
RELEASE_TAG="$DEVICE-$(date +%Y%m%d-%H%M%S)-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
export SOURCE_COMMIT BUILD_TIME RELEASE_TAG
printf 'release_tag=%s\n' "$RELEASE_TAG" >> "$GITHUB_OUTPUT"
printf 'kind\tname\turl\tref\tcommit\n' > .work/sources.lock
printf 'source\topenwrt\t%s\t%s\t%s\n' "$SOURCE_URL" "$SOURCE_BRANCH" "$SOURCE_COMMIT" >> .work/sources.lock
python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

env = os.environ
source = Path(env["SOURCE_DIR"]).resolve()
base_ref = env["BASE_CONFIG"]
baseline = b""
if base_ref:
    relative = Path(base_ref)
    base = (source / relative).resolve()
    if relative.is_absolute() or not base.is_relative_to(source) or not base.is_file():
        raise SystemExit(f"上游基线不存在或超出源码目录：{base_ref}")
    baseline = base.read_bytes()
Path(".work/baseline.config").write_bytes(baseline)
metadata = {
    "device": env["DEVICE"],
    "features": [name for name in ("passwall", "daed") if env[f"INCLUDE_{name.upper()}"] == "true"],
    "source": {"url": env["SOURCE_URL"], "branch": env["SOURCE_BRANCH"], "commit": env["SOURCE_COMMIT"]},
    "base_config": {"path": base_ref, "sha256": hashlib.sha256(baseline).hexdigest()} if base_ref else None,
    "recipe": {"repository": env["GITHUB_REPOSITORY"], "commit": env["GITHUB_SHA"]},
    "run_url": f'{env["GITHUB_SERVER_URL"]}/{env["GITHUB_REPOSITORY"]}/actions/runs/{env["GITHUB_RUN_ID"]}',
    "build_time": env["BUILD_TIME"],
    "release_tag": env["RELEASE_TAG"],
}
Path(".work/build.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"上游基线：{base_ref or '设备 Kconfig 默认值'}")
PY
echo '::endgroup::'

echo '::group::准备与安装软件源'
bash .github/scripts/feeds.sh
(
    cd "$SOURCE_DIR"
    ./scripts/feeds update -i
    ./scripts/feeds install -a -f
)
echo '::endgroup::'

echo '::group::合并上游基线与显式配置'
configs=("configs/devices/$DEVICE_CONFIG.config" configs/common.config)
feature_args=()
if [[ $INCLUDE_PASSWALL == true ]]; then
    configs+=(configs/features/passwall.config)
    feature_args+=(--passwall)
fi
if [[ $INCLUDE_DAED == true ]]; then
    configs+=(configs/features/daed.config)
    feature_args+=(--daed)
fi
# required 仅包含我们的增量；requested 还包含本次上游原始基线。
python3 .github/scripts/config.py merge "${feature_args[@]}" "${configs[@]}" > .work/required.config
python3 .github/scripts/config.py merge --base .work/baseline.config \
    "${feature_args[@]}" "${configs[@]}" > .work/requested.config
cp .work/requested.config "$SOURCE_DIR/.config"
echo '::endgroup::'

echo '::group::放入自定义文件与私有配置'
mkdir -p "$SOURCE_DIR/files"
for overlay in "$RECIPE_ROOT/files/common" "$RECIPE_ROOT/files/$FILES_PROFILE"; do
    [[ ! -d $overlay ]] || rsync -a --exclude='/.gitkeep' "$overlay/" "$SOURCE_DIR/files/"
done
python3 .github/scripts/overlay.py "$SOURCE_DIR" "$RECIPE_ROOT/configs/root-password.txt"
DDNSTO_TOKEN="$DDNSTO_TOKEN" \
WXPUSHER_TOKEN="$WXPUSHER_TOKEN" \
WXPUSHER_UIDS="$WXPUSHER_UIDS" \
WECHATPUSH_SC3KEY="$WECHATPUSH_SC3KEY" \
WECHATPUSH_SC3UID="$WECHATPUSH_SC3UID" \
    python3 .github/scripts/inject_secrets.py "$SOURCE_DIR"
# Windows checkout 不保留 Unix 可执行位，在 runner 上统一设置固件脚本权限。
find "$SOURCE_DIR/files" -type f \( -path '*/etc/board.d/*' -o -path '*/etc/uci-defaults/*' \
    -o -path '*/etc/init.d/*' -o -path '*/etc/rc.local' -o -path '*/etc/JiaoBen/*.sh' \
    -o -path '*/etc/wx/*.sh' -o -path '*/usr/libexec/rpcd/*' -o -path '*/www/cgi-bin/*' \
    -o -path '*/sbin/*' -o -path '*/usr/bin/*' \) -exec chmod 755 {} +
echo '::endgroup::'

echo '::group::解析并校验设备与插件配置'
make -C "$SOURCE_DIR" defconfig 2>&1 | tee .work/defconfig.log
python3 .github/scripts/config.py verify --base .work/baseline.config \
    .work/required.config "$SOURCE_DIR/.config" 2>&1 | tee .work/config-check.log
echo '::endgroup::'
