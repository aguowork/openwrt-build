"""在最小源码树中执行定制脚本，检查兼容处理和上游漂移诊断。"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or shutil.which("C:/Program Files/Git/bin/bash.exe")


@unittest.skipUnless(BASH, "需要 Bash")
class CustomizeTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(temporary.cleanup)
        self.recipe = Path(temporary.name) / "recipe"
        self.source = Path(temporary.name) / "source"
        self.write(self.recipe, "configs/root-password.txt", "test-password\n")
        for name in (".github/scripts/network.sh", "patches/packages/miniupnpd/999-default-leaseduration.patch"):
            self.write(self.recipe, name, (ROOT / name).read_text(encoding="utf-8"))
        files = {
            "package/base-files/files/etc/shadow": "root:*:0:0:99999:7:::\n",
            "package/base-files/files/etc/openwrt_release": "DISTRIB_DESCRIPTION='Test'\n",
            "package/base-files/files/etc/banner": "Test\n",
            "include/target.mk": "DEFAULT_PACKAGES += $(DEFAULT_PACKAGES.tweak)\nDEFAULT_PACKAGES += libustream-mbedtls\n",
            "feeds/luci/collections/luci/Makefile": "LUCI_DEPENDS:=luci-theme-bootstrap\n",
            "scripts/package-metadata.pl": "<PACKAGE_$pkgname\n",
            "custom/luci-app-wechatpush/Makefile":
                "config PACKAGE_$(PKG_NAME)_Local_Disk_Information_Detection\n"
                "config PACKAGE_$(PKG_NAME)_Host_Information_Detection\n",
            "custom/open-app-filter/files/appfilter.config":
                "config global 'global'\n\toption record_enable '1'\n"
                "\toption disable_hnat '1'\n\toption auto_load_engine '1'\n",
            "package/network/services/dnsmasq/files/dhcp.conf": "\toption dns_redirect '1'\n",
            "target/linux/mediatek/Makefile": "DEFAULT_PACKAGES += kmod-wireguard\n",
            "target/linux/qualcommax/Makefile": "DEFAULT_PACKAGES += wpad-openssl\n",
            "target/linux/qualcommax/ipq807x/target.mk": "DEFAULT_PACKAGES += ath11k-firmware-ipq8074\n",
            "package/firmware/ath11k-firmware/Makefile": "define Package/ath11k-firmware-ipq8074-ddwrt\nendef\n",
        }
        for name, content in files.items():
            self.write(self.source, name, content)

    @staticmethod
    def write(root, name, content):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def customize(self, platform="mt798x"):
        env = dict(os.environ, RECIPE_ROOT=self.recipe.as_posix(), SOURCE_DIR=self.source.as_posix(),
                   PLATFORM=platform, DEVICE="redmi_ax6000_immwrt" if platform == "mt798x" else "redmi_ax6_immwrt",
                   BUILD_TIME="2026-10-23T00:00:00+08:00",
                   INCLUDE_PASSWALL="false", TEST_PYTHON=Path(sys.executable).as_posix())
        return subprocess.run(
            [BASH, "-c", 'python3() { "$TEST_PYTHON" "$@"; }\nsource "$1"', "customize-test",
             (ROOT / ".github/scripts/customize.sh").as_posix()],
            env=env, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=20,
        )

    def test_customization_works_and_accepts_already_applied_changes(self):
        for _ in range(2):
            result = self.customize()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        wechat = (self.source / "custom/luci-app-wechatpush/Makefile").read_text(encoding="utf-8")
        self.assertIn("_Enable_Local_Disk_Information_Detection", wechat)
        self.assertIn("_Enable_Host_Information_Detection", wechat)
        oaf = (self.source / "custom/open-app-filter/files/appfilter.config").read_text(encoding="utf-8")
        self.assertNotIn("'1'", oaf)
        self.assertIn("kmod-wireguard", (self.source / "target/linux/mediatek/Makefile").read_text(encoding="utf-8"))

    def test_valid_whitespace_quotes_and_comments_do_not_trigger_drift_errors(self):
        self.write(self.source, "custom/luci-app-wechatpush/Makefile",
                   "\tconfig  PACKAGE_$(PKG_NAME)_Local_Disk_Information_Detection  \n"
                   "\tconfig  PACKAGE_$(PKG_NAME)_Enable_Host_Information_Detection\n")
        self.write(self.source, "custom/open-app-filter/files/appfilter.config",
                   'config global global\n  option  record_enable  "1" # keep comment\n'
                   "\toption disable_hnat 0\n\toption auto_load_engine '0'\n")
        result = self.customize()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_wechat_upstream_rename_fails_with_actionable_error(self):
        self.write(self.source, "custom/luci-app-wechatpush/Makefile", "config PACKAGE_$(PKG_NAME)_Unexpected_Name\n")
        result = self.customize()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("微信推送配置名称已变化", result.stderr)

    def test_oaf_upstream_change_fails_with_actionable_error(self):
        self.write(self.source, "custom/open-app-filter/files/appfilter.config", "config global 'global'\n")
        result = self.customize()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OAF 默认配置未生效", result.stderr)

    def test_ax6_selects_ddwrt_firmware(self):
        result = self.customize(platform="nss")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        target = self.source / "target/linux/qualcommax/ipq807x/target.mk"
        self.assertIn("ath11k-firmware-ipq8074-ddwrt", target.read_text(encoding="utf-8"))

    def test_ax6_firmware_selection_drift_is_rejected(self):
        self.write(self.source, "target/linux/qualcommax/ipq807x/target.mk", "DEFAULT_PACKAGES += unknown-driver\n")
        result = self.customize(platform="nss")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ath11k 固件选择未生效", result.stderr)


if __name__ == "__main__":
    unittest.main()
