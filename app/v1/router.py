"""v1 router -- mounts FactInventoryController under the /v1 prefix."""

from litestar import Router

from .controller import FactInventoryController

v1_router: Router = Router(path="/v1", route_handlers=[FactInventoryController])
