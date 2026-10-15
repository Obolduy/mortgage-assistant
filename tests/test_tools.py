import json

import pytest
from agents import RunContextWrapper
from agents.tool_context import ToolContext

from app.agents.tools import TOOLS, ClientContext, simulate_early_repayment


def test_model_cannot_choose_loan():
    for tool in TOOLS:
        assert "loan_id" not in json.dumps(tool.params_json_schema)


async def call(tool, loan_id, **args):
    ctx = ToolContext(
        context=ClientContext(loan_id), tool_name=tool.name, tool_call_id="call_1", tool_arguments=json.dumps(args)
    )
    return await tool.on_invoke_tool(ctx, json.dumps(args))


@pytest.mark.asyncio
async def test_simulate_uses_calculator():
    out = await call(simulate_early_repayment, 1, after_month=12, amount_rub=500_000, mode="payment")
    assert out["new_payment"] == "49 477,38 ₽"
    assert out["saved_on_interest"] == "771 538,25 ₽"


def test_context_wrapper_carries_loan():
    assert RunContextWrapper(ClientContext(7)).context.loan_id == 7
