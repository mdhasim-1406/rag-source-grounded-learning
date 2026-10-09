import json
import re
from typing import List, Dict, Any, Optional, AsyncGenerator
import openai
from openai import AsyncOpenAI
from ..config import settings


class LLMClient:
    def __init__(self):
        self._init_client()

    def _init_client(self):
        self.client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout,
        )
        self.model = settings.llm_model

    def _format_error(self, err: Exception) -> str:
        if isinstance(err, openai.APITimeoutError):
            return f"LLM request timed out after {settings.llm_timeout}s. Check model endpoint availability."
        if isinstance(err, openai.AuthenticationError):
            return "LLM authentication failed. Verify API key configuration."
        if isinstance(err, openai.RateLimitError):
            return "LLM rate limit reached. Please retry after a brief delay."
        if isinstance(err, openai.APIConnectionError):
            return f"Cannot connect to LLM gateway at {settings.llm_base_url}. Verify service is reachable."
        if isinstance(err, openai.APIStatusError):
            return f"LLM gateway returned error HTTP {err.status_code}: {err.message or 'Request failed'}"
        if isinstance(err, openai.OpenAIError):
            return f"LLM provider error: {str(err)}"
        return f"Unexpected error during LLM generation: {str(err)}"

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2500
    ) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=settings.llm_timeout,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise RuntimeError(self._format_error(e)) from e

    async def generate_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2
    ) -> Any:
        raw_text = await self.generate_completion(messages, temperature=temperature)
        return self._extract_json(raw_text)

    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3
    ) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                temperature=temperature,
                stream=True,
                timeout=settings.llm_timeout,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise RuntimeError(self._format_error(e)) from e

    def _extract_json(self, text: str) -> Any:
        """Robustly extracts JSON from raw text or markdown code fences."""
        text = text.strip()
        # Look for ```json ... ``` or ``` ... ```
        fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                pass

        # Look for { ... } or [ ... ]
        first_brace = text.find('{')
        first_bracket = text.find('[')
        
        start = -1
        is_array = False
        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            start = first_brace
        elif first_bracket != -1:
            start = first_bracket
            is_array = True

        if start != -1:
            end = text.rfind(']' if is_array else '}')
            if end != -1 and end > start:
                candidate = text[start:end+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    pass

        # Direct parse attempt
        return json.loads(text)


llm_client = LLMClient()
