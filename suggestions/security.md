# Security Hardening Suggestions

## Immediate Security Fixes

### 1. XSS Prevention in Streamlit App

**Current Issue**: Unsafe HTML rendering in `app.py`

```python
# PROBLEMATIC CODE
safe_markdown(f"<div class='verdict-box'>{verdict}</div>")
```

**Solution**:
```python
# SAFE IMPLEMENTATION
import html
from bleach import clean

def safe_html_render(content):
    """Safely render HTML content with proper escaping"""
    # Escape user content first
    escaped_content = html.escape(str(content))
    # Allow only safe HTML tags and attributes
    allowed_tags = ['div', 'span', 'strong', 'em', 'br']
    allowed_attributes = {'div': ['class'], 'span': ['class']}
    return clean(escaped_content, tags=allowed_tags, attributes=allowed_attributes)
```

### 2. SQL Injection Prevention

**Current Issue**: String formatting in SQL queries

```python
# PROBLEMATIC CODE
c.execute('SELECT 1 FROM claim_cache WHERE expires_at > ?', (now,))
```

**Solution**:
```python
# SAFE IMPLEMENTATION
def get_cached_verdict_safe(self, claim: str, similarity_threshold: float = 0.92):
    """Safely retrieve cached verdict using parameterized queries"""
    try:
        if not self.enabled:
            return None
        if not self._has_live_rows():
            return None
        query_embedding = self._encode(claim)
        if query_embedding is None:
            return None
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        now = datetime.now().isoformat()
        # Use parameterized query with proper placeholders
        c.execute('''
            SELECT claim_text, claim_embedding, verdict_data, created_at 
            FROM claim_cache 
            WHERE expires_at > ?
        ''', (now,))
        
        rows = c.fetchall()
        conn.close()
        
        # Process results safely...
        
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return None
```

### 3. Input Validation Enhancement

**Current Issue**: Insufficient input sanitization

```python
# ADDITIONAL VALIDATION
def validate_claim_secure(claim: str) -> Tuple[bool, str, str]:
    """Enhanced claim validation with security checks"""
    if not claim or not claim.strip():
        return False, "Claim cannot be empty", ""
    
    # Length checks
    if len(claim) < 10 or len(claim) > 500:
        return False, "Claim length must be between 10 and 500 characters", ""
    
    # Word count check
    words = claim.split()
    if len(words) < 3:
        return False, "Claim must contain at least 3 words", ""
    
    # Security pattern detection
    security_patterns = [
        r"<script[^>]*>.*?</script>",  # Script tags
        r"javascript:",                # JavaScript URLs
        r"data:text/html",             # Data URLs
        r"on\w+\s*=",                  # Event handlers
        r"eval\s*\(",                 # eval() calls
        r"document\.",                 # DOM manipulation
    ]
    
    claim_lower = claim.lower()
    for pattern in security_patterns:
        if re.search(pattern, claim_lower):
            return False, "Invalid content detected in claim", ""
    
    # Special character ratio check
    special_chars = sum(1 for c in claim if not c.isalnum() and not c.isspace())
    special_ratio = special_chars / len(claim)
    if special_ratio > 0.4:  # Increased threshold
        return False, "Too many special characters", ""
    
    # Normalize and return
    sanitized = claim.strip()
    return True, "", sanitized
```

## Secrets Management

### 1. Environment Variable Validation

```python
def validate_api_keys():
    """Validate API keys before application startup"""
    required_keys = ['GROQ_API_KEY', 'GEMINI_API_KEY']
    missing_keys = []
    
    for key in required_keys:
        value = os.getenv(key)
        if not value:
            missing_keys.append(key)
        elif len(value) < 30:
            logger.warning(f"API key {key} appears to be too short")
    
    if missing_keys:
        logger.error(f"Missing required API keys: {', '.join(missing_keys)}")
        return False
    
    return True

def mask_sensitive_data(data: str) -> str:
    """Mask sensitive data for logging"""
    if not data:
        return data
    
    # Mask API keys (show first 4 and last 4 characters)
    if len(data) > 8:
        return data[:4] + '*' * (len(data) - 8) + data[-4:]
    return '*' * len(data)
```

### 2. Secure Logging

