from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_host: str = "redis"
    redis_port: int = 6379
    openai_api_key: str = ""
    teams_webhook_url: str = ""
    service_port: int = 1985


settings = Settings()

