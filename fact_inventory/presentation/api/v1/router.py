"""Router for the v1 API.

Assembles the /v1 namespace with all fact submission handlers.

Notes
-----
v1_router is the Router instance mounted at ``/v1``.

Examples
--------
To submit system and package facts, send a POST request to /v1/facts.
"""

from litestar import Router

from fact_inventory.presentation.api.v1.controller import FactInventoryController

__all__ = ["v1_router"]

v1_router: Router = Router(path="/v1", route_handlers=[FactInventoryController])
