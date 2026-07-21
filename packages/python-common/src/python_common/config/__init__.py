from pydantic import BaseModel


class AppConfig(BaseModel):
    service_name: str
    environment: str = "dev"
