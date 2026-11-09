import asyncio
import inspect
import logging

_LOG = logging.getLogger("comfy-deploy.execute_hook")
_MARKER = "_comfy_deploy_execute_hook"
_TIMING_NAMES = ("server", "dynprompt", "current_item", "prompt_id")


def install_execute_hook(execution_module, on_node_finished):
    origin = getattr(execution_module, "execute", None)
    if origin is None:
        return False
    if getattr(origin, _MARKER, False):
        return True
    if not asyncio.iscoroutinefunction(origin):
        return False

    signature = inspect.signature(origin)
    if any(name not in signature.parameters for name in _TIMING_NAMES):
        return False

    indexes = _positional_indexes(signature)

    async def forward(*args, **kwargs):
        result = await origin(*args, **kwargs)
        try:
            recorded = _timing_args(args, kwargs, indexes)
            if recorded is not None:
                on_node_finished(*recorded)
        except Exception:
            _LOG.exception("node timing failed")
        return result

    setattr(forward, _MARKER, True)
    execution_module.execute = forward
    return True


def _positional_indexes(signature):
    indexes = {}
    position = 0
    for name, param in signature.parameters.items():
        if param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            indexes[name] = position
            position += 1
        elif param.kind is inspect.Parameter.VAR_POSITIONAL:
            break
    return indexes


def _timing_args(args, kwargs, indexes):
    values = []
    for name in _TIMING_NAMES:
        if name in kwargs:
            values.append(kwargs[name])
            continue
        index = indexes.get(name)
        if index is None or index >= len(args):
            return None
        values.append(args[index])
    server, dynprompt, current_item, prompt_id = values
    class_type = dynprompt.get_node(current_item)["class_type"]
    return (
        class_type,
        server.last_node_id,
        prompt_id,
        server,
        current_item,
    )
