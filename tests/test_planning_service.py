from app.knowledge_base.models import AssetSearchResult, EnterpriseAsset
from app.capability.registry import RegistryCapabilityProvider
from app.planning.service import PlanningService
from conftest import sample_records


def load_records(*flow_ids):
    return sample_records(*flow_ids)


def test_static_flow_goal_routes_to_known_route():
    records = load_records("loan.refinance")
    tools = RegistryCapabilityProvider(records).list_registered_tools()

    trace = PlanningService().analyze("Quiero refinanciar mi prestamo", records, tools)

    assert trace.goal.type == "business_goal"
    assert trace.route.mode == "known_route"
    assert trace.user_needs[0].resolution_action == "invoke_known_flow"
    assert trace.route.primary_target.id == "loan.refinance"
    assert trace.multiple_intentions_plan.planning_mode == "known_route_projection"
    assert any(step.step == "review_refinance_options" for step in trace.multiple_intentions_plan.steps)


def test_tool_explanation_routes_to_known_tool():
    records = load_records("loan.refinance")
    tools = RegistryCapabilityProvider(records).list_registered_tools()

    trace = PlanningService().analyze("Como calculan las nuevas condiciones de mi prestamo?", records, tools)

    assert trace.route.mode == "known_route"
    assert any(need.resolution_action == "explain_tool" for need in trace.user_needs)
    assert any(
        target.id == "loan.conditions.calculate"
        for need in trace.user_needs
        for target in need.known_targets
    )


def test_multiple_intentions_question_composes_flow_tool_and_question_needs():
    records = load_records("loan.refinance", "savings_account_opening", "loan.payment")
    tools = RegistryCapabilityProvider(records).list_registered_tools()
    question = (
        "Quiero refinanciar mi prestamo para bajar la cuota, explicame como calculan "
        "las condiciones y dime si necesito abrir una cuenta para pago automatico"
    )

    trace = PlanningService().analyze(question, records, tools)

    assert trace.route.mode == "multiple_intentions"
    assert {need.resolution_action for need in trace.user_needs} >= {
        "invoke_known_flow",
        "explain_tool",
        "answer_question",
    }
    assert trace.multiple_intentions_plan.planning_mode == "multiple_intentions"
    assert any(step.tools for step in trace.multiple_intentions_plan.steps)
    assert trace.multiple_intentions_plan.validation_errors == []


def test_direct_qa_route_stays_known_route_even_with_multiple_flow_candidates():
    records = load_records("savings_account_opening", "loan.payment")
    tools = RegistryCapabilityProvider(records).list_registered_tools()

    trace = PlanningService().analyze("Necesito una cuenta para pago automatico?", records, tools)

    assert trace.route.mode == "known_route"
    assert trace.route.primary_target.id == "qa.automatic_payment_account_required"
    assert {need.resolution_action for need in trace.user_needs} == {"answer_question"}


def test_unsupported_question_rejects_unknown_goal():
    trace = PlanningService().analyze("Quiero comprar entradas para un concierto", [], [])

    assert trace.route.mode == "unsupported"
    assert trace.user_needs[0].resolution_action == "reject_unsupported"


def test_asset_search_can_supply_consultable_rule_answer_target():
    asset_search = AssetSearchResult(
        query="Cuales son las reglas para refinanciar?",
        supporting_assets=[
            EnterpriseAsset(
                asset_id="business_rule.refinance_eligibility",
                asset_type="business_rule",
                name="Loan refinance eligibility",
            )
        ],
    )

    trace = PlanningService().analyze(
        "Cuales son las reglas para refinanciar?",
        [],
        [],
        asset_search=asset_search,
    )

    assert trace.route.mode == "known_route"
    assert trace.route.primary_target.id == "business_rule.refinance_eligibility"
    assert {need.resolution_action for need in trace.user_needs} == {"answer_question"}
