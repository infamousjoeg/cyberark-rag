"""
Vector Database Indexer for CyberArk Documentation

This module loads scraped documentation, chunks it intelligently, and indexes it
into a ChromaDB vector database for semantic search.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
from urllib.parse import urlparse

import chromadb
from chromadb.config import Settings as ChromaSettings
import tiktoken
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from cyberark_rag.bm25_index import BM25Index
from cyberark_rag.config import Settings
from cyberark_rag.content_classifier import classify_content_primary
from cyberark_rag.contextual_chunker import contextualize_chunks


class DocumentIndexer:
    """
    Indexes CyberArk documentation into a ChromaDB vector database.
    """

    def __init__(
        self,
        docs_dir: str = None,
        db_dir: str = None,
        collection_name: str = None,
        embedding_model: str = None,
        chunk_size: int = None,
        chunk_overlap: int = None,
        batch_size: int = 100
    ):
        """
        Initialize the document indexer.

        Args:
            docs_dir: Directory containing scraped JSON files (defaults to Settings.DOCS_DIR)
            db_dir: Directory for ChromaDB storage (defaults to Settings.DB_DIR)
            collection_name: Name of the ChromaDB collection
            embedding_model: SentenceTransformer model name
            chunk_size: Target tokens per chunk
            chunk_overlap: Overlap tokens between chunks
            batch_size: Number of chunks to embed at once
        """
        self.docs_dir = Path(docs_dir) if docs_dir else Settings.DOCS_DIR
        self.db_dir = Path(db_dir) if db_dir else Settings.DB_DIR
        self.collection_name = collection_name or Settings.COLLECTION_NAME
        self.chunk_size = chunk_size if chunk_size is not None else Settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else Settings.CHUNK_OVERLAP
        self.batch_size = batch_size

        # Initialize tokenizer for accurate token counting
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

        # Initialize ChromaDB client
        print(f"Initializing ChromaDB at {self.db_dir}...")
        self.client = chromadb.PersistentClient(
            path=str(self.db_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        _model_name = embedding_model or Settings.EMBEDDING_MODEL
        # Initialize embedding model
        print(f"Loading embedding model '{_model_name}'...")
        self.model = SentenceTransformer(_model_name)

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "CyberArk documentation embeddings"}
        )

    def extract_product_category(self, url: str) -> str:
        """
        Extract product category from URL path.

        Args:
            url: Documentation URL

        Returns:
            Product category string
        """
        try:
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split('/') if p]
            # First part of path is usually the product
            if path_parts:
                return path_parts[0]
            return "general"
        except Exception:
            return "general"

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens in

        Returns:
            Number of tokens
        """
        return len(self.tokenizer.encode(text))

    def chunk_text(
        self,
        text: str,
        metadata: Dict
    ) -> List[Tuple[str, Dict]]:
        """
        Split text into chunks with smart boundary detection.

        Args:
            text: Text to chunk
            metadata: Base metadata for chunks

        Returns:
            List of (chunk_text, chunk_metadata) tuples
        """
        chunks = []

        # Split on paragraph boundaries first
        paragraphs = text.split('\n\n')

        current_chunk = []
        current_tokens = 0
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_tokens = self.count_tokens(para)

            # If single paragraph exceeds chunk size, split it further
            if para_tokens > self.chunk_size:
                # Save current chunk if it has content
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunk_meta = metadata.copy()
                    chunk_meta['chunk_index'] = chunk_index
                    chunks.append((chunk_text, chunk_meta))
                    chunk_index += 1
                    current_chunk = []
                    current_tokens = 0

                # Split long paragraph by sentences
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sentence in sentences:
                    sentence_tokens = self.count_tokens(sentence)

                    if current_tokens + sentence_tokens > self.chunk_size:
                        if current_chunk:
                            chunk_text = ' '.join(current_chunk)
                            chunk_meta = metadata.copy()
                            chunk_meta['chunk_index'] = chunk_index
                            chunks.append((chunk_text, chunk_meta))
                            chunk_index += 1

                            # Keep overlap
                            overlap_text = ' '.join(current_chunk[-2:]) if len(current_chunk) >= 2 else ''
                            overlap_tokens = self.count_tokens(overlap_text)

                            if overlap_tokens <= self.chunk_overlap:
                                current_chunk = current_chunk[-2:] if len(current_chunk) >= 2 else []
                                current_tokens = overlap_tokens
                            else:
                                current_chunk = []
                                current_tokens = 0

                    current_chunk.append(sentence)
                    current_tokens += sentence_tokens

            # Normal paragraph fits in chunk size
            elif current_tokens + para_tokens > self.chunk_size:
                # Save current chunk
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunk_meta = metadata.copy()
                    chunk_meta['chunk_index'] = chunk_index
                    chunks.append((chunk_text, chunk_meta))
                    chunk_index += 1

                # Start new chunk with overlap
                overlap_text = current_chunk[-1] if current_chunk else ''
                overlap_tokens = self.count_tokens(overlap_text)

                if overlap_tokens <= self.chunk_overlap:
                    current_chunk = [overlap_text, para] if overlap_text else [para]
                    current_tokens = overlap_tokens + para_tokens
                else:
                    current_chunk = [para]
                    current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens

        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunk_meta = metadata.copy()
            chunk_meta['chunk_index'] = chunk_index
            chunks.append((chunk_text, chunk_meta))

        return chunks

    def load_documents(self) -> List[Dict]:
        """
        Load all JSON documents from docs directory.

        Returns:
            List of document dictionaries
        """
        print(f"Loading documents from {self.docs_dir}...")
        docs = []

        json_files = list(self.docs_dir.glob("*.json"))
        print(f"Found {len(json_files)} JSON files")

        for json_file in tqdm(json_files, desc="Loading files"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
                    docs.append(doc)
            except Exception as e:
                print(f"\nError loading {json_file}: {e}")
                continue

        return docs

    def index_documents(self, documents: List[Dict]) -> None:
        """
        Index documents into ChromaDB.

        Args:
            documents: List of document dictionaries
        """
        print(f"\nChunking and indexing {len(documents)} documents...")

        all_chunks = []
        all_metadata = []
        all_ids = []

        # Track unique products for caching
        unique_products = set()

        chunk_counter = 0

        # Process documents and create chunks
        for doc in tqdm(documents, desc="Processing documents"):
            try:
                url = doc.get('url', '')
                title = doc.get('title', 'Untitled')
                content = doc.get('content', '')

                if not content:
                    continue

                # Base metadata
                product_category = self.extract_product_category(url)
                metadata = {
                    'url': url,
                    'title': title,
                    'product_category': product_category,
                    'content_type': classify_content_primary(url, title, content),
                }

                # Track unique product
                unique_products.add(product_category)

                # Chunk the document
                chunks = self.chunk_text(content, metadata)

                # Add contextual retrieval prefixes
                chunks = contextualize_chunks(chunks, full_content=content)

                for chunk_text, chunk_meta in chunks:
                    all_chunks.append(chunk_text)
                    all_metadata.append(chunk_meta)
                    all_ids.append(f"chunk_{chunk_counter}")
                    chunk_counter += 1

            except Exception as e:
                print(f"\nError processing document {doc.get('url', 'unknown')}: {e}")
                continue

        print(f"\nCreated {len(all_chunks)} chunks from {len(documents)} documents")

        # Batch embed and index
        print(f"Embedding and indexing in batches of {self.batch_size}...")

        for i in tqdm(range(0, len(all_chunks), self.batch_size), desc="Indexing batches"):
            batch_chunks = all_chunks[i:i + self.batch_size]
            batch_metadata = all_metadata[i:i + self.batch_size]
            batch_ids = all_ids[i:i + self.batch_size]

            # Generate embeddings
            embeddings = self.model.encode(
                batch_chunks,
                show_progress_bar=False,
                convert_to_numpy=True
            ).tolist()

            # Add to collection
            self.collection.add(
                embeddings=embeddings,
                documents=batch_chunks,
                metadatas=batch_metadata,
                ids=batch_ids
            )

        print(f"\n✓ Successfully indexed {len(all_chunks)} chunks into ChromaDB!")

        # Build BM25 keyword index from the same chunks
        print("Building BM25 keyword index...")
        bm25 = BM25Index()
        for i, (chunk_text, chunk_meta) in enumerate(zip(all_chunks, all_metadata)):
            bm25.add_document(all_ids[i], chunk_text, chunk_meta)
        bm25.build()
        bm25.save()
        print(f"✓ BM25 index saved to {Settings.BM25_PATH}")

        # Save products cache
        self._save_products_cache(unique_products)

    def _save_products_cache(self, products: set) -> None:
        """
        Save the list of unique products to cache file.

        Args:
            products: Set of unique product category names
        """
        cache_path = self.db_dir / 'products_cache.json'

        cache_data = {
            'products': sorted(list(products)),
            'indexed_at': datetime.utcnow().isoformat() + 'Z',
            'total_products': len(products)
        }

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            print(f"✓ Saved {len(products)} products to cache: {cache_path}")
        except Exception as e:
            print(f"⚠️  Failed to save products cache: {e}")

    def get_stats(self) -> Dict:
        """
        Get statistics about the indexed collection.

        Returns:
            Dictionary with collection statistics
        """
        count = self.collection.count()
        return {
            'total_chunks': count,
            'collection_name': self.collection_name,
            'db_path': str(self.db_dir)
        }

    def run(self) -> None:
        """
        Run the complete indexing pipeline.
        """
        print("=" * 60)
        print("CyberArk Documentation Indexer")
        print("=" * 60)

        # Load documents
        documents = self.load_documents()

        if not documents:
            print("No documents found to index!")
            return

        # Index documents
        self.index_documents(documents)

        # Show stats
        stats = self.get_stats()
        print("\n" + "=" * 60)
        print("Indexing Complete!")
        print("=" * 60)
        print(f"Total chunks indexed: {stats['total_chunks']}")
        print(f"Collection name: {stats['collection_name']}")
        print(f"Database location: {stats['db_path']}")
        print("=" * 60)


def main():
    """
    Main entry point for the indexer.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Index CyberArk documentation into vector database"
    )
    parser.add_argument(
        '--docs-dir',
        default=None,
        help='Directory containing scraped JSON files (default: project scraped_docs)'
    )
    parser.add_argument(
        '--db-dir',
        default=None,
        help='Directory for ChromaDB storage (default: project chroma_db)'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=None,
        help=f'Target tokens per chunk (default: {Settings.CHUNK_SIZE})'
    )
    parser.add_argument(
        '--chunk-overlap',
        type=int,
        default=None,
        help=f'Overlap tokens between chunks (default: {Settings.CHUNK_OVERLAP})'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for embedding (default: 100)'
    )

    args = parser.parse_args()

    indexer = DocumentIndexer(
        docs_dir=args.docs_dir,
        db_dir=args.db_dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        batch_size=args.batch_size
    )

    indexer.run()


if __name__ == "__main__":
    main()
