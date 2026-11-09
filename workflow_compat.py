def wrap_async_execute(origin_execute, on_executed):
    async def swizzle_execute(*args, **kwargs):
        server = args[0]
        dynprompt = args[1]
        current_item = args[3]
        prompt_id = args[6]
        class_type = dynprompt.get_node(current_item)["class_type"]
        result = await origin_execute(*args, **kwargs)
        on_executed(
            class_type, server.last_node_id, prompt_id, server, current_item
        )
        return result

    return swizzle_execute
