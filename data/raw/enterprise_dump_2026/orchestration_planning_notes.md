# Orchestration Planning Notes

The platform team documented how agents should compose customer journeys from
business tasks and tools. These notes are draft operational guidance, not a
formal asset export.

## Plan: International transfer review

Goal: decide whether a high value international transfer can be released.

Steps:
1. Identify the customer and validate active relationship.
2. Capture transfer details and normalize amount, currency, beneficiary, and
   destination country.
3. Screen the beneficiary through the compliance screening gateway.
4. Evaluate high value transfer controls and destination risk.
5. Request purpose document when the control requires evidence.
6. Route to manager or compliance review when policy gates are triggered.
7. Notify customer and record decision evidence.

Expected tools: ui.customer.identify, customer.identity.validate,
ui.transfer.capture, transfer.create, api.sanctions.screen, risk.case.create,
ui.document.request, notification.send, approval.update.

## Plan: Loan refinance assistance

Goal: help a customer understand and request refinance options.

Steps:
1. Identify the customer.
2. Read current loan status and arrears status.
3. Calculate refinance conditions.
4. Compare refinance options and show payment impact.
5. Check manager approval threshold.
6. Collect missing evidence when required.
7. Submit request or explain decline reason.

Expected tools: ui.customer.identify, customer.identity.validate,
loan.conditions.calculate, loan_refinance.compare, document.upload,
approval.update.

## Plan: Automatic payment setup

Goal: configure recurring payment for an existing loan.

Steps:
1. Identify the customer.
2. Verify the loan is active.
3. Check eligible savings account.
4. Explain account requirement when no eligible account exists.
5. Offer account opening journey.
6. Capture payment day and customer acceptance.
7. Enable automatic debit and send confirmation.

Expected tools: customer.identity.validate, loan.status.read,
account.eligibility.check, ui.account.open, automatic_debit.create,
notification.send.
