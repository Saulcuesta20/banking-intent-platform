from __future__ import annotations

import json
from pathlib import Path
from textwrap import indent

import typer
from rich.console import Console
from rich.table import Table
from app.factory import build_ingestion_provider, build_intent_service

console = Console()
app = typer.Typer()


@app.command()
def ask(
    question: str,
    trace: bool = typer.Option(True, "--trace/--no-trace", help="Print component resolution steps."),
    debug_trace: bool = typer.Option(False, "--debug-trace", help="Print detailed class/method trace."),
    full_result: bool = typer.Option(False, "--full-result", help="Print the full result payload."),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Ask for clarification when the intent is ambiguous."),
) -> None:
    """Ask a banking question using the configured intent service."""
    trace_events: list[tuple[str, str]] = []

    def collect_trace(component: str, message: str) -> None:
        trace_events.append((component, message))

    try:
        intent_service = build_intent_service()
        result = intent_service.resolve(question, trace=collect_trace if trace else None)
    except Exception as exc:
        console.print("[bold red]Error[/bold red] No pude completar la pregunta.")
        console.print(_friendly_error(str(exc)))
        raise typer.Exit(1)
    if trace:
        _print_ask_flow_trace(question, trace_events, result)
        if debug_trace:
            _print_debug_events(trace_events)
    if interactive and not result.to_dict()["can_resolve"]:
        clarified_question = _prompt_for_clarification(question, result.to_dict())
        if clarified_question:
            trace_events = []
            try:
                result = intent_service.resolve(clarified_question, trace=collect_trace if trace else None)
            except Exception as exc:
                console.print("[bold red]Error[/bold red] No pude completar la aclaracion.")
                console.print(_friendly_error(str(exc)))
                raise typer.Exit(1)
            if trace:
                _print_ask_flow_trace(clarified_question, trace_events, result)
                if debug_trace:
                    _print_debug_events(trace_events)
    if full_result or not trace:
        console.print(result.to_dict())
        return

    payload = result.to_dict()
    summary = Table(show_header=False, box=None, padding=(0, 1))
    summary.add_column("Field", style="bold")
    summary.add_column("Value")
    summary.add_row("Can resolve", str(payload["can_resolve"]))
    summary.add_row("Selected flow", f'{payload["flow_id"]} ({payload["flow_name"]})')
    summary.add_row("Intent", payload["intent"])
    summary.add_row("Confidence", str(payload["confidence"]))
    summary.add_row("Business event", payload["business_event"])
    summary.add_row("Human approval", str(payload["requires_human_approval"]))
    summary.add_row("Trace file", "see debug_trace file above")
    console.print(summary)

    if payload["explanation"]:
        console.print(f'[bold]Why[/bold] {payload["explanation"]}')

    if payload["plan"]:
        console.print("[bold]Plan[/bold]")
        for index, step in enumerate(payload["plan"], start=1):
            console.print(f"  {index}. {step}")

    if payload["tasks"]:
        console.print("[bold]Tasks[/bold]")
        for task in payload["tasks"]:
            console.print(f'  - {task["task"]} ({task["type"]})')

    if payload["related_capabilities"]:
        shown_actions = payload["related_capabilities"][:12]
        hidden_count = len(payload["related_capabilities"]) - len(shown_actions)
        suffix = f" (+{hidden_count} more)" if hidden_count else ""
        console.print("[bold]Actions[/bold] " + ", ".join(shown_actions) + suffix)

    if payload["related_ontology_nodes"]:
        console.print("[bold]Ontology[/bold] " + ", ".join(payload["related_ontology_nodes"]))


def _prompt_for_clarification(question: str, payload: dict) -> str | None:
    options = payload.get("clarification_options") or []
    if not options:
        return None
    console.print("[bold]Necesito una aclaracion[/bold]")
    console.print("La pregunta puede ir por varios caminos. Elige una opcion:")
    for index, option in enumerate(options, start=1):
        label = option.get("label") or option.get("value") or "opcion"
        detail = option.get("flow_id") or option.get("intent") or option.get("value")
        suffix = f" ({detail})" if detail and detail != label else ""
        console.print(f"  {index}. {label}{suffix}")
    console.print("  0. Ninguna / cancelar")
    try:
        raw_choice = typer.prompt("Que quieres hacer", default="0")
    except (EOFError, KeyboardInterrupt):
        console.print("No se recibio aclaracion; dejo el resultado como unknown.")
        return None
    try:
        selected_index = int(str(raw_choice).strip())
    except ValueError:
        console.print("La opcion no es valida; dejo el resultado como unknown.")
        return None
    if selected_index <= 0 or selected_index > len(options):
        return None
    selected = options[selected_index - 1]
    label = selected.get("label") or selected.get("value")
    value = selected.get("flow_id") or selected.get("intent") or selected.get("value") or label
    console.print(f"Seleccionaste: {label}")
    return f"{question}\nAclaracion del usuario: quiere {label} ({value})."


