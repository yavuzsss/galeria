"""Embedding models.

Everything downstream depends only on the `Encoder` protocol, so the CLIP implementation can be
swapped (e.g. for SigLIP 2) and tests can run with `FakeEncoder` without downloading weights.
"""

import hashlib
import threading
from collections.abc import Sequence
from typing import Protocol

import numpy as np
from PIL import Image


class Encoder(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def dim(self) -> int: ...

    def warmup(self) -> None:
        """Load weights ahead of time so the first query is not charged for it."""
        ...

    def encode_images(self, images: Sequence[Image.Image]) -> np.ndarray:
        """Return an (n, dim) float32 array of L2-normalized embeddings."""
        ...

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        """Return an (n, dim) float32 array of L2-normalized embeddings."""
        ...


def resolve_device(device: str) -> str:
    if device != "auto":
        return device
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


class ClipEncoder:
    """CLIP image tower + multilingual text tower, loaded lazily on first use."""

    def __init__(
        self,
        image_model: str,
        text_model: str,
        device: str = "auto",
        batch_size: int = 32,
        text_device: str = "cpu",
    ):
        self.image_model_name = image_model
        self.text_model_name = text_model
        self.device = resolve_device(device)
        self.text_device = resolve_device(text_device)
        self.batch_size = batch_size
        self._image_model = None
        self._text_model = None
        self._dim: int | None = None
        # One lock per tower: torch modules are not safe to call from several threads at once,
        # and separate locks let searches run while the indexer is busy with images.
        self._image_lock = threading.Lock()
        self._text_lock = threading.Lock()

    @property
    def name(self) -> str:
        return f"{self.image_model_name}+{self.text_model_name}"

    @property
    def dim(self) -> int:
        if self._dim is None:
            dim = self._image().get_embedding_dimension()
            if dim is None:
                dim = self.encode_images([Image.new("RGB", (32, 32))]).shape[1]
            self._dim = int(dim)
        return self._dim

    def _image(self):
        if self._image_model is None:
            from sentence_transformers import SentenceTransformer

            self._image_model = SentenceTransformer(self.image_model_name, device=self.device)
        return self._image_model

    def _text(self):
        if self._text_model is None:
            from sentence_transformers import SentenceTransformer

            self._text_model = SentenceTransformer(self.text_model_name, device=self.text_device)
        return self._text_model

    def warmup(self) -> None:
        """Load both models and run one dummy pass so the first real query is fast."""
        self.encode_images([Image.new("RGB", (224, 224))])
        self.encode_texts(["warmup"])

    def encode_images(self, images: Sequence[Image.Image]) -> np.ndarray:
        if not images:
            return np.zeros((0, self.dim), dtype=np.float32)
        with self._image_lock:
            out = self._image().encode(
                list(images),
                batch_size=self.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        return np.asarray(out, dtype=np.float32)

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        with self._text_lock:
            out = self._text().encode(
                list(texts),
                batch_size=self.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        return np.asarray(out, dtype=np.float32)


_COLOR_WORDS = {
    "red": 0, "kırmızı": 0,
    "green": 1, "yeşil": 1,
    "blue": 2, "mavi": 2,
}  # fmt: skip


class FakeEncoder:
    """Deterministic stand-in for tests: images embed by mean RGB, color words embed by axis.

    A mostly red image therefore ranks first for "red" or "kırmızı", which is enough to test
    indexing and search end to end without a real model.
    """

    name = "fake-color-encoder"
    dim = 8

    def warmup(self) -> None:
        pass

    def encode_images(self, images: Sequence[Image.Image]) -> np.ndarray:
        vectors = np.zeros((len(images), self.dim), dtype=np.float32)
        for i, image in enumerate(images):
            rgb = np.asarray(image.convert("RGB").resize((8, 8)), dtype=np.float32)
            vectors[i, :3] = rgb.mean(axis=(0, 1)) / 255.0
            vectors[i, 3] = 0.05  # keeps black images from being a zero vector
        return l2_normalize(vectors) if len(images) else vectors

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in text.lower().split():
                if word in _COLOR_WORDS:
                    vectors[i, _COLOR_WORDS[word]] += 1.0
            if not vectors[i].any():
                seed = int.from_bytes(hashlib.sha1(text.encode()).digest()[:4], "little")
                vectors[i, 3:] = np.random.default_rng(seed).random(self.dim - 3)
        return l2_normalize(vectors) if len(texts) else vectors
