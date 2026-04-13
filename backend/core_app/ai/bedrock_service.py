from __future__ import annotations

import ast
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any, Literal

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from core_app.config import get_settings

logger = logging.getLogger(__name__)

try:
    from core_app.services.circuit_breaker import CircuitBreakerRegistry
    _bedrock_breaker = CircuitBreakerRegistry.get("bedrock", failure_threshold=3, recovery_timeout=60)
except Exception:  # pragma: no cover
    _bedrock_breaker = None

# AWS Bedrock Model Pricing (per 1M tokens, as of 2024)
MODEL_PRICING = {
    "anthropic.claude-3-5-sonnet-20241022-v2:0": {
        "input": Decimal("3.00"),  # $3 per 1M input tokens
        "output": Decimal("15.00"),  # $15 per 1M output tokens
    },
    "anthropic.claude-3-5-sonnet-20240620-v1:0": {
        "input": Decimal("3.00"),
        "output": Decimal("15.00"),
    },
    "anthropic.claude-3-opus-20240229-v1:0": {
        "input": Decimal("15.00"),  # $15 per 1M input tokens
        "output": Decimal("75.00"),  # $75 per 1M output tokens
    },
    "anthropic.claude-3-sonnet-20240229-v1:0": {
        "input": Decimal("3.00"),
        "output": Decimal("15.00"),
    },
    "anthropic.claude-3-haiku-20240307-v1:0": {
        "input": Decimal("0.25"),  # $0.25 per 1M input tokens
        "output": Decimal("1.25"),  # $1.25 per 1M output tokens
    },
}

# Default model for different use cases
DEFAULT_MODELS = {
    "high_accuracy": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "balanced": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "fast": "anthropic.claude-3-haiku-20240307-v1:0",
}


class BedrockClientError(Exception):
    """Custom exception for Bedrock client errors"""
    pass


class BedrockRateLimitError(BedrockClientError):
    """Raised when rate limit is exceeded"""
    pass


class BedrockThrottlingError(BedrockClientError):
    """Raised when request is throttled"""
    pass


