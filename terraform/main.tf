# AutoTrader Terraform Main Configuration
# Phase 11: Infrastructure as Code

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket         = "autotrader-terraform-state"
    key            = "autotrader/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "autotrader-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "AutoTrader"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Phase       = "11"
    }
  }
}

# Local variables
locals {
  name_prefix = "autotrader-${var.environment}"
  
  common_tags = {
    Project     = "AutoTrader"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# VPC and Networking
module "networking" {
  source = "./modules/networking"
  
  environment         = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  
  tags = local.common_tags
}

# Compute Resources (ECS/Lambda)
module "compute" {
  source = "./modules/compute"
  
  environment    = var.environment
  vpc_id         = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  public_subnet_ids  = module.networking.public_subnet_ids
  
  # Trading engine configuration
  trading_image     = var.trading_image
  trading_cpu       = var.trading_cpu
  trading_memory    = var.trading_memory
  trading_replicas  = var.trading_replicas
  
  tags = local.common_tags
}

# Storage (S3, RDS)
module "storage" {
  source = "./modules/storage"
  
  environment = var.environment
  vpc_id      = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  
  # Database configuration
  db_instance_class = var.db_instance_class
  db_storage_size   = var.db_storage_size
  db_backup_retention = var.db_backup_retention
  
  tags = local.common_tags
}

# Airflow Infrastructure
module "airflow" {
  source = "./modules/airflow"
  
  environment        = var.environment
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  public_subnet_ids  = module.networking.public_subnet_ids
  
  # Airflow configuration
  airflow_version    = var.airflow_version
  executor_type      = var.executor_type
  scheduler_count    = var.scheduler_count
  worker_count       = var.worker_count
  
  # Database connection
  metadata_db_endpoint = module.storage.rds_endpoint
  metadata_db_name     = module.storage.airflow_db_name
  
  tags = local.common_tags
}

# Monitoring (CloudWatch, Prometheus, Grafana)
module "monitoring" {
  source = "./modules/monitoring"
  
  environment = var.environment
  vpc_id      = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  public_subnet_ids  = module.networking.public_subnet_ids
  
  # ECS cluster for monitoring
  ecs_cluster_name = module.compute.ecs_cluster_name
  
  # Trading service
  trading_service_name = module.compute.trading_service_name
  
  # Airflow
  airflow_environment_name = module.airflow.environment_name
  
  # Alert configuration
  alert_email         = var.alert_email
  pagerduty_api_key   = var.pagerduty_api_key
  slack_webhook_url   = var.slack_webhook_url
  
  tags = local.common_tags
}

# Load Balancer
resource "aws_lb" "trading" {
  name               = "${local.name_prefix}-trading-lb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [module.networking.lb_security_group_id]
  subnets            = module.networking.public_subnet_ids
  
  enable_deletion_protection = var.environment == "production" ? true : false
  enable_http2              = true
  
  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-trading-lb"
    }
  )
}

# Target Group for Blue Environment
resource "aws_lb_target_group" "blue" {
  name        = "${local.name_prefix}-blue-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = module.networking.vpc_id
  target_type = "ip"
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }
  
  deregistration_delay = 30
  
  tags = merge(
    local.common_tags,
    {
      Name        = "${local.name_prefix}-blue-tg"
      Environment_Type = "blue"
    }
  )
}

# Target Group for Green Environment
resource "aws_lb_target_group" "green" {
  name        = "${local.name_prefix}-green-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = module.networking.vpc_id
  target_type = "ip"
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }
  
  deregistration_delay = 30
  
  tags = merge(
    local.common_tags,
    {
      Name        = "${local.name_prefix}-green-tg"
      Environment_Type = "green"
    }
  )
}

# Listener
resource "aws_lb_listener" "trading" {
  load_balancer_arn = aws_lb.trading.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = var.ssl_certificate_arn
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.blue.arn
  }
  
  tags = local.common_tags
}

# HTTP to HTTPS redirect
resource "aws_lb_listener" "trading_http" {
  load_balancer_arn = aws_lb.trading.arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type = "redirect"
    
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
  
  tags = local.common_tags
}

# Route53 DNS
resource "aws_route53_record" "trading" {
  count   = var.domain_name != "" ? 1 : 0
  zone_id = var.route53_zone_id
  name    = "trading.${var.domain_name}"
  type    = "A"
  
  alias {
    name                   = aws_lb.trading.dns_name
    zone_id                = aws_lb.trading.zone_id
    evaluate_target_health = true
  }
}

# Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.compute.ecs_cluster_name
}

output "trading_service_name" {
  description = "Trading service name"
  value       = module.compute.trading_service_name
}

output "load_balancer_dns" {
  description = "Load balancer DNS name"
  value       = aws_lb.trading.dns_name
}

output "blue_target_group_arn" {
  description = "Blue target group ARN"
  value       = aws_lb_target_group.blue.arn
}

output "green_target_group_arn" {
  description = "Green target group ARN"
  value       = aws_lb_target_group.green.arn
}

output "airflow_webserver_url" {
  description = "Airflow webserver URL"
  value       = module.airflow.webserver_url
}

output "grafana_url" {
  description = "Grafana dashboard URL"
  value       = module.monitoring.grafana_url
}

output "prometheus_url" {
  description = "Prometheus URL"
  value       = module.monitoring.prometheus_url
}

output "s3_data_bucket" {
  description = "S3 bucket for data storage"
  value       = module.storage.data_bucket_name
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.storage.rds_endpoint
}
