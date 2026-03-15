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
        # ---- Medium ----
        {
            "type": "managed_policy_name",
            "pattern": "*FullAccess",
            "match": "wildcard",
            "risk": "medium",
            "reason": "Full-access policies are rarely needed — violates principle of least privilege"
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
    ]
}

# Risk level ordering for comparison
RISK_LEVELS = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}
