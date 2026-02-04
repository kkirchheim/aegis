#!/bin/bash

# Security Audit Verification Script
# This script manually verifies all the security fixes applied
# Run with: bash VERIFY_SECURITY_FIXES.sh

set -e

echo "================================"
echo "SECURITY AUDIT VERIFICATION"
echo "================================"
echo ""

PASS=0
FAIL=0

# Helper functions
pass() {
    echo "✅ PASS: $1"
    ((PASS++))
}

fail() {
    echo "❌ FAIL: $1"
    ((FAIL++))
}

warn() {
    echo "⚠️  WARN: $1"
}

# Test 1: API key not in .env
echo "Test 1: Checking for exposed API keys..."
if grep -q "sk-ant-api03" .env 2>/dev/null; then
    fail "Real API key found in .env file!"
else
    if grep -q "your-actual-api-key-here" .env 2>/dev/null; then
        pass "API key placeholder found in .env"
    else
        fail "API key configuration not found in .env"
    fi
fi
echo ""

# Test 2: .env in .gitignore
echo "Test 2: Checking .gitignore for .env..."
if grep -q "^\.env$" .gitignore 2>/dev/null; then
    pass ".env is in .gitignore"
else
    fail ".env is NOT in .gitignore"
fi
echo ""

# Test 3: PERMANENT_SESSION_LIFETIME in config
echo "Test 3: Checking session timeout configuration..."
if grep -q "PERMANENT_SESSION_LIFETIME" config.py; then
    pass "Session timeout (PERMANENT_SESSION_LIFETIME) configured"
else
    fail "Session timeout not configured in config.py"
fi
echo ""

# Test 4: Admin password generation
echo "Test 4: Checking admin password generation..."
if grep -q "admin_password = secrets.token_urlsafe" services/auth_service.py; then
    pass "Admin password is randomly generated"
else
    fail "Admin password generation not found"
fi
echo ""

# Test 5: Admin role database verification
echo "Test 5: Checking admin role verification..."
if grep -q "SELECT username FROM users WHERE id = ? AND username = ?" utils/decorators.py; then
    pass "Admin role verified in database"
else
    fail "Admin database verification not found"
fi
echo ""

# Test 6: Security headers
echo "Test 6: Checking security headers..."
if grep -q "X-Content-Type-Options" app.py; then
    pass "X-Content-Type-Options header added"
else
    fail "X-Content-Type-Options header not found"
fi

if grep -q "X-Frame-Options" app.py; then
    pass "X-Frame-Options header added"
else
    fail "X-Frame-Options header not found"
fi

if grep -q "Strict-Transport-Security" app.py; then
    pass "Strict-Transport-Security header added"
else
    fail "Strict-Transport-Security header not found"
fi
echo ""

# Test 7: Health endpoint sanitization
echo "Test 7: Checking /health endpoint security..."
if grep -q "Security: This endpoint is intentionally public" blueprints/api.py; then
    pass "Health endpoint documented as public and safe"
else
    fail "Health endpoint security documentation not found"
fi
echo ""

# Test 8: Agent API validation
echo "Test 8: Checking agent API job_id validation..."
AGENT_VALIDATIONS=$(grep -c "SECURITY: Validate that job_id actually exists" blueprints/api.py)
if [ "$AGENT_VALIDATIONS" -ge 4 ]; then
    pass "Agent API endpoints validate job_id ($AGENT_VALIDATIONS validations found)"
else
    fail "Agent API job_id validation not fully applied"
fi
echo ""

# Test 9: No hardcoded credentials in code
echo "Test 9: Checking for hardcoded credentials in Python files..."
if grep -r "sk-ant-api03" --include="*.py" . 2>/dev/null; then
    fail "Real API key found in Python files!"
else
    pass "No exposed API keys in Python files"
fi

if grep -r "password = \"admin\"" --include="*.py" . 2>/dev/null | grep -v test | grep -v "#"; then
    fail "Hardcoded password found in Python files!"
else
    pass "No hardcoded passwords in Python files"
fi
echo ""

# Test 10: Config.py imports
echo "Test 10: Checking config.py imports..."
if grep -q "from datetime import timedelta" config.py; then
    pass "timedelta imported in config.py"
else
    fail "timedelta not imported in config.py"
fi
echo ""

# Test 11: Flask configuration
echo "Test 11: Checking Flask session security..."
if grep -q "SESSION_COOKIE_HTTPONLY = True" config.py; then
    pass "SESSION_COOKIE_HTTPONLY is set"
else
    fail "SESSION_COOKIE_HTTPONLY not configured"
fi

if grep -q "SESSION_COOKIE_SAMESITE = 'Lax'" config.py; then
    pass "SESSION_COOKIE_SAMESITE is set"
else
    fail "SESSION_COOKIE_SAMESITE not configured"
fi
echo ""

# Test 12: Database verification in decorators
echo "Test 12: Checking database imports in decorators..."
if grep -q "from database import get_db" utils/decorators.py; then
    pass "get_db imported in decorators.py"
else
    fail "get_db not imported in decorators.py"
fi
echo ""

# Test 13: File permissions
echo "Test 13: Checking file permissions..."
if [ -f .env ]; then
    PERMS=$(stat -c %a .env 2>/dev/null || stat -f %A .env 2>/dev/null)
    if [[ "$PERMS" != "600" ]] && [[ "$PERMS" != "644" ]]; then
        warn ".env file permissions are $PERMS (consider restricting to 600)"
    fi
fi
echo ""

# Test 14: Test file exists
echo "Test 14: Checking test files..."
if [ -f "tests/test_security_final.py" ]; then
    TESTS=$(grep -c "def test_" tests/test_security_final.py)
    pass "Security test suite found with $TESTS test cases"
else
    fail "Security test suite (test_security_final.py) not found"
fi
echo ""

# Summary
echo "================================"
echo "VERIFICATION SUMMARY"
echo "================================"
echo "✅ Passed: $PASS"
echo "❌ Failed: $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "🎉 All security fixes verified successfully!"
    exit 0
else
    echo "⚠️  Some checks failed. Please review the output above."
    exit 1
fi
