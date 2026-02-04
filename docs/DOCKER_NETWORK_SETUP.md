# Docker Network Setup Guide

The Paper Reproducibility Checker uses Docker containers for sandboxed code execution. These containers need to run on a Docker network that allows communication between the main Flask app and agent containers.

## Quick Start

### For Traefik-Based Deployments (OpenClaw)
If you're using this inside OpenClaw with Traefik, the network already exists:

```bash
DOCKER_NETWORK=workspace_traefik
DOCKER_BACKEND_URL=http://paper-reproducibility:5000
```

### For Standalone Deployments (No Traefik)
If you're deploying on a new machine without Traefik:

**Step 1: Create a Docker network**
```bash
docker network create paper-network
```

**Step 2: Update `.env`**
```bash
# .env
DOCKER_NETWORK=paper-network
DOCKER_BACKEND_URL=http://localhost:5000
```

**Step 3: Verify**
```bash
docker network ls | grep paper-network
```

## How It Works

1. **Main Flask app** runs in a container or on the host
2. **Agent containers** are spawned for each job analysis
3. Both containers need network access to communicate:
   - Agent container needs to POST logs to main app
   - Main app needs to receive updates from agent

### Network Communication Flow

```
┌─────────────────────────────────────────────┐
│ Host Machine                                 │
│                                              │
│  Docker Network: paper-network              │
│  ├─ Flask Container (paper-reproducibility) │
│  │  - Listens on 0.0.0.0:5000              │
│  │  - Receives logs from agents             │
│  │                                          │
│  └─ Agent Container (per job)               │
│     - Spawned for each analysis             │
│     - POSTs to DOCKER_BACKEND_URL           │
│                                              │
└─────────────────────────────────────────────┘
```

## Common Setups

### Setup 1: Docker Compose on Same Host
```yaml
# docker-compose.yml
services:
  web:
    image: paper-reproducibility
    ports:
      - "5000:5000"
    networks:
      - paper-network
    environment:
      DOCKER_NETWORK: paper-network
      DOCKER_BACKEND_URL: http://web:5000

networks:
  paper-network:
    driver: bridge
```

### Setup 2: Host-Based Flask + Docker Agent Containers
Flask runs on host, agents in Docker:

```bash
# .env
DOCKER_NETWORK=paper-network
DOCKER_BACKEND_URL=http://host.docker.internal:5000  # macOS/Windows
# or
DOCKER_BACKEND_URL=http://172.17.0.1:5000  # Linux (Docker bridge gateway)
```

### Setup 3: Kubernetes (Advanced)
For Kubernetes deployments, adjust network names and backend URLs:

```bash
DOCKER_NETWORK=default  # or your namespace
DOCKER_BACKEND_URL=http://paper-reproducibility-service:5000
```

## Troubleshooting

### Error: "network paper-network not found"
**Solution:** Create the network
```bash
docker network create paper-network
```

### Error: Agent can't reach Flask app
**Check:** Verify `DOCKER_BACKEND_URL` is reachable from inside container
```bash
docker run -it --rm --network paper-network \
  ubuntu curl http://host.docker.internal:5000/api/health
```

### Error: "cannot connect to Docker daemon"
**Check:** Docker is running and current user has permissions
```bash
docker ps  # Should list running containers
```

### Error: Port 5000 already in use
**Solution:** Use different port in `docker-compose.yml` or set `FLASK_PORT` env var

## Network Isolation

By default, containers on the same network can communicate. If you need strict isolation:

1. Create separate networks per job (advanced)
2. Use network policies (Kubernetes)
3. Use firewall rules on host (Linux `ufw`, `iptables`)

## Production Considerations

- Use overlay networks for multi-host setups
- Set network MTU appropriately (`docker network create --opt com.docker.network.driver.mtu=1450 ...`)
- Monitor network traffic: `docker stats --no-stream`
- Use service discovery for dynamic deployments

## See Also

- [Docker Networks Documentation](https://docs.docker.com/network/)
- [Docker Compose Networking](https://docs.docker.com/compose/networking/)
- [PROJECT_SETUP.md](PROJECT_SETUP.md) - Full deployment guide
