from databricks_mcp import DatabricksMCPClient
from databricks.sdk import WorkspaceClient



mcp_server_url = "https://mcp-stonex-udp-genie-2808042768897897.aws.databricksapps.com/mcp"
ws_url = "https://dbc-57e0a25f-9bec.cloud.databricks.com"

# First, get an OAuth token using M2M credentials
ws_client = WorkspaceClient(
    host=ws_url,
    client_id="c3df30ca-0414-446f-9ab6-834747432dcd",
    client_secret="dose46b091345b727efd7b76361e7b44f614",
    auth_type="oauth-m2m"
)

# Direct tool call using DatabricksMCPClient
mcp_client = DatabricksMCPClient(
    server_url=mcp_server_url,
    workspace_client=ws_client
)

# List available tools
tools = mcp_client.list_tools()
print(f"Available tools: {[tool.name for tool in tools]}")