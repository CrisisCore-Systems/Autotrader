# Terraform Variables
# Phase 11: Infrastructure Configuration

# Environment
variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# Networking
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

# Compute
variable "trading_image" {
  description = "Docker image for trading service"
  type        = string
}

variable "trading_cpu" {
  description = "CPU units for trading service (1024 = 1 vCPU)"
  type        = number
  default     = 2048
}

variable "trading_memory" {
  description = "Memory for trading service (MB)"
  type        = number
  default     = 4096
}

variable "trading_replicas" {
  description = "Number of trading service replicas"
  type        = number
  default     = 2
}

# Database
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_storage_size" {
  description = "RDS storage size (GB)"
  type        = number
  default     = 100
}

variable "db_backup_retention" {
  description = "RDS backup retention period (days)"
  type        = number
  default     = 7
}

# Airflow
variable "airflow_version" {
  description = "Apache Airflow version"
  type        = string
  default     = "2.7.3"
}

variable "executor_type" {
  description = "Airflow executor type (CeleryExecutor, LocalExecutor)"
  type        = string
  default     = "CeleryExecutor"
}

variable "scheduler_count" {
  description = "Number of Airflow schedulers"
  type        = number
  default     = 2
}

variable "worker_count" {
  description = "Number of Airflow workers"
  type        = number
  default     = 4
}

# Monitoring
variable "alert_email" {
  description = "Email address for alerts"
  type        = string
}

variable "pagerduty_api_key" {
  description = "PagerDuty API key"
  type        = string
  sensitive   = true
}

variable "slack_webhook_url" {
  description = "Slack webhook URL"
  type        = string
  sensitive   = true
}

# DNS
variable "domain_name" {
  description = "Domain name for services"
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID"
  type        = string
  default     = ""
}

variable "ssl_certificate_arn" {
  description = "SSL certificate ARN"
  type        = string
}
