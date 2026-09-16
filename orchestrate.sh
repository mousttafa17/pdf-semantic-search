#!/usr/bin/env bash

set -euo pipefail

ACTION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --action)
            if [[ $# -lt 2 ]]; then
                echo "Error: --action requires a value."
                exit 1
            fi

            ACTION="$2"
            shift 2
            ;;

        *)
            echo "Error: Unknown argument '$1'."
            echo "Usage: ./orchestrate.sh --action {start|terminate}"
            exit 1
            ;;
    esac
done

case "$ACTION" in
    start)
        echo "Starting PDF Semantic Search API..."
        docker compose up --build -d
        echo "Service started."
        ;;

    terminate)
        echo "Stopping PDF Semantic Search API..."
        docker compose down -v
        echo "Service terminated."
        ;;

    *)
        echo "Usage: ./orchestrate.sh --action {start|terminate}"
        exit 1
        ;;
esac