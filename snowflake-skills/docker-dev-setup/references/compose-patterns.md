# Compose Patterns

Docker Compose v2 patterns for local development. All examples use the modern `compose.yaml` format (no `version:` key).

## Basic Structure

```yaml
# compose.yaml — no "version:" key needed (Compose v2)
services:
  app:
    build: .
    ports:
      - "3000:3000"
    volumes:
      - .:/app
      - node_modules:/app/node_modules
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/appdb
      REDIS_URL: redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: appdb
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
  redisdata:
  node_modules:
```

## Health Checks for Common Services

Health checks let `depends_on` wait until a service is actually ready (not just started).

### PostgreSQL
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 10s
```

### MySQL
```yaml
healthcheck:
  test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 20s
```

### Redis
```yaml
healthcheck:
  test: ["CMD", "redis-cli", "ping"]
  interval: 10s
  timeout: 5s
  retries: 5
```

### MongoDB
```yaml
healthcheck:
  test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 15s
```

### RabbitMQ
```yaml
healthcheck:
  test: ["CMD", "rabbitmq-diagnostics", "check_port_connectivity"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

### HTTP App (generic)
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:3000/health || exit 1"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 15s
```

## depends_on with Health Conditions

```yaml
services:
  app:
    depends_on:
      db:
        condition: service_healthy      # Wait until healthy
      redis:
        condition: service_healthy
      migrations:
        condition: service_completed_successfully  # Wait until exit 0
```

Available conditions:
- `service_started` — default, just waits for container to start
- `service_healthy` — waits for health check to pass
- `service_completed_successfully` — waits for container to exit with code 0

## Volumes

### Named Volumes (for persistent data)
```yaml
services:
  db:
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:  # Named volume — data persists across container restarts
```

### Bind Mounts (for development — host files synced into container)
```yaml
services:
  app:
    volumes:
      - .:/app                            # Sync source code for hot reload
      - node_modules:/app/node_modules    # Named volume — don't sync from host
```

**Why a named volume for node_modules?** If you bind-mount `.:/app`, the host's `node_modules/` overwrites the container's. Using a named volume for `node_modules` keeps the container's installed deps separate from the host.

### Anonymous Volumes (avoid — use named instead)
```yaml
# BAD: anonymous volume — can't easily reference or clean up
volumes:
  - /app/node_modules

# GOOD: named volume — clear what it is
volumes:
  - node_modules:/app/node_modules
```

## Environment Variables

```yaml
services:
  app:
    # Inline (good for non-sensitive values)
    environment:
      NODE_ENV: development
      DATABASE_URL: postgresql://postgres:postgres@db:5432/appdb

    # From .env file (good for secrets in development)
    env_file:
      - .env

    # From host environment (good for CI)
    environment:
      API_KEY: ${API_KEY}  # Reads from host shell environment
```

## Port Mapping

```yaml
ports:
  - "3000:3000"      # host:container — access at localhost:3000
  - "5432:5432"      # expose DB for local tools (DBeaver, pgAdmin)
  - "127.0.0.1:6379:6379"  # bind to localhost only (more secure)
```

## Restart Policies

```yaml
services:
  db:
    restart: unless-stopped   # Restarts unless manually stopped

  app:
    restart: "no"             # Don't restart (default) — good for dev
```

Options: `"no"`, `always`, `on-failure`, `unless-stopped`

## Override Files

Compose automatically merges `compose.yaml` + `compose.override.yaml`:

```yaml
# compose.yaml — base configuration (committed to git)
services:
  app:
    build: .
    depends_on:
      db:
        condition: service_healthy

# compose.override.yaml — local overrides (optionally gitignored)
services:
  app:
    volumes:
      - .:/app
    ports:
      - "3000:3000"
    environment:
      DEBUG: "true"
```

## Multiple Compose Files (Production vs Dev)

```bash
# Development (default — uses compose.yaml + compose.override.yaml)
docker compose up

# Production (explicit files)
docker compose -f compose.yaml -f compose.prod.yaml up -d

# CI/Testing
docker compose -f compose.yaml -f compose.test.yaml run --rm test
```

## Networking

By default, Compose creates one network per project. All services can reach each other by service name.

```yaml
# app can connect to db at hostname "db"
DATABASE_URL: postgresql://postgres:postgres@db:5432/appdb

# app can connect to redis at hostname "redis"
REDIS_URL: redis://redis:6379
```

Custom networks (for isolation):
```yaml
services:
  app:
    networks:
      - frontend
      - backend
  db:
    networks:
      - backend  # Not accessible from frontend network

networks:
  frontend:
  backend:
```

## Common Development Patterns

### Hot Reload (Node.js with bind mount)
```yaml
services:
  app:
    build: .
    command: npm run dev  # Override CMD for dev (e.g., nodemon)
    volumes:
      - .:/app
      - node_modules:/app/node_modules
    ports:
      - "3000:3000"
```

### Database Initialization (run SQL on first start)
```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql  # Runs on first start only
```

### One-off Commands (migrations, seeds)
```bash
# Run migrations
docker compose run --rm app npm run db:migrate

# Run a one-off command
docker compose run --rm app sh

# Run tests
docker compose run --rm app npm test
```
