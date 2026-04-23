# TODO

Outstanding work items. Not prioritized; items should be evaluated against
use-case requirements before implementation.

## Database

- [ ] Implement Alembic schema versioning (optional; evaluate if expand-only
      strategy becomes limiting)
- [ ] Document table partitioning strategy for deployments with 5M+ rows
      (affects cleanup performance)

## Application

- [ ] Add distributed rate-limit state (Redis or similar) for multi-instance
      deployments that require rate-limit persistence across restarts
- [ ] Implement authentication/authorization if clients require identity
      (currently network-level security only)

## Observability

- [ ] Add custom Prometheus metrics (cleanup duration, fact sizes, rate-limit
      violations)
- [ ] Implement structured/JSON logging option

## Repository

- [ ] Set up CI to verify compatibility with latest `advanced-alchemy`,
      `litestar`, and `sqlalchemy` releases
