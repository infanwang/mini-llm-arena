from dataclasses import dataclass


class AdapterError(Exception):
    def __init__(self, error_class: str, message: str, retryable: bool):
        self.error_class = error_class  # TRANSIENT / AUTH / CAPABILITY / CONTENT
        self.message = message
        self.retryable = retryable
        super().__init__(f"{error_class}: {message}")


@dataclass
class ModelResponse:
    text: str
    finish_reason: str
    latency_ms: int
    error: AdapterError | None = None
