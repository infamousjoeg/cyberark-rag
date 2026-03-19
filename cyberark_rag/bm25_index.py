"""
Okapi BM25 Keyword Index for CyberArk Documentation

Provides exact-match keyword search to complement vector search.
Critical for CyberArk-specific terms like error codes (PVWA error 401),
API parameters, and hyphenated product names (privilege-cloud, AAM-DAP).

Combined with vector search via Reciprocal Rank Fusion, this reduces
retrieval failures by 49% (Anthropic Contextual Retrieval research).
"""

import math
import pickle
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cyberark_rag.config import Settings
from cyberark_rag.logging_config import setup_logging

logger = setup_logging(__name__)

# Tokenizer preserves hyphenated terms (e.g., privilege-cloud, AAM-DAP)
TOKEN_PATTERN = re.compile(r"\b[\w][\w\-]*[\w]\b|\b\w\b")


def tokenize(text: str) -> List[str]:
    """
    Tokenize text preserving hyphenated compound terms.

    Args:
        text: Text to tokenize

    Returns:
        List of lowercase tokens
    """
    return [t.lower() for t in TOKEN_PATTERN.findall(text)]


class BM25Index:
    """Okapi BM25 keyword index with product filtering."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 index.

        Args:
            k1: Term frequency saturation parameter (default: 1.5)
            b: Length normalization parameter (default: 0.75)
        """
        self.k1 = k1
        self.b = b

        # Document storage
        self.doc_ids: List[str] = []
        self.doc_tokens: List[List[str]] = []
        self.doc_metadata: List[Dict] = []
        self.doc_lengths: List[int] = []

        # Index structures (populated by build())
        self.avg_dl: float = 0.0
        self.n_docs: int = 0
        self.df: Dict[str, int] = {}  # Document frequency per term
        self.tf: List[Dict[str, int]] = []  # Term frequency per document
        self._built: bool = False

    @property
    def doc_count(self) -> int:
        """Return the number of documents in the index."""
        return self.n_docs

    def add_document(self, doc_id: str, text: str, metadata: Dict = None) -> None:
        """
        Add a document to the index (pre-build).

        Args:
            doc_id: Unique document identifier
            text: Document text to index
            metadata: Optional metadata dict
        """
        tokens = tokenize(text)
        self.doc_ids.append(doc_id)
        self.doc_tokens.append(tokens)
        self.doc_metadata.append(metadata or {})
        self.doc_lengths.append(len(tokens))

    def build(self) -> None:
        """Build the BM25 index structures from added documents."""
        self.n_docs = len(self.doc_ids)
        if self.n_docs == 0:
            self._built = True
            return

        self.avg_dl = sum(self.doc_lengths) / self.n_docs

        # Build term frequency per document
        self.tf = []
        for tokens in self.doc_tokens:
            self.tf.append(dict(Counter(tokens)))

        # Build document frequency
        self.df = defaultdict(int)
        for tf_dict in self.tf:
            for term in tf_dict:
                self.df[term] += 1

        self._built = True
        logger.info("BM25 index built: %d documents, %d unique terms",
                     self.n_docs, len(self.df))

    def _score(self, query_tokens: List[str], doc_idx: int) -> float:
        """Compute BM25 score for a single document."""
        score = 0.0
        dl = self.doc_lengths[doc_idx]
        tf_dict = self.tf[doc_idx]

        for term in query_tokens:
            if term not in tf_dict:
                continue

            tf = tf_dict[term]
            df = self.df.get(term, 0)

            # IDF with floor to avoid negative values
            idf = max(
                0.0,
                math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1.0),
            )

            # BM25 TF normalization
            tf_norm = (tf * (self.k1 + 1)) / (
                tf + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
            )

            score += idf * tf_norm

        return score

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_product: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search the BM25 index.

        Args:
            query: Search query string
            top_k: Number of results to return
            filter_product: Optional product_category filter

        Returns:
            List of result dicts with doc_id, score, metadata
        """
        if not self._built:
            raise RuntimeError("Index not built. Call build() first.")

        if self.n_docs == 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scored: List[Tuple[float, int]] = []
        for idx in range(self.n_docs):
            # Apply product filter
            if filter_product:
                doc_product = self.doc_metadata[idx].get("product_category", "")
                if doc_product != filter_product:
                    continue

            score = self._score(query_tokens, idx)
            if score > 0:
                scored.append((score, idx))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, idx in scored[:top_k]:
            results.append({
                "doc_id": self.doc_ids[idx],
                "score": score,
                "metadata": self.doc_metadata[idx],
            })

        return results

    def save(self, path: Path = None) -> None:
        """
        Save index to disk.

        Omits doc_tokens (only needed during build) to reduce file size
        and memory footprint on constrained deployments.

        Args:
            path: File path (defaults to Settings.BM25_PATH)
        """
        path = path or Settings.BM25_PATH
        path.parent.mkdir(parents=True, exist_ok=True)

        # Strip metadata to essentials only (url, title, product_category,
        # chunk_index, content_type) to reduce memory
        slim_metadata = []
        keep_keys = {"url", "title", "product_category", "chunk_index",
                     "content_type", "original_text"}
        for meta in self.doc_metadata:
            slim_metadata.append({k: v for k, v in meta.items()
                                  if k in keep_keys})

        data = {
            "k1": self.k1,
            "b": self.b,
            "doc_ids": self.doc_ids,
            # doc_tokens omitted -- only needed during build(), not search
            "doc_metadata": slim_metadata,
            "doc_lengths": self.doc_lengths,
            "avg_dl": self.avg_dl,
            "n_docs": self.n_docs,
            "df": dict(self.df),
            "tf": self.tf,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info("BM25 index saved to %s (%d docs)", path, self.n_docs)

    @classmethod
    def load(cls, path: Path = None) -> "BM25Index":
        """
        Load index from disk.

        Args:
            path: File path (defaults to Settings.BM25_PATH)

        Returns:
            Loaded BM25Index instance
        """
        path = path or Settings.BM25_PATH
        with open(path, "rb") as f:
            data = pickle.load(f)

        idx = cls(k1=data["k1"], b=data["b"])
        idx.doc_ids = data["doc_ids"]
        idx.doc_tokens = data.get("doc_tokens", [])  # may be omitted in slim format
        idx.doc_metadata = data["doc_metadata"]
        idx.doc_lengths = data["doc_lengths"]
        idx.avg_dl = data["avg_dl"]
        idx.n_docs = data["n_docs"]
        idx.df = data["df"]
        idx.tf = data["tf"]
        idx._built = True

        logger.info("BM25 index loaded from %s (%d docs)", path, idx.n_docs)
        return idx
