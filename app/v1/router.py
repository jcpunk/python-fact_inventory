"""
Setup the v1 router in its prefixed namespace
"""

from litestar import Router

from .controller import FactInventoryController

v1_router: Router = Router(path="/v1", route_handlers=[FactInventoryController])
