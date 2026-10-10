#!/bin/sh
# Starts LinguaSI on your computer with Docker: the database, the API, the website and the mobile
# app preview. In a terminal, run:   sh start.sh
# GETTING-STARTED.md explains every step.

cd "$(dirname "$0")" || exit 1

say() { printf '%s\n' "$*"; }

fail() {
  say ""
  say "PROBLEM: $1"
  [ -n "${2:-}" ] && say "$2"
  say ""
  say "More help: GETTING-STARTED.md, section \"If something goes wrong\"."
  say ""
  exit 1
}

# A setting from .env (if there is one), otherwise the default.
env_value() {
  value=""
  if [ -f .env ]; then
    value=$(grep -E "^[[:space:]]*$1[[:space:]]*=" .env | tail -n 1 | cut -d= -f2- | tr -d "\r\"' ")
  fi
  printf '%s' "${value:-$2}"
}

# True when another program already listens on the port.
port_busy() {
  command -v curl >/dev/null 2>&1 || return 1
  curl -s -o /dev/null -m 2 "http://127.0.0.1:$1/"
  [ $? -ne 7 ]
}

say ""
say "LinguaSI"
say "========"

if [ ! -f docker-compose.yml ]; then
  fail "docker-compose.yml is missing from $(pwd)." \
    "Run this script from the LinguaSI folder you downloaded (unzip it first)."
fi

if ! command -v docker >/dev/null 2>&1; then
  fail "Docker is not installed." \
    "Install Docker Desktop from https://www.docker.com/products/docker-desktop/ and open it once, then run: sh start.sh"
fi

if docker info 2>&1 | grep -qi "permission denied"; then
  fail "Your user is not allowed to use Docker." \
    "Run: sudo usermod -aG docker \$USER   then log out and back in, and run: sh start.sh"
fi

if ! docker info >/dev/null 2>&1; then
  if [ "$(uname -s)" = "Darwin" ]; then
    say "Opening Docker Desktop..."
    open -a Docker >/dev/null 2>&1
  fi
  say "Waiting for Docker to start (this can take a few minutes)..."
  tries=0
  until docker info >/dev/null 2>&1; do
    tries=$((tries + 1))
    if [ "$tries" -ge 60 ]; then
      fail "Docker is not running." \
        "Open Docker Desktop and wait until it says \"Engine running\", then run: sh start.sh"
    fi
    sleep 3
  done
fi

if ! docker compose version >/dev/null 2>&1; then
  fail "This Docker has no \"docker compose\" command." \
    "Update Docker Desktop to the latest version (on Linux, install the docker-compose-plugin package)."
fi
if ! docker compose version --short 2>/dev/null | awk -F. '{ sub(/^v/, "", $1); exit !($1 + 0 > 2 || ($1 + 0 == 2 && $2 + 0 >= 24)) }'; then
  fail "Your Docker Compose is too old: LinguaSI needs version 2.24 or newer." \
    "Update Docker Desktop to the latest version."
fi

WEB_PORT=$(env_value WEB_PORT 3000)
API_PORT=$(env_value API_PORT 8000)
MOBILE_PORT=$(env_value MOBILE_PORT 8081)

# Containers left over from an earlier start are removed first. Your data is kept.
docker compose down --remove-orphans >/dev/null 2>&1

for setting in WEB_PORT=$WEB_PORT API_PORT=$API_PORT MOBILE_PORT=$MOBILE_PORT; do
  port=${setting#*=}
  if port_busy "$port"; then
    fail "Port $port is already used by another program." \
      "Close that program, or choose another port: create a file named .env in this folder with the line ${setting%%=*}=$((port + 1)) and run: sh start.sh"
  fi
done

say ""
say "Building and starting LinguaSI. The first start downloads and builds everything,"
say "which takes 5-15 minutes. Later starts take about a minute."
say ""
if ! docker compose up --build --detach --wait; then
  say ""
  say "Recent messages from LinguaSI:"
  docker compose logs --tail 40
  fail "LinguaSI did not start." "Read the messages above, then see GETTING-STARTED.md for the usual fixes."
fi

say ""
say "Preparing the demo learner (the first time takes a minute or two)..."
if ! docker compose exec -T api python -m app.cli demo --if-missing; then
  say "The demo learner could not be created. You can still create your own account on the website."
fi

URL="http://localhost:$WEB_PORT"
say ""
say "LinguaSI is running."
say ""
say "  Website:             $URL"
say "  Mobile app preview:  http://localhost:$MOBILE_PORT"
say "  API documentation:   http://localhost:$API_PORT/docs"
say ""
say "  Demo learner:        demo@linguasi.app  /  LinguaSI-demo-2026"
say "  (or click \"Create an account\" on the website)"
say ""
say "  To stop LinguaSI:    sh stop.sh   (your data is kept)"
say ""

if [ "$(uname -s)" = "Darwin" ]; then
  open "$URL"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 &
fi
