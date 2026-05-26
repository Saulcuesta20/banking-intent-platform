DOCKER_API_VERSION ?= 1.44
DOCKER ?= docker
APP_IMAGE ?= banking-intent-platform-app
APP_CONTAINER ?= banking-intent-app
NEO4J_CONTAINER ?= banking-intent-neo4j
NEO4J_COMPOSE_CONTAINER ?= banking-intent-platform-neo4j-1
DOCKER_NETWORK ?= banking-intent-net
NEO4J_VOLUME ?= banking-intent-neo4j-data
PYTHON ?= .venv/bin/python
FLOW ?= money.transfer
DEPTH ?= 3
PROVIDER ?= openai
MODEL ?=

ifneq (,$(wildcard .env))
include .env
export
endif

ifeq ($(firstword $(MAKECMDGOALS)),configure-openrouter-prompt)
OPENROUTER_KEY_FROM_GOALS := $(word 2,$(MAKECMDGOALS))
endif

.PHONY: docker-network app-image platform-up up neo4j-up neo4j-ps neo4j-logs neo4j-stop neo4j-down app-up app-ps app-logs app-stop configure-ai configure-openrouter configure-openrouter-prompt configure-ai-prompt configure-ai-check configure-ai-inline ask ask-ai ask-trace-latest ingest ingest-graph extract extract-reasoning extract-autogen extract-langgraph extract-autogen-langgraph extract-apply extract-autogen-apply graph-load graph-tree graph-tree-all test require-openai-key

ifneq ($(OPENROUTER_KEY_FROM_GOALS),)
.PHONY: $(OPENROUTER_KEY_FROM_GOALS)
$(OPENROUTER_KEY_FROM_GOALS):
	@:
endif

docker-network:
	@$(DOCKER) network inspect $(DOCKER_NETWORK) >/dev/null 2>&1 || $(DOCKER) network create $(DOCKER_NETWORK)

app-image:
	@$(DOCKER) build --quiet -t $(APP_IMAGE) . >/dev/null 2>&1

platform-up: docker-network neo4j-up app-up

up: platform-up

neo4j-up: docker-network
	@$(DOCKER) volume inspect $(NEO4J_VOLUME) >/dev/null 2>&1 || $(DOCKER) volume create $(NEO4J_VOLUME)
	@if $(DOCKER) ps -a --format '{{.Names}}' | grep -qx '$(NEO4J_CONTAINER)'; then \
		$(DOCKER) start $(NEO4J_CONTAINER) >/dev/null; \
	elif $(DOCKER) ps -a --format '{{.Names}}' | grep -qx '$(NEO4J_COMPOSE_CONTAINER)'; then \
		$(DOCKER) start $(NEO4J_COMPOSE_CONTAINER) >/dev/null; \
		$(DOCKER) network connect --alias $(NEO4J_CONTAINER) $(DOCKER_NETWORK) $(NEO4J_COMPOSE_CONTAINER) >/dev/null 2>&1 || true; \
	else \
		$(DOCKER) run -d --name $(NEO4J_CONTAINER) --network $(DOCKER_NETWORK) -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=$(NEO4J_USER)/$(NEO4J_PASSWORD) -v $(NEO4J_VOLUME):/data neo4j:5-community >/dev/null; \
	fi

neo4j-ps:
	$(DOCKER) ps -a --filter name=$(NEO4J_CONTAINER)

neo4j-logs:
	$(DOCKER) logs $(NEO4J_CONTAINER)

neo4j-stop:
	$(DOCKER) stop $(NEO4J_CONTAINER)

neo4j-down:
	-$(DOCKER) stop $(APP_CONTAINER) $(NEO4J_CONTAINER)
	-$(DOCKER) rm $(APP_CONTAINER) $(NEO4J_CONTAINER)

app-up: docker-network app-image
	@if $(DOCKER) ps -a --format '{{.Names}}' | grep -qx '$(APP_CONTAINER)'; then \
		$(DOCKER) rm -f $(APP_CONTAINER) >/dev/null; \
	fi
	$(DOCKER) run -d --name $(APP_CONTAINER) --network $(DOCKER_NETWORK) -p 8000:8000 -v $(PWD):/app -w /app -e PYTHONPATH=/app -e USE_AI_PROVIDERS -e OPENAI_API_KEY -e OPENAI_BASE_URL -e INTENT_LLM_MODEL -e NEO4J_URI=bolt://$(NEO4J_CONTAINER):7687 -e NEO4J_USER -e NEO4J_PASSWORD $(APP_IMAGE) >/dev/null

app-ps:
	$(DOCKER) ps -a --filter name=$(APP_CONTAINER)

app-logs:
	$(DOCKER) logs $(APP_CONTAINER)

app-stop:
	$(DOCKER) stop $(APP_CONTAINER)

configure-ai:
	@test -n "$(KEY)" || (echo "Usage: make configure-ai KEY=<real_openai_key>"; exit 1)
	@printf "NEO4J_URI=bolt://localhost:7687\nNEO4J_USER=neo4j\nNEO4J_PASSWORD=banking-intent-dev\n\nOPENAI_API_KEY=%s\nINTENT_LLM_MODEL=gpt-4o-mini\nUSE_AI_PROVIDERS=true\n\nQDRANT_HOST=http://localhost:6333\nQDRANT_API_KEY=\n" "$(KEY)" > .env
	@echo ".env configured. Future 'make ask' calls will use knowledge graph + LangChain + LLM."

configure-openrouter:
	@test -n "$(KEY)" || (echo "Usage: make configure-openrouter KEY=<real_openrouter_key>"; exit 1)
	@printf "NEO4J_URI=bolt://localhost:7687\nNEO4J_USER=neo4j\nNEO4J_PASSWORD=banking-intent-dev\n\nOPENAI_API_KEY=%s\nOPENAI_BASE_URL=https://openrouter.ai/api/v1\nINTENT_LLM_MODEL=$(if $(MODEL),$(MODEL),openrouter/auto)\nUSE_AI_PROVIDERS=true\n\nQDRANT_HOST=http://localhost:6333\nQDRANT_API_KEY=\nPOSTGRES_DSN=postgresql://banking_intent:banking-intent-dev@localhost:5432/banking_intent\nREDIS_URL=redis://localhost:6379/0\n" "$(KEY)" > .env
	@echo ".env configured for OpenRouter. Future 'make ask' and 'make ingest-graph' calls will use OpenRouter."

configure-openrouter-prompt:
	@if [ -n "$(OPENROUTER_KEY_FROM_GOALS)" ]; then key="$(OPENROUTER_KEY_FROM_GOALS)"; else printf "OpenRouter API key: "; stty -echo; read key; stty echo; printf "\n"; fi; \
	if [ -z "$$key" ]; then echo "Missing key"; exit 1; fi; \
	printf "NEO4J_URI=bolt://localhost:7687\nNEO4J_USER=neo4j\nNEO4J_PASSWORD=banking-intent-dev\n\nOPENAI_API_KEY=%s\nOPENAI_BASE_URL=https://openrouter.ai/api/v1\nINTENT_LLM_MODEL=$(if $(MODEL),$(MODEL),openrouter/auto)\nUSE_AI_PROVIDERS=true\n\nQDRANT_HOST=http://localhost:6333\nQDRANT_API_KEY=\nPOSTGRES_DSN=postgresql://banking_intent:banking-intent-dev@localhost:5432/banking_intent\nREDIS_URL=redis://localhost:6379/0\n" "$$key" > .env; \
	echo ".env configured for OpenRouter."

configure-ai-prompt:
	@printf "OpenAI API key: "; stty -echo; read key; stty echo; printf "\n"; \
	if [ -z "$$key" ]; then echo "Missing key"; exit 1; fi; \
	printf "NEO4J_URI=bolt://localhost:7687\nNEO4J_USER=neo4j\nNEO4J_PASSWORD=banking-intent-dev\n\nOPENAI_API_KEY=%s\nINTENT_LLM_MODEL=gpt-4o-mini\nUSE_AI_PROVIDERS=true\n\nQDRANT_HOST=http://localhost:6333\nQDRANT_API_KEY=\n" "$$key" > .env; \
	echo ".env configured. Future 'make ask' calls will use knowledge graph + LangChain + LLM."

configure-ai-check:
	$(PYTHON) tools/configure_openai_key.py --provider "$(PROVIDER)" $(if $(MODEL),--model "$(MODEL)",)

configure-ai-inline:
	@test -n "$(KEY)" || (echo "Usage: make configure-ai-inline KEY='<real_openai_key>'"; exit 1)
	$(PYTHON) tools/configure_openai_key.py --provider "$(PROVIDER)" --key "$(KEY)" $(if $(MODEL),--model "$(MODEL)",)

require-openai-key:
	@test -n "$$OPENAI_API_KEY" || (echo "OPENAI_API_KEY is required. Run once: make configure-ai KEY=<real_key>"; exit 1)
	@test "$$OPENAI_API_KEY" != "tu_api_key" || (echo "OPENAI_API_KEY still has the placeholder value. Run: make configure-ai KEY=<real_key>"; exit 1)

ask: require-openai-key neo4j-up app-image
	$(DOCKER) run --rm -i --network $(DOCKER_NETWORK) -v $(PWD):/app -w /app -e PYTHONPATH=/app -e USE_AI_PROVIDERS=true -e OPENAI_API_KEY -e OPENAI_BASE_URL -e INTENT_LLM_MODEL -e NEO4J_URI=bolt://$(NEO4J_CONTAINER):7687 -e NEO4J_USER -e NEO4J_PASSWORD $(APP_IMAGE) python -m app.cli ask "$(Q)"

ask-ai: ask

ask-trace-latest:
	@ls -t data/processed/ask_trace/ask_trace_*.json 2>/dev/null | head -1 | xargs -r $(PYTHON) -m json.tool

ingest:
	$(PYTHON) -m app.cli.ingest data/raw

ingest-graph: require-openai-key neo4j-up app-image
	$(DOCKER) run --rm --network $(DOCKER_NETWORK) -v $(PWD):/app -w /app -e PYTHONPATH=/app -e OPENAI_API_KEY -e OPENAI_BASE_URL -e INTENT_LLM_MODEL $(APP_IMAGE) python tools/extract_flows_from_corpus.py --raw-dir data/raw --apply
	$(DOCKER) run --rm --network $(DOCKER_NETWORK) -v $(PWD):/app -w /app -e PYTHONPATH=/app -e NEO4J_URI=bolt://$(NEO4J_CONTAINER):7687 -e NEO4J_USER -e NEO4J_PASSWORD $(APP_IMAGE) python tools/push_flows_to_neo4j.py --clear

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

graph-load: neo4j-up app-image
	$(DOCKER) run --rm --network $(DOCKER_NETWORK) -v $(PWD):/app -w /app -e PYTHONPATH=/app -e NEO4J_URI=bolt://$(NEO4J_CONTAINER):7687 -e NEO4J_USER -e NEO4J_PASSWORD $(APP_IMAGE) python tools/push_flows_to_neo4j.py --clear

graph-tree: neo4j-up app-image
	$(DOCKER) run --rm --network $(DOCKER_NETWORK) -v $(PWD):/app -w /app -e PYTHONPATH=/app -e NEO4J_URI=bolt://$(NEO4J_CONTAINER):7687 -e NEO4J_USER -e NEO4J_PASSWORD $(APP_IMAGE) python tools/neo4j_tree.py --source $(FLOW) --depth $(DEPTH)

graph-tree-all: neo4j-up app-image
	$(DOCKER) run --rm --network $(DOCKER_NETWORK) -v $(PWD):/app -w /app -e PYTHONPATH=/app -e NEO4J_URI=bolt://$(NEO4J_CONTAINER):7687 -e NEO4J_USER -e NEO4J_PASSWORD $(APP_IMAGE) python tools/neo4j_tree.py --depth $(DEPTH)

test:
	$(PYTHON) -m pytest
