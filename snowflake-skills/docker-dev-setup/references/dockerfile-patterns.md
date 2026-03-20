# Dockerfile Patterns

Best practices for writing production-grade Dockerfiles.

## Multi-Stage Build Anatomy

Every production Dockerfile should use multi-stage builds. The idea: use a large image to build, then copy only the artifact into a tiny runtime image.

```dockerfile
# Stage 1: BUILD — has compilers, dev dependencies, source code
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: RUNTIME — has only what's needed to run
FROM node:22-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
CMD ["node", "dist/server.js"]
```

**Why it matters:** A single-stage Node.js image is ~1.2 GB. Multi-stage with alpine: ~150 MB. Go with scratch: ~10 MB.

## Layer Ordering (Cache Optimization)

Docker caches layers top-to-bottom. Once a layer changes, ALL subsequent layers rebuild. Order instructions from least-frequently changed to most-frequently changed:

```dockerfile
FROM node:22-alpine                      # 1. Base image (rarely changes)
RUN apk add --no-cache dumb-init         # 2. System packages (rarely changes)
WORKDIR /app                             # 3. Working directory (never changes)
COPY package.json package-lock.json ./   # 4. Dependency files (changes sometimes)
RUN npm ci --production                  # 5. Install deps (cached if #4 unchanged)
COPY . .                                 # 6. Source code (changes every build)
CMD ["dumb-init", "node", "server.js"]   # 7. Run command (rarely changes)
```

**The golden rule:** Copy dependency lock files BEFORE source code. This means `npm ci` only re-runs when dependencies actually change, not on every code change.

## Base Image Selection

| Image Type | Size | Use When |
|-----------|------|----------|
| `node:22` / `python:3.12` | 800 MB–1 GB | Never in production |
| `node:22-alpine` | ~130 MB | Default for Node.js |
| `node:22-slim` | ~200 MB | Need glibc (some native modules fail on Alpine/musl) |
| `python:3.12-slim` | ~150 MB | Default for Python |
| `python:3.12-alpine` | ~50 MB | Only if no C extensions needed |
| `gcr.io/distroless/nodejs22` | ~40 MB | Maximum security (no shell, no package manager) |
| `gcr.io/distroless/static` | ~2 MB | Go/Rust static binaries |
| `scratch` | 0 bytes | Go/Rust with CGO_ENABLED=0 (truly empty filesystem) |

**Rules:**
- Pin versions: `node:22.12-alpine` not `node:latest`
- Alpine uses musl libc — some native modules (bcrypt, sharp) may need `node:22-slim` instead
- Distroless has no shell — you can't `docker exec -it container sh` (use `:debug` tag for debugging)

## Non-Root User

Never run containers as root in production. Add a non-root user after installing packages but before copying application files:

```dockerfile
# Alpine
RUN addgroup -S app && adduser -S app -G app

# Debian/Ubuntu
RUN groupadd -r app && useradd -r -g app app

# Copy files with correct ownership
COPY --from=builder --chown=app:app /app/dist ./dist

# Switch to non-root
USER app
```

Many base images already include a non-root user:
- `node` images: user `node` (uid 1000)
- Distroless: user `nonroot` (uid 65534), available via `:nonroot` tag

## Signal Handling (PID 1 Problem)

In Docker, the main process runs as PID 1. PID 1 has special kernel behavior: it doesn't receive default signal handlers, so `SIGTERM` (used by `docker stop`) may be ignored, leading to a 10-second timeout and `SIGKILL`.

**Fix for Node.js:** Use `dumb-init` or `tini`:
```dockerfile
RUN apk add --no-cache dumb-init
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "server.js"]
```

**Fix for Python:** Gunicorn/uvicorn handle signals correctly. No extra tool needed.

**Fix for Go:** Go binaries handle signals correctly by default.

**General rule:** Use exec form (JSON array) for CMD and ENTRYPOINT:
```dockerfile
# GOOD: exec form — process is PID 1, receives signals
CMD ["node", "server.js"]

# BAD: shell form — runs as /bin/sh -c "node server.js", node is NOT PID 1
CMD node server.js
```

## Health Checks

Add `HEALTHCHECK` so Docker can monitor container health:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1
```

For images without `curl` (Alpine, distroless), use alternatives:
```dockerfile
# Node.js — use node itself
HEALTHCHECK CMD node -e "require('http').get('http://localhost:3000/health', (r) => { process.exit(r.statusCode === 200 ? 0 : 1) })"

# wget (available on Alpine)
HEALTHCHECK CMD wget --spider -q http://localhost:3000/health || exit 1
```

## COPY vs ADD

- **COPY** — Copies files from build context to image. Use this 99% of the time.
- **ADD** — Same as COPY but also extracts tar archives and can download URLs. Avoid unless you need tar extraction.

```dockerfile
# GOOD
COPY package.json ./

# BAD (unclear intent — is it copying or extracting?)
ADD package.json ./

# OK (legitimate use — extracting an archive)
ADD app.tar.gz /app/
```

## BuildKit Cache Mounts

Cache package manager downloads across builds. Even if the dependency layer rebuilds, downloads are reused:

```dockerfile
# Node.js
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Python
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Go
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go build -o /server ./cmd/server
```

Requires BuildKit (enabled by default in Docker Desktop, or set `DOCKER_BUILDKIT=1`).

## Combine RUN Commands

Each `RUN` creates a layer. Combine related commands and clean up in the same layer:

```dockerfile
# BAD: 3 layers, apt cache persists
RUN apt-get update
RUN apt-get install -y curl
RUN rm -rf /var/lib/apt/lists/*

# GOOD: 1 layer, clean filesystem
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
```

## Build Arguments and Secrets

```dockerfile
# Build arguments (visible in image history — NOT for secrets)
ARG NODE_ENV=production
ENV NODE_ENV=$NODE_ENV

# Build secrets (BuildKit — never stored in image layers)
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc \
    npm ci
```

Pass secrets at build time:
```bash
docker build --secret id=npmrc,src=.npmrc .
```

## .dockerignore

Always create `.dockerignore` at the project root. Without it, `.git/` (hundreds of MB) and `node_modules/` (hundreds of MB) get sent to the Docker daemon on every build.

See `templates/dockerignore` for a universal template.
