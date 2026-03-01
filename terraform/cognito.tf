# -----------------------------------------------------------------------------
# Cognito Identity Pool — Federated Identity with Okta
# -----------------------------------------------------------------------------

resource "aws_cognito_identity_pool" "main" {
  identity_pool_name               = "${var.resource_prefix}-identity-pool"
  allow_unauthenticated_identities = false

  openid_connect_provider_arns = [] # Added dynamically via custom provider if needed, or using direct config

  # Okta OIDC Configuration
  # Note: For full automation, an aws_iam_openid_connect_provider would be created first.
  # However, Cognito also allows directing OIDC providers via client_id.
}

resource "aws_iam_openid_connect_provider" "okta" {
  url             = "https://${var.okta_domain}/oauth2/default"
  client_id_list  = [var.okta_client_id]
  thumbprint_list = ["9E99A48A9960B14926BB7F3B02E22DA2B0AB7280"] # Standard DigiCert Global Root CA for Okta
}

resource "aws_cognito_identity_pool" "federated" {
  identity_pool_name               = "${var.resource_prefix}-identity-pool"
  allow_unauthenticated_identities = false

  openid_connect_provider_arns = [aws_iam_openid_connect_provider.okta.arn]
}

# -----------------------------------------------------------------------------
# IAM Roles for Cognito Identities
# -----------------------------------------------------------------------------

resource "aws_iam_role" "cognito_authenticated" {
  name = "${var.resource_prefix}-cognito-auth-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = "cognito-identity.amazonaws.com"
        }
        Condition = {
          StringEquals = {
            "cognito-identity.amazonaws.com:aud" = aws_cognito_identity_pool.federated.id
          }
          "ForAnyValue:StringLike" = {
            "cognito-identity.amazonaws.com:amr" = "authenticated"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "cognito_athena_proxy_access" {
  name = "${var.resource_prefix}-cognito-athena-proxy-policy"
  role = aws_iam_role.cognito_authenticated.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunctionUrl"
        Resource = aws_lambda_function.athena_proxy.arn
        Condition = {
          "StringEquals" = {
            "lambda:FunctionUrlAuthType" = "AWS_IAM"
          }
        }
      }
    ]
  })
}

resource "aws_cognito_identity_pool_roles_attachment" "main" {
  identity_pool_id = aws_cognito_identity_pool.federated.id

  roles = {
    authenticated = aws_iam_role.cognito_authenticated.arn
  }
}
