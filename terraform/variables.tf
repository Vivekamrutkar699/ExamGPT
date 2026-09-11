variable "aws_region" {
  description = "AWS region resources are provisioned in"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Application prefix for naming tags"
  type        = string
  default     = "examgpt"
}

variable "environment" {
  description = "Deployment lifecycle stage"
  type        = string
  default     = "production"
}

variable "db_password" {
  description = "Master password for target RDS Postgres database instance"
  type        = string
  sensitive   = true
  default     = "ExamGPTSecurePassWord2026!"
}
