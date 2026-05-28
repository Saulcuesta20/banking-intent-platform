# Raw Ingestion Corpus

Esta carpeta simula fuentes reales de una empresa. Los documentos no estan
preclasificados por intencion. La ingestion debe analizar el corpus, detectar
patrones escondidos y proponer si cada fragmento sirve para Q&A, caso guiado,
ejecucion de proceso, reglas, excepciones, sistemas o aprobaciones.

Fuentes empresariales nuevas:

- `enterprise_operations_manual.md`: manual operativo mezclado.
- `enterprise_policy_and_controls.md`: politicas, controles, aprobaciones y excepciones.
- `enterprise_support_wiki.md`: wiki de soporte con preguntas y guias.
- `enterprise_systems_catalog.md`: sistemas, servicios legados y protocolos.

Los procesos estructurados viven en `data/processes/*.process.json`. Los flows
runtime viven en `data/flows/*.flow.json`. La ingestion genera o refresca
flows/user_tasks/action_registry desde textos empresariales y deja evidencia
para revision humana antes de cargar el grafo.

Comandos utiles:

```bash
make extract-reasoning
make extract-autogen
make extract-apply
make graph-load
```
