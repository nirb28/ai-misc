import json
import os
import sys
import time
from urllib import error, parse, request


BASE_URL = os.environ.get("WREN_AI_BASE_URL", "http://localhost:5555").rstrip("/")
TIMEOUT_SECONDS = float(os.environ.get("WREN_AI_TIMEOUT", "30"))
POLL_INTERVAL_SECONDS = float(os.environ.get("WREN_AI_POLL_INTERVAL", "1.0"))
POLL_TIMEOUT_SECONDS = float(os.environ.get("WREN_AI_POLL_TIMEOUT", "20"))


def call(method, path, payload=None):
    url = f"{BASE_URL}{path}"
    headers = {}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")
            payload = json.loads(body) if "application/json" in content_type else body
            return response.status, payload
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = body
        return exc.code, payload


def print_result(title, status, payload):
    print(f"\n=== {title} ===")
    print(f"status: {status}")
    print(json.dumps(payload, indent=2) if isinstance(payload, (dict, list)) else str(payload))


def poll(path, terminal_statuses):
    started = time.time()
    while time.time() - started < POLL_TIMEOUT_SECONDS:
        status, payload = call("GET", path)
        print_result(f"poll {path}", status, payload)
        if isinstance(payload, dict) and payload.get("status") in terminal_statuses:
            return status, payload
        time.sleep(POLL_INTERVAL_SECONDS)
    return status, payload


def main():
    status, payload = call("GET", "/health")
    print_result("health", status, payload)

    status, payload = call("GET", "/openapi.json")
    paths = sorted(payload.get("paths", {}).keys()) if isinstance(payload, dict) else []
    print_result("openapi paths", status, paths)

    status, payload = call("POST", "/v1/question-recommendations", {"mdl": "model test"})
    print_result("question recommendations create", status, payload)
    if isinstance(payload, dict) and payload.get("id"):
        print_result(
            "question recommendations get",
            *call("GET", f"/v1/question-recommendations/{parse.quote(payload['id'])}")
        )

    status, payload = call("POST", "/v1/relationship-recommendations", {"mdl": "model test"})
    print_result("relationship recommendations create", status, payload)
    if isinstance(payload, dict) and payload.get("id"):
        print_result(
            "relationship recommendations get",
            *call("GET", f"/v1/relationship-recommendations/{parse.quote(payload['id'])}")
        )

    mdl_hash = f"probe-{int(time.time())}"
    status, payload = call("POST", "/v1/semantics-preparations", {"mdl": "model test", "mdl_hash": mdl_hash})
    print_result("semantics preparations create", status, payload)
    print_result(
        "semantics preparations status",
        *call("GET", f"/v1/semantics-preparations/{parse.quote(mdl_hash)}/status")
    )

    status, payload = call("POST", "/v1/sql-questions", {"sqls": ["select 1 as value"]})
    print_result("sql questions create", status, payload)
    if isinstance(payload, dict) and payload.get("query_id"):
        print_result("sql questions get", *call("GET", f"/v1/sql-questions/{payload['query_id']}"))

    status, payload = call(
        "POST",
        "/v1/sql-answers",
        {
            "query": "What is the value?",
            "sql": "select 1 as value",
            "sql_data": {"columns": ["value"], "data": [[1]]},
        },
    )
    print_result("sql answers create", status, payload)
    if isinstance(payload, dict) and payload.get("query_id"):
        poll(f"/v1/sql-answers/{payload['query_id']}", {"succeeded", "failed"})

    status, payload = call("POST", "/v1/charts", {"query": "show a chart", "sql": "select 1 as value"})
    print_result("charts create", status, payload)
    if isinstance(payload, dict) and payload.get("query_id"):
        print_result("charts get", *call("GET", f"/v1/charts/{payload['query_id']}"))
        print_result("charts stop", *call("PATCH", f"/v1/charts/{payload['query_id']}", {"status": "stopped"}))

    status, payload = call("POST", "/v1/asks", {"query": "hello", "mdl_hash": "probe-mdl-hash"})
    print_result("asks create", status, payload)
    if isinstance(payload, dict) and payload.get("query_id"):
        print_result("asks result", *call("GET", f"/v1/asks/{payload['query_id']}/result"))
        print_result("asks stop", *call("PATCH", f"/v1/asks/{payload['query_id']}", {"status": "stopped"}))

    status, payload = call("POST", "/v1/asks", {"query": "hello"})
    print_result("asks validation failure example", status, payload)

    return 0


if __name__ == "__main__":
    sys.exit(main())
