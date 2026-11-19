"""Handlers package."""
from app.handlers.auth_user_handler import AuthUserHandler
from app.handlers.film_handler import FilmHandler
from app.handlers.review_handler import ReviewHandler
from app.handlers.storage_handler import StorageHandler

__all__ = [
    "AuthUserHandler",
    "FilmHandler",
    "ReviewHandler",
    "StorageHandler",
]
