# Production Environment Configuration
# terraform/environments/production.tfvars

environment = "production"
aws_region  = "us-east-1"

# Networking
vpc_cidr           = "10.0.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

# Compute
trading_image    = "your-registry.amazonaws.com/autotrader:v1.0.0"
trading_cpu      = 4096  # 4 vCPU
trading_memory   = 8192  # 8 GB
trading_replicas = 3

# Database
db_instance_class   = "db.r5.xlarge"
db_storage_size     = 500
db_backup_retention = 30

# Airflow
airflow_version  = "2.7.3"
executor_type    = "CeleryExecutor"
scheduler_count  = 2
worker_count     = 4

# Monitoring
alert_email       = "ops-team@example.com"
pagerduty_api_key = "your-production-pagerduty-api-key"
slack_webhook_url = "https://hooks.slack.com/services/YOUR/PROD/WEBHOOK"

# DNS
domain_name         = "yourdomain.com"
route53_zone_id     = "Z1234567890ABC"
ssl_certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/prod-cert-id"
