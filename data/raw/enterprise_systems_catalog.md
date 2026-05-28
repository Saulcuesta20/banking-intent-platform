# Catalogo de Sistemas e Integraciones

## Sistemas internos

Sistema: Customer Onboarding
Uso: alta de cliente, validacion de documentos y condiciones.
Protocolos: API interna.
Operaciones: customer.create, customer.conditions.validate, document.verify.

Sistema: Core Banking
Uso: creacion de cuenta, consulta de cuenta, validacion de saldo.
Protocolos: API interna, base de datos controlada.
Operaciones: account.create, account.balance.validate, customer.read.

Sistema: Loan Origination
Uso: creacion y seguimiento de solicitudes de prestamo.
Protocolos: API interna.
Operaciones: loan.application.create, loan.read, approval.update.

Sistema: Credit Bureau
Uso: consulta de historial crediticio.
Protocolos: API externa.
Operaciones: credit_history.read.

Sistema: Loan Scoring Service
Uso: calculo de score y elegibilidad.
Protocolos: gRPC.
Endpoint: LoanScoringService/Evaluate.
Operaciones: scoring.evaluate, loan.eligibility.calculate.

Sistema: Banking Policy Context
Uso: recuperacion de politicas, reglas y contexto documental.
Protocolos: MCP.
Endpoint: banking_policy.search.
Operaciones: policy.search.

Sistema: Payments
Uso: validacion y creacion de transferencias.
Protocolos: API interna, servicio legado.
Operaciones: customer.validate, transfer.create, notification.send.

Sistema: Claims Management
Uso: creacion, evidencia y seguimiento de reclamos.
Protocolos: API interna.
Operaciones: claim.create, claim.intake, claim.evidence.collect.

Sistema: Transaction Ledger
Uso: lectura de cargos, comisiones y reconciliacion.
Protocolos: API interna.
Operaciones: billing.read, transaction.reconcile.

## Regla de integracion

La ingestion debe detectar sistemas, protocolos y operaciones para construir
integraciones candidatas en procesos. Las llamadas reales deben quedar detras
de providers. En carga inicial, las integraciones se pueden simular hasta que
el equipo humano apruebe endpoint, protocolo, permisos y contrato de datos.
