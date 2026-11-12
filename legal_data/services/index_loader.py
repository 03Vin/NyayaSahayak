"""
Lazy Singleton Loader for FAISS Index, Metadata, and Embedding Model.
Ensures large embedding models and index objects are loaded once in memory
and reused across requests.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)

_FAISS_INDEX = None
_METADATA: Optional[List[Dict[str, Any]]] = None
_EMBEDDING_MODEL = None


def get_embedding_model():
    """
    Returns the cached sentence-transformers embedding model, loading it lazily on first access.
    """
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        import os
        from sentence_transformers import SentenceTransformer
        # Avoid unnecessary network retries to HF Hub if weights are cached
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        logger.info(f"Loading embedding model '{settings.EMBEDDING_MODEL_NAME}' into memory...")
        try:
            _EMBEDDING_MODEL = SentenceTransformer(settings.EMBEDDING_MODEL_NAME, local_files_only=True)
        except Exception:
            _EMBEDDING_MODEL = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    return _EMBEDDING_MODEL


def get_faiss_index_and_metadata() -> Tuple[Any, List[Dict[str, Any]]]:
    """
    Returns (index, metadata) singleton tuple.
    Returns (None, []) if the index has not been built yet.
    """
    global _FAISS_INDEX, _METADATA

    if _FAISS_INDEX is not None and _METADATA is not None:
        return _FAISS_INDEX, _METADATA

    index_path = settings.INDEX_DIR / "acts.index"
    meta_path = settings.INDEX_DIR / "metadata.json"

    if not index_path.exists() or not meta_path.exists():
        logger.warning(f"Index or metadata not found at {settings.INDEX_DIR}. Run 'python manage.py ingest_acts'.")
        return None, []

    import faiss
    try:
        logger.info(f"Loading FAISS index from {index_path}...")
        _FAISS_INDEX = faiss.read_index(str(index_path))

        logger.info(f"Loading chunk metadata from {meta_path}...")
        with open(meta_path, 'r', encoding='utf-8') as f:
            _METADATA = json.load(f)

        logger.info(f"Successfully loaded index with {_FAISS_INDEX.ntotal} vectors and {len(_METADATA)} metadata entries.")
    except Exception as e:
        logger.error(f"Error loading FAISS index or metadata: {e}")
        _FAISS_INDEX = None
        _METADATA = []

    return _FAISS_INDEX, _METADATA


def reload_index():
    """
    Forces reload of index and metadata from disk after ingestion.
    """
    global _FAISS_INDEX, _METADATA
    _FAISS_INDEX = None
    _METADATA = None
    return get_faiss_index_and_metadata()