def _print_ask_flow_trace(question: str, events: list[tuple[str, str]], result) -> None:
    payload = result.to_dict()
    provider = _message_value(events, "retrieval", "provider=") or "unknown"
    matched_records = _message_value(events, "retrieval", "matched_records=") or "0"
    candidate_flows = _message_value(events, "retrieval", "candidate_flows=") or "none"
    query_provider = _query_understanding_provider(events)
    route = _route(events, payload["can_resolve"])
    trace_file = _message_value(events, "debug_trace", "file=") or "not written"
    llm_answer = _message_value(events, "llm", "answer can_resolve=")
    llm_reason = _message_value(events, "llm", "reason=")
    warning = _message_value(events, "retrieval", "warning=")
    query_output = _json_message_value(events, "query_understanding", "output=") or {}
    corrected_question = query_output.get("corrected_question") or question
    corrections = query_output.get("corrections") or []
    search_terms = query_output.get("search_terms") or []
    entities = query_output.get("entities") or []
    possible_intents = query_output.get("possible_intents") or []
    ambiguity = query_output.get("ambiguity")
    llm_json = _json_message_value(events, "llm", "answer_json=")

    console.print("[bold]Banking Intent flow[/bold]")
    console.print("Con tu ejemplo:")
    console.print("")
    console.print(question)
    console.print("")
    console.print("el flujo de ejecucion es:")
    console.print("")

    console.print("[bold]1. Entra la pregunta[/bold]")
    console.print("")
    console.print("Comando:")
    console.print(f'make ask Q="{question}"')
    console.print("Entra por:")
    console.print("app.cli.ask()")
    console.print("Luego llama:")
    console.print("app.factory.build_intent_service()")
    console.print("Ahi se arma el servicio principal:")
    console.print("IntentResolutionService")
    console.print("con retrieval, classifier, approval, audit y trace.")
    console.print("")

    console.print("[bold]2. LangGraph orquesta los pasos[/bold]")
    console.print("")
    console.print("IntentResolutionService.resolve() intenta correr LangGraph:")
    console.print("IntentResolutionService._resolve_with_langgraph()")
    console.print("LangGraph arma este workflow:")
    console.print("")
    console.print("retrieve_context -> classify_intent -> project_flow_context")
    console.print("                                      -> unknown_result")
    console.print("Si el LLM no encuentra un flow unico, termina en unknown_result.")
    console.print("Si el LLM selecciona un flow valido, termina en project_flow_context.")
    console.print(f"Ruta real de este run: {route}")
    console.print("")

    console.print("[bold]3. Query Understanding entiende la pregunta[/bold]")
    console.print("")
    console.print("Antes de buscar en el grafo, se llama:")
    console.print("QueryUnderstandingService.understand(question)")
    console.print("Si estas con AI activo:")
    console.print("LLMQueryUnderstandingProvider.understand()")
    console.print("El LLM deberia recibir algo como:")
    console.print("")
    console.print("Question:")
    console.print(question)
    console.print("Y devolver JSON con esta forma:")
    console.print(_pretty_json({
        "corrected_question": "pregunta corregida por el LLM",
        "corrections": [{"from": "texto original", "to": "texto corregido"}],
        "search_terms": ["terminos", "sinonimos", "conceptos para buscar en grafo"],
        "entities": ["ConceptosDominio"],
        "possible_intents": ["pistas.de.intencion"],
        "ambiguity": {
            "is_ambiguous": False,
            "reason": "por que es clara o ambigua",
            "options": ["opciones si aplica"],
        },
    }))
    console.print("Aqui el LLM no decide el flow final. Solo ayuda a entender, corregir y ampliar la busqueda.")
    if query_provider:
        console.print("Salida real de Query Understanding en este run:")
        console.print(f"provider: {query_provider}")
        console.print(_pretty_json({
            "corrected_question": corrected_question,
            "corrections": corrections,
            "search_terms": search_terms,
            "entities": entities,
            "possible_intents": possible_intents,
            "ambiguity": ambiguity,
        }))
    console.print("")

    console.print("[bold]4. Retrieval usa el grafo Neo4j[/bold]")
    console.print("")
    console.print("Luego se llama:")
    console.print("KnowledgeRetrievalService.retrieve(question)")
    console.print("Si USE_AI_PROVIDERS=true, usa:")
    console.print("GraphRAGKnowledgeRetrievalProvider.retrieve()")
    console.print("Este usa los terminos generados por el LLM:")
    for term in search_terms:
        console.print(term)
    console.print("y arma una query Cypher contra Neo4j:")
    console.print("")
    console.print("MATCH (f:Flow)")
    console.print("OPTIONAL MATCH (f)-[:EXEMPLIFIES]->(u:Utterance)")
    console.print("OPTIONAL MATCH (f)-[:HAS_ONTOLOGY]->(o:Ontology)")
    console.print("OPTIONAL MATCH (o)-[:HAS_SYNONYM]->(s:Synonym)")
    console.print("...")
    console.print("WHERE size(matched_tokens) > 0")
    console.print("RETURN flow_id, intent, business_event, utterances, ontology_nodes, actions...")
    console.print("Neo4j devuelve candidatos.")
    console.print("Resultado real de retrieval en este run:")
    console.print(f"provider: {provider}")
    if warning:
        console.print(f"warning: {warning}")
    console.print(f"candidate_flows: {candidate_flows}")
    console.print(f"matched_records: {matched_records}")
    console.print("")

    console.print("[bold]5. LLM clasifica contra esos candidatos[/bold]")
    console.print("")
    console.print("Despues LangGraph pasa al nodo:")
    console.print("classify_intent")
    console.print("Que llama:")
    console.print("IntentClassificationService.classify()")
    console.print("Y este usa:")
    console.print("LangchainGraphRAGReasoningProvider.classify_intent()")
    console.print("Aqui LangChain arma un prompt con:")
    console.print("- pregunta original")
    console.print("- pregunta corregida/contexto")
    console.print("- flows candidatos del grafo")
    console.print("- utterances")
    console.print("- ontology nodes")
    console.print("- acciones")
    console.print("- explicacion de cada flow")
    console.print("El LLM debe responder JSON con esta forma:")
    console.print(_pretty_json({
        "can_resolve": True,
        "selected_flow_id": "flow_id o unknown",
        "confidence": 0.0,
        "reason": "explicacion basada en el grafo",
    }))
    if llm_answer:
        console.print("Respuesta real del LLM en este run:")
        console.print(_pretty_json(llm_json) if llm_json else llm_answer)
        if llm_reason:
            console.print(f"Reason: {llm_reason}")
    else:
        console.print("No hubo decision LLM en este run; esto indica error de configuracion.")
    if route == "unknown":
        console.print("En este caso no debe elegir loan.request ni money.transfer automaticamente.")
    console.print("")

    console.print("[bold]6. LangGraph decide la ruta[/bold]")
    console.print("")
    console.print("LangGraph evalua:")
    console.print("selected_record is None")
    console.print("Si es None toma unknown_result; si existe toma project_flow_context.")
    console.print(f"Ruta real de este run: {route}")
    if route == "unknown":
        console.print("No toma project_flow_context porque no hay flow unico.")
    else:
        console.print("Toma project_flow_context porque hay flow unico seleccionado.")
    console.print("")

    console.print("[bold]7. Se arma la respuesta final[/bold]")
    console.print("")
    console.print("Se llama:")
    console.print("IntentResolutionService._build_unknown_result()" if route == "unknown" else "IntentResolutionService._build_projected_result()")
    console.print("Resultado:")
    if route == "unknown":
        console.print(_pretty_json({
            "can_resolve": False,
            "intent": "unknown",
            "business_event": "UnknownBusinessQuestionAsked",
            "requires_human_approval": True,
            "plan": ["clarify_customer_request", "approve_business_case"],
            "explanation": "The request is ambiguous. Ask whether the customer wants to request a loan, make/receive a transfer, or another operation.",
        }))
    else:
        console.print(_pretty_json({
            "can_resolve": payload["can_resolve"],
            "intent": payload["intent"],
            "business_event": payload["business_event"],
            "requires_human_approval": payload["requires_human_approval"],
            "plan": payload["plan"],
            "explanation": payload["explanation"],
        }))
    console.print("Resultado real de este run:")
    console.print(_pretty_json({
        "can_resolve": payload["can_resolve"],
        "intent": payload["intent"],
        "business_event": payload["business_event"],
        "requires_human_approval": payload["requires_human_approval"],
        "plan": payload["plan"],
        "explanation": payload["explanation"],
    }))
    console.print("")

    console.print("[bold]Resumen del flujo[/bold]")
    console.print("")
    console.print("CLI")
    console.print(" -> build_intent_service")
    console.print(" -> IntentResolutionService.resolve")
    console.print(" -> LangGraph")
    console.print("    -> retrieve_context")
    console.print("       -> QueryUnderstandingService")
    if query_provider == "llm_query_understanding":
        console.print("          -> LLM corrige/entiende pregunta")
    else:
        console.print("          -> LLM requerido no ejecuto")
    console.print("       -> GraphRAGKnowledgeRetrievalProvider")
    console.print("          -> Neo4j busca flows candidatos")
    console.print("    -> classify_intent")
    if llm_answer:
        console.print("       -> LangchainGraphRAGReasoningProvider")
        console.print("          -> LLM decide si hay flow unico")
    else:
        console.print("       -> LangchainGraphRAGReasoningProvider")
        console.print("          -> LLM requerido no ejecuto")
    if payload["can_resolve"]:
        console.print("    -> project_flow_context")
        console.print("       -> proyecta plan y tareas")
    else:
        console.print("    -> unknown_result")
        console.print("       -> pide aclaracion")
    console.print(" -> Audit")
    console.print(" -> ask_trace JSON")
    console.print(f"    -> {trace_file}")
    console.print(" -> respuesta al usuario")
    console.print("")


