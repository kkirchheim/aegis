# Docker Network Setup Guide

The Paper Reproducibility Checker uses Docker containers for sandboxed code execution. These containers need to run on a Docker network that allows communication between the main Flask app and agent containers.

## Quick Start

### Default Behavior (Recommended for Standalone)
If `DOCKER_NETWORK` is empty or not set, the app uses Docker's default bridge network:

```bash
# .env
DOCKER_NETWORK=          # Leave blank for default bridge network
DOCKER_BACKEND_URL=http://localhost:5000
```

This works out-of-the-box on any Docker installation with no additional setup.

### For Traefik-Based Deployments (OpenClaw)
If you're using this inside OpenClaw with Traefik, set the network explicitly:

```bash
# .env
DOCKER_NETWORK=workspace_traefik
DOCKER_BACKEND_URL=http://paper-reproducibility:5000
```

### For Custom Docker Networks
If you want to use a specific custom network:

**Step 1: Create the network**
```bash
docker network create my-network
```

**Step 2: Set in `.env`**
```bash
# .env
DOCKER_NETWORK=my-network
DOCKER_BACKEND_URL=http://localhost:5000
```

**Step 3: Verify**
```bash
docker network ls | grep my-network
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

### Setup 1: Standalone Docker on Single Host (Simplest)
Flask and agents on same Docker default bridge:

```bash
# .env - No Docker network configuration needed!
DOCKER_NETWORK=          # Leave blank to use Docker default bridge
DOCKER_BACKEND_URL=http://localhost:5000
```

No additional setup required. Works immediately.

### Setup 2: Docker Compose with Custom Network
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

### Setup 3: Traefik-Based (OpenClaw)
When DOCKER_NETWORK is set to the Traefik network:

```bash
# .env
DOCKER_NETWORK=workspace_traefik
DOCKER_BACKEND_URL=http://paper-reproducibility:5000
```

Containers can reach Flask app by service name on shared network.

### Setup 4: Host-Based Flask + Docker Agent Containers
Flask runs on host, agents in Docker. Agents reach host via special addresses:

```bash
# .env
DOCKER_NETWORK=          # Use default bridge
DOCKER_BACKEND_URL=http://host.docker.internal:5000  # macOS/Windows
# or
DOCKER_BACKEND_URL=http://172.17.0.1:5000  # Linux (Docker bridge gateway)
```

### Setup 5: Kubernetes (Advanced)
For Kubernetes deployments, set network to pod network:

```bash
DOCKER_NETWORK=          # Or use the pod network name if applicable
DOCKER_BACKEND_URL=http://paper-reproducibility-service:5000
```

## Troubleshooting

### Error: "network X not found"
**Solution 1:** If using custom network, create it:
```bash
docker network create X
```

**Solution 2:** Leave `DOCKER_NETWORK` blank to use default bridge:
```bash
# .env
DOCKER_NETWORK=
```

### Error: Agent can't reach Flask app
**Check:** Verify `DOCKER_BACKEND_URL` is correct and reachable:

For default bridge:
```bash
docker run -it --rm ubuntu curl http://host.docker.internal:5000/api/health  # macOS/Windows
docker run -it --rm ubuntu curl http://172.17.0.1:5000/api/health  # Linux
```

For custom network:
```bash
docker run -it --rm --network paper-network ubuntu curl http://localhost:5000/api/health
```

### Error: "cannot connect to Docker daemon"
**Check:** Docker is running and current user has permissions
```bash
docker ps  # Should list running containers
sudo usermod -aG docker $USER  # Add user to docker group
```

### Error: Port 5000 already in use
**Solution 1:** Use different port:
```bash
FLASK_PORT=5001
```

**Solution 2:** Stop container using port:
```bash
docker ps | grep 5000
docker stop <container-id>
```

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
