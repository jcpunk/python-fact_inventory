import logging
import os

from .app_factory import create_app

logger = logging.getLogger(__name__)

app = create_app()

if __name__ == "__main__":
    host = os.getenv("HOST", "localhost")
    port = int(os.getenv("PORT", "8000"))
    logger.info("Running development server on %s:%s", host, port)

    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=True)
