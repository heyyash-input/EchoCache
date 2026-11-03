"""Local ONNX embeddings; no embedding API key required."""
import threading
from pathlib import Path


class Embeddings:
    def __init__(self, model_name: str, cache_dir: Path):
        self.model_name, self.cache_dir = model_name, cache_dir
        self._model = None
        self._lock = threading.Lock()

    def encode(self, text: str) -> list[float]:
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding
                self._model = TextEmbedding(model_name=self.model_name, cache_dir=str(self.cache_dir), threads=2)
            return next(iter(self._model.embed([text]))).tolist()
