import os
import json
import re
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP


SUPERSET_INTERNAL_URL = os.environ.get("SUPERSET_INTERNAL_URL", "http://127.0.0.1:8088")
SUPERSET_PUBLIC_URL = os.environ.get("SUPERSET_PUBLIC_URL", SUPERSET_INTERNAL_URL)
SUPERSET_API_TIMEOUT = int(os.environ.get("SUPERSET_API_TIMEOUT", "30"))
SUPERSET_USERNAME = os.environ.get("SUPERSET_API_USERNAME", os.environ.get("SUPERSET_ADMIN_USERNAME", "admin"))
SUPERSET_PASSWORD = os.environ.get("SUPERSET_API_PASSWORD", os.environ.get("SUPERSET_ADMIN_PASSWORD", "admin"))
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8811"))
MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "streamable-http")

mcp = FastMCP("superset-dashboard-mcp", host=MCP_HOST, port=MCP_PORT)


def _slugify(value: str, default: str = "superset_asset") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value or "").strip("_").lower()
    return slug or default


def _result_payload(payload: Any) -> Any:
    if isinstance(payload, dict) and "result" in payload:
        return payload["result"]
    return payload


def _make_adhoc_metric(column: str, aggregate: str = "SUM") -> dict[str, Any]:
    label = f"{aggregate}({column})"
    return {
        "expressionType": "SQL",
        "sqlExpression": f"{aggregate}({column})",
        "label": label,
        "optionName": label,
    }


def _build_chart_payload(
    dataset_id: int,
    dataset_name: str,
    dashboard_id: int,
    chart_title: str,
    chart_type: str,
    x_axis: str | None,
    y_axis: str | None,
    row_limit: int,
) -> dict[str, Any]:
    resolved_chart_type = (chart_type or "table").lower()
    datasource = {"id": dataset_id, "type": "table"}
    viz_type = "table"
    form_data: dict[str, Any] = {
        "datasource": f"{dataset_id}__table",
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "slice_id": None,
        "viz_type": "table",
        "row_limit": row_limit,
    }
    query_context: dict[str, Any] = {
        "datasource": datasource,
        "force": False,
        "queries": [
            {
                "columns": [column for column in [x_axis, y_axis] if column],
                "metrics": [],
                "orderby": [],
                "row_limit": row_limit,
                "time_range": "No filter",
            }
        ],
        "result_format": "json",
        "result_type": "full",
    }

    if resolved_chart_type in {"line", "area"} and x_axis and y_axis:
        metric = _make_adhoc_metric(y_axis)
        viz_type = "echarts_timeseries_line" if resolved_chart_type == "line" else "echarts_area"
        form_data.update(
            {
                "viz_type": viz_type,
                "granularity_sqla": x_axis,
                "adhoc_metrics": [metric],
                "metrics": [metric],
                "groupby": [],
            }
        )
        query_context["queries"][0].update(
            {
                "columns": [],
                "metrics": [metric],
                "granularity": x_axis,
                "orderby": [],
            }
        )
    elif resolved_chart_type in {"bar", "hbar"} and x_axis and y_axis:
        metric = _make_adhoc_metric(y_axis)
        viz_type = "dist_bar"
        form_data.update(
            {
                "viz_type": viz_type,
                "groupby": [x_axis],
                "adhoc_metrics": [metric],
                "metrics": [metric],
                "orientation": "horizontal" if resolved_chart_type == "hbar" else "vertical",
            }
        )
        query_context["queries"][0].update(
            {
                "columns": [x_axis],
                "metrics": [metric],
                "groupby": [x_axis],
            }
        )
    elif resolved_chart_type == "pie" and x_axis and y_axis:
        metric = _make_adhoc_metric(y_axis)
        viz_type = "pie"
        form_data.update(
            {
                "viz_type": viz_type,
                "groupby": [x_axis],
                "adhoc_metrics": [metric],
                "metric": metric,
                "metrics": [metric],
            }
        )
        query_context["queries"][0].update(
            {
                "columns": [x_axis],
                "metrics": [metric],
                "groupby": [x_axis],
            }
        )
    elif resolved_chart_type == "scatter" and x_axis and y_axis:
        viz_type = "scatter_plot"
        form_data.update(
            {
                "viz_type": viz_type,
                "x": x_axis,
                "y": y_axis,
            }
        )
        query_context["queries"][0].update(
            {
                "columns": [x_axis, y_axis],
                "metrics": [],
            }
        )

    return {
        "slice_name": chart_title,
        "description": f"Auto-generated for dashboard '{chart_title}'",
        "viz_type": viz_type,
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "datasource_name": dataset_name,
        "params": json.dumps(form_data),
        "query_context": json.dumps(query_context),
        "dashboards": [dashboard_id],
    }


