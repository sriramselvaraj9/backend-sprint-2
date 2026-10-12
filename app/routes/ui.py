import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_film_service
from app.services.film_service import FilmService

logger = logging.getLogger("ui_router")

# Base directory for Jinja2 templates (app/templates)
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["UI"])


@router.get("/films", response_class=HTMLResponse)
async def get_films_page(
    request: Request,
) -> HTMLResponse:
    """
    Serve the complete server-rendered Film Search HTML page.
    Contains the search input with htmx attributes, dynamic results container,
    and official htmx library loaded in the head.
    """
    logger.info("Serving full HTML film search page")
    return templates.TemplateResponse(
        request=request,
        name="ui/films.html",
    )


@router.get("/films/search", response_class=HTMLResponse)
async def search_films_fragment(
    request: Request,
    q: str | None = None,
    film_service: FilmService = Depends(get_film_service),
) -> HTMLResponse:
    """
    Serve the server-rendered HTML fragment of matching film cards for htmx dynamic replacement.
    Accepts search query 'q', normalizes whitespace, retrieves active films with average ratings,
    and returns only the partial HTML markup.
    """
    search_term = q.strip() if q is not None else None 
    logger.info(f"Rendering film search fragment for query: '{search_term}'")

    films = await film_service.search_films_by_title(title=search_term)

    return templates.TemplateResponse(
        request=request, 
        name="ui/partials/film_results.html", 
        context={
            "films": films, 
            "query": search_term or "", 
        },
    )
