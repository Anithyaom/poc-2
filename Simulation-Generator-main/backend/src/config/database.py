from src.config.settings import settings

# Every domain package's models module must be listed here, or its tables are
# invisible to both the runtime and `tortoise makemigrations`.
MODELS = [
    "src.course.models",
    "src.lab.models",
    "src.plan.models",
    "src.job.models",
    "src.simulation.models",
]

TORTOISE_ORM = {
    "connections": {"default": settings.database_url},
    "apps": {
        "models": {
            "models": MODELS,
            "default_connection": "default",
            "migrations": "src.migrations",
        }
    },
}
