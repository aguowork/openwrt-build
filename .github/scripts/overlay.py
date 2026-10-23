"""只生成固件覆盖文件，不修改上游 base-files。"""

from pathlib import Path
import re
import subprocess
import sys


def configure_login(root, password_path):
    password = Path(password_path).read_text(encoding="utf-8").strip()
    if not password or any(ord(char) < 32 or ord(char) == 127 for char in password):
        raise ValueError("默认密码必须是非空的单行文本。")
    password_hash = subprocess.run(
        ["openssl", "passwd", "-6", "-stdin"],
        input=password + "\n", text=True, capture_output=True, check=True,
    ).stdout.strip()
    shadow = root / "files/etc/shadow"
    template = shadow if shadow.is_file() else root / "package/base-files/files/etc/shadow"
    content, count = re.subn(
        r"^(root:)[^:\n]*(:.*)$",
        lambda match: f"{match[1]}{password_hash}{match[2]}",
        template.read_text(encoding="utf-8"), flags=re.MULTILINE,
    )
    if count != 1:
        raise ValueError(f"{template}: 预期恰好一处 root 密码项，实际找到 {count} 处。")
    shadow.parent.mkdir(parents=True, exist_ok=True)
    shadow.write_text(content, encoding="utf-8")
    shadow.chmod(0o600)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("用法：overlay.py OPENWRT_ROOT ROOT_PASSWORD_FILE")
        configure_login(Path(sys.argv[1]), Path(sys.argv[2]))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"生成登录默认值失败：{error}", file=sys.stderr)
        sys.exit(1)
