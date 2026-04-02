from google.adk.agents import LlmAgent
import src.frosty_ai.objagents.config as cfg
from src.frosty_ai.objagents.sub_agents.pillar_callbacks import before_model_callback, after_model_callback
from .prompt import AGENT_NAME, DESCRIPTION, INSTRUCTIONS
from .tools import list_all_warehouses, check_warehouse_exists

ag_sf_inspect_warehouse = LlmAgent(
    model=cfg.PRIMARY_MODEL,
    name=AGENT_NAME,
    description=DESCRIPTION,
    instruction=INSTRUCTIONS,
    tools=[list_all_warehouses, check_warehouse_exists],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)
