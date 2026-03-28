from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from django.conf import settings

from .text_tools import tokenize

try:
    import faiss
except Exception:  # pragma: no cover
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover
    SentenceTransformer = None


@dataclass
class QuestionDoc:
    id: int
    topic: str
    question: str


class RAGStore:
    _instance: "RAGStore | None" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._index = None
        self._matrix: np.ndarray | None = None
        self._docs: list[QuestionDoc] = []
        self._embedding_model = None
        self._dim = 384
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "RAGStore":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = RAGStore()
        return cls._instance

    def _load_embedding_model(self):
        if self._embedding_model is not None:
            return self._embedding_model
        if SentenceTransformer is None or not settings.EMBEDDING_MODEL:
            return None
        try:
            self._embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        except Exception:
            self._embedding_model = None
        return self._embedding_model

    def _hash_embedding(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float32)
        for token in tokenize(text):
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(digest, 16) % self._dim
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        model = self._load_embedding_model()
        if model is not None:
            arr = model.encode(texts, normalize_embeddings=True)
            return np.asarray(arr, dtype=np.float32)
        embeddings = np.vstack([self._hash_embedding(text) for text in texts])
        return embeddings.astype(np.float32)

    def _parse_question_markdown(self, path: Path) -> list[QuestionDoc]:
        if not path.exists():
            return []

        docs: list[QuestionDoc] = []
        current_topic = "通用"
        idx = 1

        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("##"):
                current_topic = line.lstrip("#").strip() or "通用"
                continue
            if line.startswith("-"):
                question = line.lstrip("- ").strip()
                if question:
                    docs.append(QuestionDoc(id=idx, topic=current_topic, question=question))
                    idx += 1
        return docs

    def build_index(self) -> None:
        with self._lock:
            self._docs = self._parse_question_markdown(Path(settings.INTERVIEW_QUESTIONS_PATH))
            if not self._docs:
                self._docs = [
                    QuestionDoc(id=1, topic="Python后端", question="请解释 Python 中 GIL 的作用与影响。"),
                    QuestionDoc(id=2, topic="Django", question="Django 中间件的执行顺序是什么？"),
                    QuestionDoc(id=3, topic="数据库", question="MySQL 索引失效的常见场景有哪些？"),
                    QuestionDoc(id=4, topic="缓存", question="Redis 在高并发场景下如何保证热点 Key 稳定性？"),
                ]

            text_corpus = [f"{doc.topic}: {doc.question}" for doc in self._docs]
            embeddings = self._embed_texts(text_corpus)
            self._dim = embeddings.shape[1]

            if faiss is not None:
                index = faiss.IndexFlatIP(self._dim)
                index.add(embeddings)
                self._index = index
                faiss.write_index(index, str(settings.VECTOR_INDEX_PATH))
                self._matrix = embeddings
            else:
                self._index = None
                self._matrix = embeddings

            meta = {
                "dim": self._dim,
                "docs": [asdict(doc) for doc in self._docs],
            }
            Path(settings.VECTOR_META_PATH).write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def load_index(self) -> None:
        with self._lock:
            meta_path = Path(settings.VECTOR_META_PATH)
            index_path = Path(settings.VECTOR_INDEX_PATH)
            if not meta_path.exists():
                self.build_index()
                return

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self._dim = int(meta.get("dim", 384))
            self._docs = [QuestionDoc(**doc) for doc in meta.get("docs", [])]

            if faiss is not None and index_path.exists():
                try:
                    self._index = faiss.read_index(str(index_path))
                except Exception:
                    self.build_index()
                    return
                text_corpus = [f"{doc.topic}: {doc.question}" for doc in self._docs]
                self._matrix = self._embed_texts(text_corpus)
            else:
                text_corpus = [f"{doc.topic}: {doc.question}" for doc in self._docs]
                self._matrix = self._embed_texts(text_corpus)
                self._index = None

    def ensure_ready(self) -> None:
        if self._docs and (self._index is not None or self._matrix is not None):
            return
        self.load_index()

    def search(self, query: str, top_k: int | None = None) -> list[QuestionDoc]:
        self.ensure_ready()
        if not self._docs:
            return []

        top_k = top_k or settings.RAG_TOP_K
        query_vector = self._embed_texts([query])

        if self._index is not None and faiss is not None:
            scores, idxs = self._index.search(query_vector, min(top_k, len(self._docs)))
            indices = [int(i) for i in idxs[0] if i >= 0]
        else:
            assert self._matrix is not None
            sims = np.dot(self._matrix, query_vector[0])
            ranked = np.argsort(-sims)
            indices = [int(i) for i in ranked[: min(top_k, len(self._docs))]]

        return [self._docs[i] for i in indices if 0 <= i < len(self._docs)]

    def questions_for_topic(self, topic: str, top_k: int | None = None) -> list[QuestionDoc]:
        retrieved = self.search(f"{topic} 面试问题", top_k=top_k)
        if retrieved:
            return retrieved
        self.ensure_ready()
        topic_lower = topic.lower()
        fallback = [d for d in self._docs if topic_lower in d.topic.lower()]
        return fallback[: (top_k or settings.RAG_TOP_K)]
