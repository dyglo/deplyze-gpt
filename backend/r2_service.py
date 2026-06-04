import os
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config


PRESIGN_EXPIRES_SECONDS = 3600

_client = None


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value


def get_r2_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=_required_env("R2_ENDPOINT_URL"),
            aws_access_key_id=_required_env("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=_required_env("R2_SECRET_ACCESS_KEY"),
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
    return _client


def bucket_name() -> str:
    return _required_env("R2_BUCKET_NAME")


def upload_bytes(key: str, content: bytes, content_type: Optional[str] = None) -> None:
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    get_r2_client().put_object(
        Bucket=bucket_name(),
        Key=key,
        Body=content,
        **extra_args,
    )


def upload_fileobj(key: str, fileobj, content_type: Optional[str] = None) -> None:
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    kwargs = {"ExtraArgs": extra_args} if extra_args else {}
    get_r2_client().upload_fileobj(fileobj, bucket_name(), key, **kwargs)


def upload_file(key: str, path: Path, content_type: Optional[str] = None) -> None:
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    kwargs = {"ExtraArgs": extra_args} if extra_args else {}
    get_r2_client().upload_file(str(path), bucket_name(), key, **kwargs)


def download_file(key: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    get_r2_client().download_file(bucket_name(), key, str(path))


def get_object(key: str):
    return get_r2_client().get_object(Bucket=bucket_name(), Key=key)


def delete_object(key: str) -> None:
    get_r2_client().delete_object(Bucket=bucket_name(), Key=key)


def presigned_get_url(key: str, expires_in: int = PRESIGN_EXPIRES_SECONDS) -> str:
    return get_r2_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name(), "Key": key},
        ExpiresIn=expires_in,
    )
