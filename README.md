# MCP StoneX UDP Genie

A simple, production-ready template for building Model Context Protocol (MCP) servers using FastMCP and FastAPI. This project demonstrates how to create custom tools that AI assistants can discover and invoke.

## 🚀 Quickstart Setup Guide

Follow these steps to deploy and connect your MCP StoneX UDP Genie App:

---

### 0. **Update the Repository**

- Add or update tools as needed.
- **Note:** You currently need to define a separate tool for each Genie.

---

### 1. **Launch as a Databricks App**

Run the following commands in your project directory:

```bash
databricks sync --watch . /Workspace/Users/{your_databricks_username}/mcp-stonex-udp-genie

databricks apps deploy mcp-stonex-udp-genie \
  --source-code-path /Workspace/Users/{your_databricks_username}/mcp-stonex-udp-genie
```

---

### 2. **Assign App Permissions**

For the auto-created App Service Principal, grant **ALL** of the following permissions _in Databricks_:

- `CAN USE` on the App
- `CAN RUN` on the Genie Space
- `USE CATALOG` on the Genie Space's catalog target
- `USE SCHEMA` on the Genie Space's schema target
- `SELECT` on **all tables** in the Genie Space's schema target

---

### 3. **Create a Databricks App Connection**

1. Go to Databricks Account Console
2. Go to **Settings** → **App Connections**.
3. Click **Add Connection**.
4. Set up as follows:
    - **REDIRECT_URL:**  
      `{databricks_app_url}/.auth/callback`
    - **CLIENT_SECRET:**  
      YES (copy & save for step 4)
    - **OAUTH_ACCESS_SCOPE:**  
      `all-apis`

---

### 4. **Configure an External UC Connection**

Fill in the following values:

| Field            | Value                                              |
|------------------|---------------------------------------------------|
| CONNECTION_TYPE  | `HTTP`                                            |
| AUTH_TYPE        | `OAUTH Machine 2 Machine`                         |
| HOST             | `{databricks_app_url}`                            |
| CLIENT_ID        | _(from previous step)_                            |
| CLIENT_SECRET    | _(from previous step)_                            |
| OAUTH_SCOPE      | `all-apis`                                        |
| TOKEN_ENDPOINT   | `{workspace_url}/oidc/v1/token`                   |
| BASE_PATH        | `/mcp`                                            |
| IS_MCP_CONNECTION| `True`                                            |

---

### 5. **Add to Playground or Supervisor**

- Register the External MCP Server in Playground or Multi-agent Supervisor for testing and multi-agent experiments.

---




### Key Concepts

- **Tools**: Callable functions that AI assistants can invoke (e.g., search databases, process data, call APIs)
- **Server**: Exposes tools via the MCP protocol over HTTP
- **Client**: Applications (like Claude, AI assistants) that discover and call tools

## Features

- ✅ FastMCP-based server with HTTP streaming support
- ✅ FastAPI integration for additional REST endpoints
- ✅ Example tools: health check and user information
- ✅ Production-ready project structure
- ✅ Ready for Databricks Apps deployment

## Project Structure

```
mcp-server-hello-world/
├── server/
│   ├── app.py                    # FastAPI application and MCP server setup
│   ├── main.py                   # Entry point for running the server
│   ├── tools.py                  # MCP tool definitions
│   └── utils.py                  # Databricks authentication helpers
├── scripts/
│   └── dev/
│       ├── start_server.sh           # Start the MCP server locally
│       ├── query_remote.sh           # Interactive script for testing deployed app with OAuth
│       ├── query_remote.py           # Query MCP client (deployed app) with health and user auth
│       └── generate_oauth_token.py   # Generate OAuth tokens for Databricks
├── tests/
│   └── test_integration_server.py   # Integration tests for MCP server
├── pyproject.toml                # Project metadata and dependencies
├── requirements.txt              # Python dependencies (for pip)
├── app.yaml                      # Databricks Apps configuration
├── Claude.md                     # AI assistant context and documentation
└── README.md          
```

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Installation

### Option 1: Using uv (Recommended)

```bash
# Install uv if you haven't already
# Install dependencies
uv sync
```

