from __future__ import annotations

from datetime import datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings


class ObjectStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = boto3.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key,
            aws_secret_access_key=self.settings.s3_secret_key,
        )

    def ensure_bucket(self) -> None:
        bucket = self.settings.s3_bucket_raw
        try:
            self.client.head_bucket(Bucket=bucket)
        except ClientError:
            self.client.create_bucket(Bucket=bucket)

    def put_raw_html(self, source_url: str, raw_html: str) -> Optional[str]:
        try:
            self.ensure_bucket()
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            key = f"raw/{ts}/{abs(hash(source_url))}.html"
            self.client.put_object(
                Bucket=self.settings.s3_bucket_raw,
                Key=key,
                Body=raw_html.encode("utf-8"),
                ContentType="text/html",
                Metadata={"source_url": source_url[:1900]},
            )
            return key
        except Exception:
            return None

    def put_raw_bytes(self, name: str, data: bytes, content_type: str = "application/octet-stream") -> Optional[str]:
        try:
            self.ensure_bucket()
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            key = f"uploads/{ts}/{name}"
            self.client.put_object(
                Bucket=self.settings.s3_bucket_raw,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            return key
        except Exception:
            return None
