"""Import API endpoints (mounted under `/portfolios/{portfolio_id}/imports`)."""

from fastapi import APIRouter, Depends, UploadFile

from app.modules.core_data.models.user import User
from app.modules.portfolios.dependencies import get_import_service
from app.modules.portfolios.schemas.imports import (
    ImportBatchResponse,
    ImportBatchSummaryResponse,
    ImportPreviewResponse,
)
from app.modules.portfolios.services.imports import (
    MAX_IMPORT_FILE_BYTES,
    ImportService,
)
from app.modules.security.dependencies import get_current_user

router = APIRouter(
    prefix="/portfolios/{portfolio_id:int}/imports",
    tags=["imports"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[ImportBatchSummaryResponse])
def list_imports(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    service: ImportService = Depends(get_import_service),
):
    return service.list_batches(portfolio_id, user.id)


def _read_upload(file: UploadFile) -> tuple[str, bytes]:
    # One byte over the limit is enough for the service to refuse the file
    # without reading the rest of it into memory. Starlette has already spooled
    # the whole upload by now: a cap on the request body belongs at the proxy.
    return file.filename or "import", file.file.read(MAX_IMPORT_FILE_BYTES + 1)


@router.post("/preview", response_model=ImportPreviewResponse)
def preview_import(
    portfolio_id: int,
    file: UploadFile,
    user: User = Depends(get_current_user),
    service: ImportService = Depends(get_import_service),
):
    """What importing the file would do. Nothing is stored."""
    filename, content = _read_upload(file)
    return service.preview(portfolio_id, user.id, filename, content)


@router.post("", response_model=ImportBatchResponse, status_code=201)
def import_file(
    portfolio_id: int,
    file: UploadFile,
    user: User = Depends(get_current_user),
    service: ImportService = Depends(get_import_service),
):
    """Import the file: the first time anything of it is stored."""
    filename, content = _read_upload(file)
    return service.confirm(portfolio_id, user.id, filename, content)


@router.get("/{batch_id:int}", response_model=ImportBatchResponse)
def get_import(
    portfolio_id: int,
    batch_id: int,
    user: User = Depends(get_current_user),
    service: ImportService = Depends(get_import_service),
):
    return service.get_detail(batch_id, portfolio_id, user.id)


@router.post("/{batch_id:int}/revert", response_model=ImportBatchResponse)
def revert_import(
    portfolio_id: int,
    batch_id: int,
    user: User = Depends(get_current_user),
    service: ImportService = Depends(get_import_service),
):
    return service.revert(batch_id, portfolio_id, user.id)
