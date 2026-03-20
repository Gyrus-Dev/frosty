# Contributing to Frosty

Frosty is built on [Google ADK](https://google.github.io/adk-docs/) — a multi-agent framework for building LLM-powered agent hierarchies. This guide explains how to extend Frosty using ADK patterns already established in the codebase.

---

## Adding a new specialist agent

Each specialist lives in a sub-directory under its pillar folder:

```
src/frosty_ai/objagents/sub_agents/<pillar>/<specialist_name>/
    agent.py      # defines the ADK Agent
    prompt.py     # system instructions
    tools.py      # optional specialist-scoped tools
```

**Minimal agent.py:**

```python
from google.adk.agents import LlmAgent
from ..config import PRIMARY_MODEL, get_planner
from .prompt import INSTRUCTIONS

ag_my_specialist = LlmAgent(
    name="MY_SPECIALIST",
    description="One sentence describing what this specialist handles.",
    model=PRIMARY_MODEL,
    instruction=INSTRUCTIONS,
    planner=get_planner(thinking_budget=512),  # 512 for specialist-level
    tools=[],  # add tools here
)
```

Then register it in the pillar's `agent.py` via `LazyAgentTool`:

```python
LazyAgentTool(
    module_path="frosty_ai.objagents.sub_agents.<pillar>.<specialist_name>.agent",
    agent_attr="ag_my_specialist",
    name="MY_SPECIALIST",
    description="One sentence describing what this specialist handles.",
)
```

The `LazyAgentTool` pattern defers the module import until the first invocation — nothing is loaded at startup. The background pre-warmer will pick it up automatically via BFS traversal once it's registered in the pillar.

---

## Adding a new pillar

1. Create `src/frosty_ai/objagents/sub_agents/<new_pillar>/agent.py` following the same pattern as existing pillars (e.g. `administrator/agent.py`).
2. Set `planner=get_planner(thinking_budget=1024)` — pillar agents get the higher budget.
3. Populate it with `LazyAgentTool` entries for each specialist.
4. Register the new pillar in `src/frosty_ai/objagents/agent.py` using `LazyAgentTool`.
5. Add a row to the Agent Hierarchy table in `README.md`.

---

## Extending the safety callback

The `before_tool_callback` in `tools.py` intercepts every query before it reaches Snowflake. Extend the `forbidden` list to block any additional patterns:

```python
def before_tool_callback(query: str) -> str | None:
    forbidden = ["DROP ", "CREATE OR REPLACE"]
    # examples:
    # forbidden += ["TRUNCATE ", "DELETE FROM prod.", "INSERT INTO audit."]
    for pattern in forbidden:
        if pattern.upper() in query.upper():
            raise ValueError(f"Query blocked by safety callback: {pattern}")
```

This is the single enforcement point — it applies to every agent in the hierarchy.

---

## Swapping the model provider

Set `MODEL_PROVIDER` in your `.env` to switch all agents at once:

| Provider | `MODEL_PROVIDER` | Notes |
|---|---|---|
| Google Gemini | `google` (default) | Enables `BuiltInPlanner` with `ThinkingConfig` |
| OpenAI | `openai` | Routed via LiteLLM; planner disabled |
| Anthropic Claude | `anthropic` | Routed via LiteLLM; planner disabled |
| Any LiteLLM model | `openai` or `anthropic` | Set `MODEL_PRIMARY` / `MODEL_THINKING` to the LiteLLM model string |

`config.py` resolves `PRIMARY_MODEL` and `THINKING_MODEL` from env vars — no code changes needed to switch providers.

---

## Adjusting thinking budgets

`get_planner(thinking_budget)` in `config.py` returns a `BuiltInPlanner` for Google models, `None` otherwise. The budget controls how many tokens the model may spend reasoning before it responds.

Recommended tiers (already used in Frosty):

| Agent level | Budget |
|---|---|
| Manager + pillar agents | 1 024 |
| Specialist agents | 512 |
| Sub-pipeline agents | 256 |

Raise the budget if an agent makes poor multi-step decisions; lower it to reduce latency and token cost.

---

## Adding a web search backend

The Research Agent selects its search tool based on `IS_GOOGLE_MODEL` (set in `config.py`):

- **Gemini** — uses `google_search`, a built-in ADK tool with native retrieval augmentation
- **All other models** — uses `web_search` (DuckDuckGo via `duckduckgo-search`)

To swap in a different search backend, edit `src/frosty_ai/objagents/sub_agents/research/tools.py` and replace the tool passed to the inner search agent. Any callable that accepts a query string and returns text works.

---

## Session state conventions

Frosty uses ADK's scoped session state. Follow existing conventions when writing to state from a new agent or tool:

| Prefix | Scope | Examples |
|---|---|---|
| `user:` | Per user, persists across sessions | `user:USER_NAME`, `user:ROLE` |
| `app:` | Shared across all users in a session | `app:TASKS_PERFORMED`, `app:RESEARCH_RESULTS` |
| `temp:` | Single turn, discarded after | Intermediate scratchpad values |

Append completed tasks to `app:TASKS_PERFORMED` so the Manager can validate progress:

```python
state["app:TASKS_PERFORMED"].append({"task": "...", "result": "..."})
```

---

## Adding Skills to agents

ADK [Skills](https://google.github.io/adk-docs/skills/) are modular, self-contained instruction packages that agents load on demand. Unlike tools (which execute a function), a Skill carries a full instruction set plus optional reference documents — and it loads incrementally, so only the metadata hits the context window until the Skill is actually triggered. This makes them ideal for attaching domain-specific knowledge (e.g. your company's Snowflake naming conventions, approval workflows, or object templates) to any Frosty agent without inflating every prompt.

> **Note:** Skills are an experimental ADK feature. Script execution (`scripts/` directory) is not yet supported.

### Sample skill

A working sample is included at `skills/snowflake-naming-conventions/`. It enforces Snowflake object naming conventions (table prefixes, schema casing, stage naming, etc.) and can be wired into any specialist agent as-is or used as a starting point for your own rules.

```
skills/
└── snowflake-naming-conventions/
    ├── SKILL.md              # entry point — frontmatter + instructions
    └── references/
        └── rules.md          # naming rules injected when the skill fires
```

### File-based skill structure

```
src/frosty_ai/objagents/sub_agents/<pillar>/<specialist_name>/
    agent.py
    prompt.py
    tools.py
    skills/
        <skill_name>/
            SKILL.md          # required entry point
            references/       # optional markdown docs injected when skill fires
            assets/           # optional supporting files
```

**SKILL.md format:**

```markdown
---
name: my-skill-name
description: One sentence shown to the agent for discovery — be specific.
---

Step-by-step instructions the agent follows when this skill is triggered.
Reference any files in references/ by name — they are injected automatically.
```

**Wire it into an agent:**

```python
# agent.py
import pathlib
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

_skills_dir = pathlib.Path(__file__).parent / "skills"

skill_toolset = SkillToolset(
    skills=[load_skill_from_dir(_skills_dir / "snowflake-naming-conventions")]
)

ag_my_specialist = LlmAgent(
    name="MY_SPECIALIST",
    ...
    tools=[execute_query, skill_toolset],  # add alongside existing tools
)
```

To use the repo-level sample skill instead:

```python
import pathlib, sys
_repo_root = pathlib.Path(__file__).parents[6]  # adjust depth as needed
skill_toolset = SkillToolset(
    skills=[load_skill_from_dir(_repo_root / "skills" / "snowflake-naming-conventions")]
)
```

### Code-based skill (inline)

For short, self-contained rules that don't need reference files:

```python
from google.adk.skills import models
from google.adk.tools.skill_toolset import SkillToolset

naming_skill = models.Skill(
    frontmatter=models.Frontmatter(
        name="naming-conventions",
        description="Apply company Snowflake naming conventions to all DDL.",
    ),
    instructions="All table names must be UPPER_SNAKE_CASE prefixed with the domain. "
                 "All schema names must be lowercase prefixed with the environment.",
    resources=models.Resources(
        references={
            "examples.md": "SALES_ORDERS ✓  |  salesOrders ✗\nprod_raw ✓  |  ProdRaw ✗",
        }
    ),
)
skill_toolset = SkillToolset(skills=[naming_skill])
```

### Where to attach skills

| Level | Good for |
|---|---|
| Specialist | Object-type rules (e.g. table naming, stage path conventions) |
| Pillar | Domain-wide standards shared across all specialists in that pillar |
| Manager | Cross-cutting policies that apply to every delegated task |

Attach at the lowest level that covers your use case to keep higher-level context windows lean.

---

## ADK resources

- [Google ADK documentation](https://google.github.io/adk-docs/)
- [ADK models](https://google.github.io/adk-docs/agents/models/) — full list of supported providers
- [ADK tools](https://google.github.io/adk-docs/tools/) — built-in tools including `google_search`, `AgentTool`, code execution
- [ADK session state](https://google.github.io/adk-docs/sessions/state/) — scoped state management reference
- [BuiltInPlanner / ThinkingConfig](https://google.github.io/adk-docs/agents/llm-agents/#built-in-planning) — native reasoning for Gemini models