def _build_position_json(chart_id: int, chart_uuid: str | None, chart_title: str) -> str:
    chart_key = f"CHART-{chart_id}"
    layout = {
        "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["GRID_ID"], "parents": []},
        "GRID_ID": {"id": "GRID_ID", "type": "GRID", "children": ["ROW-1"], "parents": ["ROOT_ID"]},
        "ROW-1": {
            "id": "ROW-1",
            "type": "ROW",
            "children": [chart_key],
            "parents": ["ROOT_ID", "GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        },
        chart_key: {
            "id": chart_key,
            "type": "CHART",
            "children": [],
            "parents": ["ROOT_ID", "GRID_ID", "ROW-1"],
            "meta": {
                "chartId": chart_id,
                "uuid": chart_uuid,
                "sliceName": chart_title,
                "width": 12,
                "height": 50,
            },
        },
    }
    return json.dumps(layout)


class SupersetClient:
    def __init__(self) -> None:
        self._access_token: str | None = None

    def _login(self) -> str:
        response = requests.post(
            f"{SUPERSET_INTERNAL_URL}/api/v1/security/login",
            json={
                "username": SUPERSET_USERNAME,
                "password": SUPERSET_PASSWORD,
                "provider": "db",
                "refresh": True,
            },
            timeout=SUPERSET_API_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise RuntimeError("Superset login succeeded but no access token was returned")
        self._access_token = access_token
        return access_token

    def _headers(self) -> dict[str, str]:
        token = self._access_token or self._login()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        merged_headers = {**self._headers(), **headers}
        response = requests.request(
            method,
            f"{SUPERSET_INTERNAL_URL}{path}",
            headers=merged_headers,
            timeout=SUPERSET_API_TIMEOUT,
            **kwargs,
        )
        if response.status_code == 401:
            self._login()
            merged_headers = {**self._headers(), **headers}
            response = requests.request(
                method,
                f"{SUPERSET_INTERNAL_URL}{path}",
                headers=merged_headers,
                timeout=SUPERSET_API_TIMEOUT,
                **kwargs,
            )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    def health(self) -> Any:
        return self._request("GET", "/health")

    def list_dashboards(self, page: int = 0, page_size: int = 25) -> Any:
        return self._request(
            "GET",
            "/api/v1/dashboard/",
            params={"page": page, "page_size": page_size},
        )

    def get_dashboard(self, dashboard_id: int) -> Any:
        return self._request("GET", f"/api/v1/dashboard/{dashboard_id}")

    def list_charts(self, page: int = 0, page_size: int = 25) -> Any:
        return self._request(
            "GET",
            "/api/v1/chart/",
            params={"page": page, "page_size": page_size},
        )

    def get_chart(self, chart_id: int) -> Any:
        return self._request("GET", f"/api/v1/chart/{chart_id}")

    def list_datasets(self, page: int = 0, page_size: int = 25) -> Any:
        return self._request(
            "GET",
            "/api/v1/dataset/",
            params={"page": page, "page_size": page_size},
        )

    def get_dataset(self, dataset_id: int) -> Any:
        return self._request("GET", f"/api/v1/dataset/{dataset_id}")

    def list_databases(self, page: int = 0, page_size: int = 25) -> Any:
        return self._request(
            "GET",
            "/api/v1/database/",
            params={"page": page, "page_size": page_size},
        )

    def find_database_by_name(self, database_name: str) -> dict[str, Any]:
        payload = self._request(
            "GET",
            "/api/v1/database/",
            params={"page": 0, "page_size": 1000},
        )
        for item in _result_payload(payload) or []:
            if isinstance(item, dict) and item.get("database_name") == database_name:
                return item
        raise ValueError(f"Superset database '{database_name}' was not found")

    def create_dataset(
        self,
        database_id: int,
        dataset_name: str,
        sql: str,
        schema_name: str | None = None,
    ) -> Any:
        return self._request(
            "POST",
            "/api/v1/dataset/",
            json={
                "database": database_id,
                "schema": schema_name,
                "table_name": dataset_name,
                "sql": sql,
            },
        )

    def create_chart(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/api/v1/chart/", json=payload)

    def create_dashboard(self, dashboard_title: str, slug: str | None = None, published: bool = True) -> Any:
        return self._request(
            "POST",
            "/api/v1/dashboard/",
            json={
                "dashboard_title": dashboard_title,
                "slug": slug,
                "published": published,
                "position_json": json.dumps({}),
                "json_metadata": json.dumps({}),
            },
        )

    def update_dashboard_layout(
        self,
        dashboard_id: int,
        dashboard_title: str,
        position_json: str,
        published: bool = True,
    ) -> Any:
        return self._request(
            "PUT",
            f"/api/v1/dashboard/{dashboard_id}",
            json={
                "dashboard_title": dashboard_title,
                "published": published,
                "position_json": position_json,
                "json_metadata": json.dumps({}),
            },
        )

    def create_guest_token(self, dashboard_id: int, guest_username: str = "mcp-guest") -> Any:
        return self._request(
            "POST",
            "/api/v1/security/guest_token/",
            json={
                "user": {
                    "username": guest_username,
                    "first_name": "MCP",
                    "last_name": "Guest",
                },
                "resources": [{"type": "dashboard", "id": str(dashboard_id)}],
                "rls": [],
            },
        )

    def provision_dashboard_from_sql(
        self,
        dashboard_title: str,
        sql: str,
        database_name: str,
        schema_name: str | None = None,
        chart_title: str | None = None,
        dataset_name: str | None = None,
        chart_type: str = "table",
        x_axis: str | None = None,
        y_axis: str | None = None,
        row_limit: int = 1000,
        publish: bool = True,
        create_guest_token: bool = True,
        guest_username: str = "mcp-guest",
    ) -> dict[str, Any]:
        database = self.find_database_by_name(database_name)
        database_id = database.get("id")
        if not database_id:
            raise ValueError(f"Superset database '{database_name}' did not include an id")

        resolved_dataset_name = dataset_name or f"{_slugify(dashboard_title, 'dashboard')}_dataset"
        resolved_chart_title = chart_title or dashboard_title
        dashboard_response = self.create_dashboard(
            dashboard_title=dashboard_title,
            slug=_slugify(dashboard_title, "dashboard"),
            published=publish,
        )
        dashboard_result = _result_payload(dashboard_response) or {}
        dashboard_id = dashboard_result.get("id")
        if not dashboard_id:
            raise ValueError("Superset did not return a dashboard id")

        dataset_response = self.create_dataset(
            database_id=database_id,
            dataset_name=resolved_dataset_name,
            sql=sql,
            schema_name=schema_name,
        )
        dataset_result = _result_payload(dataset_response) or {}
        dataset_id = dataset_result.get("id")
        if not dataset_id:
            raise ValueError("Superset did not return a dataset id")

        chart_response = self.create_chart(
            _build_chart_payload(
                dataset_id=dataset_id,
                dataset_name=resolved_dataset_name,
                dashboard_id=dashboard_id,
                chart_title=resolved_chart_title,
                chart_type=chart_type,
                x_axis=x_axis,
                y_axis=y_axis,
                row_limit=row_limit,
            )
        )
        chart_result = _result_payload(chart_response) or {}
        chart_id = chart_result.get("id")
        if not chart_id:
            raise ValueError("Superset did not return a chart id")

        chart_detail = _result_payload(self.get_chart(chart_id)) or {}
        position_json = _build_position_json(
            chart_id=chart_id,
            chart_uuid=chart_detail.get("uuid"),
            chart_title=resolved_chart_title,
        )
        self.update_dashboard_layout(
            dashboard_id=dashboard_id,
            dashboard_title=dashboard_title,
            position_json=position_json,
            published=publish,
        )

        response: dict[str, Any] = {
            "database": database,
            "dataset": dataset_result,
            "chart": chart_detail or chart_result,
            "dashboard": _result_payload(self.get_dashboard(dashboard_id)) or dashboard_result,
            "dashboard_url": f"{SUPERSET_PUBLIC_URL}/superset/dashboard/{dashboard_id}/?standalone=1",
            "standalone_url": f"{SUPERSET_PUBLIC_URL}/superset/dashboard/{dashboard_id}/?standalone=1",
            "chart_url": f"{SUPERSET_PUBLIC_URL}/explore/?slice_id={chart_id}",
        }
        if create_guest_token:
            response["guest_token"] = self.create_guest_token(dashboard_id=dashboard_id, guest_username=guest_username)
        return response


client = SupersetClient()


@mcp.tool()
def superset_health() -> dict[str, Any]:
    return {
        "superset_url": SUPERSET_INTERNAL_URL,
        "health": client.health(),
        "mcp_transport": MCP_TRANSPORT,
    }


@mcp.tool()
def list_dashboards(page: int = 0, page_size: int = 25) -> Any:
    return client.list_dashboards(page=page, page_size=page_size)


@mcp.tool()
def get_dashboard(dashboard_id: int) -> Any:
    return client.get_dashboard(dashboard_id)


@mcp.tool()
def build_dashboard_url(dashboard_id: int, standalone: bool = False) -> dict[str, str]:
    url = f"{SUPERSET_PUBLIC_URL}/superset/dashboard/{dashboard_id}/"
    if standalone:
        url = f"{url}?standalone=1"
    return {"dashboard_id": str(dashboard_id), "url": url}


@mcp.tool()
def create_dashboard_guest_token(dashboard_id: int, guest_username: str = "mcp-guest") -> Any:
    token_payload = client.create_guest_token(dashboard_id=dashboard_id, guest_username=guest_username)
    return {
        "dashboard_id": dashboard_id,
        "guest_username": guest_username,
        "guest_token": token_payload,
        "dashboard_url": f"{SUPERSET_PUBLIC_URL}/superset/dashboard/{dashboard_id}/?standalone=1",
    }


@mcp.tool()
def list_charts(page: int = 0, page_size: int = 25) -> Any:
    return client.list_charts(page=page, page_size=page_size)


@mcp.tool()
def get_chart(chart_id: int) -> Any:
    return client.get_chart(chart_id)


@mcp.tool()
def list_datasets(page: int = 0, page_size: int = 25) -> Any:
    return client.list_datasets(page=page, page_size=page_size)


@mcp.tool()
def get_dataset(dataset_id: int) -> Any:
    return client.get_dataset(dataset_id)


@mcp.tool()
def list_databases(page: int = 0, page_size: int = 25) -> Any:
    return client.list_databases(page=page, page_size=page_size)


@mcp.tool()
def provision_dashboard_from_sql(
    dashboard_title: str,
    sql: str,
    database_name: str = "starburst",
    schema_name: str | None = None,
    chart_title: str | None = None,
    dataset_name: str | None = None,
    chart_type: str = "table",
    x_axis: str | None = None,
    y_axis: str | None = None,
    row_limit: int = 1000,
    publish: bool = True,
    create_guest_token: bool = True,
    guest_username: str = "mcp-guest",
) -> Any:
    return client.provision_dashboard_from_sql(
        dashboard_title=dashboard_title,
        sql=sql,
        database_name=database_name,
        schema_name=schema_name,
        chart_title=chart_title,
        dataset_name=dataset_name,
        chart_type=chart_type,
        x_axis=x_axis,
        y_axis=y_axis,
        row_limit=row_limit,
        publish=publish,
        create_guest_token=create_guest_token,
        guest_username=guest_username,
    )


@mcp.tool()
def serve_dashboard(dashboard_id: int, guest_username: str = "mcp-guest", standalone: bool = True) -> Any:
    url_payload = build_dashboard_url(dashboard_id=dashboard_id, standalone=standalone)
    token_payload = create_dashboard_guest_token(dashboard_id=dashboard_id, guest_username=guest_username)
    return {
        "dashboard_id": dashboard_id,
        "url": url_payload.get("url"),
        "guest_token": token_payload.get("guest_token"),
        "guest_username": guest_username,
    }


if __name__ == "__main__":
    mcp.run(transport=MCP_TRANSPORT)
