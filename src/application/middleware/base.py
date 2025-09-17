from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Generic, TypeVar

T = TypeVar('T')
R = TypeVar('R')

Handler = Callable[[T], Awaitable[R]]


class Middleware(ABC, Generic[T, R]):
    @abstractmethod
    async def __call__(self, request: T, next_handler: Handler[T, R]) -> R:
        pass


class MiddlewarePipeline(Generic[T, R]):
    def __init__(self, handler: Handler[T, R]):
        self.handler = handler
        self.middlewares: list[Middleware[T, R]] = []
    
    def use(self, middleware: Middleware[T, R]) -> MiddlewarePipeline[T, R]:
        self.middlewares.append(middleware)
        return self
    
    async def execute(self, request: T) -> R:
        def build_chain(index: int) -> Handler[T, R]:
            if index >= len(self.middlewares):
                return self.handler
            
            middleware = self.middlewares[index]
            next_handler = build_chain(index + 1)
            
            async def chained_handler(req: T) -> R:
                return await middleware(req, next_handler)
            
            return chained_handler
        
        chain = build_chain(0)
        return await chain(request)