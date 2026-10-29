#!/usr/bin/env bash
# Builds the local OSRM routing data for Ho Chi Minh City (one-off, ~minutes).
# Usage: scripts/setup_osrm.sh [--refresh]   (--refresh re-downloads the OSM extract)
set -euo pipefail

cd "$(dirname "$0")/.."
DATA_DIR="osrm/data"
PBF_URL="https://download.geofabrik.de/asia/vietnam-latest.osm.pbf"
OSRM_IMAGE="ghcr.io/project-osrm/osrm-backend:latest"
OSMIUM_IMAGE="iboates/osmium:latest"
# HCMC and surroundings (min_lon,min_lat,max_lon,max_lat)
BBOX="106.35,10.35,107.05,11.20"

mkdir -p "$DATA_DIR"

if [[ "${1:-}" == "--refresh" || ! -f "$DATA_DIR/vietnam.osm.pbf" ]]; then
  echo "[1/4] Downloading Vietnam OSM extract..."
  curl -L --fail -o "$DATA_DIR/vietnam.osm.pbf" "$PBF_URL"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$DATA_DIR/extract_downloaded_at.txt"
else
  echo "[1/4] Using existing $DATA_DIR/vietnam.osm.pbf"
fi

echo "[2/4] Cropping to HCMC bounding box ($BBOX)..."
docker run --rm -v "$PWD/$DATA_DIR:/data" "$OSMIUM_IMAGE" \
  extract --overwrite --bbox "$BBOX" -o /data/hcmc.osm.pbf /data/vietnam.osm.pbf

echo "[3/4] osrm-extract (car profile)..."
docker run --rm -v "$PWD/$DATA_DIR:/data" "$OSRM_IMAGE" \
  osrm-extract -p /opt/car.lua /data/hcmc.osm.pbf

echo "[4/4] osrm-partition + osrm-customize (MLD)..."
docker run --rm -v "$PWD/$DATA_DIR:/data" "$OSRM_IMAGE" osrm-partition /data/hcmc.osrm
docker run --rm -v "$PWD/$DATA_DIR:/data" "$OSRM_IMAGE" osrm-customize /data/hcmc.osrm

echo "Done. Start the server with: docker compose up -d osrm"
