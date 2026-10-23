"""使用本地仓库和故障替身检查重试，不访问网络。"""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or shutil.which("C:/Program Files/Git/bin/bash.exe")


@unittest.skipUnless(BASH, "需要 Bash")
class NetworkTests(unittest.TestCase):
    def run_shell(self, script, *arguments):
        return subprocess.run(
            [BASH, "-c", "set -Eeuo pipefail\nsource .github/scripts/network.sh\nsleep() { :; }\n" + script,
             "network-test", *arguments],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=20,
        )

    def test_transient_failure_retries_and_recovers(self):
        result = self.run_shell("""
attempts=0
flaky() { attempts=$((attempts + 1)); ((attempts == 3)); }
retry_network flaky
printf '%s' "$attempts"
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "3")

    def test_permanent_failure_stops_after_three_attempts_with_original_status(self):
        result = self.run_shell("""
fail() { printf 'attempt\\n'; return 23; }
retry_network fail
""")
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["attempt"] * 3)

    def test_clone_removes_partial_checkout_before_retry(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".work") as directory:
            destination = Path(directory) / "checkout"
            result = self.run_shell("""
attempts=0
git() {
    local destination=${@: -1}
    attempts=$((attempts + 1))
    if ((attempts == 1)); then
        mkdir -p "$destination"
        touch "$destination/partial"
        return 128
    fi
    [[ ! -e $destination/partial ]] || return 77
    mkdir -p "$destination"
    touch "$destination/complete"
}
git_clone "$1" --depth 1 -- https://example.invalid/source.git
""", destination.as_posix())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((destination / "complete").is_file())
            self.assertFalse((destination / "partial").exists())

    def test_clone_never_deletes_an_existing_checkout(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".work") as directory:
            marker = Path(directory) / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            result = self.run_shell('git_clone "$1" -- https://example.invalid/source.git', Path(directory).as_posix())
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_failed_clone_exhaustion_leaves_no_partial_checkout(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".work") as directory:
            destination = Path(directory) / "checkout"
            result = self.run_shell("""
git() {
    local destination=${@: -1}
    mkdir -p "$destination"
    touch "$destination/partial"
    printf 'attempt\\n'
    return 128
}
git_clone "$1" -- https://example.invalid/source.git
""", destination.as_posix())
            self.assertEqual(result.returncode, 128, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["attempt"] * 3)
            self.assertFalse(destination.exists())

    def test_real_local_clone_with_spaces_in_paths(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".work") as directory:
            source = (Path(directory) / "source repo").as_posix()
            destination = Path(directory) / "new checkout"
            destination.mkdir()
            result = self.run_shell("""
git init --quiet "$1"
git -C "$1" -c user.name=Test -c user.email=test@example.invalid commit --quiet --allow-empty -m initial
git_clone "$2" --depth 1 -- "$1"
git -C "$2" rev-parse --verify HEAD
""", source, destination.as_posix())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(result.stdout.strip()), 40)


if __name__ == "__main__":
    unittest.main()
