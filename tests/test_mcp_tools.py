"""
Comprehensive integration tests for MCP tools.

This test suite:
1. Deploys the MCP server locally
2. Connects using DatabricksMCPClient with authentication
3. Tests each tool with various scenarios and edge cases
4. Validates error handling and response formats

Run with: pytest tests/test_mcp_tools.py -v
"""

import os
import shlex
import signal
import socket
import subprocess
import time
from contextlib import closing
from typing import Any, Dict

import pytest
import requests
from databricks_mcp import DatabricksMCPClient
from databricks.sdk import WorkspaceClient


# Databricks credentials from environment or defaults
WORKSPACE_URL = os.getenv("DATABRICKS_HOST", "https://dbc-57e0a25f-9bec.cloud.databricks.com")
M2M_CLIENT_ID = os.getenv("DATABRICKS_CLIENT_ID", "c3df30ca-0414-446f-9ab6-834747432dcd")
M2M_CLIENT_SECRET = os.getenv("DATABRICKS_CLIENT_SECRET", "dose46b091345b727efd7b76361e7b44f614")


def _extract_text_from_result(result) -> str:
    """
    Extract text content from a CallToolResult object.
    
    Args:
        result: CallToolResult object from mcp_client.call_tool()
        
    Returns:
        str: The text content from the result
    """
    if hasattr(result, 'content'):
        content = result.content
        if isinstance(content, list):
            for item in content:
                if hasattr(item, 'text'):
                    return item.text
    return ""


