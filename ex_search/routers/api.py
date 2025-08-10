from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session


from databases.sql.util import get_async_session
from domain.schemas.search import SearchRequest, SearchResponse
from app.search_api.search import SearchClient

router = APIRouter(prefix="/api", tags=["api"])

CALLER_TYPE = "api.search"


@router.post(
    "/search/",
    response_model=SearchResponse,
    description="渡された値から対象のURLの価格情報を返します。",
)
async def api_get_search_result(
    request: Request,
    searchreq: SearchRequest,
    db: Session = Depends(get_async_session),
):
    if not searchreq.url and not searchreq.search_keyword:
        raise HTTPException(
            status_code=404, detail="URL or search keyword is required."
        )
    client = SearchClient(
        ses=db, request=request, searchrequest=searchreq, caller_type=CALLER_TYPE
    )
    try:
        response = await client.execute()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return response
