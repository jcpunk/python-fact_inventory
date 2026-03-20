"""
Route registry for the fact_inventory application.

Import ``routes`` from here to get all handlers - both the unversioned
operational routes (e.g. /fact_inventory/health) and every versioned API
router - in a single list ready to pass to Litestar.

Usage in the application factory::

    from .fact_inventory.routes import routes
    app = Litestar(route_handlers=[*routes, ...])
"""

from litestar import Router

from .unversioned_routes import routes as _unversioned
from .versioned_routes import routes as _versioned

routes: list[Router] = [*_unversioned, *_versioned]