### Option 2: Using pip

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Server

### Development Mode

```bash
# Quick start with script (syncs dependencies and starts server)
./scripts/dev/start_server.sh

# Or manually using uv (default port 8000)
uv run mcp-stonex-udp-genie

# Or specify a custom port
uv run mcp-stonex-udp-genie --port 8080

# Or using the installed command (after pip install -e .)
mcp-stonex-udp-genie --port 3000
```

The server will start on `http://localhost:8000` by default (or your specified port).

### Accessing the Server

- **MCP Endpoints**: `http://localhost:8000/mcp`
- **Available Tools**: 
  - `health`: Check server status
  - `get_current_user`: Get authenticated user information

## Testing the MCP Server

This project includes test scripts to verify your MCP server is working correctly in both local and deployed environments.

### Integration Tests

The project includes automated integration tests that validate the MCP server functionality:

```bash
# Run integration tests
uv run pytest tests/
```

**What the tests do:**
- Automatically start the MCP server
- Test that `list_tools()` works correctly
- Test that all registered tools can be called without errors by invoking the `call_tools()`
- Automatically clean up the server after tests complete

### Manual Testing

#### End-to-end test your locally-running MCP server

```bash
./scripts/dev/start_server.sh
```

```python
from databricks_mcp import DatabricksMCPClient
mcp_client = DatabricksMCPClient(
    server_url="http://localhost:8000"
)
# List available MCP tools
print(mcp_client.list_tools())
```

The script connects to your local MCP server without authentication and lists available tools.

#### End-to-end test your deployed MCP server

After deploying to Databricks Apps, use the interactive shell script to test with user-level OAuth authentication:

```bash
chmod +x scripts/dev/query_remote.sh
./scripts/dev/query_remote.sh
```

The script will guide you through:
1. **Profile selection**: Choose your Databricks CLI profile
2. **App name**: Enter your deployed app name
3. **Automatic configuration**: Extracts app scopes and URLs automatically
4. **OAuth flow**: Generates user OAuth token via browser
5. **End-to-end test**: Tests `list_tools()`, and invokes each tool returned in list_tools

**What it does:**
- Retrieves app configuration using `databricks apps get`
- Extracts user authorization scopes from `effective_user_api_scopes`
- Gets workspace host from your Databricks profile
- Generates OAuth token with the correct scopes
- Tests MCP client with user-level authentication
- Verifies both the `health` check and `get_current_user` tool work correctly

This test simulates the real end-user experience when they authorize your app and use it with their credentials.

Alternatively, test manually with command-line arguments:

```bash
python scripts/dev/query_remote.py \
    --host "https://your-workspace.cloud.databricks.com" \
    --token "eyJr...Dkag" \
    --app-url "https://your-workspace.cloud.databricks.com/serving-endpoints/your-app"
```

The `scripts/dev/query_remote.py` script connects to your deployed MCP server with OAuth authentication and tests both the health check and user authorization functionality.

## Adding New Tools

To add a new tool to your MCP server:

1. Open `server/tools.py`
2. Add a new function inside `load_tools()` with the `@mcp_server.tool` decorator:

```python
@mcp_server.tool
def calculate_sum(a: int, b: int) -> dict:
    """
    Calculate the sum of two numbers.
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        dict: Contains the sum result
    """
    return {"result": a + b}
```

3. Restart the server - the new tool will be automatically available to clients

### Tool Best Practices

- **Clear naming**: Use descriptive, action-oriented names
- **Comprehensive docstrings**: AI uses these to understand when to call your tool
- **Type hints**: Help with validation and documentation
- **Structured returns**: Return dicts or Pydantic models for consistent data
- **Error handling**: Use try-except blocks and return error information

### Connecting to Databricks

The `utils.py` module provides two helper methods for interacting with Databricks resources via the Databricks SDK Workspace Client:

