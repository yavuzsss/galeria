"""Wires settings, encoder and stores together; shared by the CLI and the API."""

from dataclasses import dataclass

from galeria.config import Settings
from galeria.core.encoder import ClipEncoder, Encoder
from galeria.core.indexer import Indexer
from galeria.core.metadata import MetadataStore
from galeria.core.search import Searcher
from galeria.core.vector_store import VectorStore


class EncoderMismatchError(RuntimeError):
    pass


@dataclass
class Services:
    settings: Settings
    encoder: Encoder
    store: VectorStore
    meta: MetadataStore
    indexer: Indexer
    searcher: Searcher

    def close(self) -> None:
        self.meta.close()


def build_encoder(settings: Settings) -> ClipEncoder:
    return ClipEncoder(
        settings.image_model,
        settings.text_model,
        device=settings.device,
        batch_size=settings.batch_size,
        text_device=settings.text_device,
    )


def open_services(settings: Settings | None = None, encoder: Encoder | None = None) -> Services:
    settings = settings or Settings()
    encoder = encoder or build_encoder(settings)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.thumbs_dir.mkdir(parents=True, exist_ok=True)

    meta = MetadataStore(settings.db_path)
    # Vectors from different models live in different spaces; mixing them silently would
    # return garbage, so refuse instead.
    stored = meta.get_meta("encoder")
    if stored and stored != encoder.name:
        meta.close()
        raise EncoderMismatchError(
            f"{settings.data_dir} was indexed with '{stored}', but the configured encoder is "
            f"'{encoder.name}'. Use another GALERIA_DATA_DIR or delete it and re-index."
        )
    meta.set_meta("encoder", encoder.name)

    if settings.index_path.exists():
        store = VectorStore.load(settings.index_path, encoder.dim)
    else:
        store = VectorStore(encoder.dim)

    indexer = Indexer(
        encoder,
        store,
        meta,
        index_path=settings.index_path,
        thumbs_dir=settings.thumbs_dir,
        batch_size=settings.batch_size,
        max_image_side=settings.max_image_side,
        thumb_size=settings.thumb_size,
        frame_interval=settings.frame_interval,
        frame_dedup_threshold=settings.frame_dedup_threshold,
        max_frames=settings.max_frames_per_video,
    )
    return Services(
        settings, encoder, store, meta, indexer, Searcher(encoder, store, meta, settings.min_score)
    )
