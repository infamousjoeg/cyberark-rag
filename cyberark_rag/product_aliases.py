"""
Product Aliases Resolution

Maps raw product_category values to canonical product names and provides
filtering by category (product, deprecated, metadata, navigation).
"""

import yaml
from typing import Dict, List, Optional, Set
from pathlib import Path

from cyberark_rag.config import Settings


class ProductAliasResolver:
    """
    Resolves product aliases and provides canonical product naming.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the resolver with product aliases configuration.

        Args:
            config_path: Path to product_aliases.yaml (defaults to project root)
        """
        if config_path is None:
            config_path = Settings.PRODUCT_ALIASES_PATH

        self.config_path = Path(config_path)
        self.aliases_data = self._load_config()
        self.alias_to_canonical = self._build_alias_map()

    def _load_config(self) -> Dict:
        """Load the product aliases YAML configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Product aliases config not found: {self.config_path}"
            )

        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _build_alias_map(self) -> Dict[str, str]:
        """
        Build reverse mapping from alias → canonical name.

        Returns:
            Dictionary mapping any alias to its canonical name
        """
        alias_map = {}

        for canonical_name, config in self.aliases_data.items():
            aliases = config.get('aliases', [])
            for alias in aliases:
                alias_map[alias.lower()] = canonical_name

        return alias_map

    def resolve(self, raw_name: str) -> str:
        """
        Resolve a raw product name to its canonical name.

        Args:
            raw_name: Raw product name from URL/metadata

        Returns:
            Canonical product name (or raw_name if no mapping exists)
        """
        return self.alias_to_canonical.get(raw_name.lower(), raw_name)

    def get_display_name(self, canonical_or_raw: str) -> str:
        """
        Get the human-readable display name.

        Args:
            canonical_or_raw: Canonical name or raw alias

        Returns:
            Display name for presentation
        """
        # First resolve to canonical if it's an alias
        canonical = self.resolve(canonical_or_raw)

        # Get display name from config
        if canonical in self.aliases_data:
            return self.aliases_data[canonical].get('display_name', canonical)

        # Fallback to canonical name with title case
        return canonical.replace('-', ' ').replace('_', ' ').title()

    def get_category(self, canonical_or_raw: str) -> str:
        """
        Get the category of a product.

        Args:
            canonical_or_raw: Canonical name or raw alias

        Returns:
            Category: "product", "deprecated", "metadata", or "navigation"
        """
        canonical = self.resolve(canonical_or_raw)

        if canonical in self.aliases_data:
            return self.aliases_data[canonical].get('category', 'unknown')

        return 'unknown'

    def get_description(self, canonical_or_raw: str) -> str:
        """
        Get the description of a product.

        Args:
            canonical_or_raw: Canonical name or raw alias

        Returns:
            Product description
        """
        canonical = self.resolve(canonical_or_raw)

        if canonical in self.aliases_data:
            return self.aliases_data[canonical].get('description', '')

        return ''

    def get_all_canonical_names(
        self,
        categories: Optional[List[str]] = None
    ) -> List[str]:
        """
        Get all canonical product names, optionally filtered by category.

        Args:
            categories: List of categories to include (e.g., ['product'])
                       If None, includes all categories

        Returns:
            Sorted list of canonical product names
        """
        if categories is None:
            return sorted(self.aliases_data.keys())

        filtered = [
            name for name, config in self.aliases_data.items()
            if config.get('category') in categories
        ]

        return sorted(filtered)

    def get_products_only(self) -> List[str]:
        """
        Get only active products (excludes deprecated, metadata, navigation).

        Returns:
            Sorted list of active product names
        """
        return self.get_all_canonical_names(categories=['product'])

    def resolve_list(
        self,
        raw_names: List[str],
        categories: Optional[List[str]] = None
    ) -> List[str]:
        """
        Resolve a list of raw names to canonical names with optional filtering.

        Args:
            raw_names: List of raw product names
            categories: Optional category filter

        Returns:
            Sorted list of unique canonical names
        """
        canonical_names = set()

        for raw_name in raw_names:
            canonical = self.resolve(raw_name)
            category = self.get_category(canonical)

            # Apply category filter if specified
            if categories is None or category in categories:
                canonical_names.add(canonical)

        return sorted(canonical_names)

    def get_product_info(self, canonical_or_raw: str) -> Dict:
        """
        Get complete information about a product.

        Args:
            canonical_or_raw: Canonical name or raw alias

        Returns:
            Dictionary with display_name, category, description, aliases
        """
        canonical = self.resolve(canonical_or_raw)

        if canonical in self.aliases_data:
            info = self.aliases_data[canonical].copy()
            info['canonical_name'] = canonical
            return info

        # Unknown product
        return {
            'canonical_name': canonical,
            'display_name': self.get_display_name(canonical),
            'category': 'unknown',
            'description': '',
            'aliases': [canonical]
        }


# Singleton instance
_resolver = None


def get_resolver() -> ProductAliasResolver:
    """Get or create the global product alias resolver instance."""
    global _resolver
    if _resolver is None:
        _resolver = ProductAliasResolver()
    return _resolver


def resolve_product(raw_name: str) -> str:
    """
    Convenience function to resolve a product name.

    Args:
        raw_name: Raw product name

    Returns:
        Canonical product name
    """
    resolver = get_resolver()
    return resolver.resolve(raw_name)


def get_active_products() -> List[str]:
    """
    Convenience function to get only active products.

    Returns:
        Sorted list of active product canonical names
    """
    resolver = get_resolver()
    return resolver.get_products_only()
