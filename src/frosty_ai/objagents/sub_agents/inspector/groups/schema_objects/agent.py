from google.adk.agents import LlmAgent
from .prompt import AGENT_NAME, DESCRIPTION, INSTRUCTION
import src.frosty_ai.objagents.config as cfg
from src.frosty_ai.objagents.sub_agents.pillar_callbacks import before_model_callback, after_model_callback
from src.frosty_ai.objagents.lazy_agent_tool import LazyAgentTool

from src.frosty_ai.objagents.sub_agents.inspector.database.prompt import AGENT_NAME as _DB_NAME, DESCRIPTION as _DB_DESC
from src.frosty_ai.objagents.sub_agents.inspector.schemas.prompt import AGENT_NAME as _SCH_NAME, DESCRIPTION as _SCH_DESC
from src.frosty_ai.objagents.sub_agents.inspector.tables.prompt import AGENT_NAME as _TBL_NAME, DESCRIPTION as _TBL_DESC
from src.frosty_ai.objagents.sub_agents.inspector.columns.prompt import AGENT_NAME as _COL_NAME, DESCRIPTION as _COL_DESC
from src.frosty_ai.objagents.sub_agents.inspector.views.prompt import AGENT_NAME as _VW_NAME, DESCRIPTION as _VW_DESC
from src.frosty_ai.objagents.sub_agents.inspector.stages.prompt import AGENT_NAME as _STG_NAME, DESCRIPTION as _STG_DESC
from src.frosty_ai.objagents.sub_agents.inspector.fileformats.prompt import AGENT_NAME as _FF_NAME, DESCRIPTION as _FF_DESC
from src.frosty_ai.objagents.sub_agents.inspector.pipes.prompt import AGENT_NAME as _PIPE_NAME, DESCRIPTION as _PIPE_DESC
from src.frosty_ai.objagents.sub_agents.inspector.warehouses.prompt import AGENT_NAME as _WH_NAME, DESCRIPTION as _WH_DESC

_BASE = "src.frosty_ai.objagents.sub_agents.inspector"

ag_sf_schema_objects_group = LlmAgent(
    model=cfg.PRIMARY_MODEL,
    name=AGENT_NAME,
    description=DESCRIPTION,
    instruction=INSTRUCTION,
    tools=[
        LazyAgentTool(module_path=f"{_BASE}.database.agent", agent_attr="ag_sf_inspect_database", name=_DB_NAME, description=_DB_DESC),
        LazyAgentTool(module_path=f"{_BASE}.schemas.agent", agent_attr="ag_sf_inspect_schema", name=_SCH_NAME, description=_SCH_DESC),
        LazyAgentTool(module_path=f"{_BASE}.tables.agent", agent_attr="ag_sf_inspect_table", name=_TBL_NAME, description=_TBL_DESC),
        LazyAgentTool(module_path=f"{_BASE}.columns.agent", agent_attr="ag_sf_inspect_column", name=_COL_NAME, description=_COL_DESC),
        LazyAgentTool(module_path=f"{_BASE}.views.agent", agent_attr="ag_sf_inspect_views", name=_VW_NAME, description=_VW_DESC),
        LazyAgentTool(module_path=f"{_BASE}.stages.agent", agent_attr="ag_sf_inspect_stage", name=_STG_NAME, description=_STG_DESC),
        LazyAgentTool(module_path=f"{_BASE}.fileformats.agent", agent_attr="ag_sf_inspect_file_format", name=_FF_NAME, description=_FF_DESC),
        LazyAgentTool(module_path=f"{_BASE}.pipes.agent", agent_attr="ag_sf_inspect_pipe", name=_PIPE_NAME, description=_PIPE_DESC),
        LazyAgentTool(module_path=f"{_BASE}.warehouses.agent", agent_attr="ag_sf_inspect_warehouse", name=_WH_NAME, description=_WH_DESC),
    ],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)
