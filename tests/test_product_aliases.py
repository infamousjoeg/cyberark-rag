"""Tests for product alias resolution and canonical naming."""

import pytest

from cyberark_rag.product_aliases import ProductAliasResolver, get_resolver


@pytest.fixture(scope="module")
def resolver() -> ProductAliasResolver:
    return ProductAliasResolver()


class TestAliasResolution:
    """Verify raw product names resolve to canonical names."""

    @pytest.mark.parametrize("raw,canonical", [
        ("PAS", "pam-self-hosted"),
        ("pas", "pam-self-hosted"),
        ("epm", "endpoint-privilege-manager"),
        ("dpa", "secure-infrastructure-access"),
        ("alero", "remote-access"),
    ])
    def test_alias_resolves(self, resolver, raw, canonical):
        assert resolver.resolve(raw) == canonical

    def test_canonical_maps_to_itself(self, resolver):
        # A canonical name should resolve to itself
        canonical = resolver.resolve("pam-self-hosted")
        assert resolver.resolve(canonical) == canonical

    def test_unknown_alias_returns_original(self, resolver):
        assert resolver.resolve("nonexistent-product-xyz") == "nonexistent-product-xyz"


class TestDisplayName:
    """Verify display name resolution."""

    def test_known_product_has_display_name(self, resolver):
        display = resolver.get_display_name("pam-self-hosted")
        assert display  # non-empty string
        assert len(display) > 0

    def test_all_products_have_display_names(self, resolver):
        products = resolver.get_products_only()
        for product in products:
            display = resolver.get_display_name(product)
            assert display, f"Product '{product}' has no display name"


class TestCategoryFiltering:
    """Verify product category filtering."""

    def test_get_products_only_excludes_deprecated(self, resolver):
        products = resolver.get_products_only()
        for product in products:
            category = resolver.get_category(product)
            assert category == "product", f"'{product}' has category '{category}', expected 'product'"

    def test_get_all_includes_all_categories(self, resolver):
        all_names = resolver.get_all_canonical_names()
        products_only = resolver.get_products_only()
        # All canonical names should be >= products-only
        assert len(all_names) >= len(products_only)

    def test_unknown_product_has_unknown_category(self, resolver):
        assert resolver.get_category("nonexistent-xyz") == "unknown"


class TestProductInfo:
    """Verify complete product info retrieval."""

    def test_known_product_info(self, resolver):
        info = resolver.get_product_info("pam-self-hosted")
        assert "canonical_name" in info
        assert "display_name" in info
        assert info["canonical_name"] == "pam-self-hosted"

    def test_unknown_product_info_has_defaults(self, resolver):
        info = resolver.get_product_info("nonexistent-xyz")
        assert info["canonical_name"] == "nonexistent-xyz"
        assert info["category"] == "unknown"


class TestConvenienceFunction:
    """Test module-level get_resolver() singleton."""

    def test_get_resolver_returns_instance(self):
        resolver = get_resolver()
        assert isinstance(resolver, ProductAliasResolver)
