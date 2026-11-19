from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.dependencies import (
    get_current_user,
    get_optional_current_user,
    get_storage_handler,
)
from app.handlers.storage_handler import StorageHandler
from app.schemas.storage import (
    FileDeleteResponse,
    FileListResponse,
    FileUploadResponse,
    PresignedUrlsRequest,
    PresignedUrlsResponse,
    PresignedUploadRequest,
    StoragePresignedUrlResponse,
)
from app.schemas.user import AuthenticatedUser

router = APIRouter(tags=["Files"])


@router.post(
    "/files",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file to S3",
    description="Upload a file to S3 storage. Preserves content type and filename while assigning a stable UUID identifier.",
)
async def upload_file(
    file: UploadFile = File(..., description="Multipart binary file payload"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    handler: StorageHandler = Depends(get_storage_handler),
) -> FileUploadResponse:
    """
    Accept multipart/form-data upload, validate, upload to S3, and return file metadata.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename must not be empty",
        )

    return await handler.upload_file(file)


@router.get(
    "/files/{file_id}",
    summary="Retrieve and stream a stored file from S3",
    description="Retrieve a stored binary asset by stable identifier and stream contents directly to client.",
)
async def get_file(
    file_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    handler: StorageHandler = Depends(get_storage_handler),
) -> StreamingResponse:
    """
    Retrieve stored file by ID and stream its content without blocking the event loop.
    Preserves correct Content-Type and sets attachment Content-Disposition so browsers and Swagger download the file.
    """
    stored_file = await handler.get_file(file_id)

    clean_filename = stored_file.filename.replace('"', "").replace("\r", "").replace("\n", "")
    headers = {
        "Content-Disposition": f'attachment; filename="{clean_filename}"',
    }
    if stored_file.size > 0:
        headers["Content-Length"] = str(stored_file.size)

    return StreamingResponse(
        stored_file.stream,
        media_type=stored_file.content_type,
        headers=headers,
    )


@router.get(
    "/files",
    response_model=FileListResponse,
    summary="List stored files",
    description="List stored objects matching an optional key prefix filter, with optional pagination.",
)
async def list_files(
    prefix: str | None = Query(default=None, description="Optional S3 object key prefix"),
    limit: int | None = Query(default=None, ge=1, le=1000, description="Optional page limit (max keys)"),
    continuation_token: str | None = Query(default=None, description="Optional S3 continuation token"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    handler: StorageHandler = Depends(get_storage_handler),
) -> FileListResponse:
    """
    List stored files using an optional prefix filter and pagination tokens.
    """
    return await handler.list_files(
        prefix=prefix,
        max_keys=limit,
        continuation_token=continuation_token,
    )


@router.delete(
    "/files/{file_id}",
    response_model=FileDeleteResponse,
    summary="Delete a stored file from S3",
    description="Permanently delete a stored file from S3 by its stable identifier.",
)
async def delete_file(
    file_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    handler: StorageHandler = Depends(get_storage_handler),
) -> FileDeleteResponse:
    """
    Delete a stored file from S3 by its stable ID or key. Returns 404 if not found.
    """
    return await handler.delete_file(file_id)


@router.post(
    "/files/presigned-urls",
    response_model=PresignedUrlsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate presigned upload and download URLs",
    description="Generate both an upload presigned URL (PUT) and a download presigned URL (GET) for an S3 object.",
)
async def generate_presigned_urls(
    payload: PresignedUrlsRequest,
    current_user: AuthenticatedUser | None = Depends(get_optional_current_user),
    handler: StorageHandler = Depends(get_storage_handler),
) -> PresignedUrlsResponse:
    """
    Generate paired S3 presigned PUT and GET URLs in a single request, returning status 201 Created.
    Supports Bruno workflow: upload with upload_url, view/download with download_url.
    """
    effective_expiry = payload.expires_in or payload.expiry
    return await handler.generate_presigned_urls(
        filename=payload.filename,
        content_type=payload.content_type,
        expires_in=effective_expiry,
        prefix=payload.prefix or "uploads",
        file_size=payload.file_size,
    )


@router.post(
    "/files/presigned-upload",
    response_model=PresignedUrlsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate presigned upload URL",
    description="Generate presigned URLs for client-to-S3 upload and direct retrieval.",
)
async def create_presigned_upload(
    payload: PresignedUrlsRequest,
    current_user: AuthenticatedUser | None = Depends(get_optional_current_user),
    handler: StorageHandler = Depends(get_storage_handler),
) -> PresignedUrlsResponse:
    """
    Generate presigned upload and download URLs. Accepts optional file_size, prefix, and expiry.
    """
    effective_expiry = payload.expires_in or payload.expiry
    return await handler.generate_presigned_urls(
        filename=payload.filename,
        content_type=payload.content_type,
        expires_in=effective_expiry,
        prefix=payload.prefix or "uploads",
        file_size=payload.file_size,
    )


@router.get(
    "/files/{file_id}/presigned-download",
    response_model=StoragePresignedUrlResponse,
    summary="Generate presigned download URL",
    description="Generate a cryptographically signed temporary URL for direct-from-S3 downloads.",
)
async def get_presigned_download(
    file_id: str,
    expiry: int | None = Query(default=None, ge=1, le=604800, description="Optional custom expiry in seconds"),
    content_disposition: str = Query(default="attachment", description="'attachment' or 'inline'"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    handler: StorageHandler = Depends(get_storage_handler),
) -> StoragePresignedUrlResponse:
    """
    Generate an S3 presigned GET URL allowing clients to download directly from S3.
    Resolves file_id to S3 key, configures expiry and response content-disposition.
    """
    return await handler.generate_presigned_download(
        file_id_or_key=file_id,
        expiry=expiry,
        content_disposition=content_disposition,
    )


@router.get(
    "/files/exists/{object_key:path}",
    response_model=dict[str, bool],
    summary="Check if a file exists in S3 storage",
    description="Check whether an object key exists in S3 via HEAD request.",
)
async def check_file_exists(
    object_key: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    handler: StorageHandler = Depends(get_storage_handler),
) -> dict[str, bool]:
    """
    Perform a HEAD request to check whether an object key exists in the storage bucket.
    """
    exists = await handler.file_exists(object_key)
    return {"exists": exists}


