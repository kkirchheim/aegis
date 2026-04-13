#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

IMAGES=(
  "paper-reproducibility-agent:latest|agent/Dockerfile"
  "paper-reproducibility-agent-ml:latest|agent/Dockerfile.ml"
  "paper-reproducibility-agent-py27:latest|agent/Dockerfile.py27"
  "paper-reproducibility-agent-py34:latest|agent/Dockerfile.py34"
  "paper-reproducibility-agent-py36:latest|agent/Dockerfile.py36"
  "paper-reproducibility-agent-matlab:latest|agent/Dockerfile.matlab"
  "paper-reproducibility-agent-matlab-official:latest|agent/Dockerfile.matlab-official"
)

for image in "${IMAGES[@]}"; do
  tag="${image%%|*}"
  dockerfile="${image##*|}"

  echo "==> Building ${tag} from ${dockerfile}"
  docker build "$@" -t "$tag" -f "$dockerfile" .
done

echo "==> Built ${#IMAGES[@]} agent image(s)"
