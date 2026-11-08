from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment configuration. Names mirror the keys in .env / docker-compose."""

    # In Docker every value arrives as a real environment variable. The env_file
    # entries only matter for host-run developer commands (`tortoise makemigrations`)
    # executed from backend/, which read the repo-root .env. Real env vars win, so
    # `POSTGRES_HOST=localhost uv run tortoise makemigrations` overrides the compose
    # service name.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), extra="ignore", case_sensitive=False
    )

    # Postgres
    postgres_db: str = "simgen"
    postgres_user: str = "simgen"
    postgres_password: str = ""
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # Redis (Celery result backend only — domain status lives in Postgres)
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # RabbitMQ (Celery broker)
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "simgen"
    rabbitmq_password: str = ""
    rabbitmq_vhost: str = "/"

    # OpenAI — drives simulation generation (LLM call #2, core_html). Required
    # from day one, never stubbed: core quality is what a teacher actually sees.
    openai_api_key: str = ""
    openai_model: str = "gpt-5.5"
    openai_base_url: str = ""
    openai_max_output_tokens: int = 16384

    # Ollama — drives plan generation (LLM call #1). Blueprint drafts and
    # revisions are the most-iterated call, so they run against a local,
    # OpenAI-compatible endpoint instead of spending OpenAI budget on every
    # retry. api_key is a required-but-ignored placeholder for Ollama's server.
    ollama_api_key: str = "ollama"
    ollama_model: str = "qwen3:4b"
    ollama_base_url: str = "http://host.docker.internal:11434/v1"
    ollama_max_output_tokens: int = 16384

    # Extracted textbook JSON (scripts/extract_textbook.py). Compose mounts data/textbook/
    # read-only at /app/data/textbook; the default suits host-run commands from backend/.
    textbook_dir: str = "../data/textbook"

    # App
    app_port: int = 8000
    debug: bool = True
    cors_allowed_origins: str = "http://localhost:3000"
    fake_auth: bool = True
    fake_user_sub: str = "dev-teacher"

    @property
    def database_url(self) -> str:
        return (
            f"postgres://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def broker_url(self) -> str:
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/{self.rabbitmq_vhost}"
        )

    @property
    def result_backend(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
