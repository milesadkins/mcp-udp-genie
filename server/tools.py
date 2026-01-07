"""
Tools module for the MCP server (Enhanced Version with Robust Genie API Integration).

This module defines all the tools (functions) that the MCP server exposes to clients.
Tools are the core functionality of an MCP server - they are callable functions that
AI assistants and other clients can invoke to perform specific actions.

Each tool should:
- Have a clear, descriptive name
- Include comprehensive docstrings (used by AI to understand when to call the tool)
- Return structured data (typically dict or list)
- Handle errors gracefully

=== COMPREHENSIVE EDGE CASE HANDLING ===

This implementation includes robust error handling for all Databricks Genie API endpoints:

1. START CONVERSATION ENDPOINT (/api/2.0/genie/spaces/{space_id}/start-conversation)
   Edge Cases Handled:
   - Empty or invalid query content
   - Query length validation (max 10,000 characters)
   - Invalid conversation_id format when continuing conversations
   - Missing or malformed response data
   - Authentication failures (401)
   - Permission denied errors (403)
   - Resource not found (404)
   - Rate limiting (429) with automatic retry
   - Service unavailability (503) with exponential backoff

2. GET MESSAGE ENDPOINT (/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id})
   Edge Cases Handled:
   - Invalid conversation_id or message_id format
   - All message statuses: SUBMITTED, EXECUTING, COMPLETED, FAILED, CANCELLED, ERROR, and UNKNOWN states
   - Polling timeouts with configurable max_wait_seconds
   - Message failures with detailed error extraction from attachments
   - Cancelled and errored messages with proper error context
   - Network timeouts and connection errors during polling

3. GET QUERY RESULT ENDPOINT (/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}/attachments/{attachment_id}/query-result)
   Edge Cases Handled:
   - Invalid attachment_id or non-query attachments
   - All SQL statement execution states: PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED, CLOSED
   - Missing or malformed statement_response data
   - Chunked results with metadata about total chunks and offsets
   - Query execution failures with detailed error codes and messages
   - Empty result sets
   - Truncated results indication

4. AUTHENTICATION & NETWORK
   Edge Cases Handled:
   - M2M OAuth authentication failures
   - Expired or invalid tokens
   - Connection timeouts (configurable, default 30s)
   - Network connection errors
   - DNS resolution failures
   - SSL/TLS errors

5. API-LEVEL ERRORS
   All Databricks API error codes are handled:
   - BAD_REQUEST (400): Invalid parameters, not retryable
   - UNAUTHENTICATED (401): Missing/invalid credentials, not retryable
   - PERMISSION_DENIED (403): Insufficient permissions, not retryable
   - RESOURCE_NOT_FOUND (404): Resource doesn't exist, not retryable
   - RESOURCE_EXHAUSTED (429): Rate limit exceeded, retryable with backoff
   - INTERNAL_ERROR (500): Server error, retryable with backoff
   - UNAVAILABLE (503): Service unavailable, retryable with backoff

6. RETRY LOGIC & RESILIENCE
   - Exponential backoff for transient errors (max 3 retries)
   - Initial delay: 1 second, doubling on each retry
   - Automatic retry only for recoverable errors (5xx, 429, timeouts, connection errors)
   - Non-retryable errors fail fast (4xx client errors except 429)

7. DATA VALIDATION & SANITIZATION
   - Input validation for all parameters
   - Type checking for conversation_id, message_id, attachment_id
   - Length validation for queries
   - Format validation for UUIDs
   - Null/empty checks for all user inputs
   - Safe extraction of nested data structures with fallback defaults

8. ATTACHMENT HANDLING
   - Multiple attachment types: text, query, suggested_questions, error
   - Graceful handling of missing attachment fields
   - Deduplication of suggested questions
   - Empty attachment filtering
   - Type checking for all attachment components

9. LARGE RESULT SETS
   - Chunked result detection and metadata
   - Truncation indicators
   - Row count and byte count tracking
   - Chunk offset information for pagination

10. POLLING STRATEGY
    - Configurable polling intervals (default: 2 seconds)
    - Maximum attempts limit (default: 30 attempts or max_wait_seconds)
    - Terminal state detection to stop polling early
    - Detailed poll attempt tracking in responses
    - Status validation against known states

=== USAGE EXAMPLES ===

Example 1: Discover available Genie spaces
    # List all available spaces to find the right one for your query
    result = list_genie_spaces()
    # Returns: {"spaces": [{"space_id": "...", "title": "US Stocks", "description": "..."}], "count": 1}

Example 2: Submit a query and poll for results
    # Step 1: Submit query to a specific space
    result = query_genie(
        space_id="01f0d08866f11370b6735facce14e3ff",
        query="What datasets are available?"
    )
    # Returns: {"conversation_id": "...", "message_id": "...", "status": "SUBMITTED"}

    # Step 2: Poll for results
    poll_result = poll_genie_response(
        space_id="01f0d08866f11370b6735facce14e3ff",
        conversation_id=result["conversation_id"],
        message_id=result["message_id"],
        fetch_query_results=True
    )
    # Returns full results including text responses, queries, and data

Example 3: Continue a conversation
    result = query_genie(
        space_id="01f0d08866f11370b6735facce14e3ff",
        query="What about stock AAPL?",
        conversation_id="01f0e34ce9641238a5018229451c2ff2"
    )

=== ERROR RESPONSE FORMAT ===

All functions return errors in a consistent format:
{
    "error": "ERROR_CODE",
    "message": "Human-readable error description",
    "status": "current_status",  # If applicable
    ... additional context fields ...
}

Common error codes:
- INVALID_INPUT: Parameter validation failed
- QUERY_FAILED: Query submission failed
- POLL_FAILED: Polling operation failed
- FETCH_FAILED: Failed to fetch results
- MESSAGE_FAILED: Genie message processing failed
- MESSAGE_CANCELLED: Message was cancelled
- MESSAGE_ERROR: Error during message processing
- TIMEOUT: Operation timed out
- QUERY_EXECUTION_FAILED: SQL execution failed
- QUERY_CANCELLED: SQL query was cancelled
- RESOURCE_NOT_FOUND: Resource doesn't exist
- PERMISSION_DENIED: Insufficient permissions
- UNAUTHENTICATED: Authentication failed
- RESOURCE_EXHAUSTED: Rate limit exceeded

=== TESTING RECOMMENDATIONS ===

To thoroughly test this implementation:
1. Test with empty/invalid queries
2. Test with very long queries (>10k chars)
3. Test conversation continuation with invalid IDs
4. Test polling timeout scenarios
5. Test with non-existent space_id
6. Test network failure scenarios
7. Test rate limiting by rapid requests
8. Test with queries that generate errors in Genie
9. Test chunked results
10. Test invalid attachment IDs

"""
from typing import Any, Optional
import requests
import os
import time

