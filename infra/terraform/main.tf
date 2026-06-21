# Foundation resources that don't fit a dedicated file yet.
#
# Keep this lean — once a section grows beyond a few resources, move it into
# its own .tf (we already split ecs.tf out). Don't let main.tf become a
# kitchen sink.

locals {
  name_prefix = "whatsagent-${var.environment}"
}

# --- Alert sink ---------------------------------------------------------------
# CloudWatch alarms (created by infra/cloudwatch/alarms.sh today, will move
# into Terraform after import) publish here. Operator email is wired so the
# very first alarm doesn't fail silently.

resource "aws_sns_topic" "alerts" {
  name = "${local.name_prefix}-alerts"
}

resource "aws_sns_topic_subscription" "alert_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# --- Backup bucket ------------------------------------------------------------
# Consumed by infra/scripts/backup.sh and infra/scripts/restore_drill.sh.
# Lifecycle rule mirrors the 30-day retention assumed by backup.sh.

resource "aws_s3_bucket" "backups" {
  bucket = var.backup_bucket_name

  # Prevent accidental terraform destroy of a bucket holding the only copy
  # of customer data. Operator must remove this block + apply to delete.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket = aws_s3_bucket.backups.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "expire-30d"
    status = "Enabled"

    filter {
      prefix = "backups/"
    }

    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

# --- Log groups ---------------------------------------------------------------
# Pre-create with explicit retention so the first ECS task doesn't auto-create
# a never-expiring log group (the default).

resource "aws_cloudwatch_log_group" "api" {
  name              = "/whatsagent/${var.environment}/api"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/whatsagent/${var.environment}/worker"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "beat" {
  name              = "/whatsagent/${var.environment}/beat"
  retention_in_days = 30
}

output "alert_topic_arn" {
  value       = aws_sns_topic.alerts.arn
  description = "Wire this into infra/cloudwatch/alarms.sh as SNS_ALERT_TOPIC_ARN until alarms move into Terraform."
}

output "backup_bucket" {
  value       = aws_s3_bucket.backups.bucket
  description = "Pass to infra/scripts/backup.sh and restore_drill.sh as S3_BUCKET."
}
