"""
File storage utility for Cloudflare R2.

In local development (when R2 credentials are not configured),
this module runs in MOCK mode and returns fake presigned URLs.

SETUP GUIDE FOR R2:
1. Create a Cloudflare R2 bucket: https://developers.cloudflare.com/r2/
2. Create an R2 API Token with Object Read & Write permissions
3. Add these to your .env file:
   R2_ACCOUNT_ID=your_account_id
   R2_ACCESS_KEY_ID=your_access_key_id
   R2_SECRET_ACCESS_KEY=your_secret_access_key
   R2_BUCKET_NAME=your_bucket_name

4. Install boto3 (already in dependencies):
   uv add boto3

5. The presigned URLs will work automatically once configured.
"""

import uuid

from app.core.config import settings

# Mock mode flag
_MOCK_MODE = not bool(settings.R2_ACCESS_KEY_ID)

# Initialize boto3 client only if R2 is configured
_s3_client = None
R2_ENDPOINT = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

if not _MOCK_MODE:
    import boto3
    from botocore.config import Config

    _s3_client = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",  # R2 uses "auto" region
    )


def generate_upload_url(
    filename: str,
    content_type: str,
    folder: str = "submissions",
    expires_in: int = 600,  # 10 minutes
) -> tuple[str, str]:
    """Generate a presigned PUT URL for uploading a file to R2.

    Args:
        filename: Original filename (only used for extension)
        content_type: MIME type of the file
        folder: Folder prefix for the object key
        expires_in: URL expiration time in seconds

    Returns:
        Tuple of (presigned_url, object_key)

    Mock mode (local dev):
        Returns fake URLs that won't actually upload.
        Use this for frontend development without R2.
    """
    # Generate unique object key to prevent collisions
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "jpg"
    object_key = f"{folder}/{uuid.uuid4()}.{ext}"

    if _MOCK_MODE:
        # Mock mode: return a fake URL for local development
        mock_url = f"mock://r2/upload/{object_key}"
        return mock_url, object_key

    presigned_url = _s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )

    return presigned_url, object_key


def generate_read_url(
    object_key: str,
    expires_in: int = 3600,  # 1 hour
) -> str:
    """Generate a presigned GET URL for reading a file from R2.

    Args:
        object_key: The object key stored in the database
        expires_in: URL expiration time in seconds

    Returns:
        Presigned URL string

    Mock mode (local dev):
        Returns a fake URL. The frontend won't be able to display
        actual images, but can test the UI flow.
    """
    if _MOCK_MODE:
        # Mock mode: return a fake URL for local development
        return f"mock://r2/read/{object_key}"

    return _s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": object_key,
        },
        ExpiresIn=expires_in,
    )


def is_mock_mode() -> bool:
    """Check if storage is running in mock mode."""
    return _MOCK_MODE
