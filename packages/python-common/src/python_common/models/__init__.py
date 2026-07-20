from pydantic import BaseModel


class Envelope(BaseModel):
    id: str