class BedrockClient:
    """
    AWS Bedrock client wrapper for Claude models.

    Handles:
    - Multiple model support (Claude 3.5 Sonnet, Opus, Haiku)
    - Streaming and non-streaming responses
    - Token counting and cost tracking
    - Error handling with exponential backoff retry
    - Request/response logging
    """

    def __init__(
        self,
        region: str | None = None,
        model_id: str | None = None,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize Bedrock client.

        Model ID resolution order:
        1. Explicit model_id parameter (if provided)
        2. settings.bedrock_model_id (from config.py)
        3. Config.py fallback chain:
           - BEDROCK_MODEL_ID env var (canonical)
           - AWS_BEDROCK_MODEL_ID env var (backward compat)
        4. Default: anthropic.claude-3-5-sonnet-20241022-v2:0

        Args:
            region: AWS region (defaults to settings.bedrock_region or settings.aws_region)
            model_id: Default model ID to use
            max_retries: Maximum number of retries for transient errors
        """
        settings = get_settings()
        self.region = region or settings.bedrock_region or settings.aws_region or "us-east-1"
        self.model_id = model_id or DEFAULT_MODELS["balanced"]
        self.max_retries = max_retries

        # Configure boto3 client with retries
        config = Config(
            region_name=self.region,
            retries={"max_attempts": max_retries, "mode": "adaptive"},
            read_timeout=300,  # 5 minutes for long requests
            connect_timeout=10,
        )

        try:
            self.client = boto3.client("bedrock-runtime", config=config)
        except Exception as exc:
            raise BedrockClientError(f"Failed to initialize Bedrock client: {exc}") from exc

    def calculate_cost(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Decimal:
        """
        Calculate cost in USD for a request.

        Args:
            model_id: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD (6 decimal places)
        """
        if model_id not in MODEL_PRICING:
            # Default to Sonnet pricing if model not found
            pricing = MODEL_PRICING["anthropic.claude-3-5-sonnet-20241022-v2:0"]
        else:
            pricing = MODEL_PRICING[model_id]

        input_cost = (Decimal(input_tokens) / Decimal(1_000_000)) * pricing["input"]
        output_cost = (Decimal(output_tokens) / Decimal(1_000_000)) * pricing["output"]

        return (input_cost + output_cost).quantize(Decimal("0.000001"))

    def _build_messages_payload(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        top_p: float = 1.0,
        stop_sequences: list[str] | None = None,
        anthropic_version: str = "bedrock-2023-05-31",
    ) -> dict[str, Any]:
        """
        Build the request payload for Bedrock Converse API.

        Args:
            messages: List of message dicts with role and content
            system: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 1.0)
            top_p: Nucleus sampling parameter
            stop_sequences: Stop sequences for generation
            anthropic_version: API version

        Returns:
            Request payload dict
        """
        payload: dict[str, Any] = {
            "anthropic_version": anthropic_version,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        if system:
            payload["system"] = system

        if stop_sequences:
            payload["stop_sequences"] = stop_sequences

        return payload

    @staticmethod
    def parse_json_content(
        raw_text: str,
        *,
        expected: Literal["object", "array"] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Extract structured JSON from Bedrock text output.

        Supports fenced code blocks and extra prose surrounding the JSON body.
        """
        cleaned = (raw_text or "").replace("\x00", "").strip()
        if not cleaned:
            raise BedrockClientError("Bedrock response did not contain text content.")

        if "```" in cleaned:
            segments = [segment.strip() for segment in cleaned.split("```") if segment.strip()]
            if segments:
                cleaned = segments[0]
                if cleaned.lower().startswith("json"):
                    cleaned = cleaned[4:].strip()

        candidates: list[str] = [cleaned]

        object_start = cleaned.find("{")
        object_end = cleaned.rfind("}")
        if object_start != -1 and object_end != -1 and object_end > object_start:
            candidates.append(cleaned[object_start : object_end + 1])

        array_start = cleaned.find("[")
        array_end = cleaned.rfind("]")
        if array_start != -1 and array_end != -1 and array_end > array_start:
            candidates.append(cleaned[array_start : array_end + 1])

        last_error: Exception | None = None
        for candidate in dict.fromkeys(candidates):
            candidate = candidate.strip()
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError as exc:
                last_error = exc
                try:
                    parsed = ast.literal_eval(candidate)
                except (SyntaxError, ValueError) as fallback_exc:
                    last_error = fallback_exc
                    continue

            if expected == "object" and not isinstance(parsed, dict):
                continue
            if expected == "array" and not isinstance(parsed, list):
                continue
            if not isinstance(parsed, (dict, list)):
                continue
            return parsed

        raise BedrockClientError(
            f"Bedrock response could not be parsed as {expected or 'JSON'}"
        ) from last_error

    def invoke(
        self,
        prompt: str,
        system: str | None = None,
        model_id: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        top_p: float = 1.0,
        stop_sequences: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Invoke Bedrock model (non-streaming).

        Args:
            prompt: User prompt text
            system: Optional system prompt
            model_id: Model to use (defaults to instance default)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling
            stop_sequences: Stop sequences
            metadata: Additional metadata to include in response

        Returns:
            Dict containing:
                - content: Generated text
                - model: Model ID used
                - input_tokens: Input token count
                - output_tokens: Output token count
                - total_tokens: Total token count
                - cost: Cost in USD
                - latency_ms: Request latency in milliseconds
                - stop_reason: Why generation stopped
                - metadata: Additional metadata

        Raises:
            BedrockClientError: For client errors
            BedrockRateLimitError: For rate limit errors
            BedrockThrottlingError: For throttling errors
        """
        model_id = model_id or self.model_id
        start_time = time.time()

        messages = [{"role": "user", "content": prompt}]
        payload = self._build_messages_payload(
            messages=messages,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop_sequences=stop_sequences,
        )

        try:
            # Circuit breaker pre-check for Bedrock calls
            if _bedrock_breaker is not None:
                import asyncio as _aio
                try:
                    _state = _aio.run(_bedrock_breaker._current_state())
                    from core_app.services.circuit_breaker import CircuitState
                    if _state == CircuitState.OPEN:
                        raise BedrockClientError(
                            "Bedrock circuit breaker is OPEN — calls rejected until recovery"
                        )
                except BedrockClientError:
                    raise
                except Exception:
                    pass  # breaker check failure is non-fatal

            response = self.client.invoke_model(
                modelId=model_id,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json",
            )

            # Record success with circuit breaker
            if _bedrock_breaker is not None:
                try:
                    _aio.run(_bedrock_breaker._record_success())
                except Exception:
                    pass

            raw_body = response["body"].read()
            candidate_texts: list[str] = []

            if isinstance(raw_body, str):
                candidate_texts.append(raw_body)
            elif isinstance(raw_body, (bytes, bytearray)):
                candidate_texts.append(raw_body.decode("utf-8", errors="ignore"))
            else:
                try:
                    candidate_texts.append(bytes(raw_body).decode("utf-8", errors="ignore"))
                except Exception:
                    logger.warning("Failed bytes() conversion for Bedrock response body type=%s", type(raw_body).__name__)

                raw_bytes_fn = getattr(raw_body, "__bytes__", None)
                if callable(raw_bytes_fn):
                    for call in (
                        lambda: raw_bytes_fn(),
                        lambda: raw_bytes_fn(raw_body),
                    ):
                        try:
                            value = call()
                            if isinstance(value, (bytes, bytearray)):
                                candidate_texts.append(value.decode("utf-8", errors="ignore"))
                            elif isinstance(value, str):
                                candidate_texts.append(value)
                        except Exception:
                            logger.warning("Failed __bytes__ call for Bedrock response body")
                            continue

                candidate_texts.append(str(raw_body))

            response_body = None
            for candidate in candidate_texts:
                cleaned = (candidate or "").replace("\x00", "").strip()
                if not cleaned:
                    continue
                try:
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, dict):
                        response_body = parsed
                        break
                except json.JSONDecodeError:
                    try:
                        parsed = ast.literal_eval(cleaned)
                        if isinstance(parsed, dict):
                            response_body = parsed
                            break
                    except Exception:
                        logger.warning("Failed ast.literal_eval fallback for Bedrock response parsing")
                        continue

            if response_body is None:
                raise BedrockClientError("Unable to parse Bedrock response body")
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract content and usage
            content = response_body.get("content", [{}])[0].get("text", "")
            usage = response_body.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            total_tokens = input_tokens + output_tokens

            cost = self.calculate_cost(model_id, input_tokens, output_tokens)

            result = {
                "content": content,
                "model": model_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost": float(cost),
                "latency_ms": latency_ms,
                "stop_reason": response_body.get("stop_reason", "unknown"),
                "metadata": metadata or {},
            }

            return result

        except ClientError as exc:
            # Record failure with circuit breaker
            if _bedrock_breaker is not None:
                try:
                    _aio.run(_bedrock_breaker._record_failure(exc))
                except Exception:
                    pass
            error_code = exc.response.get("Error", {}).get("Code", "")
            error_message = exc.response.get("Error", {}).get("Message", str(exc))

            # Log full provider details server-side for debugging
            logger.error(
                "Bedrock API error — code=%s message=%s",
                error_code, error_message
            )

            # Raise with generic messages (no provider detail leakage to clients)
            if error_code == "ThrottlingException":
                raise BedrockThrottlingError(
                    "Request temporarily throttled. Please retry after a short delay."
                ) from exc
            elif error_code == "TooManyRequestsException":
                raise BedrockRateLimitError(
                    "Rate limit exceeded. Service will recover shortly."
                ) from exc
            else:
                raise BedrockClientError(
                    "AI service encountered an error. Please try again later."
                ) from exc

        except BedrockClientError:
            raise

        except Exception as exc:
            # Record failure with circuit breaker
            if _bedrock_breaker is not None:
                try:
                    _aio.run(_bedrock_breaker._record_failure(exc))
                except Exception:
                    pass
            # Log full stack for debugging, raise generic message
            logger.exception("Unexpected error invoking Bedrock")
            raise BedrockClientError(
                "AI service encountered an unexpected error. Please try again later."
            ) from exc

    async def invoke_stream(
        self,
        prompt: str,
        system: str | None = None,
        model_id: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        top_p: float = 1.0,
        stop_sequences: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Invoke Bedrock model with streaming response.

        Args:
            prompt: User prompt text
            system: Optional system prompt
            model_id: Model to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling
            stop_sequences: Stop sequences

        Yields:
            Dicts containing:
                - type: Event type (content_block_start, content_block_delta, content_block_stop, message_stop)
                - content: Text content (for delta events)
                - index: Content block index
                - stop_reason: Stop reason (for message_stop)
                - usage: Token usage (for message_stop)

        Raises:
            BedrockClientError: For client errors
        """
        model_id = model_id or self.model_id

        messages = [{"role": "user", "content": prompt}]
        payload = self._build_messages_payload(
            messages=messages,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop_sequences=stop_sequences,
        )

        try:
            response = self.client.invoke_model_with_response_stream(
                modelId=model_id,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json",
            )

            # Process streaming events
            for event in response["body"]:
                chunk = json.loads(event["chunk"]["bytes"].decode())

                event_type = chunk.get("type")

                if event_type == "content_block_start":
                    yield {
                        "type": "content_block_start",
                        "index": chunk.get("index", 0),
                    }

                elif event_type == "content_block_delta":
                    delta = chunk.get("delta", {})
                    if delta.get("type") == "text_delta":
                        yield {
                            "type": "content_block_delta",
                            "content": delta.get("text", ""),
                            "index": chunk.get("index", 0),
                        }

                elif event_type == "content_block_stop":
                    yield {
                        "type": "content_block_stop",
                        "index": chunk.get("index", 0),
                    }

                elif event_type == "message_delta":
                    delta = chunk.get("delta", {})
                    usage = chunk.get("usage", {})
                    yield {
                        "type": "message_delta",
                        "stop_reason": delta.get("stop_reason"),
                        "usage": usage,
                    }

                elif event_type == "message_stop":
                    yield {"type": "message_stop"}

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            error_message = exc.response.get("Error", {}).get("Message", str(exc))

            # Log full provider details server-side
            logger.error(
                "Bedrock streaming API error — code=%s message=%s",
                error_code, error_message
            )

            # Raise generic message (no provider detail leakage to clients)
            raise BedrockClientError(
                "AI streaming service encountered an error. Please try again."
            ) from exc

        except Exception as exc:
            # Log full exception for debugging
            logger.exception("Unexpected error in Bedrock streaming")
            raise BedrockClientError(
                "AI streaming service encountered an unexpected error. Please try again."
            ) from exc

    def invoke_with_retry(
        self,
        prompt: str,
        system: str | None = None,
        model_id: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        """
        Invoke with exponential backoff retry for transient errors.

        Args:
            prompt: User prompt
            system: System prompt
            model_id: Model to use
            max_tokens: Max tokens
            temperature: Temperature
            max_retries: Override instance max_retries

        Returns:
            Response dict from invoke()

        Raises:
            BedrockClientError: After all retries exhausted
        """
        max_retries = max_retries or self.max_retries
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                return self.invoke(
                    prompt=prompt,
                    system=system,
                    model_id=model_id,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except (BedrockThrottlingError, BedrockRateLimitError) as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s, ...
                    wait_time = 2**attempt
                    time.sleep(wait_time)
                    continue
                else:
                    raise
            except BedrockClientError:
                # Don't retry on other client errors
                raise

        # Should never reach here, but satisfy type checker
        if last_error:
            raise last_error
        raise BedrockClientError("Unexpected retry loop exit")

    def count_tokens(self, text: str, model_id: str | None = None) -> int:
        """
        Estimate token count for text.

        This is an approximation using Claude's tokenization rules.
        For exact counts, use the actual API response.

        Args:
            text: Text to count tokens for
            model_id: Model ID (not currently used, reserved for future)

        Returns:
            Estimated token count
        """
        # Rough approximation: 1 token ~= 4 characters for English text
        # Claude uses a similar tokenizer to GPT-4
        # More accurate: use tiktoken or Claude's tokenizer API when available
        return len(text) // 4

    def hash_input(self, text: str) -> str:
        """
        Generate SHA256 hash of input text for deduplication.

        Args:
            text: Input text

        Returns:
            Hex-encoded SHA256 hash
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get_model_for_use_case(
        self,
        use_case: Literal["high_accuracy", "balanced", "fast"],
    ) -> str:
        """
        Get recommended model ID for a use case.

        Args:
            use_case: Use case type

        Returns:
            Model ID string
        """
        return DEFAULT_MODELS.get(use_case, DEFAULT_MODELS["balanced"])

    def resolve_model_id_for_module(self, module: str) -> str:
        """Resolve Bedrock model ID using module-specific config with canonical fallback."""
        settings = get_settings()
        module_map = {
            "command": settings.bedrock_model_id_command,
            "field": settings.bedrock_model_id_field,
            "flow": settings.bedrock_model_id_flow,
            "pulse": settings.bedrock_model_id_pulse,
            "air": settings.bedrock_model_id_air,
            "interop": settings.bedrock_model_id_interop,
            "insight": settings.bedrock_model_id_insight,
        }
        return module_map.get(module) or settings.bedrock_model_id or self.model_id

    def invoke_json_task(
        self,
        *,
        module: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1800,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Invoke model for orchestrated AI tasks and extract structured JSON safely."""
        model_id = self.resolve_model_id_for_module(module)
        raw = self.invoke(
            prompt=user_prompt,
            system=system_prompt,
            model_id=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = str(raw.get("content") or "")
        parsed = self.parse_json_content(content, expected=None)
        return {
            "model_id": model_id,
            "text": content,
            "parsed": parsed,
            "usage": {
                "input_tokens": raw.get("input_tokens", 0),
                "output_tokens": raw.get("output_tokens", 0),
                "total_tokens": raw.get("total_tokens", 0),
                "cost": raw.get("cost", 0),
            },
            "latency_ms": raw.get("latency_ms", 0),
        }


def get_bedrock_client(
    region: str | None = None,
    model_id: str | None = None,
) -> BedrockClient:
    """
    Factory function to get a configured Bedrock client.

    Args:
        region: AWS region override
        model_id: Default model ID override

    Returns:
        Configured BedrockClient instance
    """
    return BedrockClient(region=region, model_id=model_id)
