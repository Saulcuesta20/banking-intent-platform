# Operations Controls Policy Extract

This document was exported from the internal policy wiki. It mixes controls,
review queues, operational guidance, and examples used by supervisors.

## High value transfer control

International transfers above USD 50,000 must remain on hold until enhanced due
diligence is completed. The transfer record must include source account,
beneficiary identity, destination country, amount, currency, and documented
purpose of payment. If beneficiary screening is inconclusive, the case must be
routed to Compliance Review before release.

Control owner: Payments Operations.
Systems mentioned: Transfer Service, Compliance Screening Gateway, Case Manager.
Related customer phrases: "mi transferencia quedo retenida", "por que necesitan
el motivo de la transferencia", "puedo transferir hoy al exterior".

## Automatic payment account requirement

A recurring loan payment can only be configured from an eligible savings account.
If the customer does not have an eligible account, the agent must explain the
requirement and offer the account opening journey before enabling automatic
debit. The customer must accept terms and choose a payment day.

Control owner: Loan Servicing.
Systems mentioned: Account Eligibility Service, Loan Servicing Platform.
Related customer phrases: "necesito abrir cuenta para pago automatico", "quiero
pagar automaticamente mi prestamo".

## Refinance manager approval threshold

Refinance options that extend the loan term by more than 24 months or reduce
the monthly installment by more than 20 percent require manager review. The
reviewer must see current loan status, calculated options, customer income
evidence, and the comparison summary before approving the request.

Control owner: Credit Operations.
Systems mentioned: Loan Pricing Service, Approval Workbench.
Related customer phrases: "quiero bajar la cuota", "necesito mejores
condiciones", "por que no califico para refinanciar".

## Customer notification rules

When a request is held for review, the agent must notify the customer with the
reason, required evidence, and estimated review time. Notification can be sent
by mobile push, email, or branch receipt. Do not include internal risk scores in
customer-facing messages.

Control owner: Customer Communications.
Systems mentioned: Notification Service, Case Manager.
