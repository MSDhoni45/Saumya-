#!/usr/bin/env bash
# Create CloudWatch alarms for the WhatsAgent API + worker.
#
# Run once after the ECS services and the ALB target group exist:
#   ./alarms.sh
#
# Required env vars:
#   AWS_REGION              - e.g. ap-south-1
#   AWS_ACCOUNT_ID          - 12-digit account id
#   SNS_ALERT_TOPIC_ARN     - SNS topic that pages the on-call (email/SMS/PagerDuty)
#   ALB_ARN_SUFFIX          - e.g. app/whatsagent-alb/abc123 (after "loadbalancer/")
#   TARGET_GROUP_ARN_SUFFIX - e.g. targetgroup/whatsagent-api/def456
#   ECS_CLUSTER             - whatsagent-prod
#   ECS_SERVICE_API         - whatsagent-api
#   ECS_SERVICE_WORKER      - whatsagent-worker
#   LOG_GROUP_API           - /ecs/whatsagent-api
#
# Thresholds are tuned for pilot scale (low traffic). Re-tune once real
# traffic baselines are visible in CloudWatch metrics.

set -euo pipefail

: "${AWS_REGION:?}"
: "${SNS_ALERT_TOPIC_ARN:?}"
: "${ALB_ARN_SUFFIX:?}"
: "${TARGET_GROUP_ARN_SUFFIX:?}"
: "${ECS_CLUSTER:?}"
: "${ECS_SERVICE_API:?}"
: "${ECS_SERVICE_WORKER:?}"
: "${LOG_GROUP_API:=/ecs/whatsagent-api}"

ACTIONS="--alarm-actions $SNS_ALERT_TOPIC_ARN --ok-actions $SNS_ALERT_TOPIC_ARN"
COMMON="--region $AWS_REGION --treat-missing-data notBreaching"

# ---------- ALB / API HTTP health -----------------------------------------

aws cloudwatch put-metric-alarm $COMMON $ACTIONS \
  --alarm-name whatsagent-api-5xx-spike \
  --alarm-description "API returning >5 5xx/min for 2 consecutive minutes" \
  --metric-name HTTPCode_Target_5XX_Count --namespace AWS/ApplicationELB \
  --statistic Sum --period 60 --evaluation-periods 2 --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=LoadBalancer,Value="$ALB_ARN_SUFFIX" Name=TargetGroup,Value="$TARGET_GROUP_ARN_SUFFIX"

aws cloudwatch put-metric-alarm $COMMON $ACTIONS \
  --alarm-name whatsagent-api-p95-latency \
  --alarm-description "API p95 latency > 2s for 3 minutes" \
  --metric-name TargetResponseTime --namespace AWS/ApplicationELB \
  --extended-statistic p95 --period 60 --evaluation-periods 3 --threshold 2 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=LoadBalancer,Value="$ALB_ARN_SUFFIX" Name=TargetGroup,Value="$TARGET_GROUP_ARN_SUFFIX"

aws cloudwatch put-metric-alarm $COMMON $ACTIONS \
  --alarm-name whatsagent-api-unhealthy-hosts \
  --alarm-description "One or more API tasks failing target-group health checks" \
  --metric-name UnHealthyHostCount --namespace AWS/ApplicationELB \
  --statistic Maximum --period 60 --evaluation-periods 2 --threshold 0 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=LoadBalancer,Value="$ALB_ARN_SUFFIX" Name=TargetGroup,Value="$TARGET_GROUP_ARN_SUFFIX"

# ---------- ECS resource saturation ---------------------------------------

for svc in "$ECS_SERVICE_API" "$ECS_SERVICE_WORKER"; do
  aws cloudwatch put-metric-alarm $COMMON $ACTIONS \
    --alarm-name "whatsagent-${svc}-cpu-high" \
    --alarm-description "$svc CPU > 80% for 5 minutes" \
    --metric-name CPUUtilization --namespace AWS/ECS \
    --statistic Average --period 60 --evaluation-periods 5 --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=ClusterName,Value="$ECS_CLUSTER" Name=ServiceName,Value="$svc"

  aws cloudwatch put-metric-alarm $COMMON $ACTIONS \
    --alarm-name "whatsagent-${svc}-memory-high" \
    --alarm-description "$svc memory > 85% for 5 minutes" \
    --metric-name MemoryUtilization --namespace AWS/ECS \
    --statistic Average --period 60 --evaluation-periods 5 --threshold 85 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=ClusterName,Value="$ECS_CLUSTER" Name=ServiceName,Value="$svc"
done

# ---------- Log-pattern alarms (catch ERROR lines in JSON logs) -----------

aws logs put-metric-filter --region "$AWS_REGION" \
  --log-group-name "$LOG_GROUP_API" \
  --filter-name whatsagent-api-error-lines \
  --filter-pattern '{ $.level = "ERROR" }' \
  --metric-transformations \
      metricName=ApiErrorLogLines,metricNamespace=WhatsAgent/App,metricValue=1,defaultValue=0

aws cloudwatch put-metric-alarm $COMMON $ACTIONS \
  --alarm-name whatsagent-api-error-log-spike \
  --alarm-description ">10 ERROR log lines/min for 2 minutes" \
  --metric-name ApiErrorLogLines --namespace WhatsAgent/App \
  --statistic Sum --period 60 --evaluation-periods 2 --threshold 10 \
  --comparison-operator GreaterThanThreshold

echo "CloudWatch alarms created."
