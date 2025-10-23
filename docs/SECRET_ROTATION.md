# Secret Rotation Guide

## Overview

This guide provides step-by-step instructions for rotating secrets and API keys used in the AutoTrader application. Regular rotation reduces the risk of credential compromise.

## Rotation Schedule

| Secret Type | Rotation Frequency | Priority |
|-------------|-------------------|----------|
| API Keys (GROQ, OpenAI) | 90 days | High |
| Database Passwords | 90 days | Critical |
| JWT Secrets | 180 days | High |
| Service Account Keys | 90 days | High |
| SSH Keys | 365 days | Medium |
| TLS Certificates | Before expiry | Critical |

## Pre-Rotation Checklist

Before rotating any secret:

- [ ] Identify all services using the secret
- [ ] Schedule maintenance window if needed
- [ ] Prepare rollback plan
- [ ] Test new secret in non-production first
- [ ] Document the rotation in change log

## API Key Rotation

### GROQ API Key

#### Step 1: Generate New Key
```bash
# Login to GROQ dashboard
# Navigate to API Keys section
# Click "Create New Key"
# Copy the new key immediately (shown only once)
```

#### Step 2: Test New Key
```bash
# Export new key temporarily
export GROQ_API_KEY="new-key-here"

# Test connectivity
python -c "
from groq import Groq
client = Groq(api_key='${GROQ_API_KEY}')
response = client.chat.completions.create(
    model='llama3-8b-8192',
    messages=[{'role': 'user', 'content': 'test'}],
    max_tokens=10
)
print('✅ New key works!')
"
```

#### Step 3: Update Production Secret

##### Local Development
```bash
# Update .env file
echo "GROQ_API_KEY=new-key-here" > .env
```

##### AWS Secrets Manager
```bash
aws secretsmanager update-secret \
  --secret-id autotrader/groq-api-key \
  --secret-string "new-key-here" \
  --region us-east-1
```

##### Kubernetes Secret
```bash
kubectl create secret generic autotrader-secrets \
  --from-literal=groq-api-key="new-key-here" \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart pods to pick up new secret
kubectl rollout restart deployment/autotrader
```

##### Docker Compose
```bash
# Update environment file
echo "GROQ_API_KEY=new-key-here" > .env.production

# Recreate containers
docker-compose down
docker-compose up -d
```

##### Environment Variable (Direct)
```bash
# Update systemd service
sudo systemctl edit autotrader
# Add: Environment="GROQ_API_KEY=new-key-here"

sudo systemctl daemon-reload
sudo systemctl restart autotrader
```

#### Step 4: Verify New Key in Production
```bash
# Check logs for successful API calls
docker logs autotrader --tail 100 | grep -i groq

# Monitor for errors
watch 'docker logs autotrader --tail 20 | grep -i error'
```

#### Step 5: Revoke Old Key
```bash
# Login to GROQ dashboard
# Navigate to API Keys section
# Find old key by creation date
# Click "Revoke" or "Delete"
# Confirm revocation
```

#### Step 6: Document Rotation
```bash
# Add entry to rotation log
echo "$(date -I),GROQ_API_KEY,Rotated,$(whoami)" >> /secure/rotation_log.csv
```

### Other API Keys

Follow the same pattern for other services:
- **OpenAI**: Similar to GROQ process
- **Exchange APIs**: Check specific exchange documentation
- **Database**: See Database Credentials section below

## Database Credentials

### PostgreSQL/MySQL Password Rotation

#### Step 1: Create New Password
```bash
# Generate secure password
NEW_PASSWORD=$(openssl rand -base64 32)
echo "Generated: $NEW_PASSWORD"
```

#### Step 2: Add New Password (Keep Old Active)
```sql
-- Connect as admin
psql -U admin -d autotrader

-- Create new password for user
ALTER USER autotrader_app WITH PASSWORD 'new-secure-password';
```

#### Step 3: Update Application Configuration
```bash
# Update connection string
export DATABASE_URL="postgresql://autotrader_app:new-secure-password@localhost:5432/autotrader"

# Test connection
python -c "
from sqlalchemy import create_engine
engine = create_engine('${DATABASE_URL}')
with engine.connect() as conn:
    result = conn.execute('SELECT 1')
    print('✅ Database connection works!')
"
```

#### Step 4: Deploy Application with New Password
```bash
# Update secret in your deployment platform
# Restart application
# Monitor for connection errors
```

#### Step 5: Verify and Monitor
```bash
# Check application logs
tail -f /var/log/autotrader/app.log | grep -i database

# Monitor active connections
psql -U admin -d autotrader -c "
SELECT usename, COUNT(*) 
FROM pg_stat_activity 
WHERE usename = 'autotrader_app' 
GROUP BY usename;
"
```

