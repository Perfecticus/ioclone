import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = REPO_ROOT / "server"


class ServerStartupTests(unittest.TestCase):
    def test_documented_server_entrypoint_imports_from_server_directory(self):
        result = subprocess.run(
            [sys.executable, "-c", "import main; print(main.app.title)"],
            cwd=SERVER_DIR,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_package_entrypoint_imports_from_repository_root(self):
        result = subprocess.run(
            [sys.executable, "-c", "import server.main; print(server.main.app.title)"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
