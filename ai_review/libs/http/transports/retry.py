import asyncio
from http import HTTPStatus
from typing import TYPE_CHECKING

from httpx import Request, Response, AsyncBaseTransport

if TYPE_CHECKING:
    from loguru import Logger


class RetryTransport(AsyncBaseTransport):
    def __init__(
            self,
            logger: "Logger",
            transport: AsyncBaseTransport,
            max_retries: int = 5,
            retry_delay: float = 0.5,
            retry_status_codes: tuple[HTTPStatus, ...] = (
                    HTTPStatus.BAD_GATEWAY,
                    HTTPStatus.GATEWAY_TIMEOUT,
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    HTTPStatus.INTERNAL_SERVER_ERROR,
            ),
            retry_methods: tuple[str, ...] | None = None,
    ):
        self.logger = logger
        self.transport = transport
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_status_codes = retry_status_codes
        self.retry_methods = tuple(method.upper() for method in retry_methods) if retry_methods else None

    async def handle_async_request(self, request: Request) -> Response:
        last_response: Response | None = None
        for attempt in range(self.max_retries):
            last_response = await self.transport.handle_async_request(request)
            if self.retry_methods and request.method.upper() not in self.retry_methods:
                return last_response
            if last_response.status_code not in self.retry_status_codes:
                return last_response

            self.logger.warning(
                f"Attempt {attempt + 1}/{self.max_retries} failed "
                f"with status={last_response.status_code} for {request.method} {request.url}. "
                f"Retrying in {self.retry_delay:.1f}s..."
            )

            await asyncio.sleep(self.retry_delay)

        self.logger.error(
            f"All {self.max_retries} attempts failed for "
            f"{request.method} {request.url} (last status={last_response.status_code})"
        )

        return last_response
