# Open Source & Project Rules
- **Naming:** Prefix everything with the `resource_prefix` Terraform variable (e.g. `your-org-idc-gov-`).
- **Backend:** Python 3.12 (ARM64) only. Use Boto3 paginators.
- **Variables:** Never hardcode Account IDs or ARNs. Use Terraform variables with descriptions.
- **Auth:** The React frontend MUST use the Amplify Auth library configured for OIDC (Identity Center).
- **FinOps:** Reject any service with fixed costs (NAT Gateways, Glue Crawlers).
