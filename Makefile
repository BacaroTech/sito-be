.DEFAULT_GOAL := help
.PHONY: help install dev run clean-db

HOST ?= 127.0.0.1
PORT ?= 8000

help: ## Mostra i comandi disponibili
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Installa Python e le dipendenze con uv
	@command -v uv >/dev/null || { echo "uv non trovato: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	uv sync

dev: install ## Avvia il server di sviluppo con auto-reload
	uv run fastapi dev src/sito_be/app.py --host $(HOST) --port $(PORT)

run: install ## Avvia il server senza auto-reload
	uv run fastapi run src/sito_be/app.py --host $(HOST) --port $(PORT)

clean-db: ## Cancella il database SQLite locale
	rm -f contacts.db
