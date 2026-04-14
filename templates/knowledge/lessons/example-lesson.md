---
title: "Example Lesson — Three-File Docker Compose"
date: "YYYY-MM-DD"
severity: "Critical"
category: "deployment"
bloom_level: "apply"
tags: ["docker", "compose", "deployment", "production"]
---

# Three-File Docker Compose Pattern

## Discovery

Production frontend builds fail with `@tailwind` parsing errors and HTTP 500
on all dashboard routes when only two of the three compose files are used
during rebuild.

## Root Cause

The project uses three compose files:
- `docker-compose.yml` — base services
- `docker-compose.override.yml` — volume mounts and dev overrides
- `docker-compose.prod.yml` — production Dockerfile and build args

Omitting the prod file causes Docker to use the dev Dockerfile, which lacks
the production build step for CSS processing.

## Resolution

Always use all three files for production rebuilds:

```bash
docker compose -f docker-compose.yml \
  -f docker-compose.override.yml \
  -f docker-compose.prod.yml \
  up -d --build frontend
```

## Prevention

Add this check to your autonomic smoke beat or deploy script:

```bash
# Verify production CSS is compiled
curl -s https://YOUR_DOMAIN/dashboard | grep -q "tailwind" && echo "FAIL: raw tailwind in output" || echo "OK"
```

## Bloom Classification

- **Remember:** Three files exist
- **Understand:** Each file layers different concerns
- **Apply:** Use the three-file command in all deploys
- **Analyze:** If CSS breaks, check which compose files were used
