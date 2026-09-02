from nimbus_support.graph.generate import GenerateResult


class ScriptedLLM:
    def __init__(self, first: GenerateResult, *rest: GenerateResult) -> None:
        self._queue = [first, *rest]
        self.result = first
        self.calls: list[dict] = []

    def complete(
        self,
        *,
        query: str,
        chunks: list[dict],
        messages: list[dict] | None = None,
        order: dict | None = None,
    ) -> GenerateResult:
        self.calls.append(
            {
                "query": query,
                "chunks": chunks,
                "messages": messages or [],
                "order": order,
            }
        )
        if self._queue:
            return self._queue.pop(0)
        return self.result
