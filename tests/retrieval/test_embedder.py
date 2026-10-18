import numpy as np
from task1_knowledge_brain.retrieval.embedder import MockEmbedder


def test_mock_embedder_deterministic():
    e = MockEmbedder()
    a = e.embed(["hello", "world"])
    b = e.embed(["hello", "world"])
    assert np.allclose(a, b)
    assert a.shape == (2, 64)


def test_mock_embedder_unit_length():
    e = MockEmbedder()
    v = e.embed(["hello"])[0]
    assert abs(np.linalg.norm(v) - 1.0) < 1e-5


def test_mock_embedder_empty():
    e = MockEmbedder()
    assert e.embed([]).shape == (0, 64)
