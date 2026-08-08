"""Tortoise → JSON error handlers.

Tortoise ships handlers for its own exception types; registering them keeps
`DoesNotExist` / `IntegrityError` / `ValidationError` from surfacing as bare 500s.
"""

from fastapi import FastAPI
from tortoise.contrib.fastapi import tortoise_exception_handlers


def register_exception_handlers(app: FastAPI) -> None:
    for exc_type, handler in tortoise_exception_handlers().items():
        app.add_exception_handler(exc_type, handler)
