# AutoTrader Terraform Infrastructure

Infrastructure as Code for AutoTrader Phase 11 - Automation and Operations

## Overview

This Terraform configuration manages the complete AutoTrader infrastructure including:

- **Networking**: VPC, subnets, NAT gateways, security groups
- **Compute**: ECS cluster, services, task definitions
- **Storage**: S3 buckets, RDS (PostgreSQL), Redis
- **Airflow**: Managed Workflows for Apache Airflow (MWAA)
- **Monitoring**: CloudWatch, Prometheus, Grafana
- **Load Balancing**: ALB with blue/green target groups

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **Terraform** >= 1.5.0
3. **AWS CLI** configured with credentials
4. **S3 Backend**: Create bucket and DynamoDB table for state management

```bash
# Create S3 bucket for state
aws s3 mb s3://autotrader-terraform-state --region us-east-1

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name autotrader-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

## Directory Structure

```
terraform/
├── main.tf              # Main configuration
├── variables.tf         # Variable definitions
├── outputs.tf           # Output definitions
├── environments/        # Environment-specific configs
│   ├── dev.tfvars
│   ├── staging.tfvars
│   └── production.tfvars
└── modules/             # Reusable modules
    ├── networking/      # VPC, subnets, security groups
    ├── compute/         # ECS cluster and services
    ├── storage/         # S3, RDS, Redis
    ├── airflow/         # MWAA configuration
    └── monitoring/      # CloudWatch, Prometheus, Grafana
