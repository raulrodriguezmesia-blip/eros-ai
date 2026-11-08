# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ |

## Reporting a Vulnerability

If you discover a security vulnerability in Eros AI, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email the maintainer directly with details
3. Include steps to reproduce and potential impact
4. Allow 48 hours for initial response

## Security Features

Eros AI includes built-in security analysis:
- SQL injection detection
- Hardcoded secret detection
- Command injection detection
- OWASP Top 10 compliance checking
- Circuit breaker for external service failures
- Non-root Docker container
- No secrets in codebase (environment variables only)
