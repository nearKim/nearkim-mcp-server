#!/bin/bash
# Comprehensive test runner script

set -e

echo "Installing test dependencies..."
pip install -r requirements-test.txt

echo "Running type checks..."
mypy src --ignore-missing-imports --strict-optional

echo "Running unit tests..."
pytest tests/unit -m unit --cov=src --cov-report=term

echo "Running integration tests..."
pytest tests/integration -m integration

echo "Running all tests with coverage..."
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

echo "Coverage report generated at htmlcov/index.html"

# Optional: Run specific test categories
if [ "$1" == "quick" ]; then
    echo "Running quick tests only..."
    pytest tests/unit -m "not slow"
elif [ "$1" == "domain" ]; then
    echo "Running domain tests only..."
    pytest tests/unit/domain/
elif [ "$1" == "application" ]; then
    echo "Running application tests only..."
    pytest tests/unit/application/
elif [ "$1" == "integration" ]; then
    echo "Running integration tests only..."
    pytest tests/integration/
fi

echo "All tests completed!"