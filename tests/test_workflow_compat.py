import asyncio
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from workflow_compat import wrap_async_execute

ROOT = Path(__file__).resolve().parents[1]
LAUNCH_COMMIT = "2c75dc1b379a59e0880619d029607af5169a62ef"
SNAPSHOT = ROOT / "builder/modal-builder/src/template/data/snapshot.json"
CHECKOUT = ROOT / "builder/modal-builder/src/template/data/checkout_comfyui.sh"


class LaunchPinTests(unittest.TestCase):
    def test_snapshot_is_the_v044_release_commit(self):
        snapshot = json.loads(SNAPSHOT.read_text())
        self.assertEqual(snapshot["comfyui"], LAUNCH_COMMIT)

    def test_machine_default_matches_the_snapshot(self):
        snapshot = json.loads(SNAPSHOT.read_text())
        machine_default = (ROOT / "web/src/server/addMachineSchema.ts").read_text()
        self.assertIn(snapshot["comfyui"], machine_default)

    def test_both_launchers_check_out_the_snapshot(self):
        dockerfile = (ROOT / "builder/modal-builder/src/template/Dockerfile").read_text()
        modal = (ROOT / "builder/modal-builder/src/template/app.py").read_text()
        self.assertNotIn(LAUNCH_COMMIT, dockerfile)
        self.assertIn("checkout_comfyui.sh", dockerfile)
        self.assertIn("checkout_comfyui.sh", modal)
        self.assertIn("comfyui-launch-snapshot.json", dockerfile)
        self.assertIn("comfyui-launch-snapshot.json", modal)

    def test_checkout_script_selects_the_snapshot_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "comfy"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "pin@example.com"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "pin"],
                cwd=repo,
                check=True,
            )
            (repo / "readme").write_text("first\n")
            subprocess.run(["git", "add", "readme"], cwd=repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "first"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            first = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            (repo / "readme").write_text("second\n")
            subprocess.run(["git", "add", "readme"], cwd=repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "second"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps({"comfyui": first}))
            subprocess.run(
                ["sh", str(CHECKOUT), str(snapshot_path), str(repo)],
                check=True,
            )
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(head, first)


class ExecuteForwardTests(unittest.TestCase):
    def test_v044_call_reaches_execute_with_asset_manager(self):
        self.assertEqual(self._run(12), 12)

    def test_v0368_call_reaches_execute_without_asset_manager(self):
        self.assertEqual(self._run(11), 11)

    def _run(self, arg_count):
        received = {}
        recorded = []

        class Server:
            last_node_id = "7"

        class Graph:
            def get_node(self, unique_id):
                return {"class_type": "KSampler"}

        async def origin(*args, **kwargs):
            received["args"] = args
            received["kwargs"] = kwargs
            return "ran"

        def on_executed(class_type, last_node_id, prompt_id, server, unique_id):
            recorded.append((class_type, last_node_id, prompt_id, unique_id))

        wrapper = wrap_async_execute(origin, on_executed)
        args = (Server(), Graph(), "caches", "node-1", {}, set(), "prompt-9")
        args += tuple(f"extra-{i}" for i in range(arg_count - len(args)))
        result = asyncio.run(wrapper(*args, preview_method="auto"))
        self.assertEqual(result, "ran")
        self.assertEqual(received["args"], args)
        self.assertEqual(received["kwargs"], {"preview_method": "auto"})
        self.assertEqual(recorded, [("KSampler", "7", "prompt-9", "node-1")])
        return len(received["args"])


if __name__ == "__main__":
    unittest.main()
