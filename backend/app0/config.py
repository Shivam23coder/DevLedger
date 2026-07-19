from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://engineeros:engineeros@localhost:5432/engineeros"
    github_token: str | None = None
    groq_api_key: str | None = None
    redis_url: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"


settings = Settings()
