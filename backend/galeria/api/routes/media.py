import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse

router = APIRouter()

_THUMB_NAME = re.compile(r"^[0-9a-f]{20}\.jpg$")


@router.get("/media/{file_id}")
def media(file_id: int, request: Request) -> FileResponse:
    """The original photo or video. Supports HTTP Range, so <video> can seek to a timestamp."""
    meta = request.app.state.services.meta
    record = meta.get_file(file_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown media id")
    path = Path(record.path)
    # Paths come from our own database, but only ever serve files inside an indexed folder.
    if not any(path.is_relative_to(root) for root in meta.roots()) or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file is no longer available")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "no-cache"})


@router.get("/thumbs/{name}")
def thumbnail(name: str, request: Request) -> FileResponse:
    # The strict pattern rules out path traversal before the filesystem is touched.
    if not _THUMB_NAME.match(name):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    path = request.app.state.services.settings.thumbs_dir / name
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # The name is derived from path + mtime, so its content never changes.
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
