from app.factory import build_intent_service


def test_refinance_question_returns_expected_plan():
    result = build_intent_service().resolve("Quiero refinanciar mi prestamo")

    assert result.intent == "loan.refinance"
    assert result.flow_id == "loan.refinance"
    assert result.confidence == 0.9
    assert result.business_event == "LoanRefinancingRequested"
    assert result.requires_human_approval is True
    assert result.plan == [
        "identify_customer",
        "review_loan_status",
        "review_refinance_options",
        "prepare_refinance_request",
        "approve_business_case",
    ]
    assert [task.to_dict() for task in result.tasks] == [
        {"task": "identify_customer", "type": "user_task"},
        {"task": "review_loan_status", "type": "user_task"},
        {"task": "review_refinance_options", "type": "user_task"},
        {"task": "prepare_refinance_request", "type": "user_task"},
        {"task": "approve_business_case", "type": "approval"},
    ]


def test_synonym_question_returns_expected_flow():
    result = build_intent_service().resolve("Quiero refinanciar mi credito")

    assert result.intent == "loan.refinance"
    assert result.flow_id == "loan.refinance"
    assert "Loan" in result.related_ontology_nodes


def test_service_registers_actions_on_startup():
    service = build_intent_service()
    registry = service.capability_service.list_registered_actions()

    assert any(action.action == "loan.conditions.calculate" for action in registry)
    assert any(action.type == "front_action" for action in registry)
    assert any(action.type == "back_action" for action in registry)


def test_unknown_question_returns_cannot_resolve():
    result = build_intent_service().resolve("Quiero comprar entradas para un concierto")

    assert result.to_dict()["can_resolve"] is False
    assert result.intent == "unknown"
    assert result.confidence == 0.0
