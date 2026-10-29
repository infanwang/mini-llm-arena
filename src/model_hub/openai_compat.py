import httpx

from src.model_hub.base import AdapterError, ModelResponse


class OpenAICompatAdapter:
    def __init__(self, base_url: str, api_key: str, model_name: str, timeout_s: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_s = timeout_s

    async def chat(self, messages: list[dict], temperature: float = 0.7,
                   max_tokens: int | None = None) -> ModelResponse:
        payload = {"model": self.model_name, "messages": messages, "temperature": temperature}
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            return ModelResponse(text="", finish_reason="error", latency_ms=0,
                                 error=AdapterError("TRANSIENT", str(e), retryable=True))

        latency = int(resp.elapsed.total_seconds() * 1000)

        if resp.status_code == 429 or resp.status_code >= 500:
            return ModelResponse("", "error", latency,
                                 AdapterError("TRANSIENT", resp.text, retryable=True))
        if resp.status_code == 401:
            return ModelResponse("", "error", latency,
                                 AdapterError("AUTH", resp.text, retryable=False))
        if resp.status_code == 400:
            body = resp.text.lower()
            if "content_filter" in body or "content_policy" in body:
                return ModelResponse("", "content_filter", latency,
                                     AdapterError("CONTENT", resp.text, retryable=False))
            return ModelResponse("", "error", latency,
                                 AdapterError("CAPABILITY", resp.text, retryable=False))

        data = resp.json()
        choice = data["choices"][0]
        return ModelResponse(
            text=choice["message"]["content"],
            finish_reason=choice.get("finish_reason", "stop"),
            latency_ms=latency,
        )
