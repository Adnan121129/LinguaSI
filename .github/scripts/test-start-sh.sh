#!/bin/sh
# Runs start.sh and stop.sh against a stand-in docker command (no Docker needed) and checks what they
# do: a normal start, ports from .env, a busy port, old and new Compose versions, a failed start and
# a folder without docker-compose.yml.
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
WORK=$(mktemp -d)
mkdir "$WORK/bin"
cp "$ROOT/.github/scripts/fake-docker.sh" "$WORK/bin/docker"
chmod +x "$WORK/bin/docker"
PATH="$WORK/bin:$PATH"
FAKE_DOCKER_LOG="$WORK/docker.log"
export PATH FAKE_DOCKER_LOG
failures=0

# A fresh folder holding the scripts, as if just downloaded.
scenario() {
  dir="$WORK/$1"
  mkdir -p "$dir"
  cp "$ROOT/start.sh" "$ROOT/stop.sh" "$ROOT/docker-compose.yml" "$dir/"
  : > "$FAKE_DOCKER_LOG"
  echo "--- $1"
}

# TEST_SHELL picks the shell that runs the scripts, e.g. "bash --posix" (macOS's sh is bash).
run() {
  ${TEST_SHELL:-sh} "$dir/$1" > "$WORK/out.txt" 2>&1
  code=$?
}

# expect CODE TEXT: the last run exited with CODE and printed TEXT.
expect() {
  if [ "$code" -ne "$1" ]; then
    echo "FAIL: exit code $code, expected $1"
    failures=$((failures + 1))
  fi
  if ! grep -qF -- "$2" "$WORK/out.txt"; then
    echo "FAIL: the output does not contain: $2"
    sed 's/^/    | /' "$WORK/out.txt"
    failures=$((failures + 1))
  fi
}

# called ARGS: docker was called with ARGS (or not, with "called !").
called() {
  if [ "$1" = "!" ]; then
    if grep -qF -- "$2" "$FAKE_DOCKER_LOG"; then
      echo "FAIL: docker was called with: $2"
      failures=$((failures + 1))
    fi
  elif ! grep -qxF -- "$1" "$FAKE_DOCKER_LOG"; then
    echo "FAIL: docker was not called with: $1"
    sed 's/^/    > /' "$FAKE_DOCKER_LOG"
    failures=$((failures + 1))
  fi
}

scenario normal-start
run start.sh
expect 0 "LinguaSI is running."
expect 0 "Website:             http://localhost:3000"
expect 0 "Mobile app preview:  http://localhost:8081"
expect 0 "API documentation:   http://localhost:8000/docs"
called "compose down --remove-orphans"
called "compose up --build --detach --wait"
called "compose exec -T api python -m app.cli demo --if-missing"

scenario ports-from-env
printf '# my settings\r\nWEB_PORT=3101\r\nAPI_PORT = 8101\r\nMOBILE_PORT="8181"\r\nAI_PROVIDER=mock\r\n' > "$dir/.env"
run start.sh
expect 0 "Website:             http://localhost:3101"
expect 0 "API documentation:   http://localhost:8101/docs"
expect 0 "Mobile app preview:  http://localhost:8181"

scenario busy-port
python3 -m http.server 3000 --bind 127.0.0.1 > /dev/null 2>&1 &
server=$!
tries=0
until curl -s -o /dev/null -m 2 http://127.0.0.1:3000/ || [ "$tries" -ge 30 ]; do
  tries=$((tries + 1))
  sleep 1
done
run start.sh
kill "$server"
expect 1 "Port 3000 is already used by another program."
expect 1 "with the line WEB_PORT=3001"
called ! "compose up"

scenario old-compose
FAKE_COMPOSE_VERSION=2.20.3
export FAKE_COMPOSE_VERSION
run start.sh
unset FAKE_COMPOSE_VERSION
expect 1 "Your Docker Compose is too old"
called ! "compose up"

scenario newer-compose
FAKE_COMPOSE_VERSION=5.0.1
export FAKE_COMPOSE_VERSION
run start.sh
unset FAKE_COMPOSE_VERSION
expect 0 "LinguaSI is running."

scenario start-fails
FAKE_UP_EXIT=1
export FAKE_UP_EXIT
run start.sh
unset FAKE_UP_EXIT
expect 1 "PROBLEM: LinguaSI did not start."
called "compose logs --tail 40"
called ! "compose exec"

scenario no-compose-file
rm "$dir/docker-compose.yml"
run start.sh
expect 1 "docker-compose.yml is missing"
called ! "compose"

scenario stop
run stop.sh
expect 0 "LinguaSI is stopped. Your data is kept."
called "compose down"

rm -rf "$WORK"
if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed."
  exit 1
fi
echo "All start.sh and stop.sh checks passed."
