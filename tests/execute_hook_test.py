import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace


def load_execute_hook():
    path = Path(__file__).resolve().parents[1] / "execute_hook.py"
    spec = importlib.util.spec_from_file_location("execute_hook_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HOOK = load_execute_hook()

CANONICAL = (
    "server",
    "dynprompt",
    "caches",
    "current_item",
    "extra_data",
    "executed",
    "prompt_id",
    "execution_list",
    "pending_subgraph_results",
    "pending_async_nodes",
    "ui_outputs",
    "asset_manager",
)


class _Graph:
    def __init__(self, class_type):
        self.class_type = class_type

    def get_node(self, node_id):
        return {"class_type": self.class_type, "id": node_id}


def _call_args(names, values):
    return dict(zip(names, values, strict=True))


def _record(bucket):
    def record(*args):
        bucket.append(args)

    return record


class ExecuteHookTest(unittest.IsolatedAsyncioTestCase):
    async def test_forwards_twelve_positionals(self):
        seen = {}
        graph = _Graph("EmptyImage")
        server = SimpleNamespace(last_node_id="2")
        values = [
            server,
            graph,
            object(),
            "1",
            object(),
            object(),
            "prompt-twelve",
            object(),
            object(),
            object(),
            object(),
            object(),
        ]

        async def execute(
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
            seen["args"] = (
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
            )
            return seen["args"]

        recorded = []
        module = SimpleNamespace(execute=execute)
        self.assertTrue(HOOK.install_execute_hook(module, _record(recorded)))
        result = await module.execute(*values)
        self.assertIs(result, seen["args"])
        for got, expected in zip(seen["args"], values, strict=True):
            self.assertIs(got, expected)
        self.assertEqual(
            recorded,
            [("EmptyImage", "2", "prompt-twelve", server, "1")],
        )

    async def test_forwards_thirteenth_positional(self):
        seen = {}
        graph = _Graph("EmptyImage")
        server = SimpleNamespace(last_node_id="2")
        extra = object()
        values = [
            server,
            graph,
            object(),
            "1",
            object(),
            object(),
            "prompt-thirteen",
            object(),
            object(),
            object(),
            object(),
            object(),
            extra,
        ]

        async def execute(
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
            future_parameter,
        ):
            seen["thirteenth"] = future_parameter
            return future_parameter

        module = SimpleNamespace(execute=execute)
        self.assertTrue(HOOK.install_execute_hook(module, lambda *_args: None))
        result = await module.execute(*values)
        self.assertIs(result, extra)
        self.assertIs(seen["thirteenth"], extra)

    async def test_keywords_record_prompt_id(self):
        graph = _Graph("SaveImage")
        server = SimpleNamespace(last_node_id="9")
        prompt_id = "prompt-keyword"
        values = [
            server,
            graph,
            object(),
            "4",
            object(),
            object(),
            prompt_id,
            object(),
            object(),
            object(),
            object(),
            object(),
        ]
        recorded = []

        async def execute(
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
            return prompt_id

        module = SimpleNamespace(execute=execute)
        self.assertTrue(HOOK.install_execute_hook(module, _record(recorded)))
        result = await module.execute(**_call_args(CANONICAL, values))
        self.assertIs(result, prompt_id)
        self.assertEqual(recorded, [("SaveImage", "9", prompt_id, server, "4")])

    async def test_reordered_signature_records_named_prompt_id(self):
        graph = _Graph("SaveImage")
        server = SimpleNamespace(last_node_id="9")
        prompt_id = "prompt-reordered"
        recorded = []

        async def execute(prompt_id, current_item, dynprompt, server, extra):
            return prompt_id

        module = SimpleNamespace(execute=execute)
        self.assertTrue(HOOK.install_execute_hook(module, _record(recorded)))
        result = await module.execute(prompt_id, "4", graph, server, "extra")
        self.assertEqual(result, prompt_id)
        self.assertEqual(recorded, [("SaveImage", "9", prompt_id, server, "4")])

    async def test_second_install_does_not_wrap_twice(self):
        recorded = []
        graph = _Graph("EmptyImage")
        server = SimpleNamespace(last_node_id="2")

        async def execute(server, dynprompt, current_item, prompt_id):
            return "once"

        module = SimpleNamespace(execute=execute)
        self.assertTrue(HOOK.install_execute_hook(module, _record(recorded)))
        wrapped = module.execute
        self.assertTrue(HOOK.install_execute_hook(module, _record(recorded)))
        self.assertIs(module.execute, wrapped)
        result = await module.execute(server, graph, "1", "prompt-once")
        self.assertEqual(result, "once")
        self.assertEqual(len(recorded), 1)

    async def test_timing_failure_returns_original_result(self):
        sentinel = object()
        graph = _Graph("EmptyImage")
        server = SimpleNamespace(last_node_id="2")

        async def execute(server, dynprompt, current_item, prompt_id):
            return sentinel

        def fail(_class_type, _last_node_id, _prompt_id, _server, _current_item):
            raise RuntimeError("timing broke")

        module = SimpleNamespace(execute=execute)
        self.assertTrue(HOOK.install_execute_hook(module, fail))
        with self.assertLogs("comfy-deploy.execute_hook", level="ERROR") as logs:
            result = await module.execute(server, graph, "1", "prompt-timing")
        self.assertIs(result, sentinel)
        self.assertIn("node timing failed", "\n".join(logs.output))

    async def test_execute_exception_propagates(self):
        async def execute(server, dynprompt, current_item, prompt_id):
            raise RuntimeError("node failed")

        recorded = []
        module = SimpleNamespace(execute=execute)
        self.assertTrue(HOOK.install_execute_hook(module, _record(recorded)))
        with self.assertRaisesRegex(RuntimeError, "node failed"):
            await module.execute(
                SimpleNamespace(last_node_id="2"),
                _Graph("EmptyImage"),
                "1",
                "prompt-error",
            )
        self.assertEqual(recorded, [])

    def test_missing_execute_leaves_module_alone(self):
        module = SimpleNamespace()
        self.assertFalse(HOOK.install_execute_hook(module, lambda *_args: None))
        self.assertFalse(hasattr(module, "execute"))

    def test_sync_execute_stays_in_place(self):
        def execute(server, dynprompt, current_item, prompt_id):
            return "sync"

        module = SimpleNamespace(execute=execute)
        self.assertFalse(HOOK.install_execute_hook(module, lambda *_args: None))
        self.assertIs(module.execute, execute)

    def test_missing_name_stays_in_place(self):
        async def execute(server, current_item, prompt_id):
            return "missing dynprompt"

        module = SimpleNamespace(execute=execute)
        self.assertFalse(HOOK.install_execute_hook(module, lambda *_args: None))
        self.assertIs(module.execute, execute)


if __name__ == "__main__":
    unittest.main()
