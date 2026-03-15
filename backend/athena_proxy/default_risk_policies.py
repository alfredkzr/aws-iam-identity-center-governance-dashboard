"""
Default Risk Policies — Industry-standard rules for flagging high-risk permissions.

Based on CIS AWS Benchmark recommendations and Rhino Security Labs' AWS privilege
escalation research (https://github.com/RhinoSecurityLabs/AWS-IAM-Privilege-Escalation).

This module is shared by:
  - Worker Lambda: evaluates permission sets at crawl time
  - Athena Proxy Lambda: returns defaults when no custom rules exist in S3
"""

DEFAULT_RISK_POLICIES = {
    "version": 1,
    "rules": [
        # ---- Critical ----
        {
            "type": "managed_policy_name",
            "pattern": "AdministratorAccess",
            "match": "exact",
            "risk": "critical",
            "reason": "Grants full administrative access to all AWS services and resources"
        },
        {
            "type": "inline_policy_action",
            "pattern": "*:*",
            "match": "exact",
            "risk": "critical",
            "reason": "Wildcard actions grant unrestricted access to all AWS services"
        },
        {
            "type": "inline_policy_action",
            "pattern": "*",
            "match": "exact",
            "risk": "critical",
            "reason": "Star action grants unrestricted access to all AWS services"
        },
        # ---- High ----
        {
            "type": "managed_policy_name",
            "pattern": "PowerUserAccess",
            "match": "exact",
            "risk": "high",
            "reason": "Grants access to all services except IAM and Organizations — near-admin level"
        },
        {
            "type": "managed_policy_name",
            "pattern": "IAMFullAccess",
            "match": "exact",
            "risk": "high",
            "reason": "Grants full IAM control — can create users, roles, and policies (privilege escalation risk)"
        },
        {
            "type": "inline_policy_action",
            "pattern": "iam:Create*",
            "match": "wildcard",
            "risk": "high",
            "reason": "Can create IAM entities — privilege escalation path"
        },
        {
            "type": "inline_policy_action",
            "pattern": "iam:PassRole",
            "match": "exact",
            "risk": "high",
            "reason": "Can pass IAM roles to services — privilege escalation path"
        },
        {
            "type": "inline_policy_action",
            "pattern": "iam:AttachUserPolicy",
            "match": "exact",
            "risk": "high",
            "reason": "Can attach policies to users — privilege escalation path"
        },
        {
            "type": "inline_policy_action",
            "pattern": "iam:AttachRolePolicy",
            "match": "exact",
            "risk": "high",
            "reason": "Can attach policies to roles — privilege escalation path"
        },
        {
            "type": "inline_policy_action",
            "pattern": "iam:AttachGroupPolicy",
            "match": "exact",
            "risk": "high",
            "reason": "Can attach policies to groups — privilege escalation path"
        },
        {
            "type": "inline_policy_action",
            "pattern": "iam:PutUserPolicy",
            "match": "exact",
            "risk": "high",
            "reason": "Can create inline policies on users — privilege escalation path"
        },
        {
            "type": "inline_policy_action",
            "pattern": "iam:PutRolePolicy",
            "match": "exact",
            "risk": "high",
            "reason": "Can create inline policies on roles — privilege escalation path"
        },
        {
            "type": "inline_policy_action",
            "pattern": "iam:CreatePolicyVersion",
            "match": "exact",
            "risk": "high",
            "reason": "Can create new policy versions — can escalate permissions by modifying existing policies"
        },
        {
            "type": "inline_policy_action",
            "pattern": "iam:SetDefaultPolicyVersion",
            "match": "exact",
            "risk": "high",
            "reason": "Can set default policy version — can restore a more permissive version"
        },
        {
            "type": "inline_policy_action",
            "pattern": "sts:AssumeRole",
            "match": "exact",
            "risk": "high",
            "reason": "Can assume other IAM roles — lateral movement and privilege escalation"
        },
        {
            "type": "inline_policy_action",
            "pattern": "lambda:UpdateFunctionCode",
            "match": "exact",
            "risk": "high",
            "reason": "Can modify Lambda code — can execute arbitrary code with the function's IAM role"
        },
        {
            "type": "inline_policy_action",
            "pattern": "lambda:CreateFunction",
            "match": "exact",
            "risk": "high",
            "reason": "Can create Lambda functions — can execute code with passed IAM roles"
        },
        {
            "type": "inline_policy_action",
            "pattern": "cloudtrail:StopLogging",
            "match": "exact",
            "risk": "high",
            "reason": "Can stop CloudTrail logging — audit evasion"
        },
        {
            "type": "inline_policy_action",
            "pattern": "cloudtrail:DeleteTrail",
            "match": "exact",
            "risk": "high",
            "reason": "Can delete CloudTrail trails — destroys audit evidence"
        },
        {
            "type": "inline_policy_action",
            "pattern": "cloudtrail:UpdateTrail",
            "match": "exact",
            "risk": "high",
            "reason": "Can modify CloudTrail configuration — audit tampering"
        },
        {
            "type": "inline_policy_action",
            "pattern": "guardduty:DeleteDetector",
            "match": "exact",
            "risk": "high",
            "reason": "Can delete GuardDuty detectors — disables threat detection"
        },
        {
            "type": "inline_policy_action",
            "pattern": "config:StopConfigurationRecorder",
            "match": "exact",
            "risk": "high",
            "reason": "Can stop AWS Config recorder — disables compliance monitoring"
        },
        {
            "type": "inline_policy_action",
            "pattern": "config:DeleteConfigRule",
            "match": "exact",
            "risk": "high",
            "reason": "Can delete AWS Config rules — removes compliance checks"
        },
        {
            "type": "inline_policy_action",
            "pattern": "iam:UpdateAssumeRolePolicy",
            "match": "exact",
            "risk": "high",
            "reason": "Can modify role trust policies — privilege escalation via trust manipulation"
        },
        {
            "type": "inline_policy_action",
            "pattern": "iam:DeleteRolePermissionsBoundary",
            "match": "exact",
            "risk": "high",
            "reason": "Can remove permissions boundaries — escalates effective permissions"
        },
        {
            "type": "inline_policy_action",
            "pattern": "organizations:*",
            "match": "exact",
            "risk": "high",
            "reason": "Full Organizations access — can modify account structure and policies"
        },
        {
            "type": "inline_policy_action",
            "pattern": "glue:CreateDevEndpoint",
            "match": "exact",
            "risk": "high",
            "reason": "Can create Glue dev endpoints — code execution with IAM role"
        },
        {
            "type": "inline_policy_action",
            "pattern": "cloudformation:CreateStack",
            "match": "exact",
            "risk": "high",
            "reason": "Can create CloudFormation stacks — create resources with IAM roles"
        },
        # ---- Medium ----
        {
            "type": "managed_policy_name",
            "pattern": "*FullAccess",
            "match": "wildcard",
            "risk": "medium",
            "reason": "Full-access policies are rarely needed — violates principle of least privilege"
        },
        {
            "type": "managed_policy_name",
            "pattern": "AmazonS3FullAccess",
            "match": "exact",
            "risk": "medium",
            "reason": "Full S3 access — can read/write/delete any data in any bucket"
        },
        {
            "type": "managed_policy_name",
            "pattern": "AmazonEC2FullAccess",
            "match": "exact",
            "risk": "medium",
            "reason": "Full EC2 access — can launch instances and modify network/security groups"
        },
        {
            "type": "managed_policy_name",
            "pattern": "AmazonRDSFullAccess",
            "match": "exact",
            "risk": "medium",
            "reason": "Full RDS access — can create/modify/delete databases and access sensitive data"
        },
        {
            "type": "inline_policy_action",
            "pattern": "s3:*",
            "match": "exact",
            "risk": "medium",
            "reason": "Full S3 access — can read/write/delete any data in any bucket"
        },
        {
            "type": "inline_policy_action",
            "pattern": "ec2:*",
            "match": "exact",
            "risk": "medium",
            "reason": "Full EC2 access — can launch instances, modify security groups, and access network resources"
        },
        {
            "type": "inline_policy_action",
            "pattern": "rds:*",
            "match": "exact",
            "risk": "medium",
            "reason": "Full RDS access — can create/modify/delete databases and access sensitive data"
        },
        {
            "type": "inline_policy_action",
            "pattern": "kms:*",
            "match": "exact",
            "risk": "medium",
            "reason": "Full KMS access — can manage encryption keys and decrypt sensitive data"
        },
        {
            "type": "inline_policy_action",
            "pattern": "secretsmanager:GetSecretValue",
            "match": "exact",
            "risk": "medium",
            "reason": "Can read secrets — access to credentials and sensitive configuration"
        },
        {
            "type": "inline_policy_action",
            "pattern": "ssm:GetParameter*",
            "match": "wildcard",
            "risk": "medium",
            "reason": "Can read SSM parameters — access to secrets and sensitive configuration"
        },
        {
            "type": "inline_policy_action",
            "pattern": "ec2:AuthorizeSecurityGroupIngress",
            "match": "exact",
            "risk": "medium",
            "reason": "Can open inbound network access — exposes resources to external traffic"
        },
        {
            "type": "inline_policy_action",
            "pattern": "sso:*",
            "match": "exact",
            "risk": "medium",
            "reason": "Full SSO/Identity Center access — can modify identity federation and access"
        },
        {
            "type": "inline_policy_action",
            "pattern": "identitystore:*",
            "match": "exact",
            "risk": "medium",
            "reason": "Full Identity Store access — can modify users, groups, and memberships"
        },
        {
            "type": "inline_policy_action",
            "pattern": "securityhub:DisableSecurityHub",
            "match": "exact",
            "risk": "medium",
            "reason": "Can disable Security Hub — removes centralized security monitoring"
        },
        {
            "type": "inline_policy_action",
            "pattern": "access-analyzer:DeleteAnalyzer",
            "match": "exact",
            "risk": "medium",
            "reason": "Can delete IAM Access Analyzer — removes external access detection"
        },
        {
            "type": "inline_policy_action",
            "pattern": "ses:SendEmail",
            "match": "exact",
            "risk": "medium",
            "reason": "Can send emails via SES — phishing and social engineering risk"
        },
    ]
}

# Risk level ordering for comparison
RISK_LEVELS = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}
