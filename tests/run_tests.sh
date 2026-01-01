#!/usr/bin/env bash
# Quick test runner script for MCP tools

set -e

echo "🧪 MCP Tools Test Suite"
echo "======================="
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing..."
    uv pip install pytest requests databricks-mcp databricks-sdk
fi

# Parse command line arguments
VERBOSE=""
PATTERN=""
STOP_ON_FIRST=""
COVERAGE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -vv|--very-verbose)
            VERBOSE="-vv"
            shift
            ;;
        -s|--show-output)
            VERBOSE="$VERBOSE -s"
            shift
            ;;
        -k)
            PATTERN="-k $2"
            shift 2
            ;;
        -x|--stop-first)
            STOP_ON_FIRST="-x"
            shift
            ;;
        --coverage)
            COVERAGE="--cov=server --cov-report=html --cov-report=term"
            shift
            ;;
        -h|--help)
            echo "Usage: ./run_tests.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -v, --verbose         Show verbose output"
            echo "  -vv, --very-verbose   Show very verbose output"
            echo "  -s, --show-output     Show print statements"
            echo "  -k PATTERN            Run tests matching pattern"
            echo "  -x, --stop-first      Stop on first failure"
            echo "  --coverage            Generate coverage report"
            echo "  -h, --help            Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./run_tests.sh                    # Run all tests"
            echo "  ./run_tests.sh -v                 # Run with verbose output"
            echo "  ./run_tests.sh -k query           # Run tests matching 'query'"
            echo "  ./run_tests.sh -vv -s             # Very verbose with prints"
            echo "  ./run_tests.sh --coverage         # Generate coverage report"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Set default verbose if none specified
if [ -z "$VERBOSE" ]; then
    VERBOSE="-v"
fi

# Run tests
echo "Running tests with: pytest tests/test_mcp_tools.py $VERBOSE $PATTERN $STOP_ON_FIRST $COVERAGE"
echo ""

pytest tests/test_mcp_tools.py $VERBOSE $PATTERN $STOP_ON_FIRST $COVERAGE

# Show coverage report if generated
if [ -n "$COVERAGE" ]; then
    echo ""
    echo "📊 Coverage report generated: htmlcov/index.html"
    echo "   Open with: open htmlcov/index.html"
fi

echo ""
echo "✅ Test run complete!"

