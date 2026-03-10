from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str


class ValidationErrorResponse(BaseModel):
    detail: str
    errors: list[dict] | None = None
