# Security Policy

## Supported Versions

We take security seriously and provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please follow these steps:

1. **DO NOT** open a public issue
2. Email security@crisiscore.systems with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

We will respond within 48 hours and provide updates every 5 business days.

## Security Measures

### Secrets Management

#### API Keys and Tokens
- **Storage**: All API keys MUST be stored in environment variables, never in code
- **Rotation**: Rotate API keys every 90 days or immediately upon suspected compromise
- **Scope**: Use minimal necessary scopes for all API tokens
- **Environment Files**: 
  - Use `.env` files for local development (excluded from git)
  - Use secure secret management systems in production (AWS Secrets Manager, HashiCorp Vault, etc.)
  - Reference `.env.template` for required environment variables

#### Best Practices
```bash
# ✅ GOOD - Using environment variables
export GROQ_API_KEY="your-key-here"
python run_scanner.py

# ❌ BAD - Hardcoded in code
GROQ_API_KEY = "sk-abc123..."  # Never do this!
```

#### Secret Detection
- Pre-commit hooks run `detect-secrets` to catch hardcoded secrets
- CI/CD runs TruffleHog and Gitleaks on every commit
- Baseline file: `.secrets.baseline` (update with `detect-secrets scan --baseline .secrets.baseline`)

### Dependency Management

#### Automated Scanning
- **Dependabot**: Automated PR creation for dependency updates (weekly)
- **pip-audit**: Python vulnerability scanning in CI
- **Trivy**: Container and filesystem vulnerability scanning
- **Grype**: SBOM-based vulnerability detection

#### Manual Review Process
1. Review Dependabot PRs within 48 hours
2. Check CHANGELOG and release notes for breaking changes
3. Run full test suite before merging
4. Update pinned versions in `requirements.txt`

#### Vulnerability Response
- **Critical**: Patch within 24 hours
- **High**: Patch within 7 days
- **Medium**: Patch within 30 days
- **Low**: Address in next scheduled update

### Docker Security

#### Image Hardening
Our Dockerfile implements multiple security layers:

1. **Multi-stage Build**: Separates build dependencies from runtime
2. **Non-root User**: Runs as `autotrader` (UID 1000), not root
3. **Minimal Base**: Uses `python:3.11-slim-bookworm` for smaller attack surface
4. **No Unnecessary Packages**: Only runtime dependencies in final image
5. **Read-only Root Filesystem**: Where possible, mount root filesystem as read-only

#### Container Best Practices
```bash
# Build with security scanning
docker build --tag autotrader:latest .

# Run with security options
docker run \
  --read-only \
  --security-opt=no-new-privileges:true \
  --cap-drop=ALL \
  --user autotrader \
  autotrader:latest
```

#### Image Scanning
- **Trivy**: Scans for vulnerabilities in dependencies and OS packages
- **Hadolint**: Dockerfile linter for best practices
- **Base Image**: Updated weekly via Dependabot

### Code Security

#### Static Analysis
- **Semgrep**: Custom rules for crypto trading and LLM security
- **Bandit**: Python security linter
- **mypy**: Type checking to prevent runtime errors
- **Ruff**: Fast Python linter with security rules

#### Security Rules Focus Areas
1. **Injection Prevention**: SQL, command, and code injection
2. **Cryptography**: Weak algorithms, hardcoded keys
3. **Secrets Detection**: API keys, passwords, tokens
4. **Deserialization**: Unsafe pickle, YAML, JSON operations
5. **Supply Chain**: Package verification, download integrity
6. **LLM Security**: Output validation, prompt injection

### Authentication & Authorization

#### API Security
- Rate limiting via `slowapi` (configured per endpoint)
- API key authentication for sensitive endpoints
- CORS configuration restricts allowed origins
- Request timeout enforcement (all external calls)

#### Session Management
- Secure session cookies (httponly, secure flags)
- Strong session secret (32+ bytes random)
- Session expiration and rotation

### Network Security

#### TLS/SSL
- All external API calls use HTTPS
- SSL certificate verification enabled (never use `verify=False`)
- Minimum TLS 1.2 for production

#### Timeouts
- All HTTP requests have explicit timeouts (default 30s)
- Database queries have connection timeouts
- Prevents resource exhaustion attacks

### Supply Chain Security

#### Dependency Verification
1. **Lock Files**: Pin exact versions in `requirements.txt`
2. **Checksums**: Verify package integrity during install
3. **Source Control**: Only install from trusted PyPI or vetted mirrors
4. **License Compliance**: Automated scanning for prohibited licenses

#### SBOM (Software Bill of Materials)
- Generated automatically in CI via Anchore
- Stored as artifact for compliance and auditing
- Scanned for vulnerabilities with Grype

### Monitoring & Incident Response

#### Security Monitoring
- Structured logging with `structlog` (no sensitive data)
- Prometheus metrics for anomaly detection
- OpenTelemetry for distributed tracing

#### Incident Response
1. **Detection**: Automated alerts from security scanners
2. **Containment**: Disable compromised credentials immediately
3. **Investigation**: Review logs and audit trails
4. **Remediation**: Apply patches, rotate secrets
5. **Post-mortem**: Document lessons learned

### Secret Rotation Process

#### Quarterly Rotation (Every 90 Days)
```bash
# 1. Generate new API key from provider
# 2. Update environment variables
export GROQ_API_KEY="new-key"

# 3. Test with new key
python -c "from src.llm_client import test_connection; test_connection()"

# 4. Update production secrets (example for AWS)
aws secretsmanager update-secret \
  --secret-id autotrader/groq-api-key \
  --secret-string "new-key"

# 5. Revoke old key from provider dashboard
# 6. Document rotation in security log
```

#### Emergency Rotation (Suspected Compromise)
- Rotate within 1 hour of detection
- Review access logs for unauthorized usage
- Change all related credentials
- Notify security team

### Development Security

#### Pre-commit Hooks
Required hooks (configured in `.pre-commit-config.yaml`):
- `detect-private-key`: Catch SSH/PEM keys
- `detect-secrets`: Scan for API keys, tokens
- `bandit`: Python security issues
- `hadolint`: Dockerfile security

#### Code Review Checklist
- [ ] No hardcoded secrets
- [ ] Environment variables used for configuration
- [ ] Input validation on all user inputs
- [ ] Parameterized queries for database
- [ ] Explicit timeouts on network calls
- [ ] Error messages don't leak sensitive info
- [ ] Dependencies are up-to-date
- [ ] Security scanner findings addressed

### Compliance & Auditing

#### Audit Trail
- All CI/CD security scans stored as artifacts (90 days)
- License compliance reports generated weekly
- SBOM generated on every release
- Security scan results in GitHub Security tab

#### Compliance Standards
- OWASP Top 10 coverage via Semgrep
- CWE mappings in security rules
- SARIF output for GitHub Advanced Security
- Regular security posture reviews

## Security Contacts

- **Security Issues**: security@crisiscore.systems
- **Security Team**: @CrisisCore-Systems/security-team

## Acknowledgments

We appreciate responsible disclosure and will acknowledge security researchers who help improve our security posture.

---

**Last Updated**: 2025-10-22  
**Next Review**: 2026-01-22
