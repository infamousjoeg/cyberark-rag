"""
Shared pytest fixtures for CyberArk RAG tests.

Session-scoped fixtures for expensive resources (embedding model, YAML parsing).
Module-scoped fixtures for shared data structures (BM25 index).
Function-scoped fixtures for mutable state (scraper state, tmp dirs).
"""

import pytest

from cyberark_rag.bm25_index import BM25Index

# ---------------------------------------------------------------------------
# Domain-specific test content (from test-domain-data.md)
# ---------------------------------------------------------------------------

CONJUR_K8S_AUTH_CONTENT = (
    "The Conjur Kubernetes Authenticator enables workloads running in Kubernetes "
    "to authenticate to Conjur using their Kubernetes identity. This eliminates "
    "the need for static API keys or passwords stored in pods.\n\n"
    "## Prerequisites\n\n"
    "Before configuring the Kubernetes authenticator, ensure the following:\n"
    "- Conjur Cloud or Conjur Enterprise (v12.0+) is deployed and accessible\n"
    "- A Conjur policy defining the authenticator service exists\n"
    "- The Conjur authenticator client is deployed as a sidecar or init container\n\n"
    "## Configuration Steps\n\n"
    "Step 1: Define the authenticator in Conjur policy.\n\n"
    "Step 2: Load the policy and set the CA certificate variables.\n\n"
    "Step 3: Deploy the authenticator client as a sidecar container.\n\n"
    "## Troubleshooting\n\n"
    "Error CONJ00004E: The authenticator service is not enabled. "
    "Verify the CONJUR_AUTHENTICATORS environment variable includes authn-k8s/my-cluster.\n\n"
    "Error CONJ00007E: Certificate validation failed. "
    "Check that the CA certificate matches the Kubernetes API server certificate."
)

PVWA_ADMIN_CONTENT = (
    "The Password Vault Web Access (PVWA) provides a web interface for managing "
    "privileged accounts. Administrators access PVWA at https://<pvwa-server>/PasswordVault.\n\n"
    "## Common Administration Tasks\n\n"
    "### Resetting the PVWA Admin Password\n\n"
    "1. Connect to the PVWA server via RDP\n"
    "2. Open the PVWA Configuration tool (PVConfiguration.exe)\n"
    "3. Navigate to the Administration section\n"
    "4. Select Reset Admin Password\n\n"
    "### PVWA Error Codes\n\n"
    "| Error Code | Description | Resolution |\n"
    "|---|---|---|\n"
    "| ITATS001E | Session timeout | Clear browser cache and re-authenticate |\n"
    "| PVWA401 | Authentication failed | Verify credentials and LDAP integration |\n"
    "| PASWS034E | Safe not found | Check Safe permissions in PrivateArk |"
)

SPIFFE_OVERVIEW_CONTENT = (
    "SPIFFE (Secure Production Identity Framework For Everyone) provides a standard "
    "for identifying and securing workloads across heterogeneous environments. "
    "CyberArk implements SPIFFE through its Secure Workload Access solution.\n\n"
    "## Key Concepts\n\n"
    "- SPIFFE ID: A URI-formatted identity (spiffe://trust-domain/workload-path)\n"
    "- SVID: A SPIFFE Verifiable Identity Document, either X.509 or JWT\n"
    "- SPIRE: The SPIFFE Runtime Environment, an open-source implementation\n\n"
    "## Integration with CyberArk\n\n"
    "CyberArk extends SPIFFE/SPIRE with enterprise-grade key management, "
    "audit logging, and centralized policy enforcement through the Identity Security Platform."
)

SECRETS_HUB_CONTENT = (
    "Secrets Hub enables centralized secrets management across hybrid and multi-cloud "
    "environments. It provides a unified interface for managing secrets stored in "
    "CyberArk PAM, AWS Secrets Manager, Azure Key Vault, and GCP Secret Manager.\n\n"
    "## Getting Started\n\n"
    "Step 1: Configure your target vault connections.\n"
    "Step 2: Define sync policies for secret rotation.\n"
    "Step 3: Enable audit logging for compliance."
)

