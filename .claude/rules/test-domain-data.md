# CyberArk Domain Test Data

Use this data to make tests realistic and catch domain-specific edge cases. These are representative samples, not production data.

## Sample Document Content

### CONJUR_K8S_AUTH_CONTENT (~300 words)
```
The Conjur Kubernetes Authenticator enables workloads running in Kubernetes to authenticate to Conjur using their Kubernetes identity. This eliminates the need for static API keys or passwords stored in pods.

## Prerequisites

Before configuring the Kubernetes authenticator, ensure the following:
- Conjur Cloud or Conjur Enterprise (v12.0+) is deployed and accessible
- A Conjur policy defining the authenticator service exists
- The Conjur authenticator client is deployed as a sidecar or init container

## Configuration Steps

Step 1: Define the authenticator in Conjur policy:

```yaml
- !policy
  id: conjur/authn-k8s/my-cluster
  body:
  - !webservice
  - !variable ca/cert
  - !variable ca/key
```

Step 2: Load the policy and set the CA certificate variables.

Step 3: Deploy the authenticator client as a sidecar container in your application pod.

## Troubleshooting

Error CONJ00004E: The authenticator service is not enabled. Verify the CONJUR_AUTHENTICATORS environment variable includes authn-k8s/my-cluster.

Error CONJ00007E: Certificate validation failed. Check that the CA certificate matches the Kubernetes API server certificate.
```

### PVWA_ADMIN_CONTENT (~200 words)
```
The Password Vault Web Access (PVWA) provides a web interface for managing privileged accounts. Administrators access PVWA at https://<pvwa-server>/PasswordVault.

## Common Administration Tasks

### Resetting the PVWA Admin Password

1. Connect to the PVWA server via RDP
2. Open the PVWA Configuration tool (PVConfiguration.exe)
3. Navigate to the Administration section
4. Select Reset Admin Password

### PVWA Error Codes

| Error Code | Description | Resolution |
|---|---|---|
| ITATS001E | Session timeout | Clear browser cache and re-authenticate |
| PVWA401 | Authentication failed | Verify credentials and LDAP integration |
| PASWS034E | Safe not found | Check Safe permissions in PrivateArk |
```

### SPIFFE_OVERVIEW_CONTENT (~150 words)
```
SPIFFE (Secure Production Identity Framework For Everyone) provides a standard for identifying and securing workloads across heterogeneous environments. CyberArk implements SPIFFE through its Secure Workload Access solution.

## Key Concepts

- SPIFFE ID: A URI-formatted identity (spiffe://trust-domain/workload-path)
- SVID: A SPIFFE Verifiable Identity Document, either X.509 or JWT
- SPIRE: The SPIFFE Runtime Environment, an open-source implementation

## Integration with CyberArk

CyberArk extends SPIFFE/SPIRE with enterprise-grade key management, audit logging, and centralized policy enforcement through the Identity Security Platform.
```

## Sample URLs by Product

```python
SAMPLE_URLS = {
    "conjur-cloud": "https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/conjur-authn-k8s.htm",
    "privilege-cloud": "https://docs.cyberark.com/privilege-cloud-standard/Latest/en/Content/PASIMP/PVWA-Overview.htm",
    "pam-self-hosted": "https://docs.cyberark.com/pam-self-hosted/14.2/en/Content/PAS-INST/Installing-CyberArk.htm",
    "secrets-hub": "https://docs.cyberark.com/secrets-hub/Latest/en/Content/SecretsHub/sh-overview.htm",
    "epm": "https://docs.cyberark.com/epm/Latest/en/Content/EPM/EPM-Overview.htm",
    "dpa": "https://docs.cyberark.com/dpa/Latest/en/Content/DPA/DPA-Overview.htm",
    "identity": "https://docs.cyberark.com/identity/Latest/en/Content/Identity/identity-overview.htm",
}
```

