# Terraform Outputs
# Phase 11: Infrastructure Outputs

output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = module.networking.vpc_cidr
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.networking.private_subnet_ids
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.networking.public_subnet_ids
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.compute.ecs_cluster_name
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN"
  value       = module.compute.ecs_cluster_arn
}

output "trading_service_name" {
  description = "Trading service name"
  value       = module.compute.trading_service_name
}

output "trading_service_arn" {
  description = "Trading service ARN"
  value       = module.compute.trading_service_arn
}

output "load_balancer_dns" {
  description = "Load balancer DNS name"
  value       = aws_lb.trading.dns_name
}

output "load_balancer_arn" {
  description = "Load balancer ARN"
  value       = aws_lb.trading.arn
}

output "blue_target_group_arn" {
  description = "Blue target group ARN for blue/green deployment"
  value       = aws_lb_target_group.blue.arn
}

output "green_target_group_arn" {
  description = "Green target group ARN for blue/green deployment"
  value       = aws_lb_target_group.green.arn
}

output "trading_endpoint" {
  description = "Trading service endpoint (HTTPS)"
  value       = var.domain_name != "" ? "https://trading.${var.domain_name}" : "https://${aws_lb.trading.dns_name}"
}

output "airflow_webserver_url" {
  description = "Airflow webserver URL"
  value       = module.airflow.webserver_url
}

output "airflow_environment_arn" {
  description = "Airflow MWAA environment ARN"
  value       = module.airflow.environment_arn
}

output "grafana_url" {
  description = "Grafana dashboard URL"
  value       = module.monitoring.grafana_url
}

output "prometheus_url" {
  description = "Prometheus URL"
  value       = module.monitoring.prometheus_url
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = module.monitoring.cloudwatch_log_group
}

output "s3_data_bucket" {
  description = "S3 bucket for data storage"
  value       = module.storage.data_bucket_name
}

output "s3_models_bucket" {
  description = "S3 bucket for model artifacts"
  value       = module.storage.models_bucket_name
}

output "s3_logs_bucket" {
  description = "S3 bucket for logs"
  value       = module.storage.logs_bucket_name
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.storage.rds_endpoint
  sensitive   = true
}

output "rds_port" {
  description = "RDS port"
  value       = module.storage.rds_port
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = module.storage.redis_endpoint
}

output "redis_port" {
  description = "Redis port"
  value       = module.storage.redis_port
}

# Environment-specific outputs
output "environment_summary" {
  description = "Summary of deployed environment"
  value = {
    environment          = var.environment
    region              = var.aws_region
    vpc_id              = module.networking.vpc_id
    ecs_cluster         = module.compute.ecs_cluster_name
    trading_endpoint    = var.domain_name != "" ? "https://trading.${var.domain_name}" : "https://${aws_lb.trading.dns_name}"
    airflow_url         = module.airflow.webserver_url
    grafana_url         = module.monitoring.grafana_url
    data_bucket         = module.storage.data_bucket_name
    models_bucket       = module.storage.models_bucket_name
  }
}
