/**
 * Amplify Auth configuration for IAM Identity Center (OIDC).
 *
 * Replace the placeholder values with your actual Identity Center
 * OIDC application settings after deploying the Terraform stack.
 */

const amplifyConfig = {
    Auth: {
        Cognito: {
            // When using Identity Center as OIDC provider through Cognito,
            // these would be your Cognito User Pool settings.
            // For direct OIDC, use the loginWith.oauth configuration below.
        },
        loginWith: {
            oauth: {
                domain: process.env.REACT_APP_SSO_ISSUER_URL || 'your-identity-center-domain',
                clientId: process.env.REACT_APP_SSO_CLIENT_ID || 'your-oidc-client-id',
                responseType: 'code',
                scopes: ['openid', 'profile', 'email'],
                redirectSignIn: [window.location.origin + '/'],
                redirectSignOut: [window.location.origin + '/'],
                providers: ['OIDC'],
            },
        },
    },
    API: {
        endpoints: [
            {
                name: 'governance',
                endpoint: process.env.REACT_APP_API_ENDPOINT || 'http://localhost:3001',
            },
        ],
    },
};

export default amplifyConfig;