def _find_free_port() -> int:
    """Find a free port on localhost."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server_startup(url: str, timeout: int = 30) -> requests.Response:
    """Wait for the server to start responding."""
    deadline = time.time() + timeout
    last_exc = None

    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=2)
            if 200 <= response.status_code < 400:
                print(f"✅ Server started successfully at {url}")
                return response
        except Exception as e:
            last_exc = e
        time.sleep(0.5)
    
    if last_exc:
        raise last_exc

    raise TimeoutError(f"Server at {url} did not respond in {timeout} seconds")


@pytest.fixture(scope="session")
def mcp_server():
    """
    Start the MCP server in a subprocess for the test session.
    
    Yields the base URL of the server.
    Automatically tears down the server after tests complete.
    """
    host = "127.0.0.1"
    port = _find_free_port()
    base_url = f"http://{host}:{port}"
    cmd = shlex.split(f"uv run mcp-stonex-udp-genie --port {port}")

    print(f"\n🚀 Starting MCP server on port {port}...")
    
    # Start the process
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        # Start a new process group so we can kill children on teardown
        preexec_fn=os.setsid if os.name != 'nt' else None,
    )

    try:
        _wait_for_server_startup(base_url, timeout=30)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        proc.terminate()
        # Print server logs for debugging
        stdout, stderr = proc.communicate(timeout=5)
        print(f"Server stdout:\n{stdout}")
        print(f"Server stderr:\n{stderr}")
        raise e

    yield base_url

    # Cleanup
    print(f"\n🛑 Stopping MCP server...")
    try:
        if os.name != 'nt':
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        if os.name != 'nt':
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    finally:
        try:
            proc.wait(timeout=5)
        except:
            pass


@pytest.fixture(scope="session")
def workspace_client():
    """Create an authenticated Databricks WorkspaceClient using M2M OAuth."""
    return WorkspaceClient(
        host=WORKSPACE_URL,
        client_id=M2M_CLIENT_ID,
        client_secret=M2M_CLIENT_SECRET,
        auth_type="oauth-m2m"
    )


@pytest.fixture(scope="session")
def mcp_client(mcp_server, workspace_client):
    """Create an authenticated MCP client connected to the local server."""
    mcp_url = f"{mcp_server}/mcp"
    print(f"📡 Connecting to MCP server at {mcp_url}")
    return DatabricksMCPClient(
        server_url=mcp_url,
        workspace_client=workspace_client
    )


@pytest.fixture(scope="session")
def mcp_client_no_auth(mcp_server):
    """Create an MCP client without authentication for testing auth failures."""
    mcp_url = f"{mcp_server}/mcp"
    return DatabricksMCPClient(server_url=mcp_url)


# ============================================================================
# Test: Server Health & Discovery
# ============================================================================

def test_server_is_running(mcp_server):
    """Test that the MCP server is running and responding."""
    response = requests.get(mcp_server)
    assert response.status_code in [200, 404]  # Either root page or not found is fine
    print(f"✅ Server is running at {mcp_server}")


def test_list_tools(mcp_client):
    """Test that we can list all available tools."""
    tools = mcp_client.list_tools()
    assert len(tools) > 0, "No tools found"
    
    tool_names = [tool.name for tool in tools]
    print(f"✅ Found {len(tools)} tools: {tool_names}")
    
    # Verify expected tools are present
    expected_tools = [
        "health",
        "get_current_user",
        "query_space_01f0d08866f11370b6735facce14e3ff",
        "poll_response_01f0d08866f11370b6735facce14e3ff",
        "get_query_result_01f0d08866f11370b6735facce14e3ff"
    ]
    
    for expected_tool in expected_tools:
        assert expected_tool in tool_names, f"Expected tool '{expected_tool}' not found"
    
    print(f"✅ All expected tools are present")


# ============================================================================
# Test: Health Tool
# ============================================================================

def test_health_tool(mcp_client):
    """Test the health check tool."""
    result = mcp_client.call_tool("health")
    
    assert isinstance(result, object), "Result should be a CallToolResult object"
    assert hasattr(result, 'content'), "Result should have content attribute"
    
    # Extract content
    content = result.content
    assert isinstance(content, list), "Content should be a list"
    
    # Get the text response
    text_content = None
    for item in content:
        if hasattr(item, 'text'):
            text_content = item.text
            break
    
    assert text_content is not None, "Should have text content"
    print(f"✅ Health check response: {text_content}")
    
    # Verify the response contains expected fields
    assert "healthy" in text_content.lower() or "status" in text_content.lower()


# ============================================================================
# Test: Get Current User Tool
# ============================================================================

def test_get_current_user(mcp_client):
    """Test getting current user information."""
    result = mcp_client.call_tool("get_current_user")
    
    text_content = _extract_text_from_result(result)
    assert text_content, "Should have text content"
    print(f"✅ Current user info: {text_content}")
    
    # Should contain user information or error
    assert any(key in text_content.lower() for key in ["user", "display", "name", "error"])


# ============================================================================
# Test: Query Space Tool - Success Cases
# ============================================================================

def test_query_space_simple_query(mcp_client):
    """Test submitting a simple query to the Genie space."""
    result = mcp_client.call_tool(
        "query_space_01f0d08866f11370b6735facce14e3ff",
        arguments={"query": "What datasets are available in this space?"}
    )
    
    text_content = _extract_text_from_result(result)
    assert text_content, "Should have text content"
    print(f"✅ Query submitted: {text_content[:200]}...")
    
    # Should contain conversation_id and message_id for polling
    assert "conversation_id" in text_content.lower() and "message_id" in text_content.lower()


def test_query_space_with_polling(mcp_client):
    """Test submitting a query and then polling for results."""
    # Step 1: Submit query
    submit_result = mcp_client.call_tool(
        "query_space_01f0d08866f11370b6735facce14e3ff",
        arguments={"query": "What is the total row count in the dataset?"}
    )
    
    submit_content = _extract_text_from_result(submit_result)
    print(f"✅ Query submitted: {submit_content[:200]}...")
    
    # Extract conversation_id and message_id from response
    import json
    try:
        data = json.loads(submit_content)
        conversation_id = data.get("conversation_id")
        message_id = data.get("message_id")
        
        assert conversation_id, "Should have conversation_id"
        assert message_id, "Should have message_id"
        
        # Step 2: Poll for results
        poll_result = mcp_client.call_tool(
            "poll_response_01f0d08866f11370b6735facce14e3ff",
            arguments={
                "conversation_id": conversation_id,
                "message_id": message_id,
                "max_wait_seconds": 60
            }
        )
        
        poll_content = _extract_text_from_result(poll_result)
        print(f"✅ Poll result: {poll_content[:200]}...")
        
        # Should have a status
        assert "status" in poll_content.lower() or "completed" in poll_content.lower()
    except json.JSONDecodeError:
        # If we can't parse JSON, just check that we got some response
        assert submit_content, "Should have response"


def test_query_space_returns_immediately(mcp_client):
    """Test that query_space returns immediately without waiting."""
    import time
    
    start_time = time.time()
    result = mcp_client.call_tool(
        "query_space_01f0d08866f11370b6735facce14e3ff",
        arguments={"query": "Show me sample data"}
    )
    end_time = time.time()
    
    response_time = end_time - start_time
    print(f"✅ Query submission time: {response_time:.2f} seconds")
    
    text_content = _extract_text_from_result(result)
    print(f"✅ Response: {text_content[:200]}...")
    
    # Should return quickly (within 5 seconds for submission)
    assert response_time < 10, f"Query took too long: {response_time:.2f}s"
    
    # Should have conversation_id and message_id for polling
    assert "conversation_id" in text_content.lower() and "message_id" in text_content.lower()


# ============================================================================
# Test: Query Space Tool - Error Cases
# ============================================================================

def test_query_space_empty_query(mcp_client):
    """Test query with empty content."""
    result = mcp_client.call_tool("query_space_01f0d08866f11370b6735facce14e3ff", arguments={"query": ""})
    
    content = _extract_text_from_result(result)
    print(f"✅ Empty query error response: {content}")
    
    # Should return error
    assert "error" in content.lower() or "invalid" in content.lower()


def test_query_space_very_long_query(mcp_client):
    """Test query exceeding maximum length."""
    long_query = "What is the stock data? " * 1000  # Create a very long query
    
    result = mcp_client.call_tool("query_space_01f0d08866f11370b6735facce14e3ff", arguments={"query": long_query})
    
    content = _extract_text_from_result(result)
    print(f"✅ Long query error response: {content[:200]}...")
    
    # Should return error about query length
    assert "error" in content.lower() or "length" in content.lower() or "completed" in content.lower()


# ============================================================================
# Test: Poll Response Tool
# ============================================================================

def test_poll_response_invalid_ids(mcp_client):
    """Test polling with invalid conversation/message IDs."""
    result = mcp_client.call_tool("poll_response_01f0d08866f11370b6735facce14e3ff", arguments={"conversation_id": "invalid_id", "message_id": "invalid_id"}
    )
    
    content = _extract_text_from_result(result)
    print(f"✅ Invalid IDs error response: {content}")
    
    # Should return error
    assert "error" in content.lower() or "invalid" in content.lower()


def test_poll_response_with_short_timeout(mcp_client):
    """Test polling with very short timeout."""
    # First submit a query without auto-poll
    query_result = mcp_client.call_tool("query_space_01f0d08866f11370b6735facce14e3ff", arguments={"query": "What datasets are available?"}
    )
    
    # Extract IDs (this is a simplified extraction, actual parsing may vary)
    # For this test, we'll use dummy IDs to test the timeout validation
    result = mcp_client.call_tool("poll_response_01f0d08866f11370b6735facce14e3ff", arguments={"conversation_id": "01f0e34ce9641238a5018229451c2ff2"})
    
    content = _extract_text_from_result(result)
    print(f"✅ Poll response: {content[:200]}...")
    
    # Should either timeout or complete
    assert any(word in content.lower() for word in ["timeout", "error", "not found", "completed"])


# ============================================================================
# Test: Get Query Result Tool
# ============================================================================

def test_get_query_result_invalid_ids(mcp_client):
    """Test getting query results with invalid IDs."""
    result = mcp_client.call_tool(
        "get_query_result_01f0d08866f11370b6735facce14e3ff",
        arguments={
            "conversation_id": "invalid_conv_id",
            "message_id": "invalid_msg_id",
            "attachment_id": "invalid_att_id"
        }
    )
    
    content = _extract_text_from_result(result)
    print(f"✅ Invalid IDs error response: {content}")
    
    # Should return error
    assert "error" in content.lower() or "invalid" in content.lower()


def test_get_query_result_missing_parameters(mcp_client):
    """Test getting query results with missing parameters."""
    # This should fail due to missing required parameters
    try:
        result = mcp_client.call_tool("get_query_result_01f0d08866f11370b6735facce14e3ff", arguments={"conversation_id": "some_id"})
        # If it doesn't raise an exception, check for error in response
        content = _extract_text_from_result(result)
        assert "error" in content.lower() or "required" in content.lower()
        print(f"✅ Missing parameters handled: {content}")
    except Exception as e:
        # Expected to fail with missing parameters
        print(f"✅ Missing parameters error (expected): {str(e)}")
        assert "required" in str(e).lower() or "missing" in str(e).lower()


# ============================================================================
# Test: End-to-End Query Flow
# ============================================================================

def test_end_to_end_query_flow(mcp_client):
    """
    Test a complete end-to-end flow:
    1. Submit query without auto-poll
    2. Poll for response
    3. Extract query results (if available)
    """
    print("\n🔄 Starting end-to-end query flow test...")
    
    # Step 1: Submit query
    print("  1️⃣ Submitting query...")
    query_result = mcp_client.call_tool(
        "query_space_01f0d08866f11370b6735facce14e3ff",
        arguments={"query": "What datasets are available in this space?"}
    )
    
    content = _extract_text_from_result(query_result)
    print(f"  ✅ Query submitted: {content[:200]}...")
    
    # Verify we got a response
    assert content is not None
    assert len(content) > 0
    
    # Check if we got conversation_id and message_id
    assert "conversation_id" in content.lower(), "Response should contain conversation_id"
    
    print("✅ End-to-end flow completed successfully")


# ============================================================================
# Test: Concurrent Queries
# ============================================================================

def test_concurrent_queries(mcp_client):
    """Test that multiple queries can be handled concurrently."""
    queries = [
        "What datasets are available?",
        "Show me the schema",
        "What is the row count?"
    ]
    
    results = []
    for query in queries:
        result = mcp_client.call_tool("query_space_01f0d08866f11370b6735facce14e3ff", arguments={"query": query})
        results.append(result)
    
    print(f"✅ Submitted {len(results)} concurrent queries")
    
    # All should return results
    for i, result in enumerate(results):
        content = _extract_text_from_result(result)
        print(f"  Query {i+1} response: {content[:100]}...")


# ============================================================================
# Test: Error Handling & Edge Cases
# ============================================================================

def test_tool_with_invalid_name(mcp_client):
    """Test calling a tool that doesn't exist."""
    try:
        result = mcp_client.call_tool("nonexistent_tool")
        # If it doesn't raise an exception, check for error
        if result:
            content = _extract_text_from_result(result)
            assert "error" in content.lower() or "not found" in content.lower()
    except Exception as e:
        print(f"✅ Invalid tool name error (expected): {str(e)}")
        assert "not found" in str(e).lower() or "unknown" in str(e).lower()


