# ----- Stage 1: Build -----
FROM golang:1.23-alpine AS builder

WORKDIR /app

# Download dependencies first (cached if go.mod/go.sum unchanged)
COPY go.mod go.sum ./
RUN go mod download

# Build a static binary
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /server ./cmd/server

# ----- Stage 2: Production -----
# scratch = empty filesystem. Only works for static binaries.
# If you need TLS, DNS, or timezone data, use gcr.io/distroless/static-debian12 instead.
FROM scratch

# CA certificates for HTTPS calls
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# Non-root user (numeric — scratch has no /etc/passwd)
USER 65534:65534

COPY --from=builder /server /server

EXPOSE 8080

# No HEALTHCHECK — scratch doesn't have curl/wget.
# Use the Compose-level healthcheck or a load balancer health probe instead.

ENTRYPOINT ["/server"]
