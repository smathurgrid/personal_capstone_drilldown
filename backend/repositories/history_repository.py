"""In-memory drill history persistence."""


class HistoryRepository:
    """Stores ecommerce drill-down nodes for the current process."""

    def __init__(self) -> None:
        self._nodes: list[dict] = []

    def append(self, node: dict) -> None:
        self._nodes.append(node)

    def list_all(self) -> list[dict]:
        return list(self._nodes)

    def clear(self) -> None:
        self._nodes.clear()
