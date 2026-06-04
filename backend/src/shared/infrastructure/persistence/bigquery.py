import logging

from google.cloud import bigquery

logger = logging.getLogger(__name__)


def create_bigquery_client(*, project_id: str | None = None) -> bigquery.Client:
    """
    Khởi tạo BigQuery Client.
    Nếu project_id là None, thư viện sẽ tự động tìm project id từ
    biến môi trường GOOGLE_APPLICATION_CREDENTIALS hoặc Compute Engine metadata.
    """
    logger.info("Initializing BigQuery Client...")
    try:
        # Bạn có thể truyền project_id nếu muốn ghi đè mặc định
        client = (
            bigquery.Client(project=project_id) if project_id else bigquery.Client()
        )
        return client
    except Exception as e:
        logger.error(f"Failed to initialize BigQuery client: {e}")
        raise e
