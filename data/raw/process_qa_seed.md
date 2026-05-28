# Banking Process QA Seed

## Apertura de cuenta de ahorro

La apertura de una cuenta de ahorro inicia cuando el cliente solicita crear una
cuenta nueva. El banco debe identificar al cliente, recolectar documentos,
validar identidad, revisar condiciones de elegibilidad y crear la cuenta en el
sistema core. Los documentos habituales son identificacion oficial,
comprobante de domicilio y datos fiscales cuando aplican.

El proceso puede continuar de forma guiada si el cliente pide ayuda paso a paso.
La ejecucion automatica solo debe crear la cuenta despues de validar identidad,
documentos y aprobacion cuando la politica lo requiera.

Preguntas frecuentes:
- Que documentos necesito para abrir una cuenta de ahorro?
- Puedo abrir una cuenta si todavia no tengo todos mis documentos?
- Cual es el proceso para crear una cuenta de ahorro?

## Solicitud de prestamo

La solicitud de prestamo captura datos del cliente, monto solicitado, plazo,
ingresos, documentos y finalidad del credito. Despues se evalua elegibilidad
con historial crediticio, capacidad de pago, relacion deuda ingreso y reglas de
riesgo. Si el resultado es borderline o de alto riesgo, requiere aprobacion
humana antes de continuar.

El proceso guiado debe pedir datos uno por uno, validar documentos y explicar
el estado de evaluacion. La ejecucion debe registrar la solicitud, calcular
elegibilidad y detenerse si falta aprobacion.

Preguntas frecuentes:
- Como solicito un prestamo personal?
- Que evalua el banco antes de aprobar un prestamo?
- Por que mi prestamo necesita aprobacion manual?

## Reclamos

Un reclamo se registra cuando el cliente reporta una comision incorrecta,
cargo desconocido, transferencia no reconocida o problema operativo. El banco
debe crear el caso, recolectar evidencia, revisar transacciones, reconciliar
movimientos y comunicar una resolucion.

Si falta evidencia, el proceso debe pedir informacion adicional. Si el reclamo
involucra fraude o riesgo legal, debe escalarse a un equipo humano.

Preguntas frecuentes:
- Como presento un reclamo por una comision?
- Que evidencia necesito para una disputa?
- Cuanto tarda la revision de un reclamo?

## Transferencias

Una transferencia requiere identificar al cliente, validar cuenta origen,
validar saldo, verificar beneficiario o CBU, crear la transferencia y notificar
el resultado. Cuando el monto supera el limite operativo o hay riesgo, se debe
solicitar aprobacion antes de ejecutar.

El proceso guiado debe pedir cuenta origen, beneficiario, monto y concepto. La
ejecucion debe detenerse si no hay saldo suficiente, si el beneficiario no es
valido o si la politica requiere aprobacion.

Preguntas frecuentes:
- Que datos necesito para hacer una transferencia?
- Por que una transferencia puede requerir aprobacion?
- Que pasa si no tengo saldo suficiente?
