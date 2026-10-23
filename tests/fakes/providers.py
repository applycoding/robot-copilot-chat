from __future__ import annotations

import asyncio

from robot_copilot.llm.base import LLMProvider, ProposalRequest, ProviderError, ProviderResult
from robot_copilot.llm.mock import MockProvider


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


class GatedOnRepairProvider:
    """Blocks only when the orchestrator calls the provider for a repair attempt."""

    name = "mock"
    model = "mock-1"

    def __init__(self, inner: LLMProvider) -> None:
        self._inner = inner
        self.enter = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()

    async def propose(self, request: ProposalRequest) -> ProviderResult:
        if request.repair is not None:
            self.enter.set()
            await self.release.wait()
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


class ErrorProvider:
    name = "mock"
    model = "mock-1"

    def __init__(self, kind: str = "unavailable", message: str = "boom") -> None:
        self.kind = kind  # type: ignore[assignment]
        self.message = message
        self.calls = 0

    async def propose(self, request: ProposalRequest) -> ProviderResult:
        self.calls += 1
        raise ProviderError(self.kind, self.message)  # type: ignore[arg-type]

    async def aclose(self) -> None:
        return None


class ErrorOnRepairProvider:
    name = "mock"
    model = "mock-1"

    def __init__(self) -> None:
        self._mock = MockProvider("mock-1")

    async def propose(self, request: ProposalRequest) -> ProviderResult:
        if request.repair is not None:
            raise ProviderError("unavailable", "boom")
        return await self._mock.propose(request)

    async def aclose(self) -> None:
        await self._mock.aclose()


class MockThenTextProvider:
    """Mock plans on chat; plain text on repair."""

    name = "mock"
    model = "mock-1"

    def __init__(self) -> None:
        self._mock = MockProvider("mock-1")
        self._text = TextOnlyProvider()

    async def propose(self, request: ProposalRequest) -> ProviderResult:
        if request.repair is not None:
            return await self._text.propose(request)
        return await self._mock.propose(request)

    async def aclose(self) -> None:
        await self._mock.aclose()


class TextOnlyProvider:
    """Always returns plain text (no plan) for repair accounting tests."""

    name = "mock"
    model = "mock-1"

    async def propose(self, request: ProposalRequest) -> ProviderResult:
        return ProviderResult(
            kind="text",
            text="I cannot produce a structured plan right now.",
            provider="mock",
            model="mock-1",
        )

    async def aclose(self) -> None:
        return None


class RepairHangProvider:
    """Mock for initial chat; hangs on repair attempts (for timeout tests)."""

    name = "mock"
    model = "mock-1"

    def __init__(self) -> None:
        self._mock = MockProvider("mock-1")
        self._hang = HangProvider()

    async def propose(self, request: ProposalRequest) -> ProviderResult:
        if request.repair is not None:
            return await self._hang.propose(request)
        return await self._mock.propose(request)

    async def aclose(self) -> None:
        await self._mock.aclose()


class HangProvider:
    name = "mock"
    model = "mock-1"

    def __init__(self) -> None:
        self.enter = asyncio.Event()

    async def propose(self, request: ProposalRequest) -> ProviderResult:
        self.enter.set()
        await asyncio.Event().wait()
        return ProviderResult(kind="text", text="", provider="mock", model="mock-1")

    async def aclose(self) -> None:
        return None
