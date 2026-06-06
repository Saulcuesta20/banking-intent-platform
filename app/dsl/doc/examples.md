# DSL Examples

## Purpose

Show how the DSL looks for common banking assets using the `USING` keyword.

These are representative examples for the first version of the language. They
are intended to make the intended syntax obvious for a business analyst or a
knowledge engineer.

## Knowledge Base

```text
CREATE KNOWLEDGE_BASE process_kb
  USING 'process'
  STORES ('repository', 'graph')
  DESCRIPTION 'Flow and process ownership';

CREATE KNOWLEDGE_BASE rules_kb
  USING 'rules'
  STORES ('repository', 'document', 'graph', 'vector')
  DESCRIPTION 'Rules and policy governance';

CREATE KNOWLEDGE_BASE qa_kb
  USING 'qa'
  STORES ('repository', 'document', 'graph', 'vector')
  DESCRIPTION 'Approved direct answers';
```

## Rule

```text
CREATE RULE refinance_eligibility USING rules_kb
  STATUS approved
  DESCRIPTION 'Eligibility checks for refinance requests'
  WHEN loan.age_months >= 6
   AND customer.payment_history = 'good'
   AND loan.delinquency_days = 0
  THEN approve_refinance = true;

CREATE RULE transfer_limit_daily USING rules_kb
  STATUS approved
  WHEN transfer.amount > customer.daily_limit
  THEN require_manual_approval = true;

CREATE RULE kyc_must_pass USING rules_kb
  STATUS approved
  WHEN customer.kyc_status != 'passed'
  THEN block_onboarding = true;

CREATE RULE document_missing_block USING rules_kb
  STATUS approved
  WHEN required_document.missing = true
  THEN request_missing_documents = true;

CREATE RULE low_risk_fast_track USING rules_kb
  STATUS approved
  WHEN customer.risk_level = 'low'
   AND customer.payment_history = 'good'
  THEN fast_track_review = true;
```

## Flow

```text
CREATE FLOW loan_refinance USING process_kb
  INTENT 'Quiero refinanciar mi prestamo'
  BUSINESS_EVENT LoanRefinancingRequested
  DESCRIPTION 'Customer requests a refinance with new terms';

CREATE FLOW money_transfer USING process_kb
  INTENT 'Quiero transferir dinero'
  BUSINESS_EVENT MoneyTransferRequested
  DESCRIPTION 'Customer wants to move money between accounts';

CREATE FLOW savings_account_open USING process_kb
  INTENT 'Quiero abrir una cuenta de ahorro'
  BUSINESS_EVENT SavingsAccountOpeningRequested
  DESCRIPTION 'Customer wants to open a savings account';

CREATE FLOW loan_payment USING process_kb
  INTENT 'Quiero pagar mi prestamo'
  BUSINESS_EVENT LoanPaymentRequested
  DESCRIPTION 'Customer wants to make a loan payment';

CREATE FLOW loan_inquiry USING process_kb
  INTENT 'Quiero revisar el estado de mi prestamo'
  BUSINESS_EVENT LoanInformationRequested
  DESCRIPTION 'Customer wants loan status information';
```

## Process

```text
CREATE PROCESS loan_refinance USING process_kb
  VERSION '1.0.0'
  STATUS approved
  RELATED_TO process_node.identify_customer TYPE step
  RELATED_TO process_node.review_loan_status TYPE step
  RELATED_TO process_node.calculate_terms TYPE step
  RELATED_TO rule.refinance_eligibility TYPE dependency
  EMITS_EVENT LoanRefinancingRequested;

CREATE PROCESS money_transfer USING process_kb
  VERSION '1.0.0'
  RELATED_TO process_node.identify_customer TYPE step
  RELATED_TO process_node.validate_transfer TYPE step
  RELATED_TO process_node.execute_transfer TYPE step
  RELATED_TO rule.transfer_limit_daily TYPE dependency
  EMITS_EVENT MoneyTransferRequested;

CREATE PROCESS savings_account_opening USING process_kb
  VERSION '1.0.0'
  RELATED_TO process_node.identify_customer TYPE step
  RELATED_TO process_node.collect_documents TYPE step
  RELATED_TO process_node.kyc_screening TYPE step
  RELATED_TO process_node.create_account TYPE step
  RELATED_TO rule.kyc_must_pass TYPE obligation
  EMITS_EVENT SavingsAccountOpeningRequested;
```

