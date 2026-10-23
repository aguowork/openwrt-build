"""覆盖配置解析、依赖调整及所选功能缺失等构建回归。"""

from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github/scripts"))
import config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def write(self, name, text):
        path = self.directory / name
        path.write_text(text, encoding="utf-8")
        return path

    def verify(self, requested, actual):
        requested = self.write("requested.config", requested)
        actual = self.write("actual.config", actual)
        with redirect_stdout(io.StringIO()):
            config.verify_config(requested, actual)

    def test_package_names_with_dots_and_hyphens(self):
        path = self.write("input.config", "CONFIG_PACKAGE_libusb-1.0=y\n# CONFIG_PACKAGE_libfoo-2.0 is not set\n")
        self.assertEqual(config.read_config(path), {
            "CONFIG_PACKAGE_libusb-1.0": "y", "CONFIG_PACKAGE_libfoo-2.0": "n",
        })

    def test_later_fragments_override_enabled_and_disabled_options(self):
        base = self.write("base.config", "CONFIG_PACKAGE_curl=y\n# CONFIG_PACKAGE_jq is not set\n")
        feature = self.write("feature.config", "# CONFIG_PACKAGE_curl is not set\nCONFIG_PACKAGE_jq=y\n")
        merged = self.write("merged.config", config.merge_configs([base, feature]))
        self.assertEqual(config.read_config(merged), {
            "CONFIG_PACKAGE_curl": "n", "CONFIG_PACKAGE_jq": "y",
        })

    def test_kernel_modules_and_libraries_can_be_selected_by_dependencies(self):
        self.verify(
            "# CONFIG_PACKAGE_kmod-wireguard is not set\n# CONFIG_PACKAGE_libusb-1.0 is not set\n",
            "CONFIG_PACKAGE_kmod-wireguard=y\nCONFIG_PACKAGE_libusb-1.0=y\n",
        )

    def test_disabled_application_or_service_cannot_be_reenabled(self):
        for package in ("luci-app-passwall", "wireguard-tools"):
            with self.subTest(package=package), self.assertRaisesRegex(ValueError, package):
                self.verify(f"# CONFIG_PACKAGE_{package} is not set\n", f"CONFIG_PACKAGE_{package}=y\n")

    def test_selected_device_application_and_build_options_must_survive(self):
        for key in ("CONFIG_TARGET_mediatek_filogic_DEVICE_xiaomi_redmi-router-ax6000-ubootmod",
                    "CONFIG_PACKAGE_luci-app-wechatpush", "CONFIG_PACKAGE_curl",
                    "CONFIG_CCACHE", "CONFIG_JSON_OVERVIEW_IMAGE_INFO"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                self.verify(f"{key}=y\n", "")

    def test_luci_suboptions_are_allowed_to_follow_upstream(self):
        self.verify("CONFIG_PACKAGE_luci-app-wechatpush_Enable_Host_Information_Detection=y\n", "")

    def test_module_promoted_to_builtin_is_allowed(self):
        self.verify("CONFIG_PACKAGE_kmod-tls=m\n", "CONFIG_PACKAGE_kmod-tls=y\n")

    def test_daed_requires_each_kernel_capability(self):
        requested = "CONFIG_PACKAGE_luci-app-daed=y\n"
        for missing in sorted(config.DAED_KERNEL_OPTIONS):
            actual = requested + "".join(f"{key}=y\n" for key in config.DAED_KERNEL_OPTIONS if key != missing)
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, missing):
                self.verify(requested, actual)

    def test_daed_accepts_complete_kernel_support(self):
        requested = "CONFIG_PACKAGE_luci-app-daed=y\n"
        self.verify(requested, requested + "".join(f"{key}=y\n" for key in config.DAED_KERNEL_OPTIONS))

    def test_daed_rejects_reduced_debug_info(self):
        requested = "CONFIG_PACKAGE_luci-app-daed=y\n"
        actual = requested + "".join(f"{key}=y\n" for key in config.DAED_KERNEL_OPTIONS)
        with self.assertRaisesRegex(ValueError, "CONFIG_KERNEL_DEBUG_INFO_REDUCED"):
            self.verify(requested, actual + "CONFIG_KERNEL_DEBUG_INFO_REDUCED=y\n")

    def test_other_features_do_not_require_daed_kernel_options(self):
        self.verify("CONFIG_PACKAGE_luci-app-passwall=y\n", "CONFIG_PACKAGE_luci-app-passwall=y\n")


if __name__ == "__main__":
    unittest.main()
