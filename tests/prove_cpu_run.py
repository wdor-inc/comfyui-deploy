import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def workflow_api(filename_prefix):
    return {
        "1": {
            "class_type": "EmptyImage",
            "inputs": {
                "width": 64,
                "height": 64,
                "batch_size": 1,
                "color": 0,
            },
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["1", 0],
                "filename_prefix": filename_prefix,
            },
        },
    }


def workflow_graph():
    return {
        "nodes": [
            {"id": 1, "type": "EmptyImage"},
            {"id": 2, "type": "SaveImage"},
        ]
    }


def run_body(prompt_id, filename_prefix):
    return {
        "prompt_id": prompt_id,
        "workflow_api_raw": workflow_api(filename_prefix),
        "workflow": workflow_graph(),
        "inputs": {},
    }


def http(method, url, body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, raw
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def wait_ready(base, deadline):
    while time.time() < deadline:
        try:
            status, _raw = http("GET", base + "/", timeout=5)
            if status == 200:
                return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(1)
    sys.exit("ComfyUI did not answer GET /")


def history_status(base, prompt_id):
    status, raw = http("GET", f"{base}/history/{urllib.parse.quote(prompt_id)}")
    if status != 200:
        return None
    payload = json.loads(raw) if raw else {}
    entry = payload.get(prompt_id) if isinstance(payload, dict) else None
    if not isinstance(entry, dict):
        return None
    state = entry.get("status")
    if not isinstance(state, dict):
        return None
    return state


def wait_history(base, prompt_id, deadline):
    while time.time() < deadline:
        state = history_status(base, prompt_id)
        if state is not None and state.get("completed") is True:
            return state
        time.sleep(1)
    sys.exit(f"history for {prompt_id} did not complete")


def print_check_status(base, prompt_id):
    status, raw = http(
        "GET",
        f"{base}/comfyui-deploy/check-status?prompt_id={urllib.parse.quote(prompt_id)}",
    )
    text = raw.decode(errors="replace") if raw else ""
    print(f"check-status {prompt_id} http={status} {text}")


def post_run(base, body):
    status, raw = http("POST", f"{base}/comfyui-deploy/run", body)
    text = raw.decode(errors="replace") if raw else ""
    print(f"post {body['prompt_id']} http={status} {text}")
    if status != 200:
        sys.exit(f"run {body['prompt_id']} was not accepted")
    return json.loads(raw)


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8188"
    base = base.rstrip("/")
    wait_ready(base, time.time() + 180)
    runs = (
        ("proof-new-version", "proof-new"),
        ("proof-stored-version", "proof-stored"),
    )
    for prompt_id, prefix in runs:
        post_run(base, run_body(prompt_id, prefix))
        state = wait_history(base, prompt_id, time.time() + 180)
        print_check_status(base, prompt_id)
        completed = state.get("completed")
        status_str = state.get("status_str")
        print(f"history {prompt_id} completed={completed} status_str={status_str}")
        if completed is not True or status_str != "success":
            sys.exit(f"history for {prompt_id} was {status_str}")
    print("both history entries completed with status_str success")


if __name__ == "__main__":
    main()
