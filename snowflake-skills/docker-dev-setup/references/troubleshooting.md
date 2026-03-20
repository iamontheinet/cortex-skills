# Troubleshooting

Common Docker and Compose errors, their causes, and fixes.

## Build Errors

### COPY failed: file not found in build context

**Cause:** The file is excluded by `.dockerignore`, the path is wrong, or the build context doesn't include the file.

**Fix:**
1. Check `.dockerignore` — is the file or its parent directory listed?
2. Verify the file path is relative to the build context (usually project root)
3. Check the build context: `docker build .` uses `.` as context — files outside this directory aren't available
4. Common mistake: `.dockerignore` excludes `*.json` which catches `package.json`

### Image is unexpectedly large (1 GB+)

**Cause:** Using a full base image, not using multi-stage builds, or build artifacts left in the final image.

**Fix:**
1. Check layer sizes: `docker history myapp:latest`
2. Switch from `node:22` (1 GB) to `node:22-alpine` (130 MB)
3. Add multi-stage build — don't copy build tools into the final image
4. Verify `.dockerignore` exists and excludes `.git/`, `node_modules/`, etc.
5. Clean package manager caches in the same `RUN` layer:
   ```dockerfile
   RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
   ```

### Build is slow despite no code changes

**Cause:** Layer cache invalidated by copying source code before installing dependencies.

**Fix:**
```dockerfile
# BAD — any source change invalidates npm install cache
COPY . .
RUN npm ci

# GOOD — deps cached separately from source
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
```

### npm install fails with EACCES permission denied

**Cause:** Switching to non-root user before `npm install`, or using `npm install -g` as non-root.

**Fix:**
- Install dependencies as root, then switch to non-root:
  ```dockerfile
  COPY package.json package-lock.json ./
  RUN npm ci --production
  USER node
  COPY . .
  ```

### Python: pip install fails with "No space left on device"

**Cause:** Building wheels for C extensions fills up the builder layer.

**Fix:** Use BuildKit cache mounts and multi-stage:
```dockerfile
FROM python:3.12 AS builder
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir=/wheels -r requirements.txt

FROM python:3.12-slim
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/*.whl && rm -rf /wheels
```

## Runtime Errors

### Container exits immediately (exit code 0 or 1)

**Causes:**
1. No foreground process — CMD runs a background process or script that exits
2. Application crashes on startup
3. Missing environment variables

**Fix:**
1. Check logs: `docker logs <container>`
2. Ensure CMD runs a foreground process:
   ```dockerfile
   # GOOD: foreground
   CMD ["node", "server.js"]

   # BAD: background — container exits immediately
   CMD ["node", "server.js", "&"]
   ```
3. Run interactively to debug: `docker run -it myapp sh`

### Container doesn't respond to docker stop (takes 10 seconds)

**Cause:** PID 1 signal handling problem. The main process doesn't receive `SIGTERM`.

**Fix:**
1. Use exec form for CMD (not shell form):
   ```dockerfile
   # GOOD: node is PID 1, receives SIGTERM
   CMD ["node", "server.js"]

   # BAD: /bin/sh is PID 1, node doesn't get SIGTERM
   CMD node server.js
   ```
2. For Node.js, use `dumb-init` or `tini`:
   ```dockerfile
   RUN apk add --no-cache dumb-init
   ENTRYPOINT ["dumb-init", "--"]
   CMD ["node", "server.js"]
   ```

### Port already allocated

**Cause:** Another container or process is using the same host port.

**Fix:**
1. Check what's using the port: `lsof -i :3000` or `docker ps`
2. Change the host port in Compose: `"3001:3000"` (different host port, same container port)
3. Stop the conflicting container: `docker compose down`

### Volume permission denied

**Cause:** Container runs as non-root but the volume was created by root.

**Fix:**
1. Use `--chown` when copying files:
   ```dockerfile
   COPY --chown=node:node . .
   ```
2. Set volume ownership in an entrypoint script
3. Or match the container user's UID with the host user's UID

## Compose Errors

### depends_on doesn't wait for database to be ready

**Cause:** Using `depends_on` without `condition: service_healthy`. By default, `depends_on` only waits for the container to start, not for the service to be ready.

**Fix:**
```yaml
depends_on:
  db:
    condition: service_healthy  # Add this

# AND add a health check to the db service:
db:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres"]
    interval: 10s
    timeout: 5s
    retries: 5
```

### Service can't connect to database (connection refused)

**Cause:** Using `localhost` instead of the service name. Inside Compose, services connect via service names, not `localhost`.

**Fix:**
```yaml
# WRONG: "localhost" means the app container itself
DATABASE_URL: postgresql://postgres:postgres@localhost:5432/appdb

# RIGHT: "db" is the service name from compose.yaml
DATABASE_URL: postgresql://postgres:postgres@db:5432/appdb
```

### Bind mount changes not reflected in container

**Cause:** Volume caching on macOS/Windows, or the bind mount path is wrong.

**Fix:**
1. Verify the volume mount path is correct in `compose.yaml`
2. On macOS, ensure the path is in Docker Desktop's file sharing settings
3. Try adding `:cached` for better performance on macOS:
   ```yaml
   volumes:
     - .:/app:cached
   ```

### node_modules conflicts between host and container

**Cause:** Bind-mounting `.:/app` overwrites the container's `node_modules/` with the host's (which may be compiled for a different OS).

**Fix:** Use a named volume for `node_modules`:
```yaml
volumes:
  - .:/app
  - node_modules:/app/node_modules  # Preserves container's node_modules

volumes:
  node_modules:
```

## Debug Commands

```bash
# View container logs
docker compose logs -f app

# Shell into a running container
docker compose exec app sh

# Run a one-off command
docker compose run --rm app npm test

# Inspect container health
docker inspect --format='{{json .State.Health}}' <container_id> | jq

# Check image layer sizes
docker history myapp:latest

# View build context size (what gets sent to Docker daemon)
du -sh --exclude=.git .

# Rebuild without cache (nuclear option)
docker compose build --no-cache

# Clean up everything (containers, images, volumes, networks)
docker system prune -a --volumes
```
