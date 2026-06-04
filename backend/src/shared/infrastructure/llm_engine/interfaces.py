from typing import Protocol

from .models import LLMOptions


class LLMEngine(Protocol):
    """Interface for LLM engines used across modules."""

    async def generate_response(self, prompt: str) -> str:
        """Generate a text response from a prompt."""
        raise NotImplementedError

    async def generate_response_with_pdf(self, prompt: str, file_bytes: bytes) -> str:
        """Generate a text response from a prompt and PDF bytes."""
        raise NotImplementedError

    async def generate_structured_response(
        self,
        prompt: str,
        response_schema: dict,
        options: LLMOptions | None = None,
    ) -> dict:
        """Generate a structured JSON response from a prompt."""
        raise NotImplementedError

    async def generate_structured_response_with_pdf(
        self,
        file_bytes: bytes,
        prompt: str,
        response_schema: dict,
    ) -> dict:
        """Generate a structured JSON response from a prompt and PDF bytes."""
        raise NotImplementedError

    async def search_for_document_name(self, description: str) -> str | None:
        """Search the web to resolve a document identifier from a legal citation description."""
        raise NotImplementedError

    @staticmethod
    def is_font_corrupted(text: str, threshold: float = 0.05) -> bool:
        """Check if text has corrupted font encoding."""
        raise NotImplementedError