def _print_debug_events(events: list[tuple[str, str]]) -> None:
    console.print("[bold]Raw debug events[/bold]")
    for component, message in events:
        if message.startswith("file="):
            console.print(f"[bold cyan]{component}[/bold cyan] file: {message.removeprefix('file=')}")
            continue
        if "=" in message and message.startswith(
            (
                "input=",
                "output=",
                "filters=",
                "top_candidates=",
                "params=",
                "rows_preview=",
                "answer_json=",
            )
        ):
            key, value = message.split("=", 1)
            console.print(f"[bold cyan]{component}[/bold cyan] {key}:")
            console.print(indent(_format_trace_value(value), "  "))
            continue
        if message.startswith("query=") or message.startswith("prompt_preview="):
            key, value = message.split("=", 1)
            console.print(f"[bold cyan]{component}[/bold cyan] {key}:")
            console.print(indent(value, "  "))
            continue
        console.print(f"[bold cyan]{component}[/bold cyan] {message}")


def _message_value(events: list[tuple[str, str]], component: str, prefix: str) -> str | None:
    for event_component, message in events:
        if event_component == component and message.startswith(prefix):
            return message.removeprefix(prefix)
    return None


def _json_message_value(events: list[tuple[str, str]], component: str, prefix: str):
    value = _message_value(events, component, prefix)
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _pretty_json(value) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def _query_understanding_provider(events: list[tuple[str, str]]) -> str | None:
    for component, message in events:
        if component == "query_understanding" and message.startswith("provider="):
            return message.split(" ", 1)[0].removeprefix("provider=")
    return None


