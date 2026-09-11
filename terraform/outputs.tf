output "alb_dns_name" {
  description = "Target public Application Load Balancer DNS URL for accessing website pages"
  value       = aws_lb.main.dns_name
}

output "rds_endpoint" {
  description = "Database server hostname mapping"
  value       = aws_db_instance.db.endpoint
}
