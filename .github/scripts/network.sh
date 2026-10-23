#!/usr/bin/env bash
# 仅重试可重复执行的网络操作；最多三次，保留最后一次的退出码。
retry_network() {
    local attempt status delay=5
    for attempt in 1 2 3; do
        if "$@"; then
            return 0
        else
            status=$?
        fi
        if ((attempt == 3)); then
            echo "网络操作连续失败 3 次：$1（退出码 $status）" >&2
            return "$status"
        fi
        echo "网络操作失败（$attempt/3），${delay}s 后重试：$1" >&2
        sleep "$delay"
        delay=$((delay * 2))
    done
}

clone_once() {
    local destination=$1 status
    shift
    if git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=60 clone "$@" "$destination"; then
        return 0
    else
        status=$?
    fi
    # git_clone 已确认目标不存在或为空，仅清理本次克隆的残留。
    rm -rf -- "$destination"
    return "$status"
}

git_clone() {
    local destination=$1
    shift
    if [[ -e $destination || -L $destination ]]; then
        if [[ ! -d $destination || -L $destination ]] || \
            [[ -n $(find "$destination" -mindepth 1 -maxdepth 1 -print -quit) ]]; then
            echo "拒绝覆盖已有内容的克隆目录：$destination" >&2
            return 1
        fi
    fi
    retry_network clone_once "$destination" "$@"
}
