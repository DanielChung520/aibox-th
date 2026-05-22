#!/bin/bash
# =============================================================================
# docker-entrypoint.sh — Rust API Gateway entrypoint
# =============================================================================
#
# Creates a symlink so the Rust binary can find the frontend dist/ directory
# at ../dist (which resolves to /dist when the binary runs from /app).
#
# The docker-compose setup mounts the dist/ directory at /app/dist, so we
# create a symlink: /dist → /app/dist.
#
# @file         docker-entrypoint.sh
# @description  Entrypoint script for abc-api Docker container
# @lastUpdate   2026-05-22
# @author       ABC Team
# @version      1.0.0
# =============================================================================

set -e

# Create symlink so Rust binary's ServeDir("../dist") resolves correctly.
# In Docker, the binary runs from /app, so ../dist = /dist.
# The frontend dist/ is mounted at /app/dist in docker-compose.
ln -sf /app/dist /dist

exec /app/abc-api
