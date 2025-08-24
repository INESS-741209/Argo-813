"""
Vector Store Implementation for ARGO System
Handles embeddings, similarity search, and semantic knowledge retrieval
"""

import json
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib
import asyncio
from enum import Enum
import logging
from sklearn.metrics.pairwise import cosine_similarity
import faiss
import pickle
import os

logger = logging.getLogger(__name__)


class VectorIndexType(Enum):
    """Types of vector indices"""
    FLAT = "flat"  # Brute force search
    HNSW = "hnsw"  # Hierarchical Navigable Small World
    IVF = "ivf"    # Inverted File Index
    LSH = "lsh"    # Locality Sensitive Hashing


class EmbeddingModel(Enum):
    """Supported embedding models"""
    OPENAI_ADA = "text-embedding-ada-002"
    OPENAI_3_SMALL = "text-embedding-3-small"
    OPENAI_3_LARGE = "text-embedding-3-large"
    SENTENCE_TRANSFORMER = "all-MiniLM-L6-v2"
    CUSTOM = "custom"


@dataclass
class VectorDocument:
    """Document with vector embedding"""
    id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any]
    timestamp: datetime
    source: str
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "confidence": self.confidence
        }


@dataclass
class SearchResult:
    """Vector search result"""
    document: VectorDocument
    score: float
    rank: int
    explanation: Optional[str] = None


