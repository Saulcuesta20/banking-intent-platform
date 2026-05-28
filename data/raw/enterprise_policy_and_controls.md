# Politicas, Controles y Excepciones

## Politicas comunes

Todo proceso ejecutable debe validar permisos, trazabilidad y fuente de datos.
Las respuestas informativas no ejecutan acciones. Los casos guiados pueden
recolectar datos, pero no deben invocar servicios finales sin confirmacion y
validaciones completas. La ejecucion de proceso puede invocar servicios legados
si el usuario confirma la operacion y los datos requeridos estan presentes.

## Apertura de cuenta

Regla: identity_must_be_valid.
La identidad del cliente debe estar validada antes de crear una cuenta.

Regla: documents_must_be_complete.
Los documentos obligatorios deben estar completos. Si faltan, el proceso debe
quedar en waiting_for_user_input.

Excepcion: identity_validation_failed.
Si la validacion de identidad falla, no se crea la cuenta y se escala al
ejecutivo bancario.

## Prestamos

Regla: income_required.
La evidencia de ingresos es obligatoria antes de evaluar capacidad de pago.

Regla: borderline_requires_approval.
Si scoring, DTI o politica interna clasifican la solicitud como borderline o
alto riesgo, se requiere aprobacion humana.

Excepcion: manual_credit_approval.
La solicitud queda pausada hasta recibir approval_decision y evidencia de
aprobacion.

## Transferencias

Regla: balance_must_be_available.
La cuenta origen debe tener saldo disponible suficiente.

Regla: high_amount_requires_approval.
Montos sobre el limite operativo requieren aprobacion del equipo de operaciones.

Excepcion: insufficient_balance.
Si no hay saldo, no se crea la transferencia.

## Reclamos

Regla: claim_evidence_required.
Todo reclamo debe tener evidencia o referencia de transaccion.

Regla: fraud_risk_requires_escalation.
Casos con posible fraude o riesgo legal se escalan al equipo de riesgo.

Excepcion: missing_claim_evidence.
Si falta evidencia, el sistema debe pedir informacion adicional al cliente.

## Revision humana

Los artefactos extraidos por ingestion deben quedar como candidatos cuando:
- el corpus contiene instrucciones contradictorias
- una accion ejecutable no tiene sistema destino claro
- una regla impacta aprobacion o riesgo
- un proceso tiene servicios legados sin protocolo definido
- el LLM infiere un flujo que no aparece claramente soportado por la fuente
