variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for all resources in this stack."
}

variable "environment" {
  type        = string
  description = "prod | staging | pilot — used in resource names and the default-tags block."
  validation {
    condition     = contains(["prod", "staging", "pilot"], var.environment)
    error_message = "environment must be one of: prod, staging, pilot."
  }
}

variable "vpc_cidr" {
  type        = string
  default     = "10.40.0.0/16"
  description = "Primary VPC CIDR. Pick a non-overlapping block per environment so we can peer them later."
}

variable "api_image" {
  type        = string
  description = "ECR image URI for the FastAPI container, including tag (e.g. .../whatsagent-api:abc123)."
}

variable "worker_image" {
  type        = string
  description = "ECR image URI for the Celery worker container, including tag."
}

variable "beat_image" {
  type        = string
  description = "ECR image URI for the Celery beat container, including tag."
}

variable "alert_email" {
  type        = string
  description = "Email subscribed to the SNS alert topic — receives CloudWatch alarm notifications."
}

variable "backup_bucket_name" {
  type        = string
  description = "Globally unique S3 bucket name for nightly Postgres dumps."
}
