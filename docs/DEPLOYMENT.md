# Deployment

The standalone application factory serves all routes at the root (`/`). For
production the `/fact_inventory` URL prefix should be handled by either a
reverse proxy (nginx, Apache) or a parent ASGI application that imports the
router.

## Uvicorn

Start the ASGI server on all interfaces:

```bash
uvicorn app.app_factory:create_app --factory --host 0.0.0.0 --port 8000
```

This binds to `http://0.0.0.0:8000` and exposes:

| Path         | Description        |
| ------------ | ------------------ |
| `/health`    | Liveness probe     |
| `/ready`     | Readiness probe    |
| `/v1/facts`  | Fact submission    |
| `/metrics`   | Prometheus metrics |

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
    #   a2enmod proxy proxy_http headers

    # Strip /fact_inventory prefix, proxy to Uvicorn at /
    ProxyPreserveHost On
    ProxyPass        /fact_inventory/ http://127.0.0.1:8000/
    ProxyPassReverse /fact_inventory/ http://127.0.0.1:8000/

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
`create_router` factory with a path argument:

```python
from litestar import Litestar
from litestar.plugins.prometheus import PrometheusController

from app.routes import create_router

# Mount fact_inventory under /fact_inventory
fact_inventory_router = create_router(path="/fact_inventory")

app = Litestar(
    route_handlers=[fact_inventory_router, PrometheusController],
    # ... other plugins, middleware, etc.
)
```

This produces:

| External Path                   | Internal Handler      |
| ------------------------------- | --------------------- |
| `/fact_inventory/health`        | `health_check()`      |
| `/fact_inventory/ready`         | `ready_check()`       |
| `/fact_inventory/v1/facts`      | `HostFactController`  |

---

## Ansible client configuration

Update the Ansible playbook URL to include the prefix:

```yaml
- name: Submit facts
  ansible.builtin.uri:
    url: "https://inventory.example.com/fact_inventory/v1/facts"
    method: POST
    body_format: json
    body:
      system_facts: "{{ ansible_facts }}"
      package_facts: "{{ ansible_facts.packages }}"
    status_code: 201
```

See `gather_facts.yml` in the repository root for a complete example.