```

## Module Overview

### Networking Module
Creates VPC with public/private subnets across multiple AZs, NAT gateways, and security groups.

**Resources**:
- VPC with DNS support
- 3 public subnets (one per AZ)
- 3 private subnets (one per AZ)
- Internet Gateway
- NAT Gateways (one per AZ)
- Security groups (LB, ECS, RDS, Redis)
- VPC endpoints (S3, ECR)

### Compute Module
Manages ECS cluster and trading service deployment.

**Resources**:
- ECS Cluster with Container Insights
- Task definitions (blue/green)
- ECS Services with auto-scaling
- CloudWatch log groups
- IAM roles and policies

### Storage Module
Provisions persistent storage resources.

**Resources**:
- S3 buckets (data, models, logs, airflow)
- RDS PostgreSQL (multi-AZ for production)
- ElastiCache Redis cluster
- Backup configurations

### Airflow Module
Sets up Managed Workflows for Apache Airflow.

**Resources**:
- MWAA environment
- S3 bucket for DAGs
- IAM execution role
- Environment configurations

### Monitoring Module
Deploys monitoring and alerting infrastructure.

**Resources**:
- CloudWatch dashboards
- Prometheus server (ECS)
- Grafana (ECS)
- SNS topics for alerts
- PagerDuty integration
- Slack integration

## Usage

### 1. Initialize Terraform

```bash
cd terraform
terraform init
```

### 2. Configure Environment

Edit environment-specific variables in `environments/*.tfvars`:

```bash
# For development
cp environments/dev.tfvars environments/dev.tfvars.local
# Edit dev.tfvars.local with your values
```

### 3. Plan Deployment

```bash
# Development
terraform plan -var-file=environments/dev.tfvars

# Production
terraform plan -var-file=environments/production.tfvars
```

### 4. Apply Configuration

```bash
# Development
terraform apply -var-file=environments/dev.tfvars

# Production (with approval)
terraform apply -var-file=environments/production.tfvars
```

### 5. Verify Deployment

```bash
# Show outputs
terraform output

# Specific output
terraform output trading_endpoint
terraform output airflow_webserver_url
```

## Environment Configurations

### Development
- **Purpose**: Development and testing
- **Resources**: Minimal (single AZ, small instances)
- **Cost**: ~$200-300/month
- **Configuration**: `environments/dev.tfvars`

### Staging
- **Purpose**: Pre-production testing
- **Resources**: Medium (2 AZs, medium instances)
- **Cost**: ~$500-700/month
- **Configuration**: `environments/staging.tfvars`

### Production
- **Purpose**: Live trading
- **Resources**: Full (3 AZs, large instances, multi-AZ RDS)
- **Cost**: ~$1,500-2,000/month
- **Configuration**: `environments/production.tfvars`

## Blue/Green Deployment

The infrastructure supports blue/green deployments through dual target groups:

```bash
# Current (blue) target group
terraform output blue_target_group_arn

# New (green) target group
terraform output green_target_group_arn
```

**Deployment Process**:
1. Deploy new version to green environment
2. Run health checks
3. Switch ALB listener to green target group
4. Retain blue for rollback (24h)

## Outputs

Key outputs available after deployment:

| Output | Description |
|--------|-------------|
| `vpc_id` | VPC ID |
| `ecs_cluster_name` | ECS cluster name |
| `trading_endpoint` | Trading service HTTPS endpoint |
| `load_balancer_dns` | Load balancer DNS name |
| `blue_target_group_arn` | Blue target group ARN |
| `green_target_group_arn` | Green target group ARN |
| `airflow_webserver_url` | Airflow UI URL |
| `grafana_url` | Grafana dashboard URL |
| `prometheus_url` | Prometheus URL |
| `s3_data_bucket` | Data storage bucket |
| `s3_models_bucket` | Model artifacts bucket |
| `rds_endpoint` | RDS endpoint (sensitive) |

## Security Considerations

1. **State Management**:
   - Remote state in S3 with encryption
   - State locking via DynamoDB
   - Versioning enabled

2. **Network Security**:
   - Private subnets for compute and data
   - Security groups with least privilege
   - VPC endpoints for AWS services

3. **Data Security**:
   - RDS encryption at rest
   - S3 encryption at rest
   - SSL/TLS in transit

4. **Secrets Management**:
   - Use AWS Secrets Manager for sensitive values
   - Never commit sensitive data to version control
   - Rotate credentials regularly

## Cost Optimization

1. **Development**:
   - Use t3/t4g instance types
   - Single NAT Gateway
   - Smaller RDS instances
   - No Multi-AZ

2. **Production**:
   - Reserved Instances for predictable workloads
   - Savings Plans for compute
   - Auto-scaling for variable workloads
   - S3 lifecycle policies

3. **General**:
   - Use VPC endpoints to avoid NAT charges
   - Enable S3 Intelligent-Tiering
   - Schedule non-critical resources

## Maintenance

### Update Infrastructure

```bash
# Pull latest code
git pull

# Review changes
terraform plan -var-file=environments/production.tfvars

# Apply updates
terraform apply -var-file=environments/production.tfvars
```

### Destroy Resources

```bash
# CAUTION: This will destroy all resources
terraform destroy -var-file=environments/dev.tfvars
```

### State Management

```bash
# List resources
terraform state list

# Show resource
terraform state show aws_lb.trading

# Move resource
terraform state mv aws_lb.old aws_lb.new

# Import existing resource
terraform import aws_lb.trading arn:aws:...
```

## Troubleshooting

### Common Issues

1. **State Lock**:
```bash
# Force unlock (use with caution)
terraform force-unlock <lock-id>
```

2. **Resource Conflicts**:
```bash
# Refresh state
terraform refresh -var-file=environments/dev.tfvars
```

3. **Plan Drift**:
```bash
# Import existing resources
terraform import <resource_type>.<name> <resource_id>
```

### Validation

```bash
# Validate configuration
terraform validate

# Format code
terraform fmt -recursive

# Security scan
tfsec .
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Terraform

on:
  push:
    branches: [main]
  pull_request:

jobs:
  terraform:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        
      - name: Terraform Init
        run: terraform init
        
      - name: Terraform Plan
        run: terraform plan -var-file=environments/${{ env.ENVIRONMENT }}.tfvars
        
      - name: Terraform Apply
        if: github.ref == 'refs/heads/main'
        run: terraform apply -auto-approve -var-file=environments/${{ env.ENVIRONMENT }}.tfvars
```

## Support

For issues or questions:
1. Check [PHASE_11_SPECIFICATION.md](../PHASE_11_SPECIFICATION.md)
2. Review [PHASE_11_IMPLEMENTATION_SUMMARY.md](../PHASE_11_IMPLEMENTATION_SUMMARY.md)
3. Open issue on GitHub

## References

- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [AWS MWAA Documentation](https://docs.aws.amazon.com/mwaa/)
- [Terraform Best Practices](https://www.terraform-best-practices.com/)
