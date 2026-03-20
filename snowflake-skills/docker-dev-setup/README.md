# docker-dev-setup

Agent skill for containerizing applications with production-grade Dockerfiles, Docker Compose for local development, and optional Dev Container configuration.

## What It Does

1. Detects your project stack (Node.js, Python, Go, etc.) and existing Docker files
2. Creates a multi-stage Dockerfile optimized for size and security
3. Generates a `.dockerignore` to keep builds fast and secure
4. Sets up `compose.yaml` for local development (app + database + cache)
5. Optionally adds `.devcontainer/` for VS Code / GitHub Codespaces

## Language Templates

| Language | Base Image | Final Size | Template |
|----------|-----------|------------|----------|
| Node.js/TS | `node:22-alpine` | ~150 MB | `Dockerfile.node` |
| Python | `python:3.12-slim` | ~80 MB | `Dockerfile.python` |
| Go | `scratch` / `distroless` | ~10 MB | `Dockerfile.go` |

## Prerequisites

- Docker Desktop or Docker Engine installed
- Docker Compose v2 (`docker compose` — not the legacy `docker-compose`)

## File Structure

```
docker-dev-setup/
├── SKILL.md                          # Agent instructions (guided workflow)
├── README.md                         # This file
├── references/
│   ├── dockerfile-patterns.md        # Multi-stage builds, caching, security
│   ├── compose-patterns.md           # Services, health checks, volumes
│   └── troubleshooting.md            # Common errors and fixes
└── templates/
    ├── Dockerfile.node               # Node.js multi-stage (3-stage)
    ├── Dockerfile.python             # Python multi-stage (2-stage)
    ├── Dockerfile.go                 # Go multi-stage (scratch)
    ├── compose.yaml                  # Local dev stack
    ├── dockerignore                  # Universal .dockerignore
    └── devcontainer.json             # VS Code Dev Container
```

## Quick Reference

```bash
# Build the image
docker build -t myapp .

# Check image size
docker images myapp

# Start the full stack
docker compose up

# Rebuild after Dockerfile changes
docker compose up --build

# View running containers and health status
docker compose ps

# Check build layer sizes
docker history myapp:latest

# Open Compose logs
docker compose logs -f app
```

## Key Principles

- **Multi-stage builds**: Separate build and runtime stages. 80-99% size reduction.
- **Layer caching**: Copy lock files before source code. Deps rebuild only when lock file changes.
- **Non-root user**: Never run containers as root in production.
- **Health checks**: Use `HEALTHCHECK` in Dockerfile and `healthcheck:` + `depends_on: condition: service_healthy` in Compose.
- **.dockerignore is required**: Without it, `.git/` and `node_modules/` bloat the build context.
- **Compose v2**: Use `docker compose` (space), no `version:` key, `compose.yaml` filename.
