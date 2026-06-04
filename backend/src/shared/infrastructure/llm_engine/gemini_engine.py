import json
import logging
import re
import time

from google import genai
from google.genai import types

from src.config import get_settings

from .interfaces import LLMEngine
from .models import JSONParseError, LLMOptions, LLMResponseError

logger = logging.getLogger(__name__)


class GeminiEngine(LLMEngine):
    """Shared Gemini LLM engine providing general-purpose LLM methods."""

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
    ):
        settings = get_settings()
        resolved_model_name = model_name or settings.GEMINI_MODEL_NAME
        resolved_api_key = api_key or settings.GEMINI_API_KEY
        if not resolved_api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini API access")

        self.client = genai.Client(api_key=resolved_api_key)
        self.model_name = resolved_model_name

    @staticmethod
    def is_font_corrupted(text: str, threshold: float = 0.05) -> bool:
        """Kiểm tra văn bản có bị lỗi font TCVN3/VNI hay không."""
        if not text:
            return False

        corrupted_pattern = r"[ñöøûîáãäåëï]"
        corrupted_chars = re.findall(corrupted_pattern, text.lower())

        standard_vn_chars = re.findall(r"[đươ]", text.lower())

        corruption_rate = len(corrupted_chars) / len(text)
        if corruption_rate > threshold and len(standard_vn_chars) == 0:
            return True

        return False

    # ── General-purpose LLM methods ──────────────────────────────────

    async def generate_response(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.7,
    ) -> str:
        """Generate a text response from a prompt (with thinking enabled)."""
        print(
            f"DEBUG: Calling Gemini model '{self.model_name}'\nTemperature: {temperature}"
        )
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    thinking_config=types.ThinkingConfig(thinking_budget=128),
                    temperature=temperature,
                ),
            )

            usage = response.usage_metadata
            token_usage_info = {
                "prompt_token_count": usage.prompt_token_count,
                "candidates_token_count": usage.candidates_token_count,
                "total_token_count": usage.total_token_count,
                "thoughts_token_count": usage.thoughts_token_count,
            }

            return {"content": response.text, "token_usage": token_usage_info}

        except Exception as e:
            logger.error(f"Lỗi khi gọi LLM: {e}")
            return None

    async def generate_response_with_pdf(self, prompt: str, file_bytes: bytes) -> str:
        """Generate a text response from a prompt + PDF bytes (with thinking enabled)."""
        try:
            t0 = time.time()
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Part.from_bytes(
                        data=file_bytes,
                        mime_type="application/pdf",
                    ),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=128)
                ),
            )
            t1 = time.time()
            logger.debug(f"[TIMING] LLM generate_content took: {t1 - t0:.2f}s")

            usage = response.usage_metadata
            logger.debug(f"Tokens đầu vào: {usage.prompt_token_count}")
            logger.debug(f"Tokens đầu ra: {usage.candidates_token_count}")
            logger.debug(f"Tổng cộng: {usage.total_token_count}")

            t2 = time.time()
            content = response.text
            t3 = time.time()
            logger.debug(f"[TIMING] response.text took: {t3 - t2:.2f}s")
            logger.debug(f"[TIMING] Content length: {len(content)} chars")

            return content

        except Exception as e:
            logger.error(f"Lỗi khi trích xuất PDF: {e}")
            raise LLMResponseError(f"Failed to generate response with PDF: {e}") from e

    # ── Structured response methods ──────────────────────────────────

    async def generate_structured_response(
        self,
        prompt: str,
        response_schema: dict,
        system_prompt: str = "You are a helpful assistant.",
        options: LLMOptions | None = None,
    ) -> dict:
        """Generate a structured JSON response from a text prompt."""
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=options.temperature if options else 0.0,
                    stop_sequences=options.stop if options else None,
                    max_output_tokens=options.max_tokens if options else 65536,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )
        except Exception as e:
            raise LLMResponseError(
                f"Failed to call Gemini model '{self.model_name}'"
            ) from e

        if not response or not getattr(response, "text", None):
            raise LLMResponseError(
                f"Gemini model '{self.model_name}' returned no response"
            )

        finish_reason = (
            response.candidates[0].finish_reason
            if response.candidates
            else None
        )
        if finish_reason == types.FinishReason.MAX_TOKENS:
            usage = getattr(response, "usage_metadata", None)
            token_info = (
                f" (candidates_token_count={usage.candidates_token_count})"
                if usage
                else ""
            )
            raise LLMResponseError(
                f"Gemini output was truncated at max_output_tokens{token_info}. "
                "Input is too long for a single structured response — consider "
                "chunking the input or reducing schema duplication."
            )

        try:
            if hasattr(response, "parsed") and response.parsed:
                return response.parsed

            return json.loads(response.text)

        except (json.JSONDecodeError, AttributeError) as e:
            raise JSONParseError(
                f"Invalid JSON returned by LLM.\nRaw response:\n{getattr(response, 'text', 'Empty')}"
            ) from e

    async def generate_structured_response_with_pdf(
        self,
        file_bytes: bytes,
        prompt: str,
        response_schema: dict,
    ) -> dict:
        """Generate a structured JSON response from a prompt + PDF bytes."""
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Part.from_bytes(
                        data=file_bytes,
                        mime_type="application/pdf",
                    ),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )

            if hasattr(response, "parsed") and response.parsed:
                return response.parsed

            return json.loads(response.text)

        except Exception as e:
            raise LLMResponseError(
                f"Failed to extract structured data from PDF: {e}"
            ) from e

    async def search_for_document_name(self, description: str) -> str | None:
        """Use Google Search to resolve a document identifier from a legal citation description."""
        prompt = (
            f"Đoạn trích dẫn pháp lý sau đây đề cập đến văn bản nào?\n\n"
            f"\"{description}\"\n\n"
            "Hãy tra cứu và trả về CHỈ mã số/ký hiệu văn bản (ví dụ: 58/2023/NĐ-CP, 666/QĐ-TTg, 518/TTg). "
            "Không giải thích, không thêm bất kỳ nội dung nào khác."
        )
        config = types.GenerateContentConfig(
            temperature=0.0,
            system_instruction=(
                "Bạn là công cụ tra cứu văn bản pháp luật Việt Nam. "
                "Chỉ trả về mã số/ký hiệu văn bản, không có chú thích hay giải thích."
            ),
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            if not response or not getattr(response, "text", None):
                return None
            return response.text.strip()
        except Exception as e:
            logger.error(f"Web search for document name failed: {e}")
            return None

    async def search_stream(self, user_input: str):
        """
        Stream kết quả dựa trên Google Search tool của Gemini
        """
        config = types.GenerateContentConfig(
            temperature=0.2,
            system_instruction="Chỉ sử dụng thông tin từ Google Search để trả lời.",
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )

        stream = await self.client.aio.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=user_input,
            config=config,
        )

        async for chunk in stream:
            if chunk.text:
                yield chunk.text
