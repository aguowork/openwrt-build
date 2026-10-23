"""Apply required private build settings to the ephemeral OpenWrt tree."""

import os
from pathlib import Path
import re
import shlex
import shutil
import sys


def required_secret(name):
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"缺少 GitHub Secret：{name}")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"GitHub Secret {name} 包含无效控制字符。")
    return value


def replace_once(path, pattern, replacement, label):
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"{path}: 预期恰好一处 {label}，实际找到 {count} 处。")
    path.write_text(updated, encoding="utf-8")


def uci_quote(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def update_shell_config(path, values):
    for key, value in values.items():
        replace_once(path, rf"^{re.escape(key)}=.*$", f"{key}={shlex.quote(value)}", key)


def update_uci_config(path, values):
    for key, value in values.items():
        pattern = rf"^(?P<indent>[ \t]*)(?:#[ \t]*)?option[ \t]+{re.escape(key)}(?:[ \t]+.*)?$"
        replacement = lambda match: f"{match.group('indent')}option {key} {uci_quote(value)}"
        replace_once(path, pattern, replacement, f"option {key}")


def update_ddnsto_config(path, token):
    content = path.read_text(encoding="utf-8")
    for key, value in (("enabled", "1"), ("index", "0")):
        pattern = rf"^(?P<indent>[ \t]*)option[ \t]+{key}(?:[ \t]+.*)?$"
        content, count = re.subn(
            pattern,
            lambda match: f"{match.group('indent')}option {key} {uci_quote(value)}",
            content,
            flags=re.MULTILINE,
        )
        if count != 1:
            raise ValueError(f"{path}: 预期恰好一处 option {key}，实际找到 {count} 处。")

    token_pattern = r"^(?P<indent>[ \t]*)(?:#[ \t]*)?option[ \t]+token(?:[ \t]+.*)?$"
    content, count = re.subn(
        token_pattern,
        lambda match: f"{match.group('indent')}option token {uci_quote(token)}",
        content,
        flags=re.MULTILINE,
    )
    if count == 0:
        content = content.rstrip() + f"\n\toption token {uci_quote(token)}\n"
    elif count != 1:
        raise ValueError(f"{path}: token 配置重复。")
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def configure(root):
    ddnsto_token = required_secret("DDNSTO_TOKEN")
    wxpusher_token = required_secret("WXPUSHER_TOKEN")
    wxpusher_uids = required_secret("WXPUSHER_UIDS")
    sc3_key = required_secret("WECHATPUSH_SC3KEY")
    sc3_uid = required_secret("WECHATPUSH_SC3UID")
    if not re.fullmatch(r"AT_[A-Za-z0-9_-]+", wxpusher_token):
        raise ValueError("GitHub Secret WXPUSHER_TOKEN 格式无效。")
    if not re.fullmatch(r"UID_[A-Za-z0-9_-]+", wxpusher_uids):
        raise ValueError("GitHub Secret WXPUSHER_UIDS 格式无效。")

    shell_configs = (
        root / "files/etc/JiaoBen/wxpusher.conf",
        root / "files/etc/wx/wx_settings.conf",
    )
    for path in shell_configs:
        update_shell_config(path, {
            "WXPUSHER_ENABLED": "1",
            "WX_APP_TOKEN": wxpusher_token,
            "WX_MY_UID": wxpusher_uids,
        })
        path.chmod(0o600)

    update_uci_config(root / "files/etc/config/wechatpush", {
        "sc3key": sc3_key,
        "sc3uid": sc3_uid,
    })
    (root / "files/etc/config/wechatpush").chmod(0o600)

    # 只改固件覆盖文件，不向下载的软件包源码写入凭据。
    ddnsto = root / "files/etc/config/ddnsto"
    ddnsto.parent.mkdir(parents=True, exist_ok=True)
    if not ddnsto.is_file():
        shutil.copyfile(root / "custom/ddnsto/files/ddnsto.config", ddnsto)
    update_ddnsto_config(ddnsto, ddnsto_token)
    permissions_script = root / "files/etc/uci-defaults/999-private-config-permissions"
    permissions_script.parent.mkdir(parents=True, exist_ok=True)
    permissions_script.write_text(
        "#!/bin/sh\n"
        "for path in /etc/config/ddnsto /etc/config/wechatpush /etc/JiaoBen/wxpusher.conf /etc/wx/wx_settings.conf; do\n"
        "    [ ! -f \"$path\" ] || chmod 600 \"$path\"\n"
        "done\n"
        "exit 0\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("用法：inject_secrets.py OPENWRT_ROOT")
        configure(Path(sys.argv[1]))
    except (OSError, ValueError) as error:
        print(f"私有配置注入失败：{error}", file=sys.stderr)
        sys.exit(1)
