# feat: Dynamic Genie Space Selection and Query Tools

## Overview

Update the MCP server to replace hardcoded Genie space tools with dynamic, parameterized tools that allow AI assistants to:
1. Discover available Genie spaces
2. Select the appropriate space for a user's query
3. Execute natural language queries against any selected space
4. Retrieve SQL and result data

**Current State**: Tools are hardcoded with space ID `01f0d08866f11370b6735facce14e3ff` ("US Stocks Price & Volume") embedded in function names.

**Target State**: Generic tools that accept `space_id` as a parameter, enabling multi-space support.

## Problem Statement / Motivation

The current implementation has several limitations:

1. **Hardcoded Space ID**: Function names like `query_space_01f0d08866f11370b6735facce14e3ff` tie the server to a single Genie space
2. **No Discovery**: AI assistants cannot discover which Genie spaces are available
3. **Poor Scalability**: Adding new spaces requires code changes and redeployment
4. **Limited Flexibility**: Users with access to multiple Genie spaces cannot leverage them

This change enables the MCP server to work with any Genie space the user has access to, making it a truly general-purpose Genie interface.

## Proposed Solution

Implement three new MCP tools following the existing patterns in `server/tools.py`:

### Tool 1: `list_genie_spaces`

Lists all Genie spaces accessible to the authenticated user.

```python
# server/tools.py

@mcp_server.tool
def list_genie_spaces() -> dict:
    """
    List all available Genie spaces.

    Call this FIRST to discover which Genie space is appropriate for the user's
    question. Returns space IDs, names, and descriptions to help select the
    right space for querying.

    Returns:
        dict: List of Genie spaces with their IDs and metadata
    """
```

### Tool 2: `query_genie`

Submits a natural language query to a specified Genie space.

```python
@mcp_server.tool
def query_genie(
    space_id: str,
    query: str,
    conversation_id: str = None
) -> dict:
    """
    Submit a natural language query to a Genie space.

    PREREQUISITE: Call list_genie_spaces first to find the appropriate space_id.

    Args:
        space_id: The Genie space ID (from list_genie_spaces)
        query: Natural language question about the data
        conversation_id: Optional - pass to continue an existing conversation

    Returns:
        dict: conversation_id, message_id for polling, and initial status
    """
```

### Tool 3: `poll_genie_response`

Polls for query completion and retrieves results.

```python
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
        space_id: The Genie space ID
        conversation_id: From query_genie response
        message_id: From query_genie response
        max_wait_seconds: Maximum time to wait (default 60)
        fetch_query_results: Whether to fetch full query results (default True)

    Returns:
        dict: Status, generated SQL, text response, and query results
    """
```

## Technical Considerations

### Architecture

- **Reuse existing helpers**: `_make_api_request()`, `_extract_attachments()`, `_get_workspace_client()`
- **Follow existing patterns**: Error codes, response format, retry logic
- **Maintain backward compatibility**: Keep existing hardcoded tools (deprecated)

### Authentication

Use `_get_workspace_client()` (M2M OAuth) for all tools, matching existing implementation:

```python
# server/tools.py:230-248
def _get_workspace_client() -> WorkspaceClient:
    return WorkspaceClient(
        host=WORKSPACE_URL,
        client_id=M2M_CLIENT_ID,
        client_secret=M2M_CLIENT_SECRET,
        auth_type="oauth-m2m"
    )
```

### Genie API Endpoints

| Operation | Endpoint |
|-----------|----------|
| List Spaces | `GET /api/2.0/genie/spaces` |
| Start Conversation | `POST /api/2.0/genie/spaces/{space_id}/start-conversation` |
| Continue Conversation | `POST /api/2.0/genie/spaces/{space_id}/conversations/{conv_id}/messages` |
| Get Message | `GET /api/2.0/genie/spaces/{space_id}/conversations/{conv_id}/messages/{msg_id}` |
| Get Query Result | `GET /api/2.0/genie/spaces/{space_id}/conversations/{conv_id}/messages/{msg_id}/attachments/{att_id}/query-result` |

### Error Handling

Follow existing error patterns from `server/tools.py:219-227`:

```python
ERROR_CODES = {
    "INVALID_INPUT": "Invalid input parameters",
    "SPACE_NOT_FOUND": "Genie space not found",
    "NO_SPACES_AVAILABLE": "No Genie spaces accessible",
    "QUERY_FAILED": "Query submission failed",
    "POLL_FAILED": "Polling for results failed",
    "PERMISSION_DENIED": "Insufficient permissions",
    "UNAUTHENTICATED": "Authentication failed",
    "TIMEOUT": "Query timed out",
}
```

### Performance

- **Rate Limits**: Databricks Genie has 5 queries/minute/workspace limit
- **Polling**: Use existing 2-second intervals, 30 max attempts
- **Timeouts**: Default 60 seconds, configurable up to 300 seconds

## Acceptance Criteria

### Functional Requirements

