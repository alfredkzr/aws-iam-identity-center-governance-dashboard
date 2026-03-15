# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Serverless AWS IAM Identity Center governance dashboard. Crawls SSO permission assignments and permission set configurations across an entire AWS Organization, stores snapshots in S3, and surfaces them via an interactive React UI. Deployed entirely with Terraform.

## Architecture (Three Layers)

**Ingestion Pipeline:** EventBridge Scheduler → Step Functions (STANDARD, Distributed Map) → Worker Lambda (one per account in parallel). Three phases: ListAccounts → CrawlAccounts → CrawlPermissionSets.

**Data Lake:** Worker Lambdas write Hive-partitioned data to S3 (`assignments/snapshot_date=YYYY-MM-DD/<account_id>.csv`, `permission_sets/snapshot_date=YYYY-MM-DD/permission_sets.json`). Athena with Glue catalog (partition projection, no Glue Crawlers) queries the data. A cache bucket holds pre-rendered `summary.json` and `ps_summary.json` (1-hour TTL).

**Presentation:** React SPA in S3 via CloudFront. API calls go through CloudFront `/api*` path behavior → Athena Proxy Lambda Function URL (AWS_IAM auth via OAC). Cache-first, Athena SQL fallback.

## Common Commands

```bash
# Terraform
cd terraform
terraform init
terraform fmt          # Format HCL
terraform validate     # Validate configuration
terraform plan         # Preview changes
terraform apply        # Deploy (also builds & deploys frontend automatically)
terraform destroy      # Requires force_destroy_buckets = true for non-empty buckets

# Frontend local dev
cd frontend
npm install
npm start              # Dev server at http://localhost:3000 (uses demo data without API endpoint)

# Backend verification (no tests exist — import check only)
cd backend/worker && python3 -c "import handler"
cd backend/athena_proxy && python3 -c "import handler"

# Trigger manual crawl
aws stepfunctions start-execution \
  --region $(terraform output -raw aws_region) \
  --state-machine-arn $(terraform output -raw step_functions_arn)
```

## Key Conventions

- **Resource naming:** All AWS resources must be prefixed with the `resource_prefix` Terraform variable
- **No hardcoded IDs:** Never hardcode Account IDs or ARNs — use Terraform variables
- **Backend:** Python 3.12 (ARM64), boto3 only (no pip dependencies). Always use boto3 paginators, never single-page API calls
- **Frontend:** React 18, plain JavaScript (no TypeScript), plain hooks (useState/useCallback/useEffect, no Redux)
- **Auth:** Okta OIDC (Authorization Code + PKCE) in production; falls back to local auth (admin/admin123) without Okta env vars
- **FinOps:** Reject any service with fixed costs — no NAT Gateways, no Glue Crawlers

## Important Backend Patterns

- `default_risk_policies.py` is duplicated identically in both `backend/worker/` and `backend/athena_proxy/` — changes must be applied to both copies
- boto3 clients use `Config(retries={"max_attempts": 5, "mode": "adaptive"})`
- Worker Lambda caches identity resolution in module-level dicts (`_user_cache`, `_group_cache`, etc.)
- Athena Proxy has a query type allowlist (`all`, `summary`, `dates`, `permission_sets`, `permission_sets_dates`, `risk_policies`, `save_risk_policies`, `change_history`, `audit_status`)
- Table names are validated with regex `^[a-zA-Z_][a-zA-Z0-9_]*$` to prevent SQL injection
- Risk levels: critical (4) > high (3) > medium (2) > low (1)
- CloudTrail Audit Trail: When `cloudtrail_bucket` is configured, a Glue table (`cloudtrail_logs`) is created with partition projection to query Organization CloudTrail logs. The Athena Proxy serves `change_history` and `audit_status` query types for the Audit Trail tab

## Important Terraform Patterns

- Lambda packaging uses `data "archive_file"` from backend source directories
- Frontend build/deploy uses `null_resource` with `local-exec` (triggers on `timestamp()`, always re-runs on apply)
- Glue tables use partition projection (not Glue Crawlers) to keep costs at zero
- All S3 buckets: AES-256 SSE, public access blocked, lifecycle auto-expiry
- CloudFront: custom error responses for SPA routing (403/404 → index.html with 200)

## Frontend Patterns

- Auth state persisted to `sessionStorage` (not localStorage)
- `REACT_APP_API_ENDPOINT` injected at build time; without it, `App.js` uses hardcoded demo data
- Four tabs managed by `activeTab` state in `App.js`: Assignments, Permission Sets, Security, Audit Trail (Audit Trail only visible when CloudTrail is configured)

## Required Terraform Variables

| Variable | Description |
|---|---|
| `resource_prefix` | Globally unique prefix for all resources (3-31 chars, lowercase alphanumeric + hyphens) |
| `sso_instance_arn` | ARN of the IAM Identity Center instance |
| `identity_store_id` | Identity Store ID |

## No Automated Tests

There are no test suites (no pytest, no jest tests, no CI/CD pipelines). Backend verification is limited to import checks.
