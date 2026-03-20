"""
Route registry for the fact_inventory sub-application.

``route_handlers`` is the complete list of Litestar route handlers for this
sub-application, all at relative paths (no prefix baked in).  The host
application mounts them at whatever URL prefix it chooses using a standard
Litestar ``Router``::

    from litestar import Litestar, Router
    from app.fact_inventory.routes import route_handlers

    app = Litestar(
        route_handlers=[
            Router(path="/fact_inventory", route_handlers=route_handlers),
            ...
        ],
    )
"""

from litestar import Router
from litestar.types import ControllerRouterHandler

from .unversioned.routes import health_check, ready_check
from .v1.controller import HostFactController as HostFactController_v1

# v1 versioned API lives one level below the prefix chosen by the host app.
_v1_router: Router = Router(
    path="/v1",
    route_handlers=[HostFactController_v1],
)

# All handlers use relative paths, prefix appied in host app
route_handlers: list[ControllerRouterHandler] = [health_check, ready_check, _v1_router]