- [ ] `list_genie_spaces` returns all spaces accessible to the service principal
- [ ] `list_genie_spaces` returns empty list (not error) when no spaces available
- [ ] `query_genie` accepts any valid space_id and submits query
- [ ] `query_genie` supports new conversations (conversation_id=None)
- [ ] `query_genie` supports continuing conversations (conversation_id provided)
- [ ] `poll_genie_response` waits for completion up to max_wait_seconds
- [ ] `poll_genie_response` returns generated SQL when available
- [ ] `poll_genie_response` returns query results when fetch_query_results=True
- [ ] All tools follow existing error response format
- [ ] All tools have clear docstrings for AI assistant consumption

### Edge Cases

- [ ] Handle space_id that doesn't exist (SPACE_NOT_FOUND error)
- [ ] Handle empty query string (INVALID_INPUT error)
- [ ] Handle conversation_id from different space (let API error, don't validate)
- [ ] Handle query timeout gracefully (TIMEOUT error with partial status)
- [ ] Handle rate limiting (429) with exponential backoff retry
- [ ] Handle permission denied on specific space

### Testing Requirements

- [ ] Unit tests for each new tool
- [ ] Integration test calling list → query → poll flow
- [ ] Test with multiple Genie spaces
- [ ] Test error scenarios (invalid space, timeout, permission denied)
- [ ] Update `tests/test_mcp_tools.py` with new tool tests

### Backward Compatibility

- [ ] Existing hardcoded tools continue to work
- [ ] Add deprecation notice to existing tool docstrings
- [ ] Document migration path in CLAUDE.md

## Success Metrics

- AI assistants can successfully discover and query any accessible Genie space
- No breaking changes for existing hardcoded tool users
- All integration tests pass
- Error messages are clear and actionable

## Dependencies & Risks

### Dependencies

- Databricks SDK Genie API (`w.genie.list_spaces()` availability)
- M2M OAuth credentials with Genie space permissions
- At least one Genie space accessible for testing

### Risks

| Risk | Mitigation |
|------|------------|
| `list_spaces` API not available in all regions | Test API availability first; fallback to error with instructions |
| Service principal may not see user's spaces | Document permission requirements; consider user auth option |
| Conversation IDs may be space-bound | Test cross-space behavior; document limitations |
| Large number of spaces (100+) | Implement pagination if needed; document limits |

## Implementation Plan

### Phase 1: API Validation

1. Test `w.genie.list_spaces()` with current credentials
2. Verify response format and available metadata
3. Confirm conversation-space binding behavior

### Phase 2: Core Implementation

1. Add `list_genie_spaces()` tool
2. Add `query_genie()` tool (refactor from existing)
3. Add `poll_genie_response()` tool (refactor from existing)
4. Add helper function for space validation

### Phase 3: Testing & Polish

1. Write unit tests for each tool
2. Write integration test for full flow
3. Update existing tests if affected
4. Add deprecation notices to old tools

### Phase 4: Documentation

1. Update CLAUDE.md with new tools
2. Update README.md with examples
3. Add migration guide for hardcoded tools

## Files to Modify

| File | Changes |
|------|---------|
| `server/tools.py` | Add 3 new tools, refactor helpers, add deprecation notices |
| `tests/test_mcp_tools.py` | Add tests for new tools |
| `CLAUDE.md` | Document new tools and migration path |

## MVP Implementation

### server/tools.py (new tools)

```python
# Add after existing helper functions (around line 520)

@mcp_server.tool
def list_genie_spaces() -> dict:
    """
    List all available Genie spaces.

    Call this FIRST to discover which Genie space is appropriate for the user's
    question. Returns space IDs, names, and descriptions to help select the
    right space for querying.

    Returns:
        dict: List of Genie spaces with metadata
            - spaces: List of {space_id, title, description}
            - count: Number of spaces found
    """
    try:
        w = _get_workspace_client()
        spaces_response = w.genie.list_spaces()

        spaces = []
        for space in spaces_response:
            spaces.append({
                "space_id": space.space_id,
                "title": space.title,
                "description": space.description or ""
            })

        return {
            "spaces": spaces,
            "count": len(spaces)
        }
    except Exception as e:
        return {
            "error": "LIST_SPACES_FAILED",
            "message": f"Failed to list Genie spaces: {str(e)}"
        }


@mcp_server.tool
def query_genie(
    space_id: str,
    query: str,
    conversation_id: str = None
) -> dict:
    """
    Submit a natural language query to a Genie space.

    PREREQUISITE: Call list_genie_spaces first to find the appropriate space_id.

    Args:
        space_id: The Genie space ID (from list_genie_spaces)
        query: Natural language question about the data
        conversation_id: Optional - pass to continue an existing conversation

    Returns:
        dict: conversation_id and message_id for polling
    """
    # Validate inputs
    if not space_id or not space_id.strip():
        return {"error": "INVALID_INPUT", "message": "space_id is required"}
    if not query or not query.strip():
        return {"error": "INVALID_INPUT", "message": "query is required"}
    if len(query) > 10000:
        return {"error": "INVALID_INPUT", "message": "Query exceeds 10000 character limit"}

    try:
        # Determine endpoint based on conversation state
        if conversation_id:
            url = f"{WORKSPACE_URL}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages"
        else:
            url = f"{WORKSPACE_URL}/api/2.0/genie/spaces/{space_id}/start-conversation"

        response = _make_api_request("POST", url, json_data={"content": query.strip()})

        if "error" in response:
            return response

        return {
            "conversation_id": response.get("conversation_id"),
            "message_id": response.get("message_id"),
            "status": response.get("status", "SUBMITTED"),
            "space_id": space_id
        }
    except Exception as e:
        return {
            "error": "QUERY_FAILED",
            "message": f"Failed to submit query: {str(e)}"
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
        space_id: The Genie space ID
        conversation_id: From query_genie response
        message_id: From query_genie response
        max_wait_seconds: Maximum time to wait (1-300, default 60)
        fetch_query_results: Whether to fetch full query results (default True)

    Returns:
        dict: Status, generated SQL, text response, and query results
    """
    # Validate inputs
    if not all([space_id, conversation_id, message_id]):
        return {"error": "INVALID_INPUT", "message": "space_id, conversation_id, and message_id are required"}

    max_wait_seconds = max(1, min(300, max_wait_seconds))
    max_attempts = max_wait_seconds // POLL_INTERVAL_SECONDS

    url = f"{WORKSPACE_URL}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}"

    for attempt in range(max_attempts):
        response = _make_api_request("GET", url)

        if "error" in response:
            return response

        status = response.get("status", "UNKNOWN")

        if status in TERMINAL_MESSAGE_STATES:
            # Extract attachments and results
            result = _extract_attachments(response)
            result["status"] = status
            result["space_id"] = space_id
            result["conversation_id"] = conversation_id
            result["message_id"] = message_id

            # Fetch query results if requested and available
            if fetch_query_results and status == "COMPLETED":
                for attachment in response.get("attachments", []):
                    if attachment.get("query") and attachment.get("attachment_id"):
                        query_result = _fetch_query_result(
                            space_id, conversation_id, message_id,
                            attachment["attachment_id"]
                        )
                        if query_result:
                            result["query_result"] = query_result
                            break

            return result

        time.sleep(POLL_INTERVAL_SECONDS)

    return {
        "error": "TIMEOUT",
        "message": f"Query did not complete within {max_wait_seconds} seconds",
        "status": status,
        "space_id": space_id
    }
```

### tests/test_mcp_tools.py (new tests)

```python
def test_list_genie_spaces(mcp_client):
    """Test listing available Genie spaces."""
    result = mcp_client.call_tool("list_genie_spaces", arguments={})

    assert "error" not in result or result.get("spaces") is not None
    if "spaces" in result:
        assert isinstance(result["spaces"], list)
        assert "count" in result


def test_query_genie_invalid_space(mcp_client):
    """Test querying with invalid space_id."""
    result = mcp_client.call_tool("query_genie", arguments={
        "space_id": "invalid-space-id",
        "query": "test query"
    })

    assert "error" in result


def test_query_genie_empty_query(mcp_client):
    """Test querying with empty query."""
    result = mcp_client.call_tool("query_genie", arguments={
        "space_id": "01f0d08866f11370b6735facce14e3ff",
        "query": ""
    })

    assert result.get("error") == "INVALID_INPUT"


def test_full_genie_flow(mcp_client):
    """Test complete flow: list spaces → query → poll."""
    # Step 1: List spaces
    spaces_result = mcp_client.call_tool("list_genie_spaces", arguments={})

    if spaces_result.get("count", 0) == 0:
        pytest.skip("No Genie spaces available")

    space_id = spaces_result["spaces"][0]["space_id"]

    # Step 2: Query
    query_result = mcp_client.call_tool("query_genie", arguments={
        "space_id": space_id,
        "query": "What tables are available?"
    })

    assert "conversation_id" in query_result
    assert "message_id" in query_result

    # Step 3: Poll
    poll_result = mcp_client.call_tool("poll_genie_response", arguments={
        "space_id": space_id,
        "conversation_id": query_result["conversation_id"],
        "message_id": query_result["message_id"],
        "max_wait_seconds": 60
    })

    assert poll_result.get("status") in ["COMPLETED", "FAILED", "TIMEOUT"]
```

## References

### Internal References

- Existing tool patterns: `server/tools.py:543-1278`
- Authentication helpers: `server/utils.py:1-32`
- API request helper: `server/tools.py:251-422`
- Attachment extraction: `server/tools.py:424-519`
- Error codes: `server/tools.py:219-227`

### External References

- [Databricks Genie API Documentation](https://docs.databricks.com/aws/en/genie/conversation-api)
- [Databricks SDK Python - Genie Module](https://databricks-sdk-py.readthedocs.io/en/stable/workspace/dashboards/genie.html)
- [FastMCP Tool Documentation](https://gofastmcp.com/servers/tools)
- [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25)

### Related Work

- Previous commit: `38e3a02` - feat: Add a more complex set of tools for genie
- Edge cases document: `EDGE_CASES_REVIEW.md`
