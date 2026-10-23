from __future__ import annotations

import asyncio

from robot_copilot.llm.base import LLMProvider, ProposalRequest, ProviderResult


class SpyProvider:
    name = "mock"
    model = "mock-1"

    def __init__(self, inner: LLMProvider) -> None:
        self._inner = inner
        self.calls = 0

    async def propose(self, request: ProposalRequest) -> ProviderResult:
        self.calls += 1
        return await self._inner.propose(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


class GatedProvider:
    name = "mock"
    model = "mock-1"

    def __init__(self, inner: LLMProvider) -> None:
        self._inner = inner
        self.enter = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()

    async def propose(self, request: ProposalRequest) -> ProviderResult:
        self.enter.set()
        await self.release.wait()
        return await self._inner.propose(request)

    async def aclose(self) -> None:
        await self._inner.aclose()
