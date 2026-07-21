from pydantic import BaseModel


class DomainEvent(BaseModel):
    event_name: str
    payload: dict
