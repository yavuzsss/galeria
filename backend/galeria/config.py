from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every field can be overridden with a GALERIA_* env variable."""

    model_config = SettingsConfigDict(env_prefix="GALERIA_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")

    # Image and text encoders share one embedding space: the multilingual text model was
    # distilled to match the original CLIP text tower, so it pairs with the CLIP image tower.
    image_model: str = "clip-ViT-B-32"
    text_model: str = "sentence-transformers/clip-ViT-B-32-multilingual-v1"
    device: str = "auto"  # image encoder: auto | cpu | mps | cuda
    # Queries are one short sentence each. On CPU they encode in a steady ~7 ms; on Apple's MPS
    # the median is similar but p95 was 128 ms, from kernel compiles for each new token length
    # (see eval/results). Indexing is batched, so images still benefit from the GPU.
    text_device: str = "cpu"

    batch_size: int = 32
    max_image_side: int = 512  # images are downscaled before encoding; CLIP sees 224px anyway
    thumb_size: int = 384

    frame_interval: float = 2.0  # seconds between sampled video frames
    # A sampled frame is dropped when its embedding is at least this similar to the last kept
    # frame, so static shots cost one vector instead of one per interval.
    frame_dedup_threshold: float = 0.95
    max_frames_per_video: int = 900  # long videos widen the interval to stay under this

    # Hide results scoring below this cosine similarity. Off by default: the eval suggests
    # ~0.28 for this encoder, but that rests on only six no-match queries.
    min_score: float | None = None

    # API. Lists are given as JSON in env vars, e.g. GALERIA_ALLOWED_ROOTS='["/media"]'.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Folders POST /api/index may index. Empty means any folder, which is fine for a server
    # bound to localhost; Docker sets it to the mounted media volume.
    allowed_roots: list[Path] = []

    @property
    def index_path(self) -> Path:
        return self.data_dir / "index.faiss"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "meta.sqlite"

    @property
    def thumbs_dir(self) -> Path:
        return self.data_dir / "thumbs"
