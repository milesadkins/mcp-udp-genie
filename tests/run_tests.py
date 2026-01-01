#!/usr/bin/env python3
"""
Cross-platform test runner for MCP tools.
Works on Windows, macOS, and Linux.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def check_pytest():
    """Check if pytest is installed."""
    try:
        subprocess.run(
            ["pytest", "--version"],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_dependencies():
    """Install required test dependencies."""
    print("❌ pytest not found. Installing dependencies...")
    subprocess.run(
        ["uv", "pip", "install", "pytest", "requests", "databricks-mcp", "databricks-sdk"],
        check=True
    )
    print("✅ Dependencies installed")


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(
        description="MCP Tools Test Suite Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                    # Run all tests
  python run_tests.py -v                 # Run with verbose output
  python run_tests.py -k query           # Run tests matching 'query'
  python run_tests.py -vv -s             # Very verbose with prints
  python run_tests.py --coverage         # Generate coverage report
        """
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=1,
        help="Increase verbosity (can be used multiple times: -v, -vv)"
    )
    
    parser.add_argument(
        "-s", "--show-output",
        action="store_true",
        help="Show print statements (disable output capture)"
    )
    
    parser.add_argument(
        "-k",
        metavar="PATTERN",
        help="Run tests matching pattern"
    )
    
    parser.add_argument(
        "-x", "--stop-first",
        action="store_true",
        help="Stop on first failure"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip test summary"
    )
    
    args = parser.parse_args()
    
    # Print header
    print("🧪 MCP Tools Test Suite")
    print("=======================")
    print()
    
    # Check if pytest is installed
    if not check_pytest():
        try:
            install_dependencies()
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies")
            print("   Try manually: uv pip install pytest requests databricks-mcp databricks-sdk")
            return 1
    
    # Build pytest command
    cmd = ["pytest", "tests/test_mcp_tools.py"]
    
    # Add verbosity flags
    if args.verbose == 1:
        cmd.append("-v")
    elif args.verbose >= 2:
        cmd.append("-vv")
    
    if args.show_output:
        cmd.append("-s")
    
    if args.k:
        cmd.extend(["-k", args.k])
    
    if args.stop_first:
        cmd.append("-x")
    
    if args.coverage:
        cmd.extend([
            "--cov=server",
            "--cov-report=html",
            "--cov-report=term"
        ])
    
    if not args.no_summary:
        cmd.append("--tb=short")
    
    # Print command
    print(f"Running: {' '.join(cmd)}")
    print()
    
    # Run tests
    try:
        result = subprocess.run(cmd)
        
        # Show coverage report info if generated
        if args.coverage:
            print()
            print("📊 Coverage report generated: htmlcov/index.html")
            coverage_path = Path("htmlcov/index.html")
            if coverage_path.exists():
                print(f"   Open with: open {coverage_path}")
        
        print()
        if result.returncode == 0:
            print("✅ Test run complete!")
        else:
            print("❌ Some tests failed")
        
        return result.returncode
        
    except KeyboardInterrupt:
        print()
        print("⚠️  Test run interrupted")
        return 130
    except Exception as e:
        print()
        print(f"❌ Error running tests: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

