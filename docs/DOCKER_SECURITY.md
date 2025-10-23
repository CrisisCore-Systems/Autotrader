# Docker Security Best Practices

## Overview

This document outlines the security measures implemented in the AutoTrader Docker configuration and provides guidelines for secure container deployment.

## Implemented Security Features

### 1. Multi-Stage Build

**Purpose**: Separates build-time dependencies from runtime, reducing attack surface.

```dockerfile
# Stage 1: Builder - Contains build tools
FROM python:3.11-slim-bookworm AS builder
# ... build dependencies ...

# Stage 2: Runtime - Only production dependencies
FROM python:3.11-slim-bookworm AS runtime
# ... minimal runtime ...
```

**Benefits**:
- Smaller final image size
- No build tools in production image
- Reduced vulnerability surface

### 2. Non-Root User

**Purpose**: Run container processes as non-privileged user.

```dockerfile
# Create user with explicit UID
RUN useradd --create-home --shell /bin/bash --uid 1000 autotrader
USER autotrader
```

**Benefits**:
- Limits damage from container escape
- Prevents privilege escalation
- Follows principle of least privilege

### 3. Minimal Base Image

**Purpose**: Use slim base image to minimize attack surface.

```dockerfile
FROM python:3.11-slim-bookworm AS runtime
```

**Benefits**:
- Fewer packages = fewer vulnerabilities
- Smaller image size
- Faster deployment

### 4. Clean Package Management

**Purpose**: Remove package lists and caches after installation.

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean
```

**Benefits**:
- Smaller image size
- No stale package metadata
- Reduced attack surface

## Production Deployment

### Running Containers Securely

#### Basic Secure Run
```bash
docker run \
  --name autotrader \
  --read-only \
  --security-opt=no-new-privileges:true \
  --cap-drop=ALL \
  --user autotrader \
  -e GROQ_API_KEY="${GROQ_API_KEY}" \
  autotrader:latest
```

#### Advanced Security Options
```bash
docker run \
  --name autotrader \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=100m \
  --tmpfs /app/logs:rw,noexec,nosuid,size=500m \
  --security-opt=no-new-privileges:true \
  --security-opt=seccomp=/path/to/seccomp-profile.json \
  --cap-drop=ALL \
  --user autotrader \
  --pids-limit=100 \
  --memory=2g \
  --memory-swap=2g \
  --cpus=2 \
  -e GROQ_API_KEY="${GROQ_API_KEY}" \
  --health-cmd="python -c 'import sys; sys.exit(0)'" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  autotrader:latest
```

#### Docker Compose Security
```yaml
version: '3.8'

services:
  autotrader:
    image: autotrader:latest
    container_name: autotrader
    user: "1000:1000"
    read_only: true
    security_opt:
      - no-new-privileges:true
      - seccomp:unconfined  # Use custom profile in production
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only if needed
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=100m
      - /app/logs:rw,noexec,nosuid,size=500m
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - PYTHONUNBUFFERED=1
    volumes:
      - ./configs:/app/configs:ro
      - logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

volumes:
  logs:
    driver: local
```

### Security Options Explained

#### `--read-only`
- Makes root filesystem read-only
- Prevents malicious writes to container
- Use `--tmpfs` for directories that need writes

#### `--security-opt=no-new-privileges:true`
- Prevents privilege escalation
- Blocks setuid/setgid bits
- Required for defense in depth

#### `--cap-drop=ALL`
- Drops all Linux capabilities
- Minimal privilege for process
- Add back only what's needed with `--cap-add`

#### `--user autotrader`
- Runs as non-root user
- Matches UID in Dockerfile
- Prevents root exploits

#### `--pids-limit`
- Limits number of processes
- Prevents fork bombs
- Protects against DoS

#### `--memory` and `--cpus`
- Resource limits prevent resource exhaustion
- Protects host from container overuse
- Essential for multi-tenant environments

## Image Scanning

### Before Deployment

```bash
# Scan with Trivy
trivy image --severity HIGH,CRITICAL autotrader:latest

# Scan with Grype
grype autotrader:latest

