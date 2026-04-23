"""Development entry point that creates the ASGI app and optionally runs uvicorn.

Run the development server with ``python -m fact_inventory.main`` or
``uvicorn fact_inventory.main:app``.

Environment variables
---------------------
HOST : str, optional
    Server host to bind to. Default is "localhost".
PORT : str, optional
    Server port to bind to. Default is "8000".
"""

import os

from fact_inventory.app_factory import create_app

app = create_app()

if __name__ == "__main__":
    host = os.getenv("HOST", "localhost")
    port = int(os.getenv("PORT", "8000"))

    import uvicorn

    uvicorn.run("fact_inventory.main:app", host=host, port=port, reload=True)
