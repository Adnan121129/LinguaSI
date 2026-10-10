#!/bin/sh
# Stands in for the docker command, so the start scripts can be tested without Docker.
# Every call is appended to $FAKE_DOCKER_LOG. FAKE_COMPOSE_VERSION and FAKE_UP_EXIT change the answers.
printf '%s\n' "$*" >> "${FAKE_DOCKER_LOG:-/dev/null}"
case "$*" in
  "info") exit 0 ;;
  "compose version --short") echo "${FAKE_COMPOSE_VERSION:-2.29.1}" ;;
  "compose version") echo "Docker Compose version v${FAKE_COMPOSE_VERSION:-2.29.1}" ;;
  "compose up"*) exit "${FAKE_UP_EXIT:-0}" ;;
  "compose exec"*) echo "Demo learner ready" ;;
esac
exit 0
