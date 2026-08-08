"""Stub auth for the POC — a single fixed dev user.

Every endpoint that will eventually need an identity takes it from here, so real
auth drops in by replacing this one function. `courses.owner_sub` is the column
it keys off.
"""

from src.config.settings import settings


def current_user_sub() -> str:
    return settings.fake_user_sub
