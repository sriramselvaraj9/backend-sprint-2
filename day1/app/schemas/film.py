from typing import Optional
from pydantic import BaseModel,ConfigDict


class FilmCreate(BaseModel):
    #model_config = ConfigDict(strict=True) - it is enabled the strick(today topic)
    title: str
    director: str
    release_year: int


class FilmResponse(BaseModel):
    id: int
    title: str
    director: str
    release_year: int
