npm install -g @antv/mcp-server-chart
Run the server with your preferred transport option:

# For SSE transport (default endpoint: /sse)
mcp-server-chart --transport sse

# For Streamable transport with custom endpoint
mcp-server-chart --transport streamable
Then you can access the server at:

SSE transport: http://localhost:1122/sse
Streamable transport: http://localhost:1122/mcp

# GPT Visualizer SSR
npm install --save @antv/gpt-vis-ssr
