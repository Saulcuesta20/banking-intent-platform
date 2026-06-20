# Polices and controls addendum

This file is intentionally unstructured and mixes policy fragments, control notes,
and exception guidance for ingestion tests.

## Loan refinance controls

When a customer asks to refinance an active loan, the advisor must verify:
- current loan status
- delinquency history
- payment regularity
- identity match against the customer profile
- any regulatory hold or pending exception

If the loan has unresolved arrears, the request must be escalated for review.

## Operational exceptions

Some cases can move forward only if:
- a supervisor approves the exception
- the customer signs the revised disclosure
- the refinance amount stays inside approved thresholds

The business rule should reflect that the exception is allowed only for verified cases.

## Evidence notes

The corpus mentions:
- automatic payment enrollment
- payment date changes
- fee waiver review
- branch and contact center channels
- service call follow-up

