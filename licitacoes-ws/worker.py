import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Suporta REDIS_URL (URL completa) ou REDIS_HOST (host:porta) + REDIS_PASSWORD opcional
_redis_url  = os.getenv("REDIS_URL")
_redis_host = os.getenv("REDIS_HOST", "localhost:6379")
_redis_pass = os.getenv("REDIS_PASSWORD", "")

if _redis_url:
    REDIS_URL = _redis_url
elif _redis_pass:
    REDIS_URL = f"redis://:{_redis_pass}@{_redis_host}/0"
else:
    REDIS_URL = f"redis://{_redis_host}/0"

celery_app = Celery("liciteview", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.task_track_started = True
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]

# Importa tasks para que o worker as registre ao iniciar
import tasks  # noqa: F401, E402
