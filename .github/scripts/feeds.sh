#!/usr/bin/env bash
# 先生成上游 feeds，再将清单中的包集中到一个本地 feed。
set -Eeuo pipefail
: "${RECIPE_ROOT:?}" "${SOURCE_DIR:?}" "${INCLUDE_PASSWALL:?}"
cd "$SOURCE_DIR"

[[ -f feeds.conf ]] || cp feeds.conf.default feeds.conf
sed -i '/^[^#]*[[:space:]]\(packages_ext\|small8\|custom_feed\|custom\)[[:space:]]/d' feeds.conf
./scripts/feeds update -a

for feed in feeds/*; do
    [[ -e "$feed/.git" ]] || continue
    printf 'feed\t%s\t%s\t%s\t%s\n' "${feed##*/}" \
        "$(git -C "$feed" remote get-url origin)" \
        "$(git -C "$feed" symbolic-ref --short -q HEAD || printf detached)" \
        "$(git -C "$feed" rev-parse HEAD)" >> "$RECIPE_ROOT/.work/sources.lock"
done

# Go 的辅助文件必须保留在 feeds/packages/lang/golang，不能移入普通插件 feed。
# shellcheck source=/dev/null
source "$RECIPE_ROOT/feeds/golang.conf"
: "${GOLANG_URL:?}" "${GOLANG_BRANCH:?}"
compiler_checkout=$(mktemp -d "$RECIPE_ROOT/.work/golang.XXXXXX")
git clone --depth 1 --branch "$GOLANG_BRANCH" -- "$GOLANG_URL" "$compiler_checkout"
[[ -f "$compiler_checkout/golang/Makefile" && -f "$compiler_checkout/golang-package.mk" ]] || {
    echo 'Go 软件源缺少编译所需的 Makefile。' >&2
    exit 1
}
printf 'toolchain\tgolang\t%s\t%s\t%s\n' "$GOLANG_URL" "$GOLANG_BRANCH" \
    "$(git -C "$compiler_checkout" rev-parse HEAD)" >> "$RECIPE_ROOT/.work/sources.lock"
rm -rf feeds/packages/lang/golang
mv "$compiler_checkout" feeds/packages/lang/golang

mkdir -p custom
while IFS='|' read -r condition policy url branch mappings; do
    [[ -n $condition && $condition != \#* ]] || continue
    case "$condition" in
        always) ;;
        passwall) [[ $INCLUDE_PASSWALL == true ]] || continue ;;
        *) echo "未知软件源条件：$condition" >&2; exit 1 ;;
    esac
    [[ $policy == replace || $policy == missing ]] || { echo "未知替换策略：$policy" >&2; exit 1; }

    read -r -a candidates <<< "$mappings"
    selected=()
    paths=()
    for mapping in "${candidates[@]}"; do
        path=${mapping%%:*}
        name=${mapping##*:}
        [[ $name =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ && $path != /* && $path != *..* ]] || {
            echo "无效的包映射：$mapping" >&2; exit 1;
        }
        if [[ $policy == missing ]] && [[ -n $(find feeds package -type f -path "*/$name/Makefile" -print -quit) ]]; then
            echo "$name：保留上游版本"
            continue
        fi
        selected+=("$mapping")
        paths+=("$path")
    done
    ((${#selected[@]})) || continue

    checkout=$(mktemp -d "$RECIPE_ROOT/.work/source.XXXXXX")
    args=(clone --depth 1 --filter=blob:none --sparse)
    [[ $branch == HEAD ]] || args+=(--branch "$branch")
    git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=60 "${args[@]}" -- "$url" "$checkout"
    if [[ " ${paths[*]} " == *' . '* ]]; then
        git -C "$checkout" sparse-checkout disable
    else
        git -C "$checkout" sparse-checkout set -- "${paths[@]}"
    fi
    printf 'custom\t%s\t%s\t%s\t%s\n' "${selected[*]}" "$url" "$branch" \
        "$(git -C "$checkout" rev-parse HEAD)" >> "$RECIPE_ROOT/.work/sources.lock"

    for mapping in "${selected[@]}"; do
        path=${mapping%%:*}
        name=${mapping##*:}
        [[ -f "$checkout/$path/Makefile" ]] || { echo "$url 缺少 $path/Makefile" >&2; exit 1; }
        # 删除同名定义后再重建索引，避免依赖解析命中另一份包。
        find feeds package -type d -name "$name" -prune -exec rm -rf {} +
        mkdir -p "custom/$name"
        cp -a "$checkout/$path/." "custom/$name/"
        rm -rf "custom/$name/.git"
        echo "$name：使用 $url ($branch)"
    done
    rm -rf "$checkout"
done < "$RECIPE_ROOT/feeds/custom.conf"

# Kong 的 LuCI 应用在运行时下载官方核心，不保留 feeds 或源码自带的
# adguardhome 包；在全部包准备完成后清理，再由 prepare.sh 统一重建索引。
find feeds package custom \( -type d -o -type l \) -name adguardhome -prune -exec rm -rf -- {} +

printf '\nsrc-link custom %s/custom\n' "$SOURCE_DIR" >> feeds.conf
# prepare.sh 在应用补丁后统一重建索引并安装，避免重复索引 custom。
