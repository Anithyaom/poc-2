from fastapi import APIRouter

from src.textbook.library import BookOutline, load_book, outline

router = APIRouter(prefix="/api/textbooks", tags=["textbooks"])


@router.get("", response_model=list[BookOutline])
async def list_textbooks() -> list[BookOutline]:
    """Chapters and sections for the lab intake picker — titles and pages, no text.

    Empty when the textbook has not been extracted and mounted; the picker hides itself.
    """
    book = load_book()
    return [outline(book)] if book else []
