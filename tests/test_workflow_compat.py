"""Locks the ComfyUI launch pin and the execution-hook contract workflows rely on."""

import json
import unittest
from pathlib import Path

from workflow_compat import COMFYUI_COMMIT, COMFYUI_RELEASE, forward_execute_args

ROOT = Path(__file__).resolve().parents[1]

# Core node types in the checked-in workflows. Input names for these nodes
# were compared from the workflow's comfy-core (v0.3.12 through v0.3.19) to
# ComfyUI v0.44.0. Required names are unchanged; v0.44.0 only adds optional inputs.
COMPATIBLE_CORE_NODES = frozenset(
    {
        "BasicGuider",
        "BasicScheduler",
        "CLIPLoader",
        "CLIPTextEncode",
        "CLIPVisionEncode",
        "CLIPVisionLoader",
        "CheckpointLoaderSimple",
        "DualCLIPLoader",
        "EmptyHunyuanLatentVideo",
        "EmptyLatentImage",
        "EmptySD3LatentImage",
        "FluxGuidance",
        "ImageToMask",
        "JoinImageWithAlpha",
        "KSampler",
        "KSamplerSelect",
        "LoadImage",
        "LoraLoader",
        "MaskToImage",
        "ModelSamplingSD3",
        "PreviewImage",
        "RandomNoise",
        "SamplerCustomAdvanced",
        "SaveAnimatedWEBP",
        "SaveImage",
        "SaveWEBM",
        "SplitImageWithAlpha",
        "TripleCLIPLoader",
        "UNETLoader",
        "VAEDecode",
        "VAEDecodeTiled",
        "VAEEncodeForInpaint",
        "VAELoader",
        "WanImageToVideo",
    }
)

UI_ONLY_NODES = frozenset({"Note", "MarkdownNote"})


def _execute_v0368(
    server,
    dynprompt,
    caches,
    current_item,
    extra_data,
    executed,
    prompt_id,
    execution_list,
    pending_subgraph_results,
    pending_async_nodes,
    ui_outputs,
):
    return ("v0.3.68", ui_outputs)


def _execute_v044(
    server,
    dynprompt,
    caches,
    current_item,
    extra_data,
    executed,
    prompt_id,
    execution_list,
    pending_subgraph_results,
    pending_async_nodes,
    ui_outputs,
    asset_manager,
):
    return ("v0.44.0", ui_outputs, asset_manager)


class ExecuteForwardTests(unittest.TestCase):
    def test_v0368_forwards_ui_outputs_and_stops_there(self):
        args = tuple(f"arg{i}" for i in range(11))
        forwarded = forward_execute_args(_execute_v0368, args)
        self.assertEqual(len(forwarded), 11)
        self.assertEqual(_execute_v0368(*forwarded), ("v0.3.68", "arg10"))

    def test_v044_forwards_asset_manager(self):
        args = tuple(f"arg{i}" for i in range(12))
        forwarded = forward_execute_args(_execute_v044, args)
        self.assertEqual(len(forwarded), 12)
        self.assertEqual(
            _execute_v044(*forwarded),
            ("v0.44.0", "arg10", "arg11"),
        )

    def test_v044_call_shape_is_not_trimmed_to_v0368(self):
        args = tuple(range(12))
        forwarded = forward_execute_args(_execute_v044, args)
        self.assertEqual(forwarded[-1], 11)
        self.assertNotEqual(len(forwarded), 11)


class LaunchPinTests(unittest.TestCase):
    def test_release_constant_matches_commit(self):
        self.assertEqual(COMFYUI_RELEASE, "v0.44.0")
        self.assertEqual(COMFYUI_COMMIT, "2c75dc1b379a59e0880619d029607af5169a62ef")

    def test_snapshot_dockerfile_and_machine_default_use_the_same_commit(self):
        snapshot = json.loads(
            (
                ROOT / "builder/modal-builder/src/template/data/snapshot.json"
            ).read_text()
        )
        dockerfile = (
            ROOT / "builder/modal-builder/src/template/Dockerfile"
        ).read_text()
        machine_default = (ROOT / "web/src/server/addMachineSchema.ts").read_text()
        launcher = (ROOT / "builder/modal-builder/src/template/app.py").read_text()

        self.assertEqual(snapshot["comfyui"], COMFYUI_COMMIT)
        self.assertIn(f"git reset --hard {COMFYUI_COMMIT}", dockerfile)
        self.assertIn(COMFYUI_COMMIT, machine_default)
        self.assertIn("comfyui-launch-snapshot.json", launcher)
        self.assertIn("git", launcher)
        self.assertIn("checkout", launcher)


class WorkflowGraphTests(unittest.TestCase):
    def test_checked_in_workflows_use_compatible_core_nodes(self):
        paths = list((ROOT / "examples").glob("*.json")) + list(
            (ROOT / "example_workflows").glob("*.json")
        )
        self.assertGreaterEqual(len(paths), 9)
        for path in paths:
            graph = json.loads(path.read_text())
            self.assertIn("nodes", graph)
            self.assertIsInstance(graph["nodes"], list)
            for node in graph["nodes"]:
                node_type = node["type"]
                if node_type in UI_ONLY_NODES or node_type.startswith("Comfy"):
                    continue
                self.assertIn(
                    node_type,
                    COMPATIBLE_CORE_NODES,
                    f"{path.name} uses {node_type}, which was not checked against {COMFYUI_RELEASE}",
                )


if __name__ == "__main__":
    unittest.main()
