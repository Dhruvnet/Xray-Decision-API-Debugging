import httpx
import asyncio


class XRayTransport:
    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip("/")
        self.enabled = True

    async def post(self, path: str, payload: dict):
        if not self.enabled:
            return

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(f"{self.api_url}{path}", json=payload)
        except Exception:
            # Fail-safe mode: never break the pipeline
            self.enabled = False
            print("[XRAY] Backend unreachable — switching to no-op mode")

    def post_sync(self, path: str, payload: dict):
        asyncio.run(self.post(path, payload))