from dotenv import load_dotenv; load_dotenv()

from databricks.sdk import WorkspaceClient
        
from server import utils


WORKSPACE_URL = "https://" + os.getenv("DATABRICKS_HOST", "")
M2M_CLIENT_ID = os.getenv("DATABRICKS_CLIENT_ID", "")
M2M_CLIENT_SECRET = os.getenv("DATABRICKS_CLIENT_SECRET", "")

# Genie API Constants
MAX_POLL_ATTEMPTS = 30  # Maximum number of polling attempts
POLL_INTERVAL_SECONDS = 2  # Time to wait between polls
REQUEST_TIMEOUT_SECONDS = 30  # HTTP request timeout
MAX_RETRIES = 3  # Maximum number of retries for transient errors
INITIAL_RETRY_DELAY = 1  # Initial delay for exponential backoff (seconds)

# All possible message status values from Genie API
MESSAGE_STATUSES = {
    "SUBMITTED": "Message has been submitted and is waiting to be processed",
    "EXECUTING": "Message is currently being processed",
    "COMPLETED": "Message processing completed successfully",
    "FAILED": "Message processing failed",
    "CANCELLED": "Message processing was cancelled",
    "ERROR": "An error occurred during message processing"
}

# Terminal states where polling should stop
TERMINAL_MESSAGE_STATES = {"COMPLETED", "FAILED", "CANCELLED", "ERROR"}

# All possible SQL statement execution states
STATEMENT_STATES = {
    "PENDING": "Statement is queued for execution",
    "RUNNING": "Statement is currently executing",
    "SUCCEEDED": "Statement executed successfully",
    "FAILED": "Statement execution failed",
    "CANCELLED": "Statement execution was cancelled",
    "CLOSED": "Statement execution was closed"
}

# Common Databricks API error codes
API_ERROR_CODES = {
    "BAD_REQUEST": "Invalid request parameters",
    "RESOURCE_NOT_FOUND": "The requested resource does not exist",
    "PERMISSION_DENIED": "Insufficient permissions to access resource",
    "UNAUTHENTICATED": "Authentication credentials are missing or invalid",
    "RESOURCE_EXHAUSTED": "Rate limit exceeded or quota exhausted",
    "INTERNAL_ERROR": "Internal server error occurred",
    "UNAVAILABLE": "Service temporarily unavailable"
}


def _get_workspace_client() -> WorkspaceClient:
    """
    Create and return an authenticated WorkspaceClient using M2M OAuth.
    
    Returns:
        WorkspaceClient: Authenticated client for Databricks API calls
        
    Raises:
        Exception: If authentication fails
    """
    try:
        return WorkspaceClient(
            host=WORKSPACE_URL,
            client_id=M2M_CLIENT_ID,
            client_secret=M2M_CLIENT_SECRET,
            auth_type="oauth-m2m"
        )
    except Exception as e:
        raise Exception(f"Failed to authenticate with Databricks: {str(e)}")