## JWT Secret Rotation

### Application JWT Secret

#### Step 1: Generate New Secret
```bash
# Generate 256-bit secret
NEW_JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
echo "New JWT Secret: $NEW_JWT_SECRET"
```

#### Step 2: Implement Dual-Key Support (Optional)
```python
# In your application code
JWT_SECRETS = [
    os.getenv('JWT_SECRET_NEW'),  # Try new key first
    os.getenv('JWT_SECRET_OLD'),  # Fallback to old key
]

def decode_token(token):
    for secret in JWT_SECRETS:
        try:
            return jwt.decode(token, secret, algorithms=['HS256'])
        except jwt.InvalidSignatureError:
            continue
    raise jwt.InvalidTokenError("Token validation failed")
```

#### Step 3: Update Configuration
```bash
# Add new secret while keeping old
export JWT_SECRET_NEW="new-secret"
export JWT_SECRET_OLD="old-secret"

# Deploy application
```

#### Step 4: Transition Period (1-7 days)
```bash
# Monitor token validation
# New tokens use new secret
# Old tokens still validate with old secret
# Wait for old tokens to expire
```

#### Step 5: Remove Old Secret
```bash
# After transition period
export JWT_SECRET="new-secret"
unset JWT_SECRET_OLD

# Update application to use single secret
# Deploy updated application
```

## SSH Key Rotation

### Service Account SSH Keys

#### Step 1: Generate New Key Pair
```bash
# Generate new ED25519 key (recommended)
ssh-keygen -t ed25519 -f ~/.ssh/autotrader_new -C "autotrader@$(date +%Y%m%d)"

# Or RSA with 4096 bits
ssh-keygen -t rsa -b 4096 -f ~/.ssh/autotrader_new -C "autotrader@$(date +%Y%m%d)"
```

#### Step 2: Add New Key to Authorized Hosts
```bash
# Add to target server
ssh-copy-id -i ~/.ssh/autotrader_new.pub user@remote-server

# Or manually
cat ~/.ssh/autotrader_new.pub | ssh user@remote-server \
  'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys'
```

#### Step 3: Test New Key
```bash
ssh -i ~/.ssh/autotrader_new user@remote-server 'echo "✅ New key works!"'
```

#### Step 4: Update Application Configuration
```bash
# Update SSH config or key path in application
# Deploy updated configuration
```

#### Step 5: Remove Old Key
```bash
# Remove from authorized_keys on remote server
ssh user@remote-server \
  'sed -i "/old-key-identifier/d" ~/.ssh/authorized_keys'

# Remove local old key
rm ~/.ssh/autotrader_old ~/.ssh/autotrader_old.pub
```

## TLS Certificate Rotation

### Let's Encrypt Certificates

#### Automated Renewal (Recommended)
```bash
# Certbot automatic renewal
sudo certbot renew --dry-run

# Enable automatic renewal
sudo systemctl enable certbot-renew.timer
sudo systemctl start certbot-renew.timer
```

#### Manual Renewal
```bash
# Stop services using certificate
sudo systemctl stop nginx

# Renew certificate
sudo certbot renew --force-renewal

# Restart services
sudo systemctl start nginx
```

## Emergency Rotation (Compromised Secret)

### Immediate Actions (Within 1 Hour)

#### Step 1: Assess Impact
```bash
# Identify compromised secret
COMPROMISED_SECRET="GROQ_API_KEY"

# Check recent usage in logs
grep -r "$COMPROMISED_SECRET" /var/log/autotrader/ | \
  grep -v "$(date +%Y-%m-%d)"
```

#### Step 2: Revoke Compromised Secret
```bash
# Immediately revoke at provider
# (Follow provider-specific steps)
# Block old secret at firewall/proxy if possible
```

#### Step 3: Generate and Deploy New Secret
```bash
# Generate new secret
# Deploy immediately to all environments
# Use emergency change process

# Example for API key
NEW_KEY="emergency-new-key"
aws secretsmanager update-secret \
  --secret-id autotrader/compromised-key \
  --secret-string "$NEW_KEY"

# Force immediate pod restart
kubectl delete pod -l app=autotrader
```

#### Step 4: Monitor for Unauthorized Access
```bash
# Check API provider logs
# Monitor application logs for errors
# Review access patterns for anomalies

# Alert security team
echo "SECURITY ALERT: Secret rotation completed after compromise" | \
  mail -s "Security Alert" security@crisiscore.systems
```

#### Step 5: Incident Response
```bash
# Document incident
cat > /secure/incidents/$(date +%Y%m%d_%H%M%S)_secret_compromise.txt << EOF
Incident: Secret Compromise
Time: $(date)
Secret: $COMPROMISED_SECRET
Actions Taken:
- Secret revoked at $(date)
- New secret deployed at $(date)
- Monitoring enabled
- Security team notified
EOF

# Review and improve security
# Update rotation schedule if needed
# Implement additional monitoring
```

## Automation Scripts

### Automated Rotation Script

```bash
#!/bin/bash
# rotate_groq_key.sh - Automated GROQ key rotation

set -euo pipefail

# Configuration
SECRET_NAME="autotrader/groq-api-key"
AWS_REGION="us-east-1"
LOG_FILE="/var/log/autotrader/rotation.log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Step 1: Generate new key (manual step - get from GROQ dashboard)
read -sp "Enter new GROQ API key: " NEW_KEY
echo

# Step 2: Test new key
log "Testing new key..."
if python -c "
from groq import Groq
client = Groq(api_key='$NEW_KEY')
response = client.chat.completions.create(
    model='llama3-8b-8192',
    messages=[{'role': 'user', 'content': 'test'}],
    max_tokens=10
)
print('Key validated')
" 2>&1 | grep -q "Key validated"; then
    log "✅ New key validated successfully"
else
    log "❌ New key validation failed"
    exit 1
fi

# Step 3: Update secret
log "Updating secret in AWS Secrets Manager..."
aws secretsmanager update-secret \
    --secret-id "$SECRET_NAME" \
    --secret-string "$NEW_KEY" \
    --region "$AWS_REGION"

# Step 4: Trigger deployment
log "Triggering application restart..."
kubectl rollout restart deployment/autotrader

# Step 5: Wait and verify
log "Waiting 30 seconds for deployment..."
sleep 30

kubectl rollout status deployment/autotrader

# Step 6: Check logs
log "Checking application logs..."
kubectl logs -l app=autotrader --tail=20 | grep -i "groq\|error" || true

log "✅ Rotation completed successfully"
log "⚠️  Remember to revoke old key in GROQ dashboard!"

# Step 7: Record rotation
echo "$(date -I),GROQ_API_KEY,Rotated,$(whoami)" >> /secure/rotation_log.csv
```

### Rotation Reminder Script

```bash
#!/bin/bash
# check_rotation_due.sh - Check for secrets due for rotation

ROTATION_LOG="/secure/rotation_log.csv"
DAYS_THRESHOLD=90

while IFS=',' read -r date secret action user; do
    days_since=$(( ( $(date +%s) - $(date -d "$date" +%s) ) / 86400 ))
    
    if [ $days_since -gt $DAYS_THRESHOLD ]; then
        echo "⚠️  $secret is due for rotation (last rotated $days_since days ago)"
    fi
done < "$ROTATION_LOG"
```

## Best Practices

1. **Never Rotate All Secrets at Once**: Stagger rotations to minimize risk
2. **Test in Non-Production First**: Always validate new secrets in staging
3. **Maintain Rollback Plan**: Keep old secrets accessible for quick rollback
4. **Document Everything**: Record every rotation with timestamp and operator
5. **Monitor After Rotation**: Watch logs for 24 hours after rotation
6. **Use Secret Managers**: Store secrets in dedicated tools (AWS SM, Vault)
7. **Automate Where Possible**: Use scripts to reduce human error
8. **Dual-Key Support**: Allow old and new secrets during transition
9. **Audit Regularly**: Review secret usage and access patterns
10. **Train Team**: Ensure all operators know rotation procedures

## Verification Checklist

After any rotation:

- [ ] New secret tested successfully
- [ ] Application deployed with new secret
- [ ] No errors in application logs (24 hours)
- [ ] Old secret revoked at provider
- [ ] Rotation documented in log
- [ ] Monitoring alerts configured
- [ ] Rollback plan validated
- [ ] Team notified of rotation
- [ ] Next rotation scheduled

## Troubleshooting

### Application Not Using New Secret

```bash
# Check environment variables
docker exec autotrader printenv | grep -i key

# Check mounted secrets
kubectl describe pod autotrader | grep -i secret

# Restart application
kubectl rollout restart deployment/autotrader
```

### Old Secret Still Being Used

```bash
# Check for cached connections
# Review connection pooling configuration
# May need to restart dependent services
```

### Secret Validation Fails

```bash
# Verify secret format
# Check for whitespace/newlines
# Test with direct API call
# Review provider documentation
```

## Security Contacts

- **Secret Compromise**: security@crisiscore.systems (Immediate)
- **Rotation Issues**: ops@crisiscore.systems
- **General Questions**: #security Slack channel

---

**Last Updated**: 2025-10-22  
**Next Review**: 2026-01-22  
**Maintained By**: CrisisCore Systems Security Team
