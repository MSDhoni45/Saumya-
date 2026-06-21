terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }

  # Remote state — configure via -backend-config so the same module can host
  # staging + prod with different keys.
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "whatsagent"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
