# Development Environment Configuration
# terraform/environments/dev.tfvars

environment = "dev"
aws_region  = "us-east-1"

# Networking
vpc_cidr           = "10.0.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b"]

# Compute
trading_image    = "your-registry.amazonaws.com/autotrader:latest"
trading_cpu      = 1024  # 1 vCPU
trading_memory   = 2048  # 2 GB
trading_replicas = 1

# Database
db_instance_class   = "db.t3.small"
db_storage_size     = 20
db_backup_retention = 3

# Airflow
airflow_version  = "2.7.3"
executor_type    = "LocalExecutor"
scheduler_count  = 1
worker_count     = 1

# Monitoring
alert_email       = "dev-team@example.com"
pagerduty_api_key = "your-pagerduty-api-key"
slack_webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# DNS
domain_name         = ""
route53_zone_id     = ""
ssl_certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id"