class VectorStore:
    """
    Main Vector Store Manager for ARGO
    Handles embeddings, indexing, and similarity search
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Vector Store
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or self._default_config()
        self.indices: Dict[str, faiss.Index] = {}
        self.documents: Dict[str, Dict[str, VectorDocument]] = {}
        self.metadata_index: Dict[str, Dict[str, List[str]]] = {}
        self.dimension = self.config.get("dimension", 768)
        self.index_type = VectorIndexType(self.config.get("index_type", "hnsw"))
        self.persistence_path = self.config.get("persistence_path", "./vector_store")
        
        # Initialize indices for different collections
        self._initialize_indices()
        
        # Load persisted data if exists
        self._load_persisted_data()
        
        logger.info(f"Vector Store initialized with {self.index_type.value} index, dimension={self.dimension}")
    
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration"""
        return {
            "dimension": 768,  # Default embedding dimension
            "index_type": "hnsw",
            "hnsw_m": 32,  # HNSW connectivity parameter
            "hnsw_ef_construction": 200,  # HNSW construction parameter
            "hnsw_ef_search": 100,  # HNSW search parameter
            "ivf_nlist": 100,  # IVF number of clusters
            "persistence_path": "./vector_store",
            "collections": [
                "knowledge",
                "patterns",
                "contexts",
                "goals",
                "tasks"
            ],
            "batch_size": 1000,
            "similarity_threshold": 0.7
        }
    
    def _initialize_indices(self):
        """Initialize FAISS indices for collections"""
        collections = self.config.get("collections", ["default"])
        
        for collection in collections:
            if self.index_type == VectorIndexType.FLAT:
                # Flat index for exact search
                index = faiss.IndexFlatL2(self.dimension)
            elif self.index_type == VectorIndexType.HNSW:
                # HNSW for fast approximate search
                index = faiss.IndexHNSWFlat(
                    self.dimension,
                    self.config.get("hnsw_m", 32)
                )
                index.hnsw.efConstruction = self.config.get("hnsw_ef_construction", 200)
                index.hnsw.efSearch = self.config.get("hnsw_ef_search", 100)
            elif self.index_type == VectorIndexType.IVF:
                # IVF for large-scale search
                quantizer = faiss.IndexFlatL2(self.dimension)
                index = faiss.IndexIVFFlat(
                    quantizer,
                    self.dimension,
                    self.config.get("ivf_nlist", 100)
                )
            else:
                # Default to flat index
                index = faiss.IndexFlatL2(self.dimension)
            
            self.indices[collection] = index
            self.documents[collection] = {}
            self.metadata_index[collection] = {}
            
            logger.info(f"Initialized {self.index_type.value} index for collection: {collection}")
    
    async def add_document(
        self,
        collection: str,
        content: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "unknown",
        confidence: float = 1.0
    ) -> str:
        """
        Add document to vector store
        
        Args:
            collection: Collection name
            content: Document content
            embedding: Pre-computed embedding (optional)
            metadata: Document metadata
            source: Document source
            confidence: Confidence score
            
        Returns:
            Document ID
        """
        # Generate document ID
        doc_id = self._generate_id(content)
        
        # Get or compute embedding
        if embedding is None:
            embedding = await self._compute_embedding(content)
        
        # Create document
        document = VectorDocument(
            id=doc_id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            timestamp=datetime.utcnow(),
            source=source,
            confidence=confidence
        )
        
        # Add to index
        await self._add_to_index(collection, document)
        
        # Update metadata index
        self._update_metadata_index(collection, document)
        
        logger.info(f"Added document {doc_id} to collection {collection}")
        
        return doc_id
    
    async def add_batch(
        self,
        collection: str,
        documents: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Add batch of documents
        
        Args:
            collection: Collection name
            documents: List of document dictionaries
            
        Returns:
            List of document IDs
        """
        doc_ids = []
        batch_embeddings = []
        batch_documents = []
        
        for doc_data in documents:
            # Generate ID
            doc_id = self._generate_id(doc_data["content"])
            
            # Get or compute embedding
            embedding = doc_data.get("embedding")
            if embedding is None:
                embedding = await self._compute_embedding(doc_data["content"])
            
            # Create document
            document = VectorDocument(
                id=doc_id,
                content=doc_data["content"],
                embedding=embedding,
                metadata=doc_data.get("metadata", {}),
                timestamp=datetime.utcnow(),
                source=doc_data.get("source", "unknown"),
                confidence=doc_data.get("confidence", 1.0)
            )
            
            batch_embeddings.append(embedding)
            batch_documents.append(document)
            doc_ids.append(doc_id)
        
        # Batch add to index
        if batch_embeddings:
            embeddings_array = np.array(batch_embeddings, dtype=np.float32)
            self.indices[collection].add(embeddings_array)
            
            # Store documents
            for doc in batch_documents:
                self.documents[collection][doc.id] = doc
                self._update_metadata_index(collection, doc)
        
        logger.info(f"Added batch of {len(doc_ids)} documents to collection {collection}")
        
        return doc_ids
    
    async def search(
        self,
        collection: str,
        query: Union[str, List[float]],
        k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        threshold: Optional[float] = None
    ) -> List[SearchResult]:
        """
        Search for similar documents
        
        Args:
            collection: Collection to search
            query: Query text or embedding
            k: Number of results
            filters: Metadata filters
            threshold: Similarity threshold
            
        Returns:
            List of search results
        """
        # Get query embedding
        if isinstance(query, str):
            query_embedding = await self._compute_embedding(query)
        else:
            query_embedding = query
        
        # Convert to numpy array
        query_array = np.array([query_embedding], dtype=np.float32)
        
        # Search in index
        distances, indices = self.indices[collection].search(query_array, k)
        
        # Build results
        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx == -1:  # No more results
                break
            
            # Convert distance to similarity score
            score = 1.0 / (1.0 + dist)
            
            # Apply threshold
            if threshold and score < threshold:
                continue
            
            # Get document
            doc_id = list(self.documents[collection].keys())[idx]
            document = self.documents[collection][doc_id]
            
            # Apply filters
            if filters and not self._match_filters(document, filters):
                continue
            
            results.append(SearchResult(
                document=document,
                score=score,
                rank=i + 1,
                explanation=f"Cosine similarity: {score:.4f}"
            ))
        
        return results
    
    async def hybrid_search(
        self,
        collection: str,
        query: str,
        k: int = 10,
        keyword_weight: float = 0.3,
        vector_weight: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Hybrid search combining keyword and vector search
        
        Args:
            collection: Collection to search
            query: Query text
            k: Number of results
            keyword_weight: Weight for keyword search
            vector_weight: Weight for vector search
            filters: Metadata filters
            
        Returns:
            List of search results
        """
        # Vector search
        vector_results = await self.search(collection, query, k * 2, filters)
        
        # Keyword search
        keyword_results = self._keyword_search(collection, query, k * 2, filters)
        
        # Combine results
        combined_scores = {}
        all_documents = {}
        
        # Add vector search results
        for result in vector_results:
            doc_id = result.document.id
            combined_scores[doc_id] = result.score * vector_weight
            all_documents[doc_id] = result.document
        
        # Add keyword search results
        for result in keyword_results:
            doc_id = result.document.id
            if doc_id in combined_scores:
                combined_scores[doc_id] += result.score * keyword_weight
            else:
                combined_scores[doc_id] = result.score * keyword_weight
                all_documents[doc_id] = result.document
        
        # Sort by combined score
        sorted_results = sorted(
            combined_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:k]
        
        # Build final results
        results = []
        for i, (doc_id, score) in enumerate(sorted_results):
            results.append(SearchResult(
                document=all_documents[doc_id],
                score=score,
                rank=i + 1,
                explanation=f"Hybrid score: {score:.4f} (vector: {vector_weight}, keyword: {keyword_weight})"
            ))
        
        return results
    
    def _keyword_search(
        self,
        collection: str,
        query: str,
        k: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Simple keyword search
        
        Args:
            collection: Collection to search
            query: Query text
            k: Number of results
            filters: Metadata filters
            
        Returns:
            List of search results
        """
        query_terms = set(query.lower().split())
        scores = []
        
        for doc_id, document in self.documents[collection].items():
            # Apply filters
            if filters and not self._match_filters(document, filters):
                continue
            
            # Calculate keyword match score
            doc_terms = set(document.content.lower().split())
            common_terms = query_terms.intersection(doc_terms)
            
            if common_terms:
                score = len(common_terms) / len(query_terms)
                scores.append((document, score))
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Build results
        results = []
        for i, (document, score) in enumerate(scores[:k]):
            results.append(SearchResult(
                document=document,
                score=score,
                rank=i + 1,
                explanation=f"Keyword match score: {score:.4f}"
            ))
        
        return results
    
    async def update_document(
        self,
        collection: str,
        doc_id: str,
        content: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update existing document
        
        Args:
            collection: Collection name
            doc_id: Document ID
            content: New content (optional)
            embedding: New embedding (optional)
            metadata: New metadata (optional)
            
        Returns:
            Success status
        """
        if doc_id not in self.documents[collection]:
            logger.warning(f"Document {doc_id} not found in collection {collection}")
            return False
        
        document = self.documents[collection][doc_id]
        
        # Update fields
        if content is not None:
            document.content = content
            if embedding is None:
                # Recompute embedding for new content
                document.embedding = await self._compute_embedding(content)
        
        if embedding is not None:
            document.embedding = embedding
        
        if metadata is not None:
            document.metadata.update(metadata)
        
        document.timestamp = datetime.utcnow()
        
        # Update in index (requires rebuild for most index types)
        await self._rebuild_index(collection)
        
        logger.info(f"Updated document {doc_id} in collection {collection}")
        
        return True
    
    async def delete_document(
        self,
        collection: str,
        doc_id: str
    ) -> bool:
        """
        Delete document from collection
        
        Args:
            collection: Collection name
            doc_id: Document ID
            
        Returns:
            Success status
        """
        if doc_id not in self.documents[collection]:
            logger.warning(f"Document {doc_id} not found in collection {collection}")
            return False
        
        # Remove from documents
        del self.documents[collection][doc_id]
        
        # Remove from metadata index
        self._remove_from_metadata_index(collection, doc_id)
        
        # Rebuild index
        await self._rebuild_index(collection)
        
        logger.info(f"Deleted document {doc_id} from collection {collection}")
        
        return True
    
    async def get_document(
        self,
        collection: str,
        doc_id: str
    ) -> Optional[VectorDocument]:
        """
        Get document by ID
        
        Args:
            collection: Collection name
            doc_id: Document ID
            
        Returns:
            Document or None
        """
        return self.documents[collection].get(doc_id)
    
    async def list_documents(
        self,
        collection: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[VectorDocument]:
        """
        List documents in collection
        
        Args:
            collection: Collection name
            filters: Metadata filters
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of documents
        """
        documents = list(self.documents[collection].values())
        
        # Apply filters
        if filters:
            documents = [
                doc for doc in documents
                if self._match_filters(doc, filters)
            ]
        
        # Apply pagination
        return documents[offset:offset + limit]
    
    async def get_statistics(
        self,
        collection: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get vector store statistics
        
        Args:
            collection: Specific collection or None for all
            
        Returns:
            Statistics dictionary
        """
        if collection:
            collections = [collection]
        else:
            collections = list(self.indices.keys())
        
        stats = {
            "total_documents": 0,
            "collections": {}
        }
        
        for coll in collections:
            num_docs = len(self.documents[coll])
            stats["total_documents"] += num_docs
            stats["collections"][coll] = {
                "document_count": num_docs,
                "index_type": self.index_type.value,
                "dimension": self.dimension,
                "index_size": self.indices[coll].ntotal if hasattr(self.indices[coll], 'ntotal') else num_docs
            }
        
        return stats
    
    async def _compute_embedding(
        self,
        text: str
    ) -> List[float]:
        """
        Compute embedding for text
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector
        """
        # Placeholder for actual embedding computation
        # In production, this would call an embedding service
        # For now, return random embedding
        np.random.seed(hash(text) % 2**32)
        return np.random.randn(self.dimension).tolist()
    
    async def _add_to_index(
        self,
        collection: str,
        document: VectorDocument
    ):
        """
        Add document to FAISS index
        
        Args:
            collection: Collection name
            document: Document to add
        """
        # Convert embedding to numpy array
        embedding_array = np.array([document.embedding], dtype=np.float32)
        
        # Add to index
        self.indices[collection].add(embedding_array)
        
        # Store document
        self.documents[collection][document.id] = document
    
    async def _rebuild_index(
        self,
        collection: str
    ):
        """
        Rebuild index for collection
        
        Args:
            collection: Collection name
        """
        # Clear current index
        self._initialize_indices()
        
        # Re-add all documents
        for document in self.documents[collection].values():
            embedding_array = np.array([document.embedding], dtype=np.float32)
            self.indices[collection].add(embedding_array)
    
    def _update_metadata_index(
        self,
        collection: str,
        document: VectorDocument
    ):
        """
        Update metadata index for fast filtering
        
        Args:
            collection: Collection name
            document: Document to index
        """
        for key, value in document.metadata.items():
            if key not in self.metadata_index[collection]:
                self.metadata_index[collection][key] = {}
            
            value_str = str(value)
            if value_str not in self.metadata_index[collection][key]:
                self.metadata_index[collection][key][value_str] = []
            
            self.metadata_index[collection][key][value_str].append(document.id)
    
    def _remove_from_metadata_index(
        self,
        collection: str,
        doc_id: str
    ):
        """
        Remove document from metadata index
        
        Args:
            collection: Collection name
            doc_id: Document ID
        """
        for key in self.metadata_index[collection]:
            for value_list in self.metadata_index[collection][key].values():
                if doc_id in value_list:
                    value_list.remove(doc_id)
    
    def _match_filters(
        self,
        document: VectorDocument,
        filters: Dict[str, Any]
    ) -> bool:
        """
        Check if document matches filters
        
        Args:
            document: Document to check
            filters: Filter criteria
            
        Returns:
            Match status
        """
        for key, value in filters.items():
            if key not in document.metadata:
                return False
            
            if isinstance(value, list):
                # Check if metadata value is in list
                if document.metadata[key] not in value:
                    return False
            elif isinstance(value, dict):
                # Handle complex filters (e.g., range queries)
                if "min" in value and document.metadata[key] < value["min"]:
                    return False
                if "max" in value and document.metadata[key] > value["max"]:
                    return False
            else:
                # Exact match
                if document.metadata[key] != value:
                    return False
        
        return True
    
    def _generate_id(
        self,
        content: str
    ) -> str:
        """
        Generate unique ID for document
        
        Args:
            content: Document content
            
        Returns:
            Document ID
        """
        timestamp = datetime.utcnow().isoformat()
        hash_input = f"{content}{timestamp}".encode()
        return hashlib.sha256(hash_input).hexdigest()[:16]
    
    def _load_persisted_data(self):
        """Load persisted vector store data"""
        if not os.path.exists(self.persistence_path):
            return
        
        try:
            # Load indices
            indices_path = os.path.join(self.persistence_path, "indices.pkl")
            if os.path.exists(indices_path):
                with open(indices_path, "rb") as f:
                    self.indices = pickle.load(f)
            
            # Load documents
            docs_path = os.path.join(self.persistence_path, "documents.pkl")
            if os.path.exists(docs_path):
                with open(docs_path, "rb") as f:
                    self.documents = pickle.load(f)
            
            # Load metadata index
            meta_path = os.path.join(self.persistence_path, "metadata.pkl")
            if os.path.exists(meta_path):
                with open(meta_path, "rb") as f:
                    self.metadata_index = pickle.load(f)
            
            logger.info(f"Loaded persisted data from {self.persistence_path}")
        except Exception as e:
            logger.error(f"Failed to load persisted data: {e}")
    
    def persist(self):
        """Persist vector store data"""
        os.makedirs(self.persistence_path, exist_ok=True)
        
        try:
            # Save indices
            indices_path = os.path.join(self.persistence_path, "indices.pkl")
            with open(indices_path, "wb") as f:
                pickle.dump(self.indices, f)
            
            # Save documents
            docs_path = os.path.join(self.persistence_path, "documents.pkl")
            with open(docs_path, "wb") as f:
                pickle.dump(self.documents, f)
            
            # Save metadata index
            meta_path = os.path.join(self.persistence_path, "metadata.pkl")
            with open(meta_path, "wb") as f:
                pickle.dump(self.metadata_index, f)
            
            logger.info(f"Persisted data to {self.persistence_path}")
        except Exception as e:
            logger.error(f"Failed to persist data: {e}")


class VectorStoreFactory:
    """Factory for creating vector stores"""
    
    @staticmethod
    def create(
        store_type: str = "faiss",
        config: Optional[Dict[str, Any]] = None
    ) -> VectorStore:
        """
        Create vector store instance
        
        Args:
            store_type: Type of vector store
            config: Configuration
            
        Returns:
            Vector store instance
        """
        if store_type == "faiss":
            return VectorStore(config)
        else:
            raise ValueError(f"Unknown vector store type: {store_type}")