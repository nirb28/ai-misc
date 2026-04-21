from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, TypedDict

try:
    from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
    from langchain_openai import ChatOpenAI
    from langgraph.graph import END, StateGraph
    from langgraph.graph.message import add_messages
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamablehttp_client
except ImportError as exc:
    raise SystemExit(
        "Missing dependency. Install the example requirements in your active environment: "
        "pip install langgraph langchain-openai mcp"
    ) from exc


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MDL_PATH = ROOT_DIR / "jaffle-shop-mdl" / "target" / "mdl.json"
DEFAULT_DUCKDB_DIR = ROOT_DIR
DEFAULT_MCP_SERVER_DIR = ROOT_DIR / "mcp-server"
DEFAULT_MCP_TRANSPORT = os.getenv("WREN_MCP_TRANSPORT", "stdio")
DEFAULT_MCP_URL = os.getenv("WREN_MCP_URL")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL")
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_WREN_URL = os.getenv("WREN_URL")


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", help="Question to answer with Wren MCP tools")
    parser.add_argument(
        "--mdl-path",
        default=str(DEFAULT_MDL_PATH),
        help="Path to compiled Wren MDL JSON",
    )
    parser.add_argument(
        "--duckdb-dir",
        default=str(DEFAULT_DUCKDB_DIR),
        help="Directory containing .duckdb files",
    )
    parser.add_argument(
        "--mcp-transport",
        choices=["stdio", "http", "sse"],
        default=DEFAULT_MCP_TRANSPORT,
        help="How to connect to the Wren MCP server",
    )
    parser.add_argument(
        "--mcp-url",
        default=DEFAULT_MCP_URL,
        help="URL for a running Wren MCP server when using http or sse transport",
    )
    parser.add_argument(
        "--mcp-command",
        default=os.getenv("WREN_MCP_COMMAND", "uv"),
        help="Command used to start the Wren MCP server",
    )
    parser.add_argument(
        "--mcp-args-json",
        default=os.getenv("WREN_MCP_ARGS_JSON"),
        help="JSON array of arguments used to start the Wren MCP server",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Chat model name for the LangGraph agent",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="OpenAI-compatible base URL for the chat model",
    )
    parser.add_argument(
        "--api-key",
        default=DEFAULT_API_KEY,
        help="API key for the chat model provider",
    )
    parser.add_argument(
        "--wren-url",
        default=DEFAULT_WREN_URL,
        help="Optional Wren Engine URL expected by the MCP server",
    )
    return parser.parse_args()


def resolve_mcp_args(raw_args: str | None) -> list[str]:
    if raw_args:
        try:
            parsed = json.loads(raw_args)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--mcp-args-json must be valid JSON: {exc}") from exc
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise SystemExit("--mcp-args-json must decode to a JSON string array")
        return parsed

    if DEFAULT_MCP_SERVER_DIR.exists():
        return ["--directory", str(DEFAULT_MCP_SERVER_DIR), "run", "app/wren.py"]

    raise SystemExit(
        "Could not infer how to start the Wren MCP server. Set WREN_MCP_ARGS_JSON or pass --mcp-args-json."
    )


def build_connection_info_file(duckdb_dir: Path) -> str:
    payload = {
        "datasource": "duckdb",
        "properties": {
            "url": str(duckdb_dir),
            "format": "duckdb",
        },
    }
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    with handle:
        json.dump(payload, handle)
    return handle.name


@asynccontextmanager
async def open_mcp_session(args: argparse.Namespace, mdl_path: Path, duckdb_dir: Path):
    if args.mcp_transport in {"http", "sse"}:
        if not args.mcp_url:
            raise SystemExit("--mcp-url is required when --mcp-transport is http or sse")

        if args.mcp_transport == "http":
            async with streamablehttp_client(args.mcp_url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
            return

        async with sse_client(args.mcp_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
        return

    connection_info_file = build_connection_info_file(duckdb_dir)
    server_env = os.environ.copy()
    server_env["CONNECTION_INFO_FILE"] = connection_info_file
    server_env["MDL_PATH"] = str(mdl_path)
    if args.wren_url:
        server_env["WREN_URL"] = args.wren_url

    mcp_args = resolve_mcp_args(args.mcp_args_json)
    server_params = StdioServerParameters(
        command=args.mcp_command,
        args=mcp_args,
        env=server_env,
        cwd=str(ROOT_DIR),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def make_llm(model: str, base_url: str | None, api_key: str | None, tool_schemas: list[dict[str, Any]]):
    kwargs: dict[str, Any] = {"model": model, "temperature": 0}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    llm = ChatOpenAI(**kwargs)
    return llm.bind_tools(tool_schemas)


def to_openai_tool_schema(tool: Any) -> dict[str, Any]:
    input_schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
    if not input_schema:
        input_schema = {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": input_schema,
        },
    }


def format_tool_result(result: Any) -> str:
    content = getattr(result, "content", None)
    if not content:
        return str(result)

    parts: list[str] = []
    for item in content:
        if hasattr(item, "text"):
            parts.append(item.text)
            continue
        if hasattr(item, "data"):
            parts.append(json.dumps(item.data, indent=2, ensure_ascii=False))
            continue
        if hasattr(item, "json"):
            parts.append(json.dumps(item.json, indent=2, ensure_ascii=False))
            continue
        parts.append(str(item))
    return "\n".join(part for part in parts if part).strip()


def build_graph(llm_with_tools: Any, session: ClientSession):
    async def agent_node(state: AgentState) -> dict[str, list[BaseMessage]]:
        response = await llm_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}

    async def tool_node(state: AgentState) -> dict[str, list[ToolMessage]]:
        last_message = state["messages"][-1]
        tool_messages: list[ToolMessage] = []
        for tool_call in getattr(last_message, "tool_calls", []) or []:
            result = await session.call_tool(tool_call["name"], tool_call.get("args") or {})
            tool_messages.append(
                ToolMessage(
                    content=format_tool_result(result),
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"],
                )
            )
        return {"messages": tool_messages}

    def route_after_agent(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


async def run_agent(args: argparse.Namespace) -> str:
    mdl_path = Path(args.mdl_path).resolve()
    duckdb_dir = Path(args.duckdb_dir).resolve()

    if args.mcp_transport == "stdio" and not mdl_path.exists():
        raise SystemExit(f"MDL file not found: {mdl_path}")
    if args.mcp_transport == "stdio" and not duckdb_dir.exists():
        raise SystemExit(f"DuckDB directory not found: {duckdb_dir}")

    async with open_mcp_session(args, mdl_path, duckdb_dir) as session:
            listed_tools = await session.list_tools()
            tool_schemas = [to_openai_tool_schema(tool) for tool in listed_tools.tools]
            llm_with_tools = make_llm(args.model, args.base_url, args.api_key, tool_schemas)
            graph = build_graph(llm_with_tools, session)
            system_prompt = (
                "You are a data assistant using Wren MCP tools. "
                "Use get_wren_guide first if it is available, then use Wren tools to answer the user's question. "
                "Ground your answer in tool outputs and be concise."
            )
            result = await graph.ainvoke(
                {
                    "messages": [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=args.question),
                    ]
                },
                config={"recursion_limit": 10},
            )
            final_message = result["messages"][-1]
            return getattr(final_message, "content", str(final_message))


def main() -> None:
    args = parse_args()
    answer = asyncio.run(run_agent(args))
    print(answer)


if __name__ == "__main__":
    main()