## User Task

```text
CREATE USER_TASK identify_customer USING business_model_kb
  DESCRIPTION 'Identify the customer before account or loan operations'
  RELATED_TO tool.customer.read TYPE usage
  RELATED_TO tool.customer.identity.validate TYPE usage;

CREATE USER_TASK collect_documents USING business_model_kb
  DESCRIPTION 'Collect supporting documents from the user'
  RELATED_TO tool.document.upload TYPE usage
  RELATED_TO tool.document.validate TYPE usage;

CREATE USER_TASK execute_transfer USING business_model_kb
  DESCRIPTION 'Execute a money transfer after validation'
  RELATED_TO tool.account.debit TYPE usage
  RELATED_TO tool.transfer.submit TYPE usage;
```

## Tool

```text
CREATE TOOL customer.read
  TYPE backend_tool
  PROTOCOL http
  ENDPOINT 'https://banking.example/api/customers/{id}'
  DESCRIPTION 'Read customer data';

CREATE TOOL customer.identity.validate
  TYPE backend_tool
  PROTOCOL http
  ENDPOINT 'https://banking.example/api/identity/validate'
  DESCRIPTION 'Validate customer identity';

CREATE TOOL ui.refinance.calculate
  TYPE frontend_tool
  FRONTEND_EVENT 'refinance.calculate.submit'
  DESCRIPTION 'Trigger refinance calculation from the UI';
```

## Entity

```text
CREATE ENTITY loan USING business_model_kb
  ATTRIBUTE loan_id TYPE string REQUIRED
  ATTRIBUTE principal_amount TYPE decimal REQUIRED
  ATTRIBUTE currency TYPE string REQUIRED
  ATTRIBUTE term_months TYPE integer REQUIRED
  ATTRIBUTE interest_rate TYPE decimal REQUIRED
  ATTRIBUTE delinquency_days TYPE integer OPTIONAL
  SYNONYM 'prestamo'
  SYNONYM 'credito'
  SYNONYM 'loan'
  RELATED_TO entity.customer TYPE dependency
  RELATED_TO entity.payment TYPE dependency
  RELATED_TO flow.loan_refinance TYPE usage
  RELATED_TO process.loan_refinance TYPE usage
  RELATED_TO qa.refinance_help TYPE explanation;

CREATE ENTITY savings_account USING business_model_kb
  ATTRIBUTE account_id TYPE string REQUIRED
  ATTRIBUTE account_number TYPE string REQUIRED
  ATTRIBUTE balance TYPE decimal REQUIRED
  ATTRIBUTE currency TYPE string REQUIRED
  ATTRIBUTE opening_date TYPE date OPTIONAL
  SYNONYM 'cuenta de ahorro'
  SYNONYM 'savings account'
  RELATED_TO flow.savings_account_open TYPE usage
  RELATED_TO process.savings_account_opening TYPE usage;

CREATE ENTITY customer USING business_model_kb
  ATTRIBUTE customer_id TYPE string REQUIRED
  ATTRIBUTE full_name TYPE string REQUIRED
  ATTRIBUTE risk_level TYPE enum OPTIONAL
  ATTRIBUTE kyc_status TYPE enum OPTIONAL
  ATTRIBUTE segment TYPE string OPTIONAL
  SYNONYM 'cliente'
  SYNONYM 'customer'
  RELATED_TO entity.account TYPE dependency
  RELATED_TO entity.document TYPE dependency
  RELATED_TO flow.customer_onboarding TYPE usage
  RELATED_TO process.customer_onboarding TYPE usage
  RELATED_TO qa.kyc_steps TYPE explanation;
```

## QA

```text
CREATE QA refinance_help USING qa_kb
  QUESTION 'Que necesito para refinanciar mi prestamo?'
  ANSWER 'Necesitas validar identidad, revisar elegibilidad y confirmar condiciones.'
  STATUS approved;

CREATE QA account_opening_docs USING qa_kb
  QUESTION 'Que documentos necesito para abrir una cuenta?'
  ANSWER 'Identificacion oficial, comprobante de domicilio y datos de contacto.'
  STATUS approved;

CREATE QA transfer_limits USING qa_kb
  QUESTION 'Cual es el limite diario de transferencias?'
  ANSWER 'Depende del perfil del cliente y de la politica vigente.'
  STATUS approved;
```
