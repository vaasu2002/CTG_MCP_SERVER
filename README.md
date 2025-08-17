# CliniSight MCP Server

A Model Context Protocol (MCP) server that provides access to ClinicalTrials.gov data through an OpenAI-compatible interface.

## 🚀 Quick Start

### 1. Start the MCP Server

First, start the MCP server in one terminal:

```bash
python start_server.py
```

The server will start on `http://localhost:3000` with the MCP endpoint at `http://localhost:3000/mcp`.

### 2. Run the Client

In another terminal, run the client:

```bash
python client.py
```

## 📁 File Structure

- `server.py` - MCP server implementation with ClinicalTrials.gov API integration
- `start_server.py` - Server startup script
- `client.py` - Client that connects to the MCP server
- `mcp_openai_bridge.py` - Bridge between OpenAI and MCP tools
- `main.py` - Alternative server startup

## 🔧 Configuration

The server runs on port 3000 by default. You can modify this in the server files if needed.

## 🐛 Troubleshooting

If you get connection errors:

1. **Make sure the server is running** - Check that `start_server.py` is running and shows "Server starting on http://localhost:3000"
2. **Check the port** - Ensure port 3000 is not blocked or in use by another service
3. **Verify the endpoint** - The client connects to `http://localhost:3000/mcp`

## 📚 Dependencies

Install required packages:

```bash
pip install -r requirements.txt
```

Or using uv:

```bash
uv sync
```
