# -----------------------------------------------------------------------------
# Core Configuration
# -----------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "resource_prefix" {
  description = "Prefix for all resource names (e.g. 'myorg-idc-gov'). Must be globally unique for S3 bucket names."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{2,30}$", var.resource_prefix))
    error_message = "resource_prefix must be 3-31 chars, lowercase alphanumeric and hyphens, starting with a letter or digit."
  }
}

variable "project_name" {
  description = "Project name used in resource tags"
  type        = string
  default     = "idc-governance"
}

variable "environment" {
  description = "Environment name used in resource tags (e.g. production, staging, demo)"
  type        = string
  default     = "production"
}

# -----------------------------------------------------------------------------
# IAM Identity Center
# -----------------------------------------------------------------------------

variable "sso_instance_arn" {
  description = "ARN of the IAM Identity Center (SSO) instance"
  type        = string
}

variable "identity_store_id" {
  description = "Identity Store ID associated with the SSO instance"
  type        = string
}

variable "org_management_account_id" {
  description = "AWS Organization management account ID"
  type        = string
}

# -----------------------------------------------------------------------------
# Security Configuration
# -----------------------------------------------------------------------------

variable "force_destroy_buckets" {
  description = "Allow Terraform to destroy S3 buckets even if they contain objects. Set to true only for dev/demo environments."
  type        = bool
  default     = false
}

variable "allowed_origins" {
  description = "List of allowed CORS origins for the Lambda Function URL. Set to your Amplify domain in production (e.g. ['https://main.d1234abcde.amplifyapp.com'])."
  type        = list(string)
  default     = ["*"]
}

variable "lambda_url_auth_type" {
  description = "Authorization type for the Athena Proxy Lambda Function URL. Use 'NONE' for demo or 'AWS_IAM' for production (requires SigV4 signed requests from frontend)."
  type        = string
  default     = "NONE"

  validation {
    condition     = contains(["NONE", "AWS_IAM"], var.lambda_url_auth_type)
    error_message = "lambda_url_auth_type must be either 'NONE' or 'AWS_IAM'."
  }
}

# -----------------------------------------------------------------------------
# Cost & Performance Guardrails
# -----------------------------------------------------------------------------

variable "log_retention_days" {
  description = "CloudWatch Logs retention period in days"
  type        = number
  default     = 7
}

variable "worker_reserved_concurrency" {
  description = "Maximum concurrent executions for the worker Lambda. Limits blast radius and cost."
  type        = number
  default     = 10
}

variable "athena_proxy_reserved_concurrency" {
  description = "Maximum concurrent executions for the Athena proxy Lambda. Limits blast radius and cost."
  type        = number
  default     = 5
}

# -----------------------------------------------------------------------------
# Amplify / GitHub Integration
# -----------------------------------------------------------------------------

variable "github_repository" {
  description = "GitHub repository URL for Amplify source (e.g. https://github.com/org/repo)"
  type        = string
  default     = ""
}

variable "github_oauth_token" {
  description = "GitHub personal access token for Amplify to access the repository"
  type        = string
  default     = ""
  sensitive   = true
}

# -----------------------------------------------------------------------------
# SSO OIDC Configuration (for frontend auth)
# -----------------------------------------------------------------------------

variable "sso_oidc_issuer_url" {
  description = "OIDC issuer URL from IAM Identity Center (e.g. https://identitycenter.amazonaws.com/ssoins-xxxxxxxx)"
  type        = string
  default     = ""
}

variable "sso_oidc_client_id" {
  description = "OIDC client/application ID registered in IAM Identity Center"
  type        = string
  default     = ""
}