def _route(events: list[tuple[str, str]], can_resolve: bool) -> str:
    for component, message in events:
        if component == "orchestration" and "method=_ask_route_after_classification output=" in message:
            raw = message.split("output=", 1)[1]
            try:
                return json.loads(raw)["route"]
            except (json.JSONDecodeError, KeyError):
                break
    return "project" if can_resolve else "unknown"


def _format_trace_value(value: str) -> str:
    try:
        return json.dumps(json.loads(value), indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return value


def _friendly_error(message: str) -> str:
    if "Cannot resolve address" in message and "neo4j" in message.lower():
        return (
            "Neo4j no esta disponible desde este proceso. Revisa que el contenedor este arriba "
            "y que el comando se ejecute en la misma red Docker."
        )
    if "OPENAI_API_KEY" in message:
        return "Falta configurar la API key. Ejecuta make configure-ai-prompt o make configure-openrouter-prompt."
    if "USE_AI_PROVIDERS must be true" in message:
        return "El flujo ask requiere USE_AI_PROVIDERS=true. Ejecuta make configure-ai-prompt o make configure-openrouter-prompt."
    return message


@app.command()
def ingest(source: Path) -> None:
    """Ingest knowledge files from a local path into the knowledge index."""
    ingestion = build_ingestion_provider()
    records = ingestion.ingest(source)
    console.print_json(
        data={
            "status": "ok",
            "source": str(source),
            "records_ingested": len(records),
            "intents": [record.intent for record in records],
        }
    )


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the FastAPI server."""
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is required to run the API server.") from exc
    from app.api import create_app

    uvicorn.run(create_app(), host=host, port=port)
