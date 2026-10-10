#!/bin/sh
# Stops LinguaSI. Your accounts and progress are kept; start again with:   sh start.sh

cd "$(dirname "$0")" || exit 1
docker compose down
printf '\nLinguaSI is stopped. Your data is kept. Start it again with: sh start.sh\n\n'
