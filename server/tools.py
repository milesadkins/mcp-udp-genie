"""
Tools module for the MCP server.

This module defines all the tools (functions) that the MCP server exposes to clients.
Tools are the core functionality of an MCP server - they are callable functions that
AI assistants and other clients can invoke to perform specific actions.

Each tool should:
- Have a clear, descriptive name
- Include comprehensive docstrings (used by AI to understand when to call the tool)
- Return structured data (typically dict or list)
- Handle errors gracefully
"""
import requests

from databricks.sdk import WorkspaceClient
        
from server import utils

WORKSPACE_URL = "https://dbc-57e0a25f-9bec.cloud.databricks.com"

M2M_CLIENT_ID = "c3df30ca-0414-446f-9ab6-834747432dcd"
M2M_CLIENT_SECRET = "dose46b091345b727efd7b76361e7b44f614"

def load_tools(mcp_server):
    """
    Register all MCP tools with the server.

    This function is called during server initialization to register all available
    tools with the MCP server instance. Tools are registered using the @mcp_server.tool
    decorator, which makes them available to clients via the MCP protocol.

    Args:
        mcp_server: The FastMCP server instance to register tools with. This is the
                   main server object that handles tool registration and routing.

    Example:
        To add a new tool, define it within this function using the decorator:

        @mcp_server.tool
        def my_new_tool(param: str) -> dict:
            '''Description of what the tool does.'''
            return {"result": f"Processed {param}"}
    """

    @mcp_server.tool
    def health() -> dict:
        """
        Check the health of the MCP server and Databricks connection.

        This is a simple diagnostic tool that confirms the server is running properly.
        It's useful for:
        - Monitoring and health checks
        - Testing the MCP connection
        - Verifying the server is responsive

        Returns:
            dict: A dictionary containing:
                - status (str): The health status ("healthy" if operational)
                - message (str): A human-readable status message

        Example response:
            {
                "status": "healthy",
                "message": "Custom MCP Server is healthy and connected to Databricks Apps."
            }
        """
        return {
            "status": "healthy",
            "message": "Custom MCP Server is healthy and connected to Databricks Apps.",
        }

    @mcp_server.tool
    def get_current_user() -> dict:
        """
        Get information about the current authenticated user.

        This tool retrieves details about the user who is currently authenticated
        with the MCP server. When deployed as a Databricks App, this returns
        information about the end user making the request. When running locally,
        it returns information about the developer's Databricks identity.

        Useful for:
        - Personalizing responses based on the user
        - Authorization checks
        - Audit logging
        - User-specific operations

        Returns:
            dict: A dictionary containing:
                - display_name (str): The user's display name
                - user_name (str): The user's username/email
                - active (bool): Whether the user account is active

        Example response:
            {
                "display_name": "John Doe",
                "user_name": "john.doe@example.com",
                "active": true
            }

        Raises:
            Returns error dict if authentication fails or user info cannot be retrieved.
        """
        try:
            w = utils.get_user_authenticated_workspace_client()
            user = w.current_user.me()
            return {
                "display_name": user.display_name,
                "user_name": user.user_name,
                "active": user.active,
            }
        except Exception as e:
            return {"error": str(e), "message": "Failed to retrieve user information"}

    @mcp_server.tool
    def query_space_01f0d153b27e1c7ca1d4e6c0f2477cae(query: str, conversation_id: str) -> dict:
        """
        Query the US Stocks Price & Volume genie space for data insights.
        
        You can ask natural language questions and will receive responses in natural language or as SQL query results. 
        You can ask for a summary of the datasets in the genie space to get an overview of the data available. 
        By default, each query is standalone. Optionally, provide a conversation_id to continue an existing conversation. 
        If you do not have a conversation_id, please provide all relevant context in the query. The response will include the conversation_id, message_id, and status of the message in the genie space. You can pass this conversation_id into subsequent queries to continue to conversation. If the message is not complete, you can use poll_response_01f0d08866f11370b6735facce14e3ff with the returned conversation_id and message_id to continue polling until completion. 
        
        The genie space description is as follows:
        Fill In Here

        Returns:
            dict: A dictionary containing:
                - status (str): The health status ("healthy" if operational)
                - message (str): A human-readable status message

        Example response:
            {
                "status": "healthy",
                "message": "Custom MCP Server is healthy and connected to Databricks Apps."
            }
        """
        space_id = "01f0d153b27e1c7ca1d4e6c0f2477cae"

        # First, get an OAuth token using M2M credentials
        w = WorkspaceClient(
            host=WORKSPACE_URL,
            client_id=M2M_CLIENT_ID,
            client_secret=M2M_CLIENT_SECRET,
            auth_type="oauth-m2m"
        )

        json_payload = {
            "content": query
        }

        start_conversation = f"/api/2.0/genie/spaces/{space_id}/start-conversation"
        response = requests.post(
            WORKSPACE_URL+start_conversation,
            headers=w.config.authenticate(),
            json=json_payload
        )
        response_dict = dict(response.json())
        conversation_id = response_dict['message']['conversation_id']
        message_id = response_dict['message_id']
        response_dict
        return {
            "status": "healthy",
            "message": "Custom MCP Server is healthy and connected to Databricks Apps."
        }

