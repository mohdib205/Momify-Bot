import json
import numpy as np
from sentence_transformers import SentenceTransformer

from core.config import QA_FILE, TOP_K

print("Loading embedding model...")
_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
print("Embedding model loaded.")

_qa_data       = []
_qa_embeddings = None


def _is_valid_question(question: str) -> bool:
    """
    Runtime filter — rejects Q&A pairs whose question is too short
    or clearly a context-dependent follow-up with no standalone meaning.
    This is a safety net for any garbage that survived data cleaning.
    """
    q = question.strip()

    # Too short to be meaningful
    if len(q.split()) < 6:
        return False

    # Starts with a reference word — clearly a follow-up
    followup_starts = (
        "this ", "that ", "it ", "these ", "those ",
        "also ", "and ", "okay ", "ok ", "so ",
        "now ", "then ", "but ", "what about ",
    )
    if q.lower().startswith(followup_starts):
        return False

    return True


def load_qa(filepath: str = QA_FILE) -> list:
    global _qa_data, _qa_embeddings

    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Filter at load time
    _qa_data = [item for item in raw if _is_valid_question(item["question"])]
    print(f"Loaded {len(raw)} pairs → {len(_qa_data)} after runtime filtering")

    print(f"Computing embeddings for {len(_qa_data)} Q&A pairs...")
    questions      = [item["question"] for item in _qa_data]
    _qa_embeddings = _model.encode(questions, convert_to_numpy=True, show_progress_bar=True)
    print("Embeddings ready.")

    return _qa_data


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return b_norm @ a_norm


def retrieve(query: str, qa_data: list, top_k: int = TOP_K) -> tuple[float, list]:
    global _qa_embeddings

    if _qa_embeddings is None or len(_qa_embeddings) == 0:
        return 0.0, []

    query_embedding = _model.encode(query, convert_to_numpy=True)
    scores          = _cosine_similarity(query_embedding, _qa_embeddings)
    top_indices     = np.argsort(scores)[::-1][:top_k]

    best_score = float(scores[top_indices[0]])
    results    = [_qa_data[i] for i in top_indices if scores[i] > 0.0]

    return best_score, results


def build_context(retrieved: list) -> str:
    lines = []
    for i, item in enumerate(retrieved, 1):
        lines.append(f"Q{i}: {item['question']}")
        lines.append(f"A{i}: {item['answer']}")
        lines.append("")
    return "\n".join(lines) 