# RAG，本地题库检索模块，四个主要功能：维护题库文档、生成向量、构建/加载索引、按query索引题目。
# 我把模拟面试题库做成了一个本地 RAGStore，支持 Markdown 题库解析、向量化、FAISS 索引构建与加载；
# 如果外部 embedding 模型或 faiss 不可用，则退化到哈希向量或 numpy 相似度检索，保证题库召回链路不断。

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
    _instance_lock = threading.Lock()  # 保证RAGStore单例运行

    def __init__(self) -> None:
        self._index = None  # FAISS索引对象
        self._matrix: np.ndarray | None = None  # 题目的矩阵向量
        self._docs: list[QuestionDoc] = []  # 原始题库文档
        self._embedding_model = None  # 向量化模型
        self._dim = 384  # 向量维度
        self._lock = threading.Lock()  # 线程锁

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
        """哈希词袋式降级向量，保证embedding不可用时，系统仍然可以把文本转化为可比较向量，
        虽然语义能力弱很多，但是至少检索链路不断"""
        vec = np.zeros(self._dim, dtype=np.float32)
        for token in tokenize(text):
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()  # md5哈希
            idx = int(digest, 16) % self._dim  # 映射到固定维度384向量桶
            vec[idx] += 1.0
        norm = np.linalg.norm(vec) # 然后归一化
        if norm > 0:
            vec = vec / norm
        return vec

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        """
        文本向量化。有模型走模型，没有退回哈希向量。
        """
        model = self._load_embedding_model()
        if model is not None:
            arr = model.encode(texts, normalize_embeddings=True)
            return np.asarray(arr, dtype=np.float32)
        embeddings = np.vstack([self._hash_embedding(text) for text in texts])
        return embeddings.astype(np.float32)

    def _parse_question_markdown(self, path: Path) -> list[QuestionDoc]:
        """markdown文件内解析题库，规则是## xx作为标题，- xxx作为问题条目"""
        """
        示例：
        ## Python后端
        - 请解释 GIL
        - Django 中间件执行顺序是什么
        """
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
        """
        核心构建索引流程
        """
        with self._lock:
            self._docs = self._parse_question_markdown(Path(settings.INTERVIEW_QUESTIONS_PATH))  # 解析题库
            if not self._docs:  # 没有题库就用内置默认题库兜底
                self._docs = [
                    QuestionDoc(id=1, topic="Python后端", question="请解释 Python 中 GIL 的作用与影响。"),
                    QuestionDoc(id=2, topic="Django", question="Django 中间件的执行顺序是什么？"),
                    QuestionDoc(id=3, topic="数据库", question="MySQL 索引失效的常见场景有哪些？"),
                    QuestionDoc(id=4, topic="缓存", question="Redis 在高并发场景下如何保证热点 Key 稳定性？"),
                ]

            text_corpus = [f"{doc.topic}: {doc.question}" for doc in self._docs]  # 每个题目拼接成topic:question文本语料
            embeddings = self._embed_texts(text_corpus)  # 生成embeddings
            self._dim = embeddings.shape[1]

            if faiss is not None:  # 如果faiss可用，就用
                index = faiss.IndexFlatIP(self._dim)  # 建立索引IndexFlatIP，写入磁盘
                index.add(embeddings)
                self._index = index
                faiss.write_index(index, str(settings.VECTOR_INDEX_PATH))
                self._matrix = embeddings
            else:  # 如果faiss不可用，那就只保留向量矩阵
                self._index = None
                self._matrix = embeddings

            meta = {  # 元数据，也就是具体的文档内容
                "dim": self._dim,
                "docs": [asdict(doc) for doc in self._docs],
            }
            Path(settings.VECTOR_META_PATH).write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def load_index(self) -> None:
        """
        载入索引，如果没有meta文件，那就直接建立，如果有就加载docs和维度。
        """
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
                    self.build_index()  # 索引损坏重建
                    return
                text_corpus = [f"{doc.topic}: {doc.question}" for doc in self._docs]
                self._matrix = self._embed_texts(text_corpus)
            else:
                text_corpus = [f"{doc.topic}: {doc.question}" for doc in self._docs]
                self._matrix = self._embed_texts(text_corpus)
                self._index = None

    def ensure_ready(self) -> None:
        """懒加载守卫，只有search时候才确保索引准备好"""
        if self._docs and (self._index is not None or self._matrix is not None):
            return
        self.load_index()

    def search(self, query: str, top_k: int | None = None) -> list[QuestionDoc]:
        """检索主逻辑。"""
        self.ensure_ready()
        if not self._docs:
            return []

        top_k = top_k or settings.RAG_TOP_K
        query_vector = self._embed_texts([query])  # query向量化

        if self._index is not None and faiss is not None:  # 如果有faiss和索引
            scores, idxs = self._index.search(query_vector, min(top_k, len(self._docs)))
            indices = [int(i) for i in idxs[0] if i >= 0]
        else:  # 如果没有就用numpy点积手工排前top_k
            assert self._matrix is not None
            sims = np.dot(self._matrix, query_vector[0])
            ranked = np.argsort(-sims)
            indices = [int(i) for i in ranked[: min(top_k, len(self._docs))]]

        return [self._docs[i] for i in indices if 0 <= i < len(self._docs)]

    def questions_for_topic(self, topic: str, top_k: int | None = None) -> list[QuestionDoc]:
        """
        业务包装，搜索topic+面试题。
        """
        retrieved = self.search(f"{topic} 面试问题", top_k=top_k)
        if retrieved:
            return retrieved
        self.ensure_ready()
        topic_lower = topic.lower()
        fallback = [d for d in self._docs if topic_lower in d.topic.lower()]
        return fallback[: (top_k or settings.RAG_TOP_K)]
