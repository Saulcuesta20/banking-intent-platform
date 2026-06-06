import os

from app.models import KnowledgeRecord, Task, UserTask
from app.knowledge_base.models import AssetRelation, EnterpriseAsset
from app.tools.models import ToolDefinition


def pytest_configure():
    os.environ.setdefault("USE_AI_PROVIDERS", "true")


def sample_records(*flow_ids: str) -> list[KnowledgeRecord]:
    records = {
        "loan.refinance": KnowledgeRecord(
            flow_id="loan.refinance",
            flow_name="Loan Refinance",
            intent="loan.refinance",
            confidence=0.9,
            business_event="LoanRefinancingRequested",
            utterances=["quiero refinanciar mi prestamo"],
            plan=[
                "identify_customer",
                "review_loan_status",
                "review_refinance_options",
                "prepare_refinance_request",
                "approve_business_case",
            ],
            tasks=[
                Task(task="identify_customer", type="user_task"),
                Task(task="review_loan_status", type="user_task"),
                Task(task="review_refinance_options", type="user_task"),
                Task(task="prepare_refinance_request", type="user_task"),
                Task(task="approve_business_case", type="approval"),
            ],
            user_tasks=[
                UserTask(task="identify_customer", type="user_task", sequence=1),
                UserTask(task="review_loan_status", type="user_task", sequence=2),
                UserTask(
                    task="review_refinance_options",
                    type="user_task",
                    sequence=3,
                    tools=[
                        ToolDefinition(
                            tool_id="ui.refinance.calculate",
                            tool_type="frontend_tool",
                            operation="calculate",
                            resource="loan_refinance",
                            label="Calculate refinance",
                            frontend_event="loan_refinance.calculate",
                        ),
                        ToolDefinition(
                            tool_id="loan.conditions.calculate",
                            tool_type="backend_tool",
                            operation="calculate",
                            resource="loan",
                        ),
                    ],
                    description="Review refinance choices with the customer.",
                ),
                UserTask(task="prepare_refinance_request", type="user_task", sequence=4),
                UserTask(task="approve_business_case", type="approval", sequence=5),
            ],
            capabilities=["loan.conditions.calculate"],
            concepts=["Loan", "LoanRefinance"],
            concept_aliases={"Loan": ["prestamo", "credito"], "LoanRefinance": ["refinanciar"]},
            explanation="The corpus describes refinance options.",
            source="test",
        ),
        "savings_account_opening": KnowledgeRecord(
            flow_id="savings_account_opening",
            flow_name="Savings Account Opening",
            intent="savings.account.opening",
            confidence=0.85,
            business_event="SavingsAccountOpeningRequested",
            utterances=["abrir cuenta de ahorro"],
            plan=["open_savings_account"],
            tasks=[Task(task="open_savings_account", type="user_task")],
            user_tasks=[UserTask(task="open_savings_account", type="user_task")],
            capabilities=["account.create"],
            concepts=["SavingsAccount"],
            explanation="Open a savings account.",
            source="test",
        ),
        "loan.payment": KnowledgeRecord(
            flow_id="loan.payment",
            flow_name="Loan Payment",
            intent="loan.payment",
            confidence=0.8,
            business_event="LoanPaymentRequested",
            utterances=["pagar prestamo"],
            plan=["make_loan_payment"],
            tasks=[Task(task="make_loan_payment", type="user_task")],
            user_tasks=[UserTask(task="make_loan_payment", type="user_task")],
            capabilities=["loan.payment.create"],
            concepts=["LoanPayment"],
            explanation="Make a loan payment.",
            source="test",
        ),
        "loan.request": KnowledgeRecord(
            flow_id="loan.request",
            flow_name="Loan Request",
            intent="loan.request",
            confidence=0.7,
            business_event="LoanRequested",
            utterances=["quiero un prestamo"],
            plan=["apply_for_loan"],
            tasks=[Task(task="apply_for_loan", type="user_task")],
            user_tasks=[UserTask(task="apply_for_loan", type="user_task")],
            capabilities=["loan.application.create"],
            concepts=["Loan"],
            explanation="Request a loan.",
            source="test",
        ),
        "money.transfer": KnowledgeRecord(
            flow_id="money.transfer",
            flow_name="Money Transfer",
            intent="money.transfer",
            confidence=0.7,
            business_event="MoneyTransferRequested",
            utterances=["transferir dinero"],
            plan=["transfer_money"],
            tasks=[Task(task="transfer_money", type="user_task")],
            user_tasks=[UserTask(task="transfer_money", type="user_task")],
            capabilities=["transfer.create"],
            concepts=["MoneyTransfer"],
            explanation="Transfer money.",
            source="test",
        ),
    }
    return [records[flow_id] for flow_id in flow_ids] if flow_ids else list(records.values())


def sample_assets() -> list[EnterpriseAsset]:
    return [
        EnterpriseAsset(
            asset_id="qa.automatic_payment_account_required",
            asset_type="qa",
            name="Automatic payment account requirement",
            text="Depende de si el cliente ya tiene una cuenta elegible para pago automatico.",
            tags=["pago automatico", "cuenta", "domiciliacion"],
            relations=[
                AssetRelation(
                    type="references_rule",
                    target_asset_id="business_rule.automatic_payment_account_required",
                ),
                AssetRelation(type="suggests_flow", target_asset_id="flow.savings_account.open"),
            ],
            payload={
                "answer": "Depende de si ya tienes una cuenta elegible para pago automatico.",
                "question_patterns": ["Necesito una cuenta para pago automatico?"],
            },
        ),
        EnterpriseAsset(
            asset_id="business_rule.automatic_payment_account_required",
            asset_type="business_rule",
            name="Automatic payment account eligibility",
            text="Solo se requiere abrir una cuenta nueva cuando el cliente no tiene una cuenta compatible.",
            tags=["automatic_payment", "pago automatico", "cuenta"],
            relations=[
                AssetRelation(type="cited_by_qa", target_asset_id="qa.automatic_payment_account_required"),
                AssetRelation(type="applies_to_flow", target_asset_id="flow.loan.payment"),
            ],
            payload={
                "gate": {
                    "applies_before_execution": True,
                    "required_data": ["customer_has_eligible_payment_account"],
                }
            },
        ),
        EnterpriseAsset(
            asset_id="business_rule.refinance_eligibility",
            asset_type="business_rule",
            name="Loan refinance eligibility",
            text="Refinance requires an eligible active loan.",
            tags=["loan", "refinance"],
            relations=[AssetRelation(type="applies_to_flow", target_asset_id="flow.loan.refinance")],
        ),
        EnterpriseAsset(
            asset_id="plan.loan_refinance",
            asset_type="plan",
            name="Loan refinance plan",
            text="Plan used when the customer wants to refinance a loan.",
            tags=["loan", "refinance"],
            relations=[AssetRelation(type="supports_flow", target_asset_id="flow.loan.refinance")],
        ),
        EnterpriseAsset(
            asset_id="plan.savings_account_opening",
            asset_type="plan",
            name="Savings account opening plan",
            text="Plan used to open a savings account for pago automatico when no eligible cuenta exists.",
            tags=["savings", "account", "pago automatico", "cuenta"],
            relations=[AssetRelation(type="supports_flow", target_asset_id="flow.savings_account.open")],
        ),
    ]
