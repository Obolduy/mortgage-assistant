from app.core.config import settings
from app.domain.schedule import round_div


def cost_micros(model: str, input_tokens: int, output_tokens: int) -> int:
    price_in, price_out = settings.llm_prices.get(model, (0, 0))
    return round_div(input_tokens * price_in + output_tokens * price_out, 1_000_000)
