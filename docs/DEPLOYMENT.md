# Deployment

The standalone application factory serves all routes at the root (`/`). For
production the `/fact_inventory` URL prefix should be handled by either a
reverse proxy (nginx, Apache) or a parent ASGI application that imports the
router.

## Uvicorn

Start the ASGI server on all interfaces:

```bash
uvicorn fact_inventory.app_factory:create_app --factory --host 0.0.0.0 --port 8000
```

This binds to `http://0.0.0.0:8000` and exposes:

| Path        | Description                                           |
| ----------- | ----------------------------------------------------- |
| `/health`   | Liveness probe (requires ENABLE_HEALTH_ENDPOINT=true) |
| `/ready`    | Readiness probe (requires ENABLE_READY_ENDPOINT=true) |
| `/v1/facts` | Fact submission                                       |
| `/metrics`  | Prometheus metrics (requires ENABLE_METRICS=true)     |

A reverse proxy in front of Uvicorn rewrites the external `/fact_inventory`
prefix to `/` so the application never sees the prefix.

---

## nginx

### Strip the prefix (recommended)

nginx receives requests at `/fact_inventory/...` and forwards them to Uvicorn
with the prefix removed:

```nginx
upstream fact_inventory {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl;
    server_name inventory.example.com;

    # Redirect bare prefix to trailing slash for consistency
    location = /fact_inventory {
        return 301 /fact_inventory/;
    }

    # Strip /fact_inventory prefix, proxy to Uvicorn at /
    location /fact_inventory/ {
        proxy_pass         http://fact_inventory/;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # Important: pass the real client IP so rate limiting
        # and the facts endpoint identify the correct source.
        proxy_set_header   X-Forwarded-Host  $host;
    }
}
```

With this configuration, external clients send requests to:

```
POST https://inventory.example.com/fact_inventory/v1/facts
GET  https://inventory.example.com/fact_inventory/health
GET  https://inventory.example.com/fact_inventory/ready
```

nginx strips `/fact_inventory` and Uvicorn sees `/v1/facts`, `/health`, etc.

---

## Apache (mod_proxy)

### Strip the prefix with ProxyPass

```apache
<VirtualHost *:443>
    ServerName inventory.example.com

    SSLEngine on
    SSLCertificateFile    /etc/pki/tls/certs/inventory.example.com.crt
    SSLCertificateKeyFile /etc/pki/tls/private/inventory.example.com.key

    # Enable required modules:
    #   a2enmod proxy proxy_http headers rewrite

    # Strip /fact_inventory prefix, proxy to Uvicorn at /
    ProxyPreserveHost On
    ProxyPass        /fact_inventory/ http://127.0.0.1:8000/
    ProxyPassReverse /fact_inventory/ http://127.0.0.1:8000/

    # Rewrite redirect responses: if Uvicorn returns Location: /v1/facts,
    # rewrite it to /fact_inventory/v1/facts so the client follows the
    # correct external path.
    ProxyPassReverseCookiePath / /fact_inventory/

    # Forward the real client IP for rate limiting
    RequestHeader set X-Forwarded-For "%{REMOTE_ADDR}e"
    RequestHeader set X-Forwarded-Proto "https"

    # Redirect bare prefix to trailing slash
    RedirectMatch ^/fact_inventory$ /fact_inventory/
</VirtualHost>
```

---

## Embedding in a larger Litestar application

If you are building a larger Litestar application and want to mount
fact_inventory as a sub-router under `/fact_inventory`, use the
`create_router` factory with a path argument.

When embedding, the parent application typically owns its own top-level
`/metrics` endpoint and health probes, making the built-in ones redundant.
Set `ENABLE_METRICS=false`, `ENABLE_HEALTH_ENDPOINT=false`, and/or
`ENABLE_READY_ENDPOINT=false` to suppress individual endpoints so the parent
app's equivalents are not shadowed or duplicated.

```python
import os

os.environ["ENABLE_METRICS"] = "false"
os.environ["ENABLE_HEALTH_ENDPOINT"] = "false"
os.environ["ENABLE_READY_ENDPOINT"] = "false"

from litestar import Litestar
from litestar.plugins.prometheus import PrometheusConfig, PrometheusController

from fact_inventory.presentation.api.router import create_router

# Mount fact_inventory under /fact_inventory with its metrics/health
# endpoints suppressed -- the parent app provides those.
fact_inventory_router = create_router(path="/fact_inventory")

prometheus_config = PrometheusConfig(app_name="my_app")

app = Litestar(
    route_handlers=[fact_inventory_router, PrometheusController],
    middleware=[prometheus_config.middleware],
    # ... other plugins, middleware, etc.
)
```

Each probe can be controlled independently. For example, to keep
per-service liveness checks while suppressing the readiness probe and
metrics:

```python
os.environ["ENABLE_METRICS"] = "false"
os.environ["ENABLE_READY_ENDPOINT"] = "false"
# ENABLE_HEALTH_ENDPOINT defaults to true -- /health is kept.
```

With both probe flags set to `true` (the default), the embedded router
produces:

| External Path              | Internal Handler          |
| -------------------------- | ------------------------- |
| `/fact_inventory/health`   | `health_check()`          |
| `/fact_inventory/ready`    | `ready_check()`           |
| `/fact_inventory/v1/facts` | `FactInventoryController` |

---

## Ansible client configuration

Update the Ansible playbook URL to include the prefix:

```yaml
- name: Make POST request with ansible_facts
  ansible.builtin.uri:
    url: http://127.0.0.1:8000/v1/facts
    method: POST
    body_format: json
    body:
      system_facts: >-
        {{
          ansible_facts
          | dict2items
          | rejectattr('key', 'in', ['ansible_local', 'packages'])
          | items2dict
          | combine({'ansible_version': ansible_version})
        }}
      package_facts: >-
        {{ ansible_facts.packages | default({}) }}
      local_facts: >-
        {{ ansible_facts.ansible_local | default({}) }}
    status_code: 201
```

See `gather_facts.yml` in the repository root for a complete example.
