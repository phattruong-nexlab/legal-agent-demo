import logging
import difflib

from google.cloud import storage

logger = logging.getLogger(__name__)


def create_gcs_client(*, project_id: str | None = None) -> storage.Client:
    """Create a GCS client; project_id is optional override."""
    logger.info("Initializing GCS Client...")
    return storage.Client(project=project_id) if project_id else storage.Client()


def upload_text_to_bucket(
    *,
    bucket_name: str,
    blob_name: str,
    content: str,
    content_type: str = "text/markdown; charset=utf-8",
    project_id: str | None = None,
    metadata: dict[str, str] | None = None,
) -> str:
    """Upload text content to a GCS bucket and return the blob name."""
    client = create_gcs_client(project_id=project_id)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    if metadata:
        blob.metadata = metadata
    blob.upload_from_string(content, content_type=content_type)
    return blob.name


def list_blob_names(
    *,
    bucket_name: str,
    prefix: str | None = None,
    project_id: str | None = None,
) -> list[str]:
    """List blob names in a GCS bucket."""
    client = create_gcs_client(project_id=project_id)
    blobs = client.list_blobs(bucket_name, prefix=prefix)
    return [blob.name for blob in blobs]


def list_blobs_with_metadata(
    *,
    bucket_name: str,
    prefix: str | None = None,
    project_id: str | None = None,
) -> list[dict]:
    """List blobs with their custom metadata. Returns list of {blob_name, metadata}."""
    client = create_gcs_client(project_id=project_id)
    blobs = client.list_blobs(bucket_name, prefix=prefix)
    return [
        {"blob_name": blob.name, "metadata": blob.metadata or {}}
        for blob in blobs
    ]


def download_text_from_bucket(
    *,
    bucket_name: str,
    blob_name: str,
    project_id: str | None = None,
) -> str:
    """Download text content from a GCS bucket blob."""
    client = create_gcs_client(project_id=project_id)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.download_as_text()


def fuzzy_search(
    *,
    target: str,
    candidates: list[str],
    cutoff: float = 0.6,
) -> str | None:
    """Return the closest candidate match for a target string."""
    if not target or not candidates:
        return None

    if target in candidates:
        return target

    matches = difflib.get_close_matches(target, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None