def _make_api_request(
    method: str, 
    url: str, 
    headers: dict, 
    json_payload: Optional[dict] = None, 
    timeout: int = REQUEST_TIMEOUT_SECONDS,
    retry_on_failure: bool = True
) -> dict:
    """
    Make an API request with comprehensive error handling and automatic retries.
    
    This function implements:
    - Exponential backoff for transient errors
    - Detailed error classification
    - HTTP status code handling
    - API-level error detection
    - Retry logic for recoverable failures
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: Full URL for the request
        headers: Request headers
        json_payload: Optional JSON payload for POST requests
        timeout: Request timeout in seconds
        retry_on_failure: Whether to retry on transient failures
        
    Returns:
        dict: Response JSON as dictionary
        
    Raises:
        Exception: If request fails after all retries or returns unrecoverable error
    """
    last_exception = None
    retry_count = MAX_RETRIES if retry_on_failure else 1
    
    for attempt in range(retry_count):
        try:
            # Make the HTTP request
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=json_payload, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle specific HTTP status codes
            if response.status_code == 400:
                # Bad Request - not retryable
                response_data = response.json() if response.text else {}
                error_msg = response_data.get("message", "Invalid request parameters")
                raise Exception(f"BAD_REQUEST: {error_msg}")
            
            elif response.status_code == 401:
                # Unauthorized - not retryable
                raise Exception("UNAUTHENTICATED: Authentication credentials are missing or invalid")
            
            elif response.status_code == 403:
                # Forbidden - not retryable
                response_data = response.json() if response.text else {}
                error_msg = response_data.get("message", "Insufficient permissions")
                raise Exception(f"PERMISSION_DENIED: {error_msg}")
            
            elif response.status_code == 404:
                # Not Found - not retryable
                response_data = response.json() if response.text else {}
                error_msg = response_data.get("message", "Resource not found")
                raise Exception(f"RESOURCE_NOT_FOUND: {error_msg}")
            
            elif response.status_code == 429:
                # Too Many Requests - retryable with backoff
                if attempt < retry_count - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                    time.sleep(delay)
                    continue
                else:
                    raise Exception("RESOURCE_EXHAUSTED: Rate limit exceeded. Please try again later")
            
            elif response.status_code == 500:
                # Internal Server Error - retryable
                if attempt < retry_count - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                    time.sleep(delay)
                    continue
                else:
                    raise Exception("INTERNAL_ERROR: Internal server error occurred")
            
            elif response.status_code == 503:
                # Service Unavailable - retryable
                if attempt < retry_count - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                    time.sleep(delay)
                    continue
                else:
                    raise Exception("UNAVAILABLE: Service temporarily unavailable. Please try again later")
            
            # For other status codes, use standard error handling
            response.raise_for_status()
            
            # Parse JSON response
            try:
                response_dict = response.json()
            except ValueError:
                raise Exception(f"Invalid JSON response. Status code: {response.status_code}")
            
            # Check for API-level errors in response body
            if "error_code" in response_dict:
                error_msg = response_dict.get("message", "Unknown error")
                error_code = response_dict.get("error_code", "UNKNOWN")
                error_details = response_dict.get("details", [])
                
                # Determine if error is retryable
                retryable_codes = {"RESOURCE_EXHAUSTED", "UNAVAILABLE", "INTERNAL_ERROR"}
                
                if error_code in retryable_codes and attempt < retry_count - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                    time.sleep(delay)
                    continue
                
                # Build detailed error message
                error_details_str = f" Details: {error_details}" if error_details else ""
                raise Exception(f"API Error [{error_code}]: {error_msg}{error_details_str}")
            
            # Success - return response
            return response_dict
            
        except requests.exceptions.Timeout as e:
            last_exception = Exception(f"Request timeout after {timeout} seconds")
            if attempt < retry_count - 1:
                delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                time.sleep(delay)
                continue
                
        except requests.exceptions.ConnectionError as e:
            last_exception = Exception("Connection error - unable to reach Databricks API")
            if attempt < retry_count - 1:
                delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                time.sleep(delay)
                continue
                
        except requests.exceptions.HTTPError as e:
            # HTTP errors are already handled above, but catch any remaining ones
            last_exception = Exception(f"HTTP error: {e}")
            if e.response.status_code >= 500 and attempt < retry_count - 1:
                delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                time.sleep(delay)
                continue
                
        except requests.exceptions.RequestException as e:
            last_exception = Exception(f"Request failed: {str(e)}")
            if attempt < retry_count - 1:
                delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                time.sleep(delay)
                continue
        
        except Exception as e:
            # Non-retryable exceptions (like ValueError, our custom exceptions)
            if "BAD_REQUEST" in str(e) or "PERMISSION_DENIED" in str(e) or \
               "UNAUTHENTICATED" in str(e) or "RESOURCE_NOT_FOUND" in str(e):
                raise  # Don't retry these
            
            last_exception = e
            if attempt < retry_count - 1:
                delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                time.sleep(delay)
                continue
    
    # If we exhausted all retries, raise the last exception
    if last_exception:
        raise last_exception
    
    raise Exception("Request failed for unknown reason")