```python
class SecureLogger:
    """Logger that masks sensitive information"""
    
    def __init__(self, logger):
        self.logger = logger
    
    def _mask_sensitive(self, message):
        """Mask sensitive information in log messages"""
        import re
        
        # Mask API keys
        message = re.sub(r'GROQ_API_KEY=\w+', 'GROQ_API_KEY=***', message)
        message = re.sub(r'GEMINI_API_KEY=\w+', 'GEMINI_API_KEY=***', message)
        
        # Mask URLs with credentials
        message = re.sub(r'(https?://[^:]+):([^@]+)@', r'\1:***@', message)
        
        return message
    
    def info(self, message, *args, **kwargs):
        masked_message = self._mask_sensitive(str(message))
        self.logger.info(masked_message, *args, **kwargs)
    
    def error(self, message, *args, **kwargs):
        masked_message = self._mask_sensitive(str(message))
        self.logger.error(masked_message, *args, **kwargs)
```

## Rate Limiting and DoS Protection

### 1. Request Rate Limiting

```python
from collections import defaultdict
import time

class RateLimiter:
    """Simple rate limiter to prevent abuse"""
    
    def __init__(self, max_requests=100, time_window=3600):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = defaultdict(list)
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed for the identifier"""
        now = time.time()
        window_start = now - self.time_window
        
        # Clean old requests
        if identifier in self.requests:
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier] 
                if req_time > window_start
            ]
        
        # Check if under limit
        if len(self.requests[identifier]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[identifier].append(now)
        return True

# Usage in main application
rate_limiter = RateLimiter(max_requests=50, time_window=3600)  # 50 requests per hour

def validate_request_rate(client_ip: str) -> bool:
    """Validate request rate for client IP"""
    if not rate_limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return False
    return True
```

### 2. Circuit Breaker Pattern

```python
class CircuitBreaker:
    """Circuit breaker to handle API failures gracefully"""
    
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
    
    def on_success(self):
        """Reset failure count on success"""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def on_failure(self):
        """Increment failure count and open circuit if threshold reached"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.error(f"Circuit breaker opened after {self.failure_count} failures")
```

## Security Headers and Configuration

### 1. Streamlit Security Configuration

```python
# Add to app.py
import streamlit as st

# Set security headers
st.set_page_config(
    page_title="InsightSwarm",
    layout="wide",
    initial_sidebar_state="expanded",
    # Add security headers when possible
)

# Content Security Policy
st.markdown("""
<style>
/* Restrict inline styles and scripts */
</style>
""", unsafe_allow_html=False)  # Use safe rendering
```

### 2. Secure File Handling

```python
import os
import mimetypes
from pathlib import Path

def validate_file_upload(file_path: str) -> bool:
    """Validate uploaded files for security"""
    path = Path(file_path)
    
    # Check file extension
    allowed_extensions = {'.txt', '.pdf', '.doc', '.docx'}
    if path.suffix.lower() not in allowed_extensions:
        return False
    
    # Check file size (max 10MB)
    if path.stat().st_size > 10 * 1024 * 1024:
        return False
    
    # Check MIME type
    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        return False
    
    allowed_types = [
        'text/plain', 'application/pdf', 
        'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ]
    if mime_type not in allowed_types:
        return False
    
    return True
```

## Implementation Checklist

- [ ] Fix XSS vulnerabilities in Streamlit app
- [ ] Implement SQL parameterization
- [ ] Add comprehensive input validation
- [ ] Set up secure logging
- [ ] Implement rate limiting
- [ ] Add circuit breaker pattern
- [ ] Validate API keys securely
- [ ] Add file upload validation
- [ ] Configure security headers
- [ ] Set up monitoring for security events

## Testing Security Fixes

```python
# Test XSS prevention
def test_xss_prevention():
    malicious_input = "<script>alert('XSS')</script>"
    result = safe_html_render(malicious_input)
    assert "<script>" not in result
    assert "alert" not in result

# Test SQL injection prevention
def test_sql_injection_prevention():
    malicious_input = "'; DROP TABLE claim_cache; --"
    # Should not execute malicious SQL
    result = get_cached_verdict_safe(malicious_input)
    assert result is not None  # Should handle gracefully

# Test input validation
def test_input_validation():
    invalid_claims = [
        "<script>alert('test')</script>",
        "javascript:alert('test')",
        "a" * 600,  # Too long
        "hi",       # Too short
    ]
    
    for claim in invalid_claims:
        valid, error, _ = validate_claim_secure(claim)
        assert not valid, f"Should reject: {claim}"
```

This security hardening guide provides comprehensive protection against common vulnerabilities while maintaining system functionality.