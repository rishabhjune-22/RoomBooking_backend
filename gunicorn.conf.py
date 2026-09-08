import multiprocessing
import os


bind = os.getenv("GUNICORN_BIND", "10.50.27.89:8000")
workers = int(os.getenv("GUNICORN_WORKERS", min(multiprocessing.cpu_count() * 2 + 1, 4)))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
accesslog = "-"
errorlog = "-"
capture_output = True
