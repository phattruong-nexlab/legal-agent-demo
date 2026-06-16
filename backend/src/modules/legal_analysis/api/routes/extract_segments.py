import logging

from fastapi import APIRouter, Depends, File, UploadFile

from ...application.usecase.extract_segments import ExtractSegmentsUseCase
from ..dependencies import get_extract_segments_usecase
from ..schemas import ExtractSegmentsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/extract-segments", response_model=ExtractSegmentsResponse)
async def extract_segments(
    file: UploadFile = File(...),
    usecase: ExtractSegmentsUseCase = Depends(get_extract_segments_usecase),
) -> ExtractSegmentsResponse:
    """Trích đơn vị cấu trúc lớn nhất của văn bản đầu vào (Chương → Điều → Toàn văn).

    Convert PDF → markdown đúng 1 lần và trả về các segment kèm nội dung, để vừa hiển
    thị trên UI vừa dùng lại trực tiếp ở bước /audit-by-graph (không convert lại).
    """
    logger.info("[extract-segments] Start - file: %s", file.filename)
    file_bytes = await file.read()
    result = await usecase.execute(file_bytes)
    logger.info(
        "[extract-segments] Done - unit=%s, segments=%d",
        result.get("unit_type"), len(result.get("segments", [])),
    )
    return result
