"""Compatibility helpers for the ComfyUI version this plugin launches and runs inside."""

import inspect

# Latest GitHub release of https://github.com/comfyanonymous/ComfyUI (v0.44.0).
COMFYUI_RELEASE = "v0.44.0"
COMFYUI_COMMIT = "2c75dc1b379a59e0880619d029607af5169a62ef"


def forward_execute_args(origin_execute, args):
    """Positional arguments the installed ``execution.execute`` accepts.

    ComfyUI adds parameters at the end of ``execute`` as it grows
    (``ui_outputs`` in v0.3.68, ``asset_manager`` in v0.44.0). The caller
    passes the full list for the version that is installed. Forward every
    positional parameter that version declares so a workflow still runs.
    """
    signature = inspect.signature(origin_execute)
    parameters = list(signature.parameters.values())
    if any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters):
        return tuple(args)
    positional_count = sum(
        1
        for parameter in parameters
        if parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    )
    return tuple(args[:positional_count])
