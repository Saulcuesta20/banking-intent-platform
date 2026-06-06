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
- `enterprise_dump_2026/enterprise_asset_corpus_expanded.md`: corpus ampliado
  con al menos 12 registros por familia principal de activo para probar
  alineacion canonica, aliases, planes y causalidad.

La ingestion ya no debe asumir solo flows. El corpus mezcla entidades, reglas,
procesos, flows, planes, causalidad, Q&A, herramientas y documentos. La ruta
de KB ingestion genera o refresca esos activos desde texto empresarial y deja
evidencia para revision humana antes de cargar el grafo.

Comandos utiles:

```bash
make extract-reasoning
make extract-autogen
make extract-apply
make graph-load
```