## CyberArk Error Codes for BM25 Testing

These are exact-match terms that BM25 should find but vector search may miss:

```python
ERROR_CODES = [
    "CONJ00004E",    # Conjur authenticator not enabled
    "CONJ00007E",    # Certificate validation failed
    "APPAP001E",     # Application authentication failed
    "ITATS001E",     # Session timeout
    "PVWA401",       # PVWA auth failed
    "PASWS034E",     # Safe not found
    "CAKM001E",      # Key management error
    "PVCONFIG.XML",  # Config file reference
]
```

## Product Alias Pairs for Testing

```python
ALIAS_PAIRS = [
    ("AAM-DAP", "secrets-manager-sh"),
    ("conjur-cloud", "secrets-manager-saas"),
    ("PrivCloud", "privilege-cloud-standard"),
    ("PAS", "pam-self-hosted"),
    ("pas", "pam-self-hosted"),
    ("epm", "endpoint-privilege-manager"),
    ("dpa", "dynamic-privileged-access"),
    ("alero", "remote-access"),
    ("secrets-hub-pam-sh", "secrets-hub"),
    ("identity-administration", "identity"),
]
```

## Query Expansion Test Cases

Queries that should trigger specific expansions:

```python
EXPANSION_CASES = [
    # (query, terms that MUST appear in expansion)
    ("configure spire kubernetes", ["spiffe", "svid", "k8s"]),
    ("conjur secrets rotation", ["dap", "secrets-manager", "rotate"]),
    ("jwt authentication setup", ["bearer-token", "oauth", "configure"]),
    ("pam privileged access", ["privilege-cloud", "pas"]),
    ("kubernetes authenticator", ["k8s", "openshift"]),
    ("certificate management", ["x509", "tls", "pki"]),
    ("cicd integration pipeline", ["jenkins", "gitlab", "github-actions"]),
]
```

## Intent Detection Test Cases

```python
INTENT_CASES = [
    # (query, expected_intent)
    ("how to rotate credentials in privilege cloud", "how-to"),
    ("how do I configure conjur authn-k8s", "how-to"),
    ("what is SPIFFE identity", "explanation"),
    ("explain the difference between Conjur and Secrets Hub", "explanation"),
    ("PVWA error 401 access denied", "troubleshooting"),
    ("fix CONJ00004E authenticator not enabled", "troubleshooting"),
    ("conjur CLI command reference", "reference"),
    ("list of PVWA API endpoints", "reference"),
    ("conjur authentication", "general"),
]
```

## Sample Sitemap XML

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/conjur-authn-k8s.htm</loc>
    <lastmod>2026-02-15T00:00:00Z</lastmod>
  </url>
  <url>
    <loc>https://docs.cyberark.com/privilege-cloud-standard/Latest/en/Content/PASIMP/PVWA-Overview.htm</loc>
    <lastmod>2026-01-20T00:00:00Z</lastmod>
  </url>
  <url>
    <loc>https://docs.cyberark.com/pam-self-hosted/14.2/en/Content/PAS-INST/Installing-CyberArk.htm</loc>
  </url>
  <url>
    <loc>https://docs.cyberark.com/secrets-hub/Latest/en/Content/SecretsHub/sh-overview.htm</loc>
    <lastmod>2026-02-01T00:00:00Z</lastmod>
  </url>
  <url>
    <loc>https://docs.cyberark.com/epm/Latest/en/Content/EPM/EPM-Overview.htm</loc>
    <lastmod>2025-12-15T00:00:00Z</lastmod>
  </url>
</urlset>
```

## Sample Sitemap Index XML

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://docs.cyberark.com/sitemap-conjur.xml</loc>
    <lastmod>2026-02-15T00:00:00Z</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://docs.cyberark.com/sitemap-pam.xml</loc>
    <lastmod>2026-01-20T00:00:00Z</lastmod>
  </sitemap>
</sitemapindex>
```
