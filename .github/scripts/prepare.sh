#!/usr/bin/env bash
# Actions 专用准备阶段；编译和发布由工作流直接执行。
set -Eeuo pipefail
trap 'echo "::error file=${BASH_SOURCE[0]},line=$LINENO::源码准备失败"' ERR

[[ ${GITHUB_ACTIONS:-} == true ]] || { echo '此脚本由 GitHub Actions 调用。' >&2; exit 1; }
: "${GITHUB_WORKSPACE:?}" "${GITHUB_OUTPUT:?}"
: "${GITHUB_RUN_ID:?}" "${GITHUB_RUN_ATTEMPT:?}" "${DEVICE:?}"
export RECIPE_ROOT="$GITHUB_WORKSPACE"
export SOURCE_DIR="$RECIPE_ROOT/openwrt"
export INCLUDE_PASSWALL=${INCLUDE_PASSWALL:-false}
export INCLUDE_DAED=${INCLUDE_DAED:-false}

[[ $DEVICE =~ ^[a-z0-9_]+$ && -f "$RECIPE_ROOT/profiles/$DEVICE.conf" ]] || {
    echo "不支持的构建目标：$DEVICE" >&2
    exit 1
}
for value in "$INCLUDE_PASSWALL" "$INCLUDE_DAED"; do
    [[ $value == true || $value == false ]] || { echo "无效的布尔值：$value" >&2; exit 1; }
done
# 配置来自本次 checkout 的仓库文件，不执行工作流输入中的代码。
# shellcheck source=/dev/null
source "$RECIPE_ROOT/profiles/$DEVICE.conf"
: "${SOURCE_URL:?}" "${SOURCE_BRANCH:?}" "${DEVICE_CONFIG:?}" "${FILES_PROFILE:?}" "${PLATFORM:?}" "${TARGET:?}"
[[ $FILES_PROFILE =~ ^[a-z0-9_]+$ ]] || { echo "无效的固件文件配置目录：FILES_PROFILE" >&2; exit 1; }
secret_names=(DDNSTO_TOKEN WXPUSHER_TOKEN WXPUSHER_UIDS WECHATPUSH_SC3KEY WECHATPUSH_SC3UID)
for name in "${secret_names[@]}"; do
    [[ -n ${!name:-} ]] || { echo "缺少 GitHub Secret：$name" >&2; exit 1; }
done
[[ $WXPUSHER_TOKEN =~ ^AT_[A-Za-z0-9_-]+$ ]] || { echo 'GitHub Secret WXPUSHER_TOKEN 格式无效。' >&2; exit 1; }
[[ $WXPUSHER_UIDS =~ ^UID_[A-Za-z0-9_-]+$ ]] || { echo 'GitHub Secret WXPUSHER_UIDS 格式无效。' >&2; exit 1; }
for name in "${secret_names[@]}"; do
    export -n "$name"
done
export SOURCE_URL SOURCE_BRANCH PLATFORM TARGET DEVICE FILES_PROFILE
cd "$RECIPE_ROOT"
mkdir -p .work
exec > >(tee .work/prepare.log) 2>&1

echo '::group::检出固件源码'
git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=60 clone \
    --depth 1 --single-branch --branch "$SOURCE_BRANCH" -- "$SOURCE_URL" "$SOURCE_DIR"
SOURCE_COMMIT=$(git -C "$SOURCE_DIR" rev-parse HEAD)
BUILD_TIME=$(date --iso-8601=seconds)
RELEASE_TAG="$DEVICE-$(date +%Y%m%d-%H%M%S)-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
export SOURCE_COMMIT BUILD_TIME RELEASE_TAG
printf 'release_tag=%s\n' "$RELEASE_TAG" >> "$GITHUB_OUTPUT"
printf 'kind\tname\turl\tref\tcommit\n' > .work/sources.lock
printf 'source\topenwrt\t%s\t%s\t%s\n' "$SOURCE_URL" "$SOURCE_BRANCH" "$SOURCE_COMMIT" >> .work/sources.lock
python3 - <<'PY'
import json
import os
from pathlib import Path

env = os.environ
metadata = {
    "device": env["DEVICE"],
    "target": env["TARGET"],
    "platform": env["PLATFORM"],
    "features": [name for name in ("passwall", "daed") if env[f"INCLUDE_{name.upper()}"] == "true"],
    "source": {"url": env["SOURCE_URL"], "branch": env["SOURCE_BRANCH"], "commit": env["SOURCE_COMMIT"]},
    "recipe": {"repository": env["GITHUB_REPOSITORY"], "commit": env["GITHUB_SHA"]},
    "run_url": f'{env["GITHUB_SERVER_URL"]}/{env["GITHUB_REPOSITORY"]}/actions/runs/{env["GITHUB_RUN_ID"]}',
    "build_time": env["BUILD_TIME"],
    "release_tag": env["RELEASE_TAG"],
}
Path(".work/build.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
echo '::endgroup::'

echo '::group::准备软件源'
bash .github/scripts/feeds.sh
echo '::endgroup::'

echo '::group::应用补丁与固件默认文件'
bash .github/scripts/customize.sh
mkdir -p "$SOURCE_DIR/files"
for overlay in "$RECIPE_ROOT/files/common" "$RECIPE_ROOT/files/$FILES_PROFILE"; do
    [[ ! -d $overlay ]] || rsync -a --exclude='/.gitkeep' "$overlay/" "$SOURCE_DIR/files/"
done
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

echo '::group::安装 feeds 并解析设备配置'
(
    cd "$SOURCE_DIR"
    ./scripts/feeds update -i
    ./scripts/feeds install -a -f
)
configs=("configs/devices/$DEVICE_CONFIG.config" configs/common.config)
[[ $PLATFORM != nss ]] || configs+=(configs/features/nss.config)
[[ $INCLUDE_PASSWALL != true ]] || configs+=(configs/features/passwall.config)
[[ $INCLUDE_DAED != true ]] || configs+=(configs/features/daed.config)
python3 .github/scripts/config.py merge "${configs[@]}" > .work/requested.config
cp .work/requested.config "$SOURCE_DIR/.config"
make -C "$SOURCE_DIR" defconfig
python3 .github/scripts/config.py verify .work/requested.config "$SOURCE_DIR/.config" \
    > .work/config-check.log
cat .work/config-check.log
echo '::endgroup::'
