import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.model_hub.base import AdapterError, ModelResponse
from src.model_hub.openai_compat import OpenAICompatAdapter


class ModelHub:
    async def _build_adapter(self, session: AsyncSession, model_version_id: str) -> OpenAICompatAdapter:
        row = (await session.execute(
            text("SELECT capabilities FROM model_versions WHERE model_version_id = :mid"),
            {"mid": model_version_id},
        )).first()
        if not row:
            raise ValueError(f"model_version_id {model_version_id} not found")
        caps = row[0] or {}
        base_url = caps.get("base_url")
        api_key = caps.get("api_key", "sk-local")
        if not base_url:
            raise ValueError(f"model {model_version_id} has no base_url in capabilities")
        return OpenAICompatAdapter(base_url=base_url, api_key=api_key, model_name=model_version_id)

    async def infer(self, session: AsyncSession, model_version_id: str,
                    prompt: str, retries: int = 2) -> ModelResponse:
        adapter = await self._build_adapter(session, model_version_id)
        attempt = 0
        while True:
            resp = await adapter.chat([{"role": "user", "content": prompt}])
            if resp.error is None or not resp.error.retryable or attempt >= retries:
                return resp
            attempt += 1
            await asyncio.sleep(2 ** attempt)

    async def parallel_infer(self, session: AsyncSession, a: str, b: str,
                             prompt: str) -> tuple[ModelResponse, ModelResponse]:
        return await asyncio.gather(
            self.infer(session, a, prompt),
            self.infer(session, b, prompt),
        )
