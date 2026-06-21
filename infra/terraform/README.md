# Terraform skeleton — WhatsAgent AWS infra

This is a starting point, not a finished IaC tree. The pilot was bootstrapped
with bash (`infra/scripts/deploy.sh`) and hand-edited ECS task-definition JSON
under `infra/ecs/`. This module converts the *durable* parts of that bootstrap
into Terraform so the next environment (staging-isolated, EU region, customer
PoC) does not start from raw `aws cli` again.

## Scope (intentional)

In scope:

- VPC, subnets, NAT (small + cheap — 1 NAT, not 1-per-AZ).
- ALB + target group + listeners.
- ECS cluster + Fargate services for `api`, `worker`, `beat`.
- IAM execution / task roles.
- CloudWatch log groups (consumed by `infra/cloudwatch/alarms.sh`).
- SNS alert topic.
- S3 bucket for DB backups with a 30-day lifecycle.

Out of scope (deliberately not Terraformed yet):

- Supabase (managed externally — Postgres + Auth + Storage live there, this
  module only needs the connection-string secret).
- Route53 / ACM cert (one-time per domain; do in console once).
- Secrets Manager *values* (only the secret containers — values are written
  out-of-band so they never live in state).
- Sentry / Stripe / Razorpay / Meta WhatsApp configs (provider consoles).

## Usage

```bash
cd infra/terraform
terraform init \
  -backend-config="bucket=whatsagent-tf-state" \
  -backend-config="key=prod/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=whatsagent-tf-locks"

terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars
```

State lives in S3 + DynamoDB lock — never commit `*.tfstate`.

## Promotion path

1. Land this skeleton as a **read-only model** of current infra
   (`terraform plan` should show no changes against what bash produced — if
   it does, the skeleton is wrong, fix it before applying).
2. Move one resource at a time under Terraform management via `terraform
   import` (start with the SNS topic + S3 backup bucket — both cheap to get
   wrong).
3. Stop editing `infra/ecs/*.json` and `infra/scripts/deploy.sh` for the
   imported resources; route those changes through Terraform PRs.
4. Once `api`, `worker`, `beat` services are imported, retire the bash
   deploy and switch to `terraform apply` + image-tag pinning via
   `var.api_image_tag`.

Don't rip the bash deploy out before step 4 — the operator needs a working
escape hatch while the imports are in flight.
