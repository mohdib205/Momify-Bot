import json
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder

from core.config import QA_FILE, TOP_K

# ── Bi-encoder — fast, finds candidates ──────────────────────────────────────
print("Loading bi-encoder model...")
_bi_encoder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
print("Bi-encoder loaded.")

# ── Cross-encoder — accurate, reranks candidates ─────────────────────────────
# This model reads query + candidate together and scores actual relevance.
# Supports multilingual including Hindi/Hinglish.
print("Loading cross-encoder model...")
_cross_encoder = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
print("Cross-encoder loaded.")

# ── In-memory cache ───────────────────────────────────────────────────────────
_qa_data       = []
_qa_embeddings = None

# How many candidates bi-encoder fetches before cross-encoder reranks
_CANDIDATE_POOL = 20


def _is_valid_question(question: str) -> bool:
    """
    Runtime filter — rejects Q&A pairs whose question is too short
    or clearly a context-dependent follow-up with   no standalone meaning.
    """
    q = question.strip()

    if len(q.split()) < 6:
        return False

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

    _qa_data = [item for item in raw if _is_valid_question(item["question"])]
    print(f"Loaded {len(raw)} pairs → {len(_qa_data)} after runtime filtering")

    print(f"Computing bi-encoder embeddings for {len(_qa_data)} Q&A pairs...")
    questions      = [item["question"] for item in _qa_data]
    _qa_embeddings = _bi_encoder.encode(
        questions,
        convert_to_numpy=True,
        show_progress_bar=True
    )
    print("Embeddings ready.")

    return _qa_data


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return b_norm @ a_norm


def retrieve(query: str, qa_data: list, top_k: int = TOP_K) -> tuple[float, list]:
    """
    Two-stage retrieval:
    Stage 1 — Bi-encoder: fast cosine similarity, fetches top _CANDIDATE_POOL results
    Stage 2 — Cross-encoder: accurate reranking of candidates, returns top_k
    """
    global _qa_embeddings

    if _qa_embeddings is None or len(_qa_embeddings) == 0:
        return 0.0, []

    # ── Stage 1: Bi-encoder — get candidate pool ──────────────────────────────
    query_embedding = _bi_encoder.encode(query, convert_to_numpy=True)
    bi_scores       = _cosine_similarity(query_embedding, _qa_embeddings)

    # Fetch larger candidate pool for reranking
    candidate_count = min(_CANDIDATE_POOL, len(_qa_data))
    candidate_indices = np.argsort(bi_scores)[::-1][:candidate_count]
    candidates        = [_qa_data[i] for i in candidate_indices]

    # ── Stage 2: Cross-encoder — rerank candidates ────────────────────────────
    # Cross-encoder scores query against each candidate's question + answer
    cross_inputs = [
        [query, f"{item['question']} {item['answer']}"]
        for item in candidates
    ]
    cross_scores = _cross_encoder.predict(cross_inputs)

    # Sort candidates by cross-encoder score
    reranked = sorted(
        zip(cross_scores, candidates),
        key=lambda x: x[0],
        reverse=True
    )

    # Best score after reranking
    best_cross_score = float(reranked[0][0]) if reranked else 0.0

    # Normalize cross-encoder score to 0-1 range using sigmoid
    # Cross-encoder outputs raw logits — sigmoid converts to probability
    def sigmoid(x):
        return 1 / (1 + np.exp(-x))

    best_score_normalized = float(sigmoid(best_cross_score))

    # Return top_k results after reranking
    results = [item for _, item in reranked[:top_k]]

    return best_score_normalized, results


def build_context(retrieved: list) -> str:
    lines = []
    for i, item in enumerate(retrieved, 1):
        lines.append(f"Q{i}: {item['question']}")
        lines.append(f"A{i}: {item['answer']}")
        lines.append("")
    return "\n".join(lines)