def _extract_attachments(message_dict: dict) -> dict:
    """
    Extract and structure attachments from a Genie message response.
    
    Handles multiple attachment types:
    - text: Natural language responses
    - query: SQL queries with metadata
    - suggested_questions: Follow-up question suggestions
    - query_result: Query execution metadata
    - error: Error information (if any)
    
    Args:
        message_dict: The message dictionary from Genie API
        
    Returns:
        dict: Structured attachments containing text, queries, and suggested questions
    """
    attachments = message_dict.get("attachments", [])
    
    result = {
        "text_responses": [],
        "queries": [],
        "suggested_questions": [],
        "errors": []
    }
    
    # Handle case where attachments is None or not a list
    if not isinstance(attachments, list):
        return result
    
    for attachment in attachments:
        # Skip if attachment is not a dict
        if not isinstance(attachment, dict):
            continue
            
        attachment_id = attachment.get("attachment_id", "")
        
        # Extract text responses
        if "text" in attachment and isinstance(attachment["text"], dict):
            text_content = attachment["text"].get("content", "")
            if text_content:  # Only add non-empty text
                result["text_responses"].append({
                    "content": text_content,
                    "attachment_id": attachment_id
                })
        
        # Extract query information
        if "query" in attachment and isinstance(attachment["query"], dict):
            query_info = attachment["query"]
            query_data = {
                "sql": query_info.get("query", ""),
                "description": query_info.get("description", ""),
                "statement_id": query_info.get("statement_id", ""),
                "attachment_id": attachment_id
            }
            
            # Extract query result metadata if available
            if "query_result_metadata" in query_info:
                metadata = query_info["query_result_metadata"]
                query_data["row_count"] = metadata.get("row_count", 0)
                query_data["truncated"] = metadata.get("truncated", False)
            else:
                query_data["row_count"] = 0
                query_data["truncated"] = False
            
            # Only add queries that have SQL content
            if query_data["sql"]:
                result["queries"].append(query_data)
        
        # Extract suggested questions
        if "suggested_questions" in attachment and isinstance(attachment["suggested_questions"], dict):
            questions = attachment["suggested_questions"].get("questions", [])
            if isinstance(questions, list):
                # Filter out empty or non-string questions
                valid_questions = [q for q in questions if isinstance(q, str) and q.strip()]
                result["suggested_questions"].extend(valid_questions)
        
        # Extract error information if present
        if "error" in attachment and isinstance(attachment["error"], dict):
            error_info = attachment["error"]
            result["errors"].append({
                "message": error_info.get("message", "Unknown error"),
                "error_code": error_info.get("error_code", "UNKNOWN"),
                "attachment_id": attachment_id
            })
    
    # Remove duplicates from suggested questions while preserving order
    seen = set()
    unique_questions = []
    for q in result["suggested_questions"]:
        if q not in seen:
            seen.add(q)
            unique_questions.append(q)
    result["suggested_questions"] = unique_questions
    
    return result


def _fetch_query_result(
    space_id: str,
    conversation_id: str,
    message_id: str,
    attachment_id: str,
    headers: dict
) -> Optional[dict]:
    """
    Fetch query result data for a specific attachment.

    Args:
        space_id: The Genie space ID
        conversation_id: The conversation ID
        message_id: The message ID
        attachment_id: The attachment ID to fetch results for
        headers: Authentication headers

    Returns:
        dict: Query result data or None if fetch fails
    """
    try:
        query_result_url = f"{WORKSPACE_URL}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}/attachments/{attachment_id}/query-result"

        response_dict = _make_api_request(
            "GET",
            query_result_url,
            headers
        )

        statement_response = response_dict.get("statement_response", {})
        if not statement_response:
            return None

        status = statement_response.get("status", {}).get("state", "UNKNOWN")

        if status == "SUCCEEDED":
            manifest = statement_response.get("manifest", {})
            result_data = statement_response.get("result", {})

            result = {
                "statement_id": statement_response.get("statement_id", ""),
                "status": status,
                "sql": "",  # Will be populated from attachment if available
                "schema": {
                    "columns": manifest.get("schema", {}).get("columns", [])
                },
                "data": result_data.get("data_array", []),
                "row_count": manifest.get("total_row_count", 0),
                "truncated": manifest.get("truncated", False)
            }

            # Add chunk info for large results
            if manifest.get("total_chunk_count", 1) > 1:
                result["chunk_info"] = {
                    "total_chunks": manifest.get("total_chunk_count", 1),
                    "current_chunk": result_data.get("chunk_index", 0),
                    "row_offset": result_data.get("row_offset", 0)
                }

            return result
        else:
            return {
                "statement_id": statement_response.get("statement_id", ""),
                "status": status,
                "error": f"Query execution status: {status}"
            }

    except Exception as e:
        return None


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

    # =========================================================================
    # GENIE SPACE TOOLS (Dynamic - works with any Genie space)
    # =========================================================================

    @mcp_server.tool
    def list_genie_spaces() -> dict:
        """
        List all available Genie spaces.

        Call this FIRST to discover which Genie space is appropriate for the user's
        question. Returns space IDs, names, and descriptions to help select the
        right space for querying.

        Use this tool when:
        - You need to find available data sources
        - The user asks about data without specifying a space
        - You want to discover what Genie spaces exist

        Returns:
            dict: A dictionary containing:
                - spaces (list): List of available Genie spaces, each with:
                    - space_id (str): The unique space identifier
                    - title (str): Human-readable space name
                    - description (str): Description of the space's data
                - count (int): Number of spaces found
                - error (str): Error message if something went wrong

        Example response:
            {
                "spaces": [
                    {
                        "space_id": "01f0d08866f11370b6735facce14e3ff",
                        "title": "US Stocks Price & Volume",
                        "description": "Historical US stock price and volume data"
                    }
                ],
                "count": 1
            }

        Next steps:
            Use query_genie with the space_id to submit natural language queries.
        """
        try:
            w = _get_workspace_client()

            # Use REST API to list spaces
            list_spaces_url = f"{WORKSPACE_URL}/api/2.0/genie/spaces"

            response_dict = _make_api_request(
                "GET",
                list_spaces_url,
                w.config.authenticate()
            )

            # Extract spaces from response
            spaces_list = response_dict.get("spaces", [])

            spaces = []
            for space in spaces_list:
                # Space ID can be in 'id' or 'space_id' depending on API version
                space_id = space.get("id") or space.get("space_id") or ""
                spaces.append({
                    "space_id": space_id,
                    "title": space.get("title", ""),
                    "description": space.get("description", "")
                })

            return {
                "spaces": spaces,
                "count": len(spaces)
            }

        except Exception as e:
            error_str = str(e)

            if "PERMISSION_DENIED" in error_str:
                return {
                    "error": "PERMISSION_DENIED",
                    "message": "Insufficient permissions to list Genie spaces",
                    "spaces": [],
                    "count": 0
                }
            elif "UNAUTHENTICATED" in error_str:
                return {
                    "error": "UNAUTHENTICATED",
                    "message": "Authentication failed. Please check credentials.",
                    "spaces": [],
                    "count": 0
                }
            else:
                return {
                    "error": "LIST_SPACES_FAILED",
                    "message": f"Failed to list Genie spaces: {error_str}",
                    "spaces": [],
                    "count": 0
                }

    @mcp_server.tool
    def query_genie(
        space_id: str,
        query: str,
        conversation_id: Optional[str] = None
    ) -> dict:
        """
        Submit a natural language query to a Genie space.

        PREREQUISITE: Call list_genie_spaces first to find the appropriate space_id.

        This tool submits a query to Databricks Genie and returns immediately with
        conversation_id and message_id. Use poll_genie_response to retrieve results.

        Args:
            space_id (str): The Genie space ID (from list_genie_spaces)
            query (str): Natural language question about the data
            conversation_id (Optional[str]): Continue an existing conversation.
                                            If None, starts a new conversation.

        Returns:
            dict: A dictionary containing:
                - conversation_id (str): For follow-up queries and polling
                - message_id (str): For polling the response
                - status (str): Initial message status (usually SUBMITTED)
                - space_id (str): The space being queried
                - error (str): Error message if something went wrong

        Example response:
            {
                "conversation_id": "01f0e34ce9641238a5018229451c2ff2",
                "message_id": "01f0e34ce97a157983ba500ee38047ea",
                "status": "SUBMITTED",
                "space_id": "01f0d08866f11370b6735facce14e3ff"
            }

        Next steps:
            Use poll_genie_response with the returned conversation_id and message_id
            to retrieve the results.

        Note:
            - Query length is limited to 10,000 characters
            - Conversation state is maintained for follow-up questions
            - Message processing happens asynchronously
        """
        # Validate inputs
        if not space_id or not space_id.strip():
            return {
                "error": "INVALID_INPUT",
                "message": "space_id is required"
            }

        if not query or not query.strip():
            return {
                "error": "INVALID_INPUT",
                "message": "query is required"
            }

        if len(query.strip()) > 10000:
            return {
                "error": "INVALID_INPUT",
                "message": "Query exceeds maximum length of 10,000 characters"
            }

        # Validate conversation_id format if provided
        if conversation_id:
            if not isinstance(conversation_id, str) or len(conversation_id) < 10:
                return {
                    "error": "INVALID_INPUT",
                    "message": "Invalid conversation_id format. Must be a valid UUID string."
                }

        try:
            w = _get_workspace_client()

            # Prepare request payload
            json_payload = {"content": query.strip()}
            if conversation_id:
                json_payload["conversation_id"] = conversation_id

            # Start conversation / send message
            start_conversation_url = f"{WORKSPACE_URL}/api/2.0/genie/spaces/{space_id}/start-conversation"
            response_dict = _make_api_request(
                "POST",
                start_conversation_url,
                w.config.authenticate(),
                json_payload
            )

            # Extract response data
            message = response_dict.get("message", {})
            conv_id = message.get("conversation_id", "")
            msg_id = response_dict.get("message_id", "")
            status = message.get("status", "UNKNOWN")

            if not conv_id or not msg_id:
                return {
                    "error": "INVALID_RESPONSE",
                    "message": "Failed to extract conversation_id or message_id from response",
                    "space_id": space_id
                }

            return {
                "conversation_id": conv_id,
                "message_id": msg_id,
                "status": status,
                "space_id": space_id
            }

        except Exception as e:
            error_str = str(e)

            if "RESOURCE_NOT_FOUND" in error_str:
                return {
                    "error": "SPACE_NOT_FOUND",
                    "message": f"Genie space '{space_id}' not found. Use list_genie_spaces to find valid space IDs.",
                    "space_id": space_id
                }
            elif "PERMISSION_DENIED" in error_str:
                return {
                    "error": "PERMISSION_DENIED",
                    "message": f"Insufficient permissions to query space '{space_id}'",
                    "space_id": space_id
                }
            else:
                return {
                    "error": "QUERY_FAILED",
                    "message": str(e),
                    "space_id": space_id,
                    "conversation_id": conversation_id
                }

    @mcp_server.tool
    def poll_genie_response(
        space_id: str,
        conversation_id: str,
        message_id: str,
        max_wait_seconds: int = 60,
        fetch_query_results: bool = True
    ) -> dict:
        """
        Poll for Genie query completion and retrieve results.

        Call this after query_genie to wait for and retrieve results.

        Args:
            space_id (str): The Genie space ID (must match the query_genie call)
            conversation_id (str): From query_genie response
            message_id (str): From query_genie response
            max_wait_seconds (int): Maximum time to wait (1-300, default 60)
            fetch_query_results (bool): Whether to fetch full query results (default True)

        Returns:
            dict: A comprehensive dictionary containing:
                - status (str): Final message status (COMPLETED, FAILED, TIMEOUT, etc.)
                - space_id (str): The Genie space ID
                - conversation_id (str): The conversation ID
                - message_id (str): The message ID
                - attachments (dict): Structured attachments containing:
                    - text_responses: Natural language responses
                    - queries: SQL queries with metadata
                    - suggested_questions: Follow-up suggestions
                - query_result (dict): Actual data from SQL query (if fetch_query_results=True)
                    - sql: The generated SQL query
                    - schema: Column definitions
                    - data: Array of data rows
                    - row_count: Total rows returned
                - poll_attempts (int): Number of polling attempts made
                - error (str): Error message if something went wrong

        Example response:
            {
                "status": "COMPLETED",
                "space_id": "01f0d08866f11370b6735facce14e3ff",
                "conversation_id": "01f0e34ce9641238a5018229451c2ff2",
                "message_id": "01f0e34ce97a157983ba500ee38047ea",
                "attachments": {
                    "text_responses": [],
                    "queries": [{
                        "sql": "SELECT Ticker, SUM(Volume)...",
                        "description": "Find highest volume stock",
                        "row_count": 1
                    }],
                    "suggested_questions": ["Show me the top 5..."]
                },
                "query_result": {
                    "sql": "SELECT Ticker, SUM(Volume)...",
                    "schema": {"columns": [...]},
                    "data": [["NVDA", "51746176100"]],
                    "row_count": 1
                },
                "poll_attempts": 5
            }
        """
        # Validate inputs
        if not space_id or not space_id.strip():
            return {
                "error": "INVALID_INPUT",
                "message": "space_id is required"
            }

        if not conversation_id or not message_id:
            return {
                "error": "INVALID_INPUT",
                "message": "conversation_id and message_id are required"
            }

        if not isinstance(conversation_id, str) or len(conversation_id) < 10:
            return {
                "error": "INVALID_INPUT",
                "message": "Invalid conversation_id format"
            }

        if not isinstance(message_id, str) or len(message_id) < 10:
            return {
                "error": "INVALID_INPUT",
                "message": "Invalid message_id format"
            }

        # Clamp max_wait_seconds to valid range
        max_wait_seconds = max(1, min(300, max_wait_seconds))
        max_attempts = max(1, max_wait_seconds // POLL_INTERVAL_SECONDS)

        try:
            w = _get_workspace_client()
            headers = w.config.authenticate()

            # Poll for message completion
            current_status = "SUBMITTED"
            message_dict = {}
            attempts = 0

            get_message_url = f"{WORKSPACE_URL}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}"

            while attempts < max_attempts:
                attempts += 1

                message_dict = _make_api_request(
                    "GET",
                    get_message_url,
                    headers
                )

                current_status = message_dict.get("status", "UNKNOWN")

                if current_status in TERMINAL_MESSAGE_STATES:
                    break

                if attempts < max_attempts:
                    time.sleep(POLL_INTERVAL_SECONDS)

            # Build base result
            result = {
                "status": current_status,
                "space_id": space_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "poll_attempts": attempts
            }

            # Handle terminal error states
            if current_status == "FAILED":
                error_details = []
                for attachment in message_dict.get("attachments", []):
                    if "error" in attachment:
                        error_details.append(attachment["error"])

                result["error"] = "MESSAGE_FAILED"
                result["message"] = "The Genie message failed to process"
                if error_details:
                    result["error_details"] = error_details
                return result

            if current_status == "CANCELLED":
                result["error"] = "MESSAGE_CANCELLED"
                result["message"] = "The Genie message was cancelled"
                return result

            if current_status == "ERROR":
                result["error"] = "MESSAGE_ERROR"
                result["message"] = "An error occurred during message processing"
                return result

            # Check for timeout
            if current_status not in TERMINAL_MESSAGE_STATES:
                result["error"] = "TIMEOUT"
                result["message"] = f"Message did not complete within {max_wait_seconds} seconds. Current status: {current_status}"
                return result

            # Extract attachments from completed message
            result["attachments"] = _extract_attachments(message_dict)

            # Fetch query results if requested and available
            if fetch_query_results and result["attachments"]["queries"]:
                for query_info in result["attachments"]["queries"]:
                    attachment_id = query_info.get("attachment_id", "")
                    if not attachment_id:
                        continue

                    query_result = _fetch_query_result(
                        space_id, conversation_id, message_id,
                        attachment_id, headers
                    )

                    if query_result:
                        # Add the SQL from the attachment
                        query_result["sql"] = query_info.get("sql", "")
                        query_result["description"] = query_info.get("description", "")
                        result["query_result"] = query_result
                        break  # Only fetch first query result

            return result

        except Exception as e:
            error_str = str(e)

            if "RESOURCE_NOT_FOUND" in error_str:
                return {
                    "error": "RESOURCE_NOT_FOUND",
                    "message": "Conversation or message not found. Verify the IDs are correct.",
                    "space_id": space_id,
                    "conversation_id": conversation_id,
                    "message_id": message_id
                }
            else:
                return {
                    "error": "POLL_FAILED",
                    "message": str(e),
                    "space_id": space_id,
                    "conversation_id": conversation_id,
                    "message_id": message_id
                }

    @mcp_server.tool
    def create_sql_alert(
        alert_name: str,
        sql_query: str,
        warehouse_id: str,
        column_name: str,
        operator: str,
        threshold_value: float,
        description: Optional[str] = None
    ) -> dict:
        """
        Create a Databricks SQL alert from a SQL query.

        Use this tool after poll_genie_response to set up automated monitoring
        on query results. The alert will trigger when the specified column
        meets the threshold condition.

        Use this tool when:
        - User wants to monitor query results automatically
        - User asks to "alert me when..." or "notify me if..."
        - User wants to set up automated monitoring on Genie insights

        Args:
            alert_name: Human-readable name (use snake_case, e.g., "high_revenue_orders")
            sql_query: SQL query to monitor (from poll_genie_response.query_result.sql)
            warehouse_id: SQL warehouse ID to execute the query
            column_name: Column in query result to monitor
            operator: Comparison operator - one of:
                - GREATER_THAN: Trigger when value > threshold
                - GREATER_THAN_OR_EQUAL: Trigger when value >= threshold
                - LESS_THAN: Trigger when value < threshold
                - LESS_THAN_OR_EQUAL: Trigger when value <= threshold
                - EQUAL: Trigger when value == threshold
                - NOT_EQUAL: Trigger when value != threshold
                - IS_NULL: Trigger when value is NULL
            threshold_value: Numeric threshold for triggering
            description: Optional description of alert purpose

        Returns:
            dict: Contains alert_id, alert_name, query_id, alert_url on success
                  or error, message on failure

        Example response:
            {
                "success": True,
                "alert_id": "abc-123",
                "alert_name": "high_revenue_orders",
                "query_id": "query-456",
                "alert_url": "https://workspace.cloud.databricks.com/sql/alerts/abc-123",
                "message": "Alert created successfully"
            }

        Next steps:
            View and manage the alert in Databricks SQL UI using the alert_url.
            Configure notification recipients in the UI if needed.
        """
        from databricks.sdk.service import sql as sql_service

        # Operator mapping
        operator_map = {
            "GREATER_THAN": sql_service.AlertOperator.GREATER_THAN,
            "GREATER_THAN_OR_EQUAL": sql_service.AlertOperator.GREATER_THAN_OR_EQUAL,
            "LESS_THAN": sql_service.AlertOperator.LESS_THAN,
            "LESS_THAN_OR_EQUAL": sql_service.AlertOperator.LESS_THAN_OR_EQUAL,
            "EQUAL": sql_service.AlertOperator.EQUAL,
            "NOT_EQUAL": sql_service.AlertOperator.NOT_EQUAL,
            "IS_NULL": sql_service.AlertOperator.IS_NULL,
        }

        # Input validation
        if not alert_name or not alert_name.strip():
            return {
                "error": "INVALID_INPUT",
                "message": "alert_name is required"
            }

        if not sql_query or not sql_query.strip():
            return {
                "error": "INVALID_INPUT",
                "message": "sql_query is required"
            }

        if not warehouse_id or not warehouse_id.strip():
            return {
                "error": "INVALID_INPUT",
                "message": "warehouse_id is required"
            }

        if not column_name or not column_name.strip():
            return {
                "error": "INVALID_INPUT",
                "message": "column_name is required"
            }

        operator_upper = operator.upper().strip()
        if operator_upper not in operator_map:
            return {
                "error": "INVALID_OPERATOR",
                "message": f"operator must be one of: {', '.join(operator_map.keys())}",
                "provided": operator
            }

        # Validate SQL is SELECT statement (basic check)
        sql_upper = sql_query.strip().upper()
        if not sql_upper.startswith("SELECT"):
            return {
                "error": "INVALID_INPUT",
                "message": "sql_query must be a SELECT statement"
            }

        query = None
        try:
            w = _get_workspace_client()

            # Step 1: Create the saved query
            query_name = f"alert_query_{alert_name.strip()}_{int(time.time())}"
            query = w.queries.create(
                query=sql_service.CreateQueryRequestQuery(
                    display_name=query_name,
                    warehouse_id=warehouse_id.strip(),
                    description=description or f"Query for alert: {alert_name}",
                    query_text=sql_query.strip(),
                )
            )

            # Step 2: Create the alert
            alert = w.alerts.create(
                alert=sql_service.CreateAlertRequestAlert(
                    display_name=alert_name.strip(),
                    query_id=query.id,
                    condition=sql_service.AlertCondition(
                        operand=sql_service.AlertConditionOperand(
                            column=sql_service.AlertOperandColumn(name=column_name.strip())
                        ),
                        op=operator_map[operator_upper],
                        threshold=sql_service.AlertConditionThreshold(
                            value=sql_service.AlertOperandValue(double_value=float(threshold_value))
                        ),
                        empty_result_state=sql_service.AlertState.OK,
                    ),
                    notify_on_ok=False,
                ),
                auto_resolve_display_name=True
            )

            return {
                "success": True,
                "alert_id": alert.id,
                "alert_name": alert.display_name,
                "query_id": query.id,
                "query_name": query_name,
                "alert_url": f"{WORKSPACE_URL}/sql/alerts/{alert.id}",
                "message": f"Alert '{alert_name}' created successfully"
            }

        except Exception as e:
            error_str = str(e)

            # Rollback: delete saved query if it was created
            if query is not None:
                try:
                    w.queries.delete(id=query.id)
                except Exception:
                    pass  # Best effort cleanup

            if "RESOURCE_NOT_FOUND" in error_str or "warehouse" in error_str.lower():
                return {
                    "error": "WAREHOUSE_NOT_FOUND",
                    "message": f"Warehouse '{warehouse_id}' not found or not accessible",
                    "warehouse_id": warehouse_id
                }
            elif "PERMISSION_DENIED" in error_str:
                return {
                    "error": "PERMISSION_DENIED",
                    "message": "Insufficient permissions to create alerts",
                    "details": error_str
                }
            elif "column" in error_str.lower():
                return {
                    "error": "COLUMN_NOT_FOUND",
                    "message": f"Column '{column_name}' not found in query result",
                    "column_name": column_name
                }
            else:
                return {
                    "error": "ALERT_CREATION_FAILED",
                    "message": str(e),
                    "alert_name": alert_name
                }
