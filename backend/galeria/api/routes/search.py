from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request

from galeria.api.schemas import SearchOut

router = APIRouter()


# A plain `def` endpoint runs in FastAPI's thread pool, so a query being encoded never blocks
# the event loop (and with it, thumbnail and video requests).
@router.get("/search", response_model=SearchOut)
def search(
    request: Request,
    q: Annotated[str, Query(min_length=1, max_length=300, description="Natural-language query")],
    k: Annotated[int, Query(ge=1, le=200)] = 24,
    type: Annotated[Literal["all", "photo", "video"], Query()] = "all",
    min_score: Annotated[
        float | None,
        Query(ge=-1, le=1, description="Hide weaker results; defaults to GALERIA_MIN_SCORE"),
    ] = None,
) -> SearchOut:
    kind = None if type == "all" else type
    response = request.app.state.services.searcher.search(q, k=k, kind=kind, min_score=min_score)
    return SearchOut.from_response(response)
