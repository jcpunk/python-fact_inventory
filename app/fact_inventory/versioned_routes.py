"""
Services evolve and APIs change

We can version each API and expose them from here
"""

from litestar import Router

from .v1.controller import HostFactController as HostFactController_v1

# ----------------------------------------------------------------------
# v1 - current stable API endpoint
#   https://github.com/orgs/litestar-org/discussions/4330
# ----------------------------------------------------------------------
v1_route: Router = Router(
    path="/v1",
    route_handlers=[HostFactController_v1],
)

routes: list[Router] = [v1_route]
