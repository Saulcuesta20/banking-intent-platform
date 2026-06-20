## Corporate Structure and Offerings (June 2026 Refresh)

### Enterprise Leadership & Departments
- Global Banking Group (corporate parent) oversees four divisions:
  - Retail & Digital Banking Division
    - Customer Experience Department: owns onboarding journeys, teller-assisted services, branch support.
    - Everyday Banking Department: manages checking, savings, debit services, overdraft policies.
  - Lending & Credit Division
    - Personal Lending Department: personal loans, credit lines, refinancing programs.
    - Commercial Lending Department: equipment finance, working capital loans.
  - Wealth & Insurance Division
    - Wealth Advisory Department: portfolio review, managed investment products.
    - Protection Services Department: insurance bundles, premium waiver rules.
  - Shared Services Division
    - Operations Control Department: payments processing, investigations, escalations.
    - Technology Enablement Department: API platforms, orchestration, monitoring.

### Product & Service Catalog
- Everyday Banking Suite (offering):
  - SmartBalance Checking (product) – transaction account with automated sweeps.
  - Horizon Savings (product) – tiered interest savings with loyalty boosters.
  - EverydayPlus Debit (service) – debit card program with fraud alerts.
- Lending Portfolio:
  - FlexPay Personal Loan (product) – unsecured, fixed rate, 24-60 months.
  - EquipLease Commercial Loan (product) – asset-backed equipment leasing.
  - RapidRefi Program (service) – refinance workflow for existing borrowers.
- Wealth & Protection:
  - GuidedWealth Portfolio (service) – managed accounts with quarterly reviews.
  - ShieldGuard Insurance Bundle (product) – life + disability package tied to lending.

### Transaction & Event Examples
- Account opening transaction: SmartBalance Checking + EverydayPlus Debit issued together, triggers Know Your Customer event and debit activation event.
- Loan disbursement transaction: FlexPay Personal Loan funding generates disbursement event, repayment schedule confirmation, collateral verification (for secured loans).
- Insurance enrollment transaction: ShieldGuard Insurance linked to loan onboarding, requires agreement acceptance and beneficiary confirmation event.

### Agreements & Policies
- Retail Banking Service Agreement – governs checking/savings features, overdraft limits, digital consent.
- FlexPay Lending Agreement – disbursement terms, repayment conditions, hardship options.
- ShieldGuard Protection Terms – coverage limits, exclusions, premium waiver triggers.

### Supporting Assets & Tools
- Customer Experience Playbook (document): outlines onboarding personas, contact center scripts, escalation matrix.
- Product Eligibility Matrix (document): CSV/JSON table mapping offerings to customer segments, credit tiers, required documents.
- OmniChannel Orchestrator (system/tool): routes events between branches, digital channels, and workflow engines.
- Insight360 Analytics Platform (system/tool): aggregates product performance, cross-sell opportunities, churn risk scores.

### Departmental Responsibilities & Relations
- Customer Experience Department **(organization layer)**
  - Works with Everyday Banking Department to craft step-by-step onboarding flows.
  - Consumes OmniChannel Orchestrator API for branch + digital step tracking.
- Personal Lending Department **(organization layer)**
  - Owns FlexPay Personal Loan, RapidRefi Program, ShieldGuard cross-sell triggers.
  - Collaborates with Protection Services Department on insurance upsells.
- Operations Control Department **(organization layer)**
  - Monitors disbursement exceptions, handles dispute events, drives root-cause investigations tied to Insight360 dashboards.

### Key Metrics & Signals
- Account onboarding SLA target: 12 minutes for digital, 20 minutes assisted.
- FlexPay approval rate: 67% average, with RapidRefi aiming for 4-hour decision window.
- ShieldGuard attachment rate: 38% of FlexPay originations; target 45%.

### Future Initiatives
- Introduce Business Banking Starter Suite (party/offering) for micro-enterprises with bundled checking + working capital line.
- Expand Insight360 to include sustainability scoring metrics for lending portfolios.
