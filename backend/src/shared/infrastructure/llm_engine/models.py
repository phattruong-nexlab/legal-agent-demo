from dataclasses import dataclass
from typing import List, Optional


@dataclass
class LLMOptions:
    temperature: float = 0.0
    max_tokens: int = 1024
    top_p: float = 1.0
    response_format: Optional[dict] = None
    stop: Optional[List[str]] = None
    seed: Optional[int] = None
    response_mime_type: Optional[str] = None
    system_instructions: Optional[str] = None


class LLMResponseError(Exception):
    """LLM did not return a valid response."""

    pass


class JSONParseError(Exception):
    """Failed to parse JSON from LLM output."""

    pass