**When deployed as a Databricks App:**
- `get_workspace_client()` - Returns a client authenticated as the service principal associated with the app. See [App Authorization](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth#app-authorization) for more details.
- `get_user_authenticated_workspace_client()` - Returns a client authenticated as the end user with scopes specified by the app creator. See [User Authorization](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth#user-authorization) for more details.

**When running locally:**
- Both methods return a client authenticated as the current developer, since no service principal identity exists in the local environment.

**Example usage in tools:**
```python
from server import utils

# Get current user information (user-authenticated)
w = utils.get_user_authenticated_workspace_client()
user = w.current_user.me()
display_name = user.display_name
```

See the `get_current_user` tool in `server/tools.py` for a complete example.

## Generating OAuth Tokens

For advanced use cases, you can manually generate OAuth tokens for Databricks workspace access using the provided script. This implements the [OAuth U2M (User-to-Machine) flow](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-u2m?language=CLI).

### Generate Workspace-Level OAuth Token

```bash
python scripts/dev/generate_oauth_token.py \
    --host https://your-workspace.cloud.databricks.com \
    --scopes "all-apis offline_access"
```

**Parameters:**
- `--host`: Databricks workspace URL (required)
- `--scopes`: Space-separated OAuth scopes (default: `all-apis offline_access`)
- `--redirect-uri`: Callback URI (default: `http://localhost:8020`)

**Note:** The script uses the `databricks-cli` OAuth client ID by default.

**The script will:**
1. Generate a PKCE code verifier and challenge
2. Open your browser for authorization
3. Capture the authorization code via local HTTP server
4. Exchange the code for an access token
5. Display the token response as JSON (token is valid for 1 hour)

**Example with custom scopes:**
```bash
python scripts/dev/generate_oauth_token.py \
    --host https://your-workspace.cloud.databricks.com \
    --scopes "clusters:read jobs:write sql:read"
```

## Configuration

### Server Settings

The server can be configured using command-line arguments:

```bash
# Change port
uv run custom-mcp-server --port 8080

# Get help
uv run custom-mcp-server --help
```

The default configuration:
- **Host**: `0.0.0.0` (listens on all network interfaces)
- **Port**: `8000` (configurable via `--port` argument)

## Deployment

### Databricks Apps

This project is configured for Databricks Apps deployment:

1. Deploy using Databricks CLI or UI
2. The server will be accessible at your Databricks app URL

For more information refer to the documentation [here](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy#deploy-the-app)

### Try Your MCP Server in AI Playground

After deploying your MCP server to Databricks Apps, you can test it interactively in the Databricks AI Playground:

1. Navigate to the **AI Playground** in your Databricks workspace
2. Select a model with the **Tools enabled** label
3. Click **Tools > + Add tool** and select your deployed MCP server
4. Start chatting with the AI agent - it will automatically call your MCP server's tools as needed

The AI Playground provides a visual interface to prototype and test your MCP server with different models and configurations before integrating it into production applications.

For more information, see [Prototype tool-calling agents in AI Playground](https://docs.databricks.com/aws/en/generative-ai/agent-framework/ai-playground-agent).

## Development

### Code Formatting

```bash
# Format code with ruff
uv run ruff format .

# Check for lint errors
uv run ruff check .
```

## Customization

### Rename the Project

1. Update `name` in `pyproject.toml`
2. Update `name` parameter in `server/app.py`: `FastMCP(name="your-name")`
3. Update the command script in `pyproject.toml` under `[project.scripts]`

### Add Custom API Endpoints

Add routes to the `app` FastAPI instance in `server/app.py`:

```python
@app.get("/custom-endpoint")
def custom_endpoint():
    return {"message": "Hello from custom endpoint"}
```

## Troubleshooting

### Port Already in Use

Change the port in `server/main.py` or set the `PORT` environment variable.

### Import Errors

Ensure all dependencies are installed:
```bash
uv sync  # or pip install -r requirements.txt
```

## Resources
- [Databricks MCP Documentation](https://docs.databricks.com/aws/en/generative-ai/mcp/custom-mcp)
- [Databricks Apps](https://www.databricks.com/product/databricks-apps)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Uvicorn Documentation](https://www.uvicorn.org)

## AI Assistant Context

See [`Claude.md`](./Claude.md) for detailed project context specifically designed for AI assistants working with this codebase.


