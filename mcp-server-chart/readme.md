npm install -g @antv/mcp-server-chart
# For SSE transport (default endpoint: /sse)
mcp-server-chart --transport sse
# For Streamable transport with custom endpoint
mcp-server-chart --transport streamable

SSE transport: http://localhost:1122/sse
Streamable transport: http://localhost:1122/mcp

## GPT Visualizer SSR 
npm install --save @antv/gpt-vis-ssr

# Server option
https://github.com/luler/gpt_vis_ssr
npm install
npm run start
# Running here: http://52.254.1.55:3000

## Use local rendering
VIS_REQUEST_SERVER=http://52.254.1.55:3000/render mcp-server-chart --transport streamable --port 3001

