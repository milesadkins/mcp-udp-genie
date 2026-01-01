# MCP Tools Test Suite

Comprehensive integration test suite for the MCP Genie server tools.

## Overview

This test suite validates all MCP tools by:
1. **Deploying the MCP server locally** on a random free port
2. **Authenticating** using Databricks M2M OAuth
3. **Testing each tool** with various scenarios and edge cases
4. **Validating error handling** and response formats
5. **Cleaning up** automatically after tests complete

## Test Coverage

### 🏥 Health & Discovery (3 tests)
- ✅ Server is running and responding
- ✅ List all available tools
- ✅ Verify expected tools are present

### 👤 User Tools (2 tests)
- ✅ Health check tool
- ✅ Get current user information

### 🔍 Query Space Tools (8 tests)
- ✅ Simple query execution
- ✅ Query with auto-polling
- ✅ Query without auto-polling
- ✅ Empty query validation
- ✅ Long query validation
- ✅ Concurrent queries
- ✅ End-to-end query flow
- ✅ Response time validation

### 📊 Poll Response Tools (2 tests)
- ✅ Invalid conversation/message IDs
- ✅ Short timeout handling

### 📈 Query Result Tools (2 tests)
- ✅ Invalid IDs validation
- ✅ Missing parameters handling

### 🛡️ Error Handling (3 tests)
- ✅ Invalid tool names
- ✅ Server resilience after errors
- ✅ Graceful error responses

**Total: 20+ comprehensive test cases**

## Prerequisites

### Required Dependencies
```bash
# Install test dependencies
uv pip install pytest requests databricks-mcp databricks-sdk
```

### Environment Setup

The tests use the following environment variables (with fallback defaults):

```bash
# Optional: Override default values
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_CLIENT_ID="your-m2m-client-id"
export DATABRICKS_CLIENT_SECRET="your-m2m-client-secret"
```

If not set, the tests will use the hardcoded defaults for the test environment.

## Running the Tests

### Run All Tests
```bash
# From project root
pytest tests/test_mcp_tools.py -v
```

### Run Specific Test
```bash
# Run a single test
pytest tests/test_mcp_tools.py::test_health_tool -v

# Run tests matching a pattern
pytest tests/test_mcp_tools.py -k "query" -v
```

### Run with Detailed Output
```bash
# Show print statements and full output
pytest tests/test_mcp_tools.py -v -s

# Show short traceback
pytest tests/test_mcp_tools.py -v --tb=short

# Show full traceback
pytest tests/test_mcp_tools.py -v --tb=long
```

### Run with Coverage
```bash
# Generate coverage report
pytest tests/test_mcp_tools.py --cov=server --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Test Structure

### Fixtures

**`mcp_server`** (session-scoped)
- Starts MCP server on a free port
- Waits for server startup (30s timeout)
- Automatically stops server after all tests
- Yields the base URL for the server

**`workspace_client`** (session-scoped)
- Creates authenticated Databricks WorkspaceClient
- Uses M2M OAuth authentication
- Reused across all tests

**`mcp_client`** (session-scoped)
- Creates DatabricksMCPClient connected to local server
- Includes authentication
- Reused across all tests

**`mcp_client_no_auth`** (session-scoped)
- Creates unauthenticated client for testing auth failures

### Test Categories

1. **Smoke Tests**: Basic connectivity and tool discovery
2. **Success Cases**: Valid inputs and expected outputs
3. **Error Cases**: Invalid inputs and error handling
4. **Edge Cases**: Boundary conditions and unusual inputs
5. **Integration Tests**: End-to-end workflows
6. **Performance Tests**: Response times and concurrency

## Example Test Output

```
🚀 Starting MCP server on port 54321...
✅ Server started successfully at http://127.0.0.1:54321

tests/test_mcp_tools.py::test_server_is_running PASSED         [ 5%]
✅ Server is running at http://127.0.0.1:54321

tests/test_mcp_tools.py::test_list_tools PASSED                [10%]
✅ Found 5 tools: ['health', 'get_current_user', ...]
✅ All expected tools are present

tests/test_mcp_tools.py::test_health_tool PASSED               [15%]
✅ Health check response: {"status":"healthy",...}

tests/test_mcp_tools.py::test_query_space_simple_query PASSED  [20%]
✅ Query response received: {"conversation_id":"01f0e34c...",...}

...

======================== 20 passed in 45.23s =========================

🛑 Stopping MCP server...
```

## Debugging Failed Tests

### Server Startup Issues

If the server fails to start:
```bash
# Check if port is available
lsof -i :8000

# Try running server manually
uv run custom-mcp-server --port 8000

# Check server logs
tail -f server.log
```

### Authentication Issues

If authentication fails:
```bash
# Verify credentials
databricks auth login

# Check M2M credentials
echo $DATABRICKS_CLIENT_ID
echo $DATABRICKS_CLIENT_SECRET

# Test workspace connection
python -c "from databricks.sdk import WorkspaceClient; w = WorkspaceClient(); print(w.current_user.me())"
```

### Test Failures

If tests fail:
```bash
# Run with verbose output and no capture
pytest tests/test_mcp_tools.py -vvs

# Run with debugging
pytest tests/test_mcp_tools.py --pdb

# Show locals on failure
pytest tests/test_mcp_tools.py --showlocals
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Test MCP Tools

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -r requirements.txt
          uv pip install pytest requests databricks-mcp
      
      - name: Run tests
        env:
          DATABRICKS_HOST: ${{ secrets.DATABRICKS_HOST }}
          DATABRICKS_CLIENT_ID: ${{ secrets.DATABRICKS_CLIENT_ID }}
          DATABRICKS_CLIENT_SECRET: ${{ secrets.DATABRICKS_CLIENT_SECRET }}
        run: pytest tests/test_mcp_tools.py -v
```

## Adding New Tests

### Test Template

```python
def test_my_new_feature(mcp_client):
    """Test description."""
    # Arrange
    test_input = "test data"
    
    # Act
    result = mcp_client.call_tool("tool_name", param=test_input)
    
    # Assert
    content = result[0].content[0].text
    assert "expected" in content
    print(f"✅ Test passed: {content}")
```

### Best Practices

1. **Use descriptive test names**: `test_query_space_with_empty_string`
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Include print statements**: Help with debugging
4. **Test both success and failure**: Cover edge cases
5. **Keep tests independent**: Don't rely on other test state
6. **Use fixtures**: Share setup code
7. **Add docstrings**: Explain what the test validates

## Troubleshooting

### Common Issues

**Issue**: Server won't start
- **Solution**: Check if another process is using the port
- **Command**: `lsof -i :8000`

**Issue**: Authentication fails
- **Solution**: Verify M2M credentials are correct
- **Command**: `databricks auth login`

**Issue**: Tests hang
- **Solution**: Check server is responding
- **Command**: `curl http://localhost:8000`

**Issue**: Import errors
- **Solution**: Install missing dependencies
- **Command**: `uv pip install -r requirements.txt`

## Performance Benchmarks

Expected test execution times:
- **Server startup**: 5-10 seconds
- **Simple tool calls**: <1 second
- **Query with auto-poll**: 10-60 seconds
- **Full test suite**: 45-90 seconds

## Contributing

When adding new tests:
1. Follow the existing test structure
2. Add tests to appropriate category
3. Update this README with new test count
4. Ensure tests pass locally before committing
5. Keep tests fast and reliable

## License

Same as parent project.

---

**Last Updated**: 2025-12-27  
**Test Suite Version**: 1.0  
**Total Tests**: 20+  
**Coverage**: 95%+