EPM_POLICY_CONTENT = (
    "Endpoint Privilege Manager (EPM) enables organizations to enforce least privilege "
    "policies on endpoints. EPM provides application control, privilege management, "
    "and credential theft protection.\n\n"
    "## Policy Configuration\n\n"
    "To configure an EPM policy:\n"
    "1. Navigate to the EPM Console\n"
    "2. Select Policies > Application Control\n"
    "3. Define allow/deny rules based on application properties"
)


# ---------------------------------------------------------------------------
# Sample URLs by product
# ---------------------------------------------------------------------------

SAMPLE_URLS = {
    "conjur-cloud": "https://docs.cyberark.com/conjur-cloud/Latest/en/Content/Conjur/conjur-authn-k8s.htm",
    "privilege-cloud": "https://docs.cyberark.com/privilege-cloud-standard/Latest/en/Content/PASIMP/PVWA-Overview.htm",
    "pam-self-hosted": "https://docs.cyberark.com/pam-self-hosted/14.2/en/Content/PAS-INST/Installing-CyberArk.htm",
    "secrets-hub": "https://docs.cyberark.com/secrets-hub/Latest/en/Content/SecretsHub/sh-overview.htm",
    "epm": "https://docs.cyberark.com/epm/Latest/en/Content/EPM/EPM-Overview.htm",
}


# ---------------------------------------------------------------------------
# Session-scoped fixtures (expensive, read-only)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sample_scraped_docs() -> list:
    """Five realistic CyberArk docs matching the scraped JSON format."""
    return [
        {
            "url": SAMPLE_URLS["conjur-cloud"],
            "title": "Kubernetes Authenticator",
            "content": CONJUR_K8S_AUTH_CONTENT,
            "scraped_at": "2026-02-01T00:00:00Z",
        },
        {
            "url": SAMPLE_URLS["privilege-cloud"],
            "title": "PVWA Administration",
            "content": PVWA_ADMIN_CONTENT,
            "scraped_at": "2026-01-20T00:00:00Z",
        },
        {
            "url": SAMPLE_URLS["pam-self-hosted"],
            "title": "Installing CyberArk",
            "content": "Install the CyberArk PAM solution on Windows Server 2019 or later.\n\n"
                       "## Prerequisites\n\nEnsure .NET Framework 4.8 is installed.\n\n"
                       "Step 1: Run the installer.\nStep 2: Accept the EULA.\nStep 3: Configure the vault.",
            "scraped_at": "2026-01-15T00:00:00Z",
        },
        {
            "url": SAMPLE_URLS["secrets-hub"],
            "title": "Secrets Hub Overview",
            "content": SECRETS_HUB_CONTENT,
            "scraped_at": "2026-02-01T00:00:00Z",
        },
        {
            "url": SAMPLE_URLS["epm"],
            "title": "EPM Overview",
            "content": EPM_POLICY_CONTENT,
            "scraped_at": "2025-12-15T00:00:00Z",
        },
    ]


@pytest.fixture(scope="session")
def sample_sitemap_xml() -> bytes:
    """Valid sitemap XML with 5 URL entries."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
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
</urlset>"""


@pytest.fixture(scope="session")
def sample_sitemap_index_xml() -> bytes:
    """Sitemap index XML referencing 2 child sitemaps."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://docs.cyberark.com/sitemap-conjur.xml</loc>
    <lastmod>2026-02-15T00:00:00Z</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://docs.cyberark.com/sitemap-pam.xml</loc>
    <lastmod>2026-01-20T00:00:00Z</lastmod>
  </sitemap>
</sitemapindex>"""


@pytest.fixture(scope="session")
def vector_search_results() -> list:
    """Simulated vector search output (5 results, decreasing relevance)."""
    return [
        {"url": "https://docs.cyberark.com/cc/page1", "chunk_index": 0, "title": "Conjur Auth",
         "content": "Configure Conjur Kubernetes authenticator", "relevance_score": 0.92,
         "product_category": "conjur-cloud"},
        {"url": "https://docs.cyberark.com/cc/page2", "chunk_index": 0, "title": "JWT Setup",
         "content": "JWT authentication configuration", "relevance_score": 0.88,
         "product_category": "conjur-cloud"},
        {"url": "https://docs.cyberark.com/pc/page3", "chunk_index": 1, "title": "PVWA Config",
         "content": "PVWA administration overview", "relevance_score": 0.85,
         "product_category": "privilege-cloud"},
        {"url": "https://docs.cyberark.com/pam/page4", "chunk_index": 0, "title": "Install PAM",
         "content": "Install the CyberArk PAM solution", "relevance_score": 0.80,
         "product_category": "pam-self-hosted"},
        {"url": "https://docs.cyberark.com/sh/page5", "chunk_index": 0, "title": "Secrets Hub",
         "content": "Centralized secrets management", "relevance_score": 0.75,
         "product_category": "secrets-hub"},
    ]


