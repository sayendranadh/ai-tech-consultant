"""Embedding providers. Real = sentence-transformers; Mock = deterministic hash-based."""
from __future__ import annotations

import hashlib
import struct
from typing import Protocol

import numpy as np


class EmbeddingProvider(Protocol):
    model_id: str
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Real embedder. Downloads the model on first use; no API key required."""
    model_id = "sentence-transformers/all-MiniLM-L6-v2"
    dim = 384

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # imported lazily
        self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vecs = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return vecs.astype(np.float32)


class MockEmbedder:
    """
    Deterministic, dependency-free embedder for tests.
    Hashes text → seeds a stable RNG → returns unit-length vector.
    NOT semantically meaningful; labels must not be treated as similarity.
    """
    model_id = "mock/hash-v1"
    dim = 64

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            h = hashlib.sha256(t.encode("utf-8")).digest()
            seed = struct.unpack("<I", h[:4])[0]
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(self.dim).astype(np.float32)
            n = np.linalg.norm(v)
            out[i] = v / n if n > 0 else v
        return out


def vector_to_blob(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


def blob_to_vector(blob: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32).reshape((dim,))
