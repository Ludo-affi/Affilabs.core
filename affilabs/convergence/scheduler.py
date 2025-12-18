from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Mapping, Sequence, TypeVar

T = TypeVar("T")


class ThreadScheduler:
    def __init__(self, max_workers: int = 1) -> None:
        self._max_workers = max(1, int(max_workers))

    def map_with_timeout(
        self,
        items: Sequence[str],
        fn: Callable[[str], T],
        timeout_s: float,
    ) -> Mapping[str, T]:
        results: Dict[str, T] = {}
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            future_to_key = {pool.submit(fn, key): key for key in items}
            for fut in as_completed(future_to_key, timeout=timeout_s if timeout_s > 0 else None):
                key = future_to_key[fut]
                try:
                    results[key] = fut.result(timeout=0)
                except Exception:
                    # Skip failed entry; caller can handle missing keys
                    pass
        return results
