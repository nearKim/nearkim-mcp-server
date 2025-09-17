
from __future__ import annotations

from typing import Iterable

from .api import TodoistAPIBase
from .cache import CacheService


class LabelService:
    
    def __init__(
        self, api: TodoistAPIBase, cache: CacheService, autocreate: bool = False
    ):
        self.api = api
        self.cache = cache
        self.autocreate = autocreate

    async def ensure_cache_loaded(self) -> None:
        if not self.cache.is_labels_cached():
            labels = await self.api.fetch_labels()
            self.cache.populate_labels(labels)

    async def ensure_labels_exist(self, names: Iterable[str]) -> dict[str, str]:
        await self.ensure_cache_loaded()
        label_map: dict[str, str] = {}
        for name in names:
            plain = name.lstrip("@")
            label_id = self.cache.labels.get_id(plain)
            if label_id:
                label_map[name] = label_id
                continue
            if not self.autocreate:
                continue
            new_label = await self.api.add_label(plain)
            self.cache.labels.add(new_label)
            label_map[name] = new_label.id
        return label_map