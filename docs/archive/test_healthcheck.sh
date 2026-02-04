#!/bin/bash
# Test script for health check endpoint and environment variable extraction

set -e

echo "========================================================================"
echo "Health Check & Environment Variables - Test Suite"
echo "========================================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

passed=0
failed=0

# Helper functions
pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((passed++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((failed++))
}

test_section() {
    echo ""
    echo -e "${YELLOW}$1${NC}"
    echo "------------------------------------------------------------------------"
}

# Test 1: Config loading
test_section "Test 1: Configuration Loading"
python3 << 'PYTHON_TEST'
import sys
from config import Config

try:
    assert Config.DATABASE == "reproducibility.db", f"DATABASE should be 'reproducibility.db', got '{Config.DATABASE}'"
    print("DATABASE_PATH env var: OK")
    
    assert Config.DOCKER_NETWORK == "workspace_traefik", f"DOCKER_NETWORK should be 'workspace_traefik', got '{Config.DOCKER_NETWORK}'"
    print("DOCKER_NETWORK env var: OK")
    
    assert Config.DOCKER_BACKEND_URL == "http://paper-reproducibility:5000", f"DOCKER_BACKEND_URL incorrect"
    print("DOCKER_BACKEND_URL env var: OK")
    
    assert Config.SECRET_KEY is not None and len(Config.SECRET_KEY) > 0, "SECRET_KEY not set"
    print("SECRET_KEY env var: OK (auto-generated)")
    
    print("\nAll configuration tests passed!")
except AssertionError as e:
    print(f"Configuration test failed: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Error during config test: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_TEST

if [ $? -eq 0 ]; then
    pass "Configuration loading tests"
else
    fail "Configuration loading tests"
fi

# Test 2: Python syntax
test_section "Test 2: Python Syntax Validation"
for file in config.py services/docker_service.py blueprints/api.py; do
    python3 -m py_compile "$file" 2>/dev/null
    if [ $? -eq 0 ]; then
        pass "$file syntax valid"
    else
        fail "$file syntax invalid"
    fi
done

# Test 3: Docker-compose YAML
test_section "Test 3: Docker Compose Configuration"
python3 << 'YAML_TEST'
import yaml
import sys

try:
    with open('docker-compose.yml', 'r') as f:
        config = yaml.safe_load(f)
    
    app = config['services']['app']
    
    # Check healthcheck
    assert 'healthcheck' in app, "No healthcheck in docker-compose"
    hc = app['healthcheck']
    assert hc['test'] == ['CMD', 'curl', '-f', 'http://localhost:5000/api/health'], "Invalid healthcheck test"
    assert hc['interval'] == '30s', "Invalid interval"
    assert hc['timeout'] == '10s', "Invalid timeout"
    assert hc['retries'] == 3, "Invalid retries"
    assert hc['start_period'] == '10s', "Invalid start_period"
    print("Healthcheck configuration: OK")
    
    # Check environment variables
    env = app['environment']
    required_env = [
        'DATABASE_PATH', 'DOCKER_NETWORK', 'DOCKER_BACKEND_URL',
        'LLM_PROVIDER', 'ANTHROPIC_MODEL', 'AGENT_CONTEXT_LIMIT'
    ]
    
    env_str = ' '.join(env)
    for var in required_env:
        if f"- {var}=" in env_str:
            print(f"Environment variable {var}: OK")
        else:
            raise AssertionError(f"Missing environment variable: {var}")
    
    print("\nDocker Compose validation passed!")
    
except Exception as e:
    print(f"Docker Compose validation failed: {e}", file=sys.stderr)
    sys.exit(1)
YAML_TEST

if [ $? -eq 0 ]; then
    pass "Docker Compose validation"
else
    fail "Docker Compose validation"
fi

# Test 4: Health check endpoint code
test_section "Test 4: Health Check Endpoint Implementation"
python3 << 'ENDPOINT_TEST'
import ast
import sys

try:
    with open('blueprints/api.py', 'r') as f:
        tree = ast.parse(f.read())
    
    # Find the health_check function
    found_endpoint = False
    found_database_check = False
    found_llm_check = False
    found_docker_check = False
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name == 'health_check':
                found_endpoint = True
                # Check for database check
                source = open('blueprints/api.py').read()
                if 'c.execute("SELECT 1")' in source:
                    found_database_check = True
                if 'init_llm_provider()' in source:
                    found_llm_check = True
                if 'is_docker_available()' in source:
                    found_docker_check = True
    
    assert found_endpoint, "health_check endpoint function not found"
    print("Health check endpoint function: OK")
    
    assert found_database_check, "Database check not implemented"
    print("Database health check: OK")
    
    assert found_llm_check, "LLM provider check not implemented"
    print("LLM provider health check: OK")
    
    assert found_docker_check, "Docker availability check not implemented"
    print("Docker health check: OK")
    
    print("\nHealth check endpoint validation passed!")
    
except Exception as e:
    print(f"Health check validation failed: {e}", file=sys.stderr)
    sys.exit(1)
ENDPOINT_TEST

if [ $? -eq 0 ]; then
    pass "Health check endpoint implementation"
else
    fail "Health check endpoint implementation"
fi

# Test 5: .env file
test_section "Test 5: Environment File (.env)"
python3 << 'ENV_TEST'
import os
import sys

try:
    with open('.env', 'r') as f:
        env_content = f.read()
    
    required_vars = [
        'ANTHROPIC_API_KEY',
        'DATABASE_PATH',
        'DOCKER_NETWORK',
        'DOCKER_BACKEND_URL',
        'LLM_PROVIDER',
        'ANTHROPIC_MODEL'
    ]
    
    for var in required_vars:
        if f"{var}=" in env_content:
            print(f"Environment variable {var}: OK")
        else:
            raise AssertionError(f"Missing environment variable in .env: {var}")
    
    print("\n.env file validation passed!")
    
except Exception as e:
    print(f".env validation failed: {e}", file=sys.stderr)
    sys.exit(1)
ENV_TEST

if [ $? -eq 0 ]; then
    pass ".env file configuration"
else
    fail ".env file configuration"
fi

# Test 6: .env.example
test_section "Test 6: Environment Documentation (.env.example)"
python3 << 'ENV_EXAMPLE_TEST'
import sys

try:
    with open('.env.example', 'r') as f:
        example_content = f.read()
    
    # Check for comprehensive documentation
    checks = [
        ('DATABASE_PATH documented', 'DATABASE_PATH'),
        ('DOCKER_NETWORK documented', 'DOCKER_NETWORK'),
        ('DOCKER_BACKEND_URL documented', 'DOCKER_BACKEND_URL'),
        ('ANTHROPIC_API_KEY documented', 'ANTHROPIC_API_KEY'),
        ('LLM_PROVIDER documented', 'LLM_PROVIDER'),
        ('OLLAMA configuration documented', 'OLLAMA_BASE_URL'),
        ('Docker section', '# ============'),
        ('Notes/production guidance', 'For production'),
    ]
    
    for check_name, check_str in checks:
        if check_str in example_content:
            print(f"{check_name}: OK")
        else:
            raise AssertionError(f"{check_name} not found")
    
    print("\n.env.example documentation validation passed!")
    
except Exception as e:
    print(f".env.example validation failed: {e}", file=sys.stderr)
    sys.exit(1)
ENV_EXAMPLE_TEST

if [ $? -eq 0 ]; then
    pass ".env.example documentation"
else
    fail ".env.example documentation"
fi

# Summary
echo ""
echo "========================================================================"
echo "Test Results"
echo "========================================================================"
echo -e "${GREEN}Passed: $passed${NC}"
echo -e "${RED}Failed: $failed${NC}"
echo "========================================================================"

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed${NC}"
    exit 1
fi
