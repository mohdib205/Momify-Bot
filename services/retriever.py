import json
import numpy as np
from sentence_transformers import SentenceTransformer

from core.config import QA_FILE, TOP_K

# ── Load model once at import time ──
# paraphrase-multilingual-MiniLM-L12-v2 supports English + Hindi/Urdu
print("Loading embedding model...")
_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
print("Embedding model loaded.")

# ── In-memory cache for dataset embeddings ──
_qa_data        = []
_qa_embeddings  = None   # numpy array of shape (N, embedding_dim)


def load_qa(filepath: str = QA_FILE) -> list:
    global _qa_data, _qa_embeddings

    with open(filepath, "r", encoding="utf-8") as f:
        _qa_data = json.load(f)

    # Pre-compute embeddings for all questions at startup
    print(f"Computing embeddings for {len(_qa_data)} Q&A pairs...")
    questions      = [item["question"] for item in _qa_data]
    _qa_embeddings = _model.encode(questions, convert_to_numpy=True, show_progress_bar=True)
    print("Embeddings ready.")

    return _qa_data


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between vector a and matrix b."""
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return b_norm @ a_norm


def retrieve(query: str, qa_data: list, top_k: int = TOP_K) -> tuple[float, list]:
    global _qa_embeddings

    if _qa_embeddings is None or len(_qa_embeddings) == 0:
        return 0.0, []

    # Embed the query
    query_embedding = _model.encode(query, convert_to_numpy=True)

    # Compute cosine similarity against all Q&A embeddings
    scores = _cosine_similarity(query_embedding, _qa_embeddings)

    # Get top_k indices sorted by score descending
    top_indices = np.argsort(scores)[::-1][:top_k]

    best_score = float(scores[top_indices[0]])
    results    = [qa_data[i] for i in top_indices if scores[i] > 0.0]

    return best_score, results


def build_context(retrieved: list) -> str:
    lines = []
    for i, item in enumerate(retrieved, 1):
        lines.append(f"Q{i}: {item['question']}")
        lines.append(f"A{i}: {item['answer']}")
        lines.append("")
    return "\n".join(lines)
