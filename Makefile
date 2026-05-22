DOCKER_API_VERSION ?= 1.44
PYTHON ?= .venv/bin/python
FLOW ?= money.transfer
DEPTH ?= 3
PROVIDER ?= openai
MODEL ?=

ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: neo4j-up neo4j-ps neo4j-logs neo4j-stop neo4j-down app-up app-ps app-logs app-stop configure-ai configure-ai-prompt configure-ai-check configure-ai-inline ask ask-ai ask-local ask-deterministic ask-trace-latest ingest extract extract-reasoning extract-autogen extract-langgraph extract-autogen-langgraph extract-apply extract-autogen-apply graph-load graph-tree test require-openai-key

neo4j-up:
	DOCKER_API_VERSION=$(DOCKER_API_VERSION) docker compose up -d neo4j

neo4j-ps:
	DOCKER_API_VERSION=$(DOCKER_API_VERSION) docker compose ps neo4j

neo4j-logs:
	DOCKER_API_VERSION=$(DOCKER_API_VERSION) docker compose logs neo4j

neo4j-stop:
	DOCKER_API_VERSION=$(DOCKER_API_VERSION) docker compose stop neo4j

neo4j-down:
	DOCKER_API_VERSION=$(DOCKER_API_VERSION) docker compose down

app-up:
	DOCKER_API_VERSION=$(DOCKER_API_VERSION) docker compose --profile optional up -d app

app-ps:
	DOCKER_API_VERSION=$(DOCKER_API_VERSION) docker compose --profile optional ps app

app-logs:
	DOCKER_API_VERSION=$(DOCKER_API_VERSION) docker compose --profile optional logs app

app-stop:
	DOCKER_API_VERSION=$(DOCKER_API_VERSION) docker compose --profile optional stop app

configure-ai:
	@test -n "$(KEY)" || (echo "Usage: make configure-ai KEY=<real_openai_key>"; exit 1)
	@printf "NEO4J_URI=bolt://localhost:7687\nNEO4J_USER=neo4j\nNEO4J_PASSWORD=banking-intent-dev\n\nOPENAI_API_KEY=%s\nINTENT_LLM_MODEL=gpt-4o-mini\nUSE_AI_PROVIDERS=true\n\nQDRANT_HOST=http://localhost:6333\nQDRANT_API_KEY=\n" "$(KEY)" > .env
	@echo ".env configured. Future 'make ask' calls will use GraphRAG + LangChain + LLM."

configure-ai-prompt:
	@printf "OpenAI API key: "; stty -echo; read key; stty echo; printf "\n"; \
	test -n "$$key" || (echo "Missing key"; exit 1); \
	printf "NEO4J_URI=bolt://localhost:7687\nNEO4J_USER=neo4j\nNEO4J_PASSWORD=banking-intent-dev\n\nOPENAI_API_KEY=%s\nINTENT_LLM_MODEL=gpt-4o-mini\nUSE_AI_PROVIDERS=true\n\nQDRANT_HOST=http://localhost:6333\nQDRANT_API_KEY=\n" "$$key" > .env; \
	echo ".env configured. Future 'make ask' calls will use GraphRAG + LangChain + LLM."

configure-ai-check:
	$(PYTHON) tools/configure_openai_key.py --provider "$(PROVIDER)" $(if $(MODEL),--model "$(MODEL)",)

configure-ai-inline:
	@test -n "$(KEY)" || (echo "Usage: make configure-ai-inline KEY='<real_openai_key>'"; exit 1)
	$(PYTHON) tools/configure_openai_key.py --provider "$(PROVIDER)" --key "$(KEY)" $(if $(MODEL),--model "$(MODEL)",)

require-openai-key:
	@test -n "$$OPENAI_API_KEY" || (echo "OPENAI_API_KEY is required. Run once: make configure-ai KEY=<real_key>"; exit 1)
	@test "$$OPENAI_API_KEY" != "tu_api_key" || (echo "OPENAI_API_KEY still has the placeholder value. Run: make configure-ai KEY=<real_key>"; exit 1)

ask: require-openai-key
	DOCKER_API_VERSION=$(DOCKER_API_VERSION) docker compose --profile optional run --rm -e USE_AI_PROVIDERS=true -e OPENAI_API_KEY -e OPENAI_BASE_URL -e INTENT_LLM_MODEL -e NEO4J_URI=bolt://neo4j:7687 app python -m app.cli ask "$(Q)"

ask-ai: ask

ask-local:
	USE_AI_PROVIDERS=true $(PYTHON) -m app.cli ask "$(Q)"

ask-deterministic:
	USE_AI_PROVIDERS=false $(PYTHON) -m app.cli ask "$(Q)"

ask-deterministic-full:
	USE_AI_PROVIDERS=false $(PYTHON) -m app.cli ask "$(Q)" --full-result

ask-trace-latest:
	@ls -t data/processed/ask_trace/ask_trace_*.json 2>/dev/null | head -1 | xargs -r $(PYTHON) -m json.tool

ingest:
	$(PYTHON) -m app.cli.ingest data/raw

extract: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw

extract-reasoning: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw --ingestion-reasoning

extract-autogen: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw --autogen-ingestion-reasoning

extract-langgraph: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw --langgraph --max-validation-retries 1 --require-human-review

extract-autogen-langgraph: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw --autogen-ingestion-reasoning --langgraph --max-validation-retries 1 --require-human-review

extract-apply: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw --apply

extract-autogen-apply: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw --autogen-ingestion-reasoning --apply

graph-load:
	$(PYTHON) tools/push_flows_to_neo4j.py --clear

graph-tree:
	$(PYTHON) tools/neo4j_tree.py --source $(FLOW) --depth $(DEPTH)

test:
	$(PYTHON) -m pytest
