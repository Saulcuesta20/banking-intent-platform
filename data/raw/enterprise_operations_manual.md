# Manual Operativo Empresarial

## Vision general

El area de banca minorista administra apertura de cuentas, solicitudes de
prestamo, transferencias, reclamos y alta de clientes. Los documentos internos
mezclan preguntas frecuentes, reglas de negocio, pasos manuales, integraciones
tecnicas y controles de aprobacion. Durante la carga, el sistema debe descubrir
si un fragmento es informativo, guiado o ejecutable sin depender de etiquetas
previas.

## Alta de cliente y apertura de cuenta

Cuando una persona quiere convertirse en cliente, el ejecutivo debe crear o
actualizar el caso de onboarding. Primero se identifica al cliente, despues se
solicitan documentos KYC: identificacion vigente, comprobante de domicilio y
datos fiscales si corresponde. Si el cliente pregunta solamente que documentos
necesita, se debe responder con la lista y la razon de cada requisito. Si pide
ayuda para abrir la cuenta, el sistema debe guiarlo paso a paso. Si pide crear
la cuenta con documentos ya cargados, se debe validar identidad y documentos
antes de llamar al core bancario.

Una cuenta de ahorro no debe crearse si faltan documentos obligatorios. Si la
validacion de identidad falla, el caso se detiene y se envia a revision manual.
La confirmacion final se notifica al cliente cuando el core bancario devuelve
una cuenta creada.

## Solicitud de prestamo

La solicitud de prestamo puede iniciar como consulta, caso guiado o ejecucion.
Si el cliente pregunta que evalua el banco, se debe explicar ingresos, historial
crediticio, relacion deuda ingreso, plazo, monto, finalidad y reglas de riesgo.
Si el cliente pide ayuda paso a paso, se deben pedir monto, plazo, finalidad,
evidencia de ingresos y documentos. Si el cliente pide ejecutar o enviar la
solicitud, el sistema crea la solicitud, consulta historial crediticio, obtiene
contexto de politica y calcula scoring.

Las solicitudes borderline o de alto riesgo requieren aprobacion humana. La
ejecucion queda pausada hasta recibir decision de aprobacion. El proceso debe
registrar auditoria de cada llamada, entrada recibida y resultado.

## Transferencias

Para una transferencia se requiere cliente identificado, cuenta origen,
beneficiario o CBU, monto y concepto. Si el cliente pregunta que datos necesita,
se responde de forma informativa. Si pide guia, se preparan los datos sin
ejecutar. Si dice "realiza", "ejecuta" o "confirma y envia", el sistema valida
saldo y riesgo antes de crear la transferencia.

Si no hay saldo suficiente, se informa al cliente y no se llama al servicio de
transferencias. Si el monto supera el limite operativo, se solicita aprobacion
de operaciones antes de continuar.

## Reclamos

Los reclamos pueden ser por comisiones incorrectas, cargos desconocidos,
transferencias no reconocidas o errores operativos. Una pregunta sobre como
presentar un reclamo se responde con requisitos y evidencia esperada. Una guia
de reclamo pide motivo, fecha, importe, referencia y evidencia. Una ejecucion
crea el caso, registra evidencia y revisa movimientos.

Los reclamos con indicios de fraude o riesgo legal se escalan a un equipo
humano. Si falta evidencia, el proceso queda esperando informacion del cliente.