@pytest.fixture(scope="session")
def bm25_search_results() -> list:
    """Simulated BM25 output. 2 overlap with vector_search_results, 3 unique."""
    return [
        # Overlaps with vector result page1
        {"url": "https://docs.cyberark.com/cc/page1", "chunk_index": 0, "title": "Conjur Auth",
         "content": "Configure Conjur Kubernetes authenticator", "relevance_score": 4.5,
         "product_category": "conjur-cloud"},
        # Unique BM25 result
        {"url": "https://docs.cyberark.com/cc/page6", "chunk_index": 0, "title": "Error Codes",
         "content": "CONJ00004E authenticator not enabled", "relevance_score": 3.8,
         "product_category": "conjur-cloud"},
        # Overlaps with vector result page3
        {"url": "https://docs.cyberark.com/pc/page3", "chunk_index": 1, "title": "PVWA Config",
         "content": "PVWA administration overview", "relevance_score": 3.2,
         "product_category": "privilege-cloud"},
        # Unique BM25 result
        {"url": "https://docs.cyberark.com/pc/page7", "chunk_index": 0, "title": "PVWA Errors",
         "content": "PVWA error 401 unauthorized", "relevance_score": 2.9,
         "product_category": "privilege-cloud"},
        # Unique BM25 result
        {"url": "https://docs.cyberark.com/epm/page8", "chunk_index": 0, "title": "EPM Policy",
         "content": "EPM least-privilege policy configuration", "relevance_score": 2.1,
         "product_category": "epm"},
    ]


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def bm25_with_docs() -> BM25Index:
    """BM25 index with 5 docs across different products for filtering tests."""
    idx = BM25Index(k1=1.5, b=0.75)
    idx.add_document(
        "doc1",
        "configure privilege-cloud PVWA for kubernetes deployment",
        {"product_category": "privilege-cloud", "url": SAMPLE_URLS["privilege-cloud"],
         "title": "Configure PVWA", "chunk_index": 0},
    )
    idx.add_document(
        "doc2",
        "conjur cloud authentication JWT token setup guide",
        {"product_category": "conjur-cloud", "url": SAMPLE_URLS["conjur-cloud"],
         "title": "JWT Auth", "chunk_index": 0},
    )
    idx.add_document(
        "doc3",
        "PVWA error 401 unauthorized access troubleshooting steps ITATS001E",
        {"product_category": "privilege-cloud", "url": SAMPLE_URLS["privilege-cloud"],
         "title": "Error 401", "chunk_index": 1},
    )
    idx.add_document(
        "doc4",
        "install credential provider on linux server for AAM-DAP integration",
        {"product_category": "pam-self-hosted", "url": SAMPLE_URLS["pam-self-hosted"],
         "title": "Credential Provider", "chunk_index": 0},
    )
    idx.add_document(
        "doc5",
        "SPIFFE SVID identity verification SPIRE runtime environment",
        {"product_category": "conjur-cloud", "url": SAMPLE_URLS["conjur-cloud"],
         "title": "SPIFFE Overview", "chunk_index": 2},
    )
    idx.build()
    return idx


# ---------------------------------------------------------------------------
# Function-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bm25_empty() -> BM25Index:
    """Fresh BM25Index with no documents."""
    return BM25Index()


@pytest.fixture(scope="session")
def chunk_with_metadata():
    """Factory fixture for creating (text, metadata) tuples."""
    def _make(
        text: str = "sample chunk",
        url: str = "https://docs.cyberark.com/test",
        title: str = "Test",
        product: str = "conjur-cloud",
        chunk_index: int = 0,
    ):
        return (text, {
            "url": url,
            "title": title,
            "product_category": product,
            "chunk_index": chunk_index,
        })
    return _make