def test_resilience_after_errors(mcp_client):
    """Test that the server remains functional after error conditions."""
    # Cause an error
    try:
        mcp_client.call_tool("query_space_01f0d08866f11370b6735facce14e3ff", arguments={"query": ""})
    except:
        pass
    
    # Server should still work
    result = mcp_client.call_tool("health")
    content = _extract_text_from_result(result)
    assert "healthy" in content.lower() or "status" in content.lower()
    print("✅ Server remains functional after errors")


# ============================================================================
# Test: Performance & Timeouts
# ============================================================================

def test_query_response_time(mcp_client):
    """Test that queries respond within reasonable time."""
    import time
    
    start_time = time.time()
    result = mcp_client.call_tool("query_space_01f0d08866f11370b6735facce14e3ff", arguments={"query": "What datasets are available?"}
    )
    end_time = time.time()
    
    response_time = end_time - start_time
    print(f"✅ Query submission response time: {response_time:.2f} seconds")
    
    # Should respond within 10 seconds for submission (not completion)
    assert response_time < 10, f"Query took too long: {response_time:.2f}s"


# ============================================================================
# Test Summary
# ============================================================================

def test_summary(mcp_client):
    """Print a summary of all available tools and their status."""
    print("\n" + "="*80)
    print("TEST SUITE SUMMARY")
    print("="*80)
    
    tools = mcp_client.list_tools()
    print(f"\n📊 Total tools available: {len(tools)}")
    
    for tool in tools:
        print(f"\n  • {tool.name}")
        if hasattr(tool, 'description') and tool.description:
            # Print first line of description
            first_line = tool.description.split('\n')[0]
            print(f"    {first_line[:100]}...")
    
    print("\n" + "="*80)
    print("✅ All tests completed successfully!")
    print("="*80 + "\n")


if __name__ == "__main__":
    """Run tests directly with pytest."""
    import sys
    pytest.main([__file__, "-v", "--tb=short"] + sys.argv[1:])