# Scan Dockerfile
hadolint Dockerfile
```

### Continuous Scanning

Our CI/CD pipeline automatically scans:
- Base images for vulnerabilities
- Final images before deployment
- Dependencies in requirements.txt
- Dockerfile for best practices

## Secret Management

### Never Bake Secrets into Images

❌ **BAD**:
```dockerfile
ENV GROQ_API_KEY="sk-abc123..."
```

✅ **GOOD**:
```bash
docker run -e GROQ_API_KEY="${GROQ_API_KEY}" autotrader:latest
```

### Using Secret Management Tools

#### Docker Secrets (Swarm)
```bash
echo "your-api-key" | docker secret create groq_api_key -

docker service create \
  --name autotrader \
  --secret groq_api_key \
  autotrader:latest
```

#### Kubernetes Secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: autotrader-secrets
type: Opaque
data:
  groq-api-key: <base64-encoded-key>
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autotrader
spec:
  template:
    spec:
      containers:
      - name: autotrader
        image: autotrader:latest
        env:
        - name: GROQ_API_KEY
          valueFrom:
            secretKeyRef:
              name: autotrader-secrets
              key: groq-api-key
```

#### AWS ECS with Secrets Manager
```json
{
  "containerDefinitions": [{
    "name": "autotrader",
    "image": "autotrader:latest",
    "secrets": [{
      "name": "GROQ_API_KEY",
      "valueFrom": "arn:aws:secretsmanager:region:account:secret:autotrader/groq-key"
    }]
  }]
}
```

## Network Security

### Least Privilege Networking

```bash
# Create isolated network
docker network create --driver bridge autotrader-net

# Run container with network restrictions
docker run \
  --network autotrader-net \
  --network-alias autotrader \
  autotrader:latest
```

### Firewall Rules

```bash
# Allow only necessary ports
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
iptables -A INPUT -j DROP
```

## File Permissions

### Secure File Ownership

```dockerfile
# In Dockerfile
COPY --chown=autotrader:autotrader src/ ./src/

# Set secure permissions
RUN chmod 750 /app && \
    chmod 640 /app/configs/*.yaml
```

### Runtime Volume Permissions

```bash
# Ensure host volumes have correct permissions
chown -R 1000:1000 /host/path/to/configs
chmod -R 750 /host/path/to/configs
```

## Monitoring & Logging

### Container Logs

```bash
# View logs securely
docker logs autotrader 2>&1 | grep -v "api_key\|token\|secret"

# Configure log rotation
docker run \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  autotrader:latest
```

### Security Monitoring

```yaml
# Docker Compose with logging
services:
  autotrader:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        labels: "service=autotrader"
```

## Hardening Checklist

Before deploying to production:

- [ ] Image scanned with Trivy/Grype (no HIGH/CRITICAL)
- [ ] Dockerfile linted with Hadolint
- [ ] Base image pinned to specific version (not `:latest`)
- [ ] Running as non-root user
- [ ] `--read-only` filesystem enabled
- [ ] `--security-opt=no-new-privileges:true` set
- [ ] All capabilities dropped with `--cap-drop=ALL`
- [ ] Resource limits configured (CPU, memory, PIDs)
- [ ] Secrets passed via environment variables (not baked in)
- [ ] Health check configured
- [ ] Logging configured with rotation
- [ ] Network isolated to necessary connections only
- [ ] Volume permissions set correctly
- [ ] No sensitive data in logs

## Security Updates

### Updating Base Images

```bash
# Pull latest security patches
docker pull python:3.11-slim-bookworm

# Rebuild image
docker build --no-cache -t autotrader:latest .

# Verify no new vulnerabilities
trivy image autotrader:latest
```

### Automated Updates

Dependabot automatically creates PRs for:
- Python base image updates
- Python package updates
- GitHub Actions updates

## Incident Response

### Compromised Container

1. **Isolate**: Disconnect network immediately
   ```bash
   docker network disconnect autotrader-net autotrader
   ```

2. **Capture**: Save logs and filesystem
   ```bash
   docker logs autotrader > incident-logs.txt
   docker export autotrader > incident-filesystem.tar
   ```

3. **Terminate**: Stop and remove container
   ```bash
   docker stop autotrader
   docker rm autotrader
   ```

4. **Investigate**: Analyze logs and filesystem offline
5. **Remediate**: Rotate all secrets, patch vulnerabilities
6. **Redeploy**: Use fresh image with fixes

## Additional Resources

- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [OWASP Container Security](https://owasp.org/www-project-docker-top-10/)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)

---

**Last Updated**: 2025-10-22  
**Maintained By**: CrisisCore Systems Security Team
