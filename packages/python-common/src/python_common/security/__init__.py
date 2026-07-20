from pydantic import BaseModel


class Actor(BaseModel):
    subject: str
    roles: list[str] = []
