#!/usr/bin/env bash
# 先生成上游 feeds，再将清单中的包集中到一个本地 feed。
set -Eeuo pipefail
: "${RECIPE_ROOT:?}" "${SOURCE_DIR:?}" "${INCLUDE_PASSWALL:?}"
# shellcheck source=.github/scripts/network.sh
source "$RECIPE_ROOT/.github/scripts/network.sh"
cd "$SOURCE_DIR"

[[ -f feeds.conf ]] || cp feeds.conf.default feeds.conf
# 只重建本项目注册的 custom feed，保留上游原有的软件源。
sed -i '/^[^#]*[[:space:]]custom[[:space:]]/d' feeds.conf
retry_network ./scripts/feeds update -a

for feed in feeds/*; do
    [[ -e "$feed/.git" ]] || continue
    printf 'feed\t%s\t%s\t%s\t%s\n' "${feed##*/}" \
        "$(git -C "$feed" remote get-url origin)" \
        "$(git -C "$feed" symbolic-ref --short -q HEAD || printf detached)" \
        "$(git -C "$feed" rev-parse HEAD)" >> "$RECIPE_ROOT/.work/sources.lock"
done

mkdir -p custom
while IFS='|' read -r condition url branch mappings; do
    [[ -n $condition && $condition != \#* ]] || continue
    case "$condition" in
        always) ;;
        passwall) [[ $INCLUDE_PASSWALL == true ]] || continue ;;
        *) echo "未知软件源条件：$condition" >&2; exit 1 ;;
    esac
    read -r -a candidates <<< "$mappings"
    paths=()
    for mapping in "${candidates[@]}"; do
        path=${mapping%%:*}
        name=${mapping##*:}
        [[ $name =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ && $path != /* && $path != *..* ]] || {
            echo "无效的包映射：$mapping" >&2; exit 1;
        }
        paths+=("$path")
    done
    ((${#candidates[@]})) || continue

    checkout=$(mktemp -d "$RECIPE_ROOT/.work/source.XXXXXX")
    args=(--depth 1 --filter=blob:none --sparse)
    [[ $branch == HEAD ]] || args+=(--branch "$branch")
    git_clone "$checkout" "${args[@]}" -- "$url"
    if [[ " ${paths[*]} " == *' . '* ]]; then
        retry_network git -C "$checkout" sparse-checkout disable
    else
        retry_network git -C "$checkout" sparse-checkout set -- "${paths[@]}"
    fi
    printf 'custom\t%s\t%s\t%s\t%s\n' "${candidates[*]}" "$url" "$branch" \
        "$(git -C "$checkout" rev-parse HEAD)" >> "$RECIPE_ROOT/.work/sources.lock"

    for mapping in "${candidates[@]}"; do
        path=${mapping%%:*}
        name=${mapping##*:}
        [[ -f "$checkout/$path/Makefile" ]] || { echo "$url 缺少 $path/Makefile" >&2; exit 1; }
        # 删除同名定义后再重建索引，避免依赖解析命中另一份包。
        find feeds package \( -type d -o -type l \) -name "$name" -prune -exec rm -rf -- {} +
        mkdir -p "custom/$name"
        cp -a "$checkout/$path/." "custom/$name/"
        rm -rf "custom/$name/.git"
        echo "$name：使用 $url ($branch)"
    done
    rm -rf "$checkout"
done < "$RECIPE_ROOT/feeds/custom.conf"

# Kong 的旧版本号含日期连字符，APK 只允许用 -r 标记修订号。
# 在建立 feed 索引前仅修正这个已知版本；点分隔写法也兼容 IPK。
adguard_makefile=custom/luci-app-adguardhome/Makefile
if [[ -f $adguard_makefile ]] && grep -qxF 'PKG_VERSION:=1.8-20221120' "$adguard_makefile"; then
    sed -i 's/^PKG_VERSION:=1[.]8-20221120$/PKG_VERSION:=1.8.20221120/' "$adguard_makefile"
    echo 'luci-app-adguardhome：版本号 1.8-20221120 → 1.8.20221120（APK 兼容）'
fi

printf '\nsrc-link custom %s/custom\n' "$SOURCE_DIR" >> feeds.conf
# 首次注册新 feed 必须执行 update；prepare.sh 的 update -i 只重建已有索引。
retry_network ./scripts/feeds update custom
