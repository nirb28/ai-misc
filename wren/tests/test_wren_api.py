import json
import os
import time
import unittest
from urllib import error, parse, request


BASE_URL = os.environ.get("WREN_AI_BASE_URL", "http://localhost:5555")
TIMEOUT_SECONDS = float(os.environ.get("WREN_AI_TIMEOUT", "30"))
POLL_INTERVAL_SECONDS = float(os.environ.get("WREN_AI_POLL_INTERVAL", "1.0"))
POLL_TIMEOUT_SECONDS = float(os.environ.get("WREN_AI_POLL_TIMEOUT", "30"))


class WrenApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, payload=None, expected_status=None):
        url = f"{self.base_url}{path}"
        headers = {}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8")
                status = response.status
                content_type = response.headers.get("Content-Type", "")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            status = exc.code
            content_type = exc.headers.get("Content-Type", "")
        except error.URLError as exc:
            raise AssertionError(f"Request to {url} failed: {exc}") from exc

        if expected_status is not None:
            if isinstance(expected_status, (list, tuple, set)):
                if status not in expected_status:
                    raise AssertionError(f"Expected status in {expected_status}, got {status} for {path}: {body}")
            elif status != expected_status:
                raise AssertionError(f"Expected status {expected_status}, got {status} for {path}: {body}")

        if "application/json" in content_type:
            return status, json.loads(body)
        return status, body

    def poll(self, path: str, terminal_statuses, timeout_seconds=POLL_TIMEOUT_SECONDS):
        started = time.time()
        last_payload = None
        while time.time() - started < timeout_seconds:
            _, payload = self.request("GET", path, expected_status=200)
            last_payload = payload
            if payload.get("status") in terminal_statuses:
                return payload
            time.sleep(POLL_INTERVAL_SECONDS)
        raise AssertionError(f"Polling timed out for {path}. Last payload: {last_payload}")


class WrenApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = WrenApiClient(BASE_URL)
        _, cls.openapi = cls.client.request("GET", "/openapi.json", expected_status=200)

    def test_health_endpoint(self):
        _, payload = self.client.request("GET", "/health", expected_status=200)
        self.assertEqual(payload.get("status"), "ok")

    def test_openapi_contains_core_routes(self):
        paths = self.openapi.get("paths", {})
        expected_paths = [
            "/v1/asks",
            "/v1/asks/{query_id}/result",
            "/v1/sql-answers",
            "/v1/sql-answers/{query_id}",
            "/v1/charts",
            "/v1/question-recommendations",
            "/v1/relationship-recommendations",
            "/v1/semantics-preparations",
            "/v1/sql-questions",
        ]
        for path in expected_paths:
            self.assertIn(path, paths)

    def test_invalid_ask_request_returns_validation_error(self):
        status, payload = self.client.request("POST", "/v1/asks", payload={"query": "hello"}, expected_status=400)
        self.assertEqual(status, 400)
        self.assertIn("detail", payload)

    def test_question_recommendations_round_trip(self):
        status, created = self.client.request(
            "POST",
            "/v1/question-recommendations",
            payload={"mdl": "model test"},
            expected_status=200,
        )
        self.assertEqual(status, 200)
        self.assertIn("id", created)

        _, result = self.client.request(
            "GET",
            f"/v1/question-recommendations/{created['id']}",
            expected_status=200,
        )
        self.assertIn("status", result)

    def test_relationship_recommendations_round_trip(self):
        _, created = self.client.request(
            "POST",
            "/v1/relationship-recommendations",
            payload={"mdl": "model test"},
            expected_status=200,
        )
        self.assertIn("id", created)

        _, result = self.client.request(
            "GET",
            f"/v1/relationship-recommendations/{created['id']}",
            expected_status=200,
        )
        self.assertIn("status", result)

    def test_semantics_preparation_round_trip(self):
        mdl_hash = f"test-{int(time.time())}"
        _, created = self.client.request(
            "POST",
            "/v1/semantics-preparations",
            payload={"mdl": "model test", "mdl_hash": mdl_hash},
            expected_status=200,
        )
        self.assertEqual(created.get("id"), mdl_hash)

        _, result = self.client.request(
            "GET",
            f"/v1/semantics-preparations/{parse.quote(mdl_hash)}/status",
            expected_status=200,
        )
        self.assertIn("status", result)
        self.assertIn(result.get("status"), {"indexing", "finished", "failed"})

    def test_sql_questions_round_trip(self):
        _, created = self.client.request(
            "POST",
            "/v1/sql-questions",
            payload={"sqls": ["select 1 as value"]},
            expected_status=200,
        )
        query_id = created.get("query_id")
        self.assertTrue(query_id)

        _, result = self.client.request("GET", f"/v1/sql-questions/{query_id}", expected_status=200)
        self.assertIn("status", result)

    def test_sql_answers_round_trip(self):
        _, created = self.client.request(
            "POST",
            "/v1/sql-answers",
            payload={
                "query": "What is the value?",
                "sql": "select 1 as value",
                "sql_data": {"columns": ["value"], "data": [[1]]},
            },
            expected_status=200,
        )
        query_id = created.get("query_id")
        self.assertTrue(query_id)

        result = self.client.poll(
            f"/v1/sql-answers/{query_id}",
            terminal_statuses={"succeeded", "failed"},
        )
        self.assertIn(result.get("status"), {"succeeded", "failed"})

    def test_charts_round_trip_and_stop(self):
        _, created = self.client.request(
            "POST",
            "/v1/charts",
            payload={"query": "Show the result as a chart", "sql": "select 1 as value"},
            expected_status=200,
        )
        query_id = created.get("query_id")
        self.assertTrue(query_id)

        _, current = self.client.request("GET", f"/v1/charts/{query_id}", expected_status=200)
        self.assertIn("status", current)

        _, stopped = self.client.request(
            "PATCH",
            f"/v1/charts/{query_id}",
            payload={"status": "stopped"},
            expected_status=200,
        )
        self.assertIn("query_id", stopped)

    def test_asks_contract_and_stop(self):
        _, created = self.client.request(
            "POST",
            "/v1/asks",
            payload={"query": "hello", "mdl_hash": "test-mdl-hash"},
            expected_status=200,
        )
        query_id = created.get("query_id")
        self.assertTrue(query_id)

        _, result = self.client.request("GET", f"/v1/asks/{query_id}/result", expected_status=200)
        self.assertIn("status", result)

        _, stopped = self.client.request(
            "PATCH",
            f"/v1/asks/{query_id}",
            payload={"status": "stopped"},
            expected_status=200,
        )
        self.assertIn("query_id", stopped)


if __name__ == "__main__":
    unittest.main()
