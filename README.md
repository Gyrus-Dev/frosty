# Frosty AI

**Frosty** is an AI-powered Snowflake management CLI built by [Gyrus Inc](https://www.thegyrus.com). It uses a multi-agent hierarchy powered by Google ADK to plan, execute, and validate Snowflake DDL operations through natural language — directly from your terminal.

Frosty supports **OpenAI**, **Claude**, and **Gemini** models out of the box. Any other model that Google ADK supports can also be used — refer to the [Google ADK Models documentation](https://google.github.io/adk-docs/agents/models/) for the full list.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                CLI  (Rich + prompt_toolkit)                                 │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               │ user message
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                             CLOUD_DATA_ARCHITECT  (Manager)                                 │
│         Strategic planner — classifies intent, produces execution plan,                     │
│              delegates one task at a time, validates every step via state                   │
└──────┬───────────────┬───────────────┬───────────────┬───────────────┬───────────────┬──────┘
       │               │               │               │               │               │
       ▼               ▼               ▼               ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│    DATA     │ │    ADMIN    │ │  SECURITY   │ │ GOVERNANCE  │ │  INSPECTOR  │ │   ACCOUNT   │
│  ENGINEER   │ │             │ │  ENGINEER   │ │             │ │   PILLAR    │ │   MONITOR   │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │               │               │               │
       ▼               ▼               ▼               ▼               ▼               ▼
    35 spec         19 spec         14 spec          8 spec         54 spec         25 spec
    (below)         (below)         (below)         (below)         (below)         (below)
       └───────────────┴───────────────┴───────────────┴───────────────┴───────────────┘
                                               │
                                               ▼
                                        execute_query()  ──►  Snowflake
                                                                      │
                                                                      ▼
                                                          app:TASKS_PERFORMED
                                                  each completed task appended to state
```

### Agent Hierarchy

| Pillar | Role | Specialists |
|---|---|---|
| **CLOUD_DATA_ARCHITECT** | Manager — plans, routes, validates | — |
| **DATA_ENGINEER** | Physical data layer orchestrator | 35 |
| **ADMINISTRATOR** | Identity, compute, RBAC | 19 |
| **SECURITY_ENGINEER** | Network & auth security | 14 |
| **GOVERNANCE_SPECIALIST** | Tags, policies, data access | 8 |
| **INSPECTOR_PILLAR** | Read-only infrastructure inspection | 54 |
| **ACCOUNT_MONITOR** | ACCOUNT_USAGE cost, billing, audit & operational health | 25 |
| **RESEARCH_AGENT** | Web search & knowledge cache — shared fallback for all pillars | — |

---

## Spotlight Features

### Web Search & Research Agent

Any pillar can call the RESEARCH_AGENT as a fallback when it cannot resolve a query from its own knowledge. The search backend adapts to the active model provider:

```
                         ┌─────────────────────────────────────────────┐
                         │              RESEARCH_AGENT                 │
                         │                                             │
      Gemini models  ──► │  google_search (built-in grounding tool)    │
                         │  Retrieval-augmented over live web results  │
                         │                                             │
   All other models  ──► │  DuckDuckGo search · returns top 5 results │
                         │  (swap in any tool via research/tools.py)   │
                         └─────────────────────────────────────────────┘
```

Results are persisted to `app:RESEARCH_RESULTS` in session state so the same answer is not fetched twice within a session.

---

### Synthetic Data Generation

Ask Frosty to populate any table with realistic sample data and it will inspect the table structure first before writing a single row:

```
  "populate ORDERS table with 10 rows"
                    │
                    ▼
         DESCRIBE TABLE <db.schema.table>
                    │
                    ▼
      ┌─────────────────────────────────┐
      │  Infer value strategy per col   │
      │  · column name  →  domain hint  │
      │  · data type    →  format rule  │
      │  · nullability  →  NULL ratio   │
      └──────────────┬──────────────────┘
                     │
                     ▼
      INSERT INTO <table> (col1, col2, …)
      VALUES (realistic row 1),
             (realistic row 2), …
```

Frosty never invents column names — `DESCRIBE TABLE` is the single source of truth. Values are contextually appropriate: an `EMAIL` column gets valid email addresses, a `STATUS` column gets domain-specific enum values, `VARIANT` columns get minimal valid JSON, and so on.

---

### Thinking & Reasoning (Gemini only)

When using Google Gemini models, every agent is equipped with a `BuiltInPlanner` backed by Gemini's native `ThinkingConfig`. Before generating a response the model silently reasons through the problem within a token budget — this reasoning is not shown to the user but improves decision quality, especially for complex DDL and multi-step plans.

Thinking budgets are tiered by agent responsibility:

| Agent level | Thinking budget |
|---|---|
| Manager (`CLOUD_DATA_ARCHITECT`) + pillar agents | 1 024 tokens |
| Specialist agents | 512 tokens |
| Streamlit pipeline sub-agents | 256 tokens |

For OpenAI and Anthropic providers the planner is disabled — those models handle reasoning internally.

To override the default thinking model set `MODEL_THINKING` in your `.env` (see Configure → Model Provider).

---

## Snowflake Objects Supported

### Data Engineering (35 object types)
Databases · Schemas · Tables · Views · Materialized Views · Semantic Views · External Tables · Hybrid Tables · Iceberg Tables · Dynamic Tables · File Formats · External Stages · Internal Stages · External Volumes · Streams · Tasks · Stored Procedures · User-Defined Functions · External Functions · Sequences · Cortex Search · Snowpipe · COPY INTO · Event Tables · Storage Lifecycle Policies · Snapshots · Snapshot Policies · Snapshot Sets · Streamlit Apps · Models · Datasets · Data Metric Functions · Notebooks · Alerts · Sample Data

### Administration (19 object types)
Users · Roles · Database Roles · Warehouses · Compute Pools · Resource Monitors · Notification Integrations (Email, Azure Event Grid, Google Pub/Sub, Webhook) · Failover Groups · Replication Groups · Organization Profiles · Connections · Application Packages · Image Repositories · Services · Provisioned Throughput · Alerts · Password Policies · Session Policies

### Security (14 object types)
Authentication Policies · Password Policies · Network Rules · Network Policies · Security Integrations (External API Auth, AWS IAM, External OAuth) · API Integrations (Amazon API Gateway) · External Access Integrations · Session Policies · Packages Policies · Secrets · Aggregation Policies · Join Policies

### Governance (8 object types)
Tags · Contacts · Masking Policies · Privacy Policies · Projection Policies · Row Access Policies · Data Exchanges · Listings

### Account Monitoring (25 views across 6 domain groups)
**Query & Access** — Access History · Copy History · Load History · Login History · Query History
**Warehouse & Compute** — Automatic Clustering · Data Transfer History · Metering Daily History · Warehouse Events History · Warehouse Metering History
**Task Automation** — Alert History · Materialized View Refresh · Serverless Task History · Task History
**Storage** — Pipes · Stages · Storage Usage · Table Storage Metrics
**Security & Identity** — Grants to Roles · Grants to Users · Roles · Sessions · Users
**Infrastructure** — Databases · Schemata

---

## CLI Features

```
███████╗██████╗  ██████╗ ███████╗████████╗██╗   ██╗
██╔════╝██╔══██╗██╔═══██╗██╔════╝╚══██╔══╝╚██╗ ██╔╝
█████╗  ██████╔╝██║   ██║███████╗   ██║    ╚████╔╝
██╔══╝  ██╔══██╗██║   ██║╚════██║   ██║     ╚██╔╝
██║     ██║  ██║╚██████╔╝███████║   ██║      ██║
╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝      ╚═╝
                      ╰─ by Gyrus Inc ─╯
                    www.thegyrus.com
```

- **Boxed input** — `prompt_toolkit` framed text input with cyan border
- **Animated spinner** — Braille frames (⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏) tracking the active agent
- **Response panels** — Markdown-rendered AI responses in blue panels
- **SQL panels** — Syntax-highlighted executed queries in green panels (monokai theme)
- **Question panels** — Clarifying questions surfaced in yellow panels
- **Object counter** — Live terminal title and inline `[● Objects created: N]` counter
- **Session export** — All executed SQL written to `queries/session_<timestamp>.sql` on exit
- **Debug mode** — `FROSTY_DEBUG=1` to print agent thinking, tool calls, and payloads

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Framework | Google ADK 1.18+; supports OpenAI, Claude, Gemini (2.5 Flash / 2.5 Pro) and [more](https://google.github.io/adk-docs/agents/models/) |
| Snowflake | snowflake-snowpark-python, snowflake-connector-python |
| Terminal UI | Rich 13+, prompt_toolkit 3+ |
| Validation | Pydantic 2.5+ |
| Utilities | croniter, python-dateutil, GitPython |

---

## Setup

### Prerequisites
- Python 3.11.10
- A Snowflake account with SYSADMIN or equivalent privileges
- An API key for your chosen model provider (Google Gemini, OpenAI, or Anthropic Claude)

### Install

```bash
# Clone and enter the repo
git clone https://github.com/MalviyaPriyank/frosty.git
cd frosty

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

Create a `.env` file in the project root with the variables below.

#### Snowflake Connection

| Variable | Required | Description |
|---|---|---|
| `SNOWFLAKE_USER_NAME` | **Yes** | Your Snowflake login username |
| `SNOWFLAKE_USER_PASSWORD` | **Yes** | Your Snowflake password |
| `SNOWFLAKE_ACCOUNT_IDENTIFIER` | **Yes** | Your Snowflake account identifier (e.g. `xy12345.us-east-1`) |
| `SNOWFLAKE_AUTHENTICATOR` | No | Set to `username_password_mfa` for DUO/TOTP MFA; leave unset for standard password auth |
| `SNOWFLAKE_ROLE` | No | Default role for the session (e.g. `SYSADMIN`); if unset, uses your account default |
| `SNOWFLAKE_WAREHOUSE` | No | Default warehouse to activate at session start; if unset, uses your account default |
| `SNOWFLAKE_DATABASE` | No | Default database context; if unset, uses your account default |

#### Application Identity

| Variable | Required | Description |
|---|---|---|
| `APP_USER_NAME` | **Yes** | Display name shown in the session (can be any string, e.g. your name) |
| `APP_USER_ID` | **Yes** | Unique user ID for session tracking (e.g. `user_001`) |
| `APP_NAME` | **Yes** | Application name for session scoping (e.g. `frosty`) |

#### Model Provider

Set `MODEL_PROVIDER` to select your LLM backend. Defaults to `google`.

| Variable | Required | Description |
|---|---|---|
| `MODEL_PROVIDER` | No | `google` (default) · `openai` · `anthropic` |
| `GOOGLE_API_KEY` | If `google` | API key for Gemini models |
| `OPENAI_API_KEY` | If `openai` | API key for OpenAI models |
| `ANTHROPIC_API_KEY` | If `anthropic` | API key for Claude models |
| `MODEL_PRIMARY` | No | Override the primary (fast) model. Defaults: `gemini-2.5-flash` · `openai/gpt-4o-mini` · `anthropic/claude-3-5-haiku-20241022` |
| `MODEL_THINKING` | No | Override the thinking (reasoning) model. Defaults: `gemini-2.5-pro-preview-03-25` · `openai/gpt-4o` · `anthropic/claude-3-5-sonnet-20241022` |

#### Debug

| Variable | Required | Description |
|---|---|---|
| `FROSTY_DEBUG` | No | Set to `1` to print agent thinking, tool calls, and payloads |

#### Example `.env`

```env
# --- Snowflake ---
SNOWFLAKE_USER_NAME=john.doe
SNOWFLAKE_USER_PASSWORD=your_password
SNOWFLAKE_ACCOUNT_IDENTIFIER=xy12345.us-east-1

# SNOWFLAKE_AUTHENTICATOR=username_password_mfa   # uncomment for DUO/TOTP MFA
# SNOWFLAKE_ROLE=SYSADMIN
# SNOWFLAKE_WAREHOUSE=COMPUTE_WH
# SNOWFLAKE_DATABASE=MY_DB

# --- App identity ---
APP_USER_NAME=John Doe
APP_USER_ID=user_001
APP_NAME=frosty

# --- Model provider (default: Google Gemini) ---
GOOGLE_API_KEY=your_google_api_key
# MODEL_PROVIDER=openai
# OPENAI_API_KEY=your_openai_api_key
# MODEL_PROVIDER=anthropic
# ANTHROPIC_API_KEY=your_anthropic_api_key
```

### Run

```bash
python -m src.frosty_ai.objagents.main
```

Enable debug output:
```bash
FROSTY_DEBUG=1 python -m src.frosty_ai.objagents.main
```

### Agent Loading & Warm-up

All ~170 specialist agents are loaded **lazily** — nothing is imported at startup. As soon as the session starts, a background thread walks the entire agent tree level by level and imports each level in parallel, so agents warm up progressively while you work.

In practice this means:
- The first time a pillar is invoked in a session it may feel slightly slower while its module loads. The CLI will show: *"Loading {agent} for the first time in this session, may take some time..."*
- Within a couple of minutes all agents are pre-warmed and subsequent calls are instant.

To measure import times, run the included timing script from the project root:
```bash
python time_imports.py
```
Contributions to improve import performance are very welcome.

---

## How It Works

1. **You type** a natural language request in the boxed input (e.g. *"Set up a data pipeline for S3 CSV ingestion"*)
2. **The Manager** classifies intent, reviews existing infrastructure (via INSPECTOR_PILLAR), and produces an execution plan
3. **Pillar agents** receive delegated tasks one at a time and create their own detailed sub-plans
4. **Specialist agents** generate and execute Snowflake DDL via `execute_query`
5. **After every step**, the Manager validates success via `get_session_state` before proceeding
6. **SQL panels** display every executed statement in real time
7. **On exit**, all queries are saved to a `.sql` file

### Key Safety Rules
- `CREATE OR REPLACE` is **forbidden** across all agents — only `CREATE IF NOT EXISTS` or `ALTER` are used
- No parallel execution — one object created at a time, in dependency order
- Every creation is verified against `app:TASKS_PERFORMED` before the plan advances
- **`execute_query` tool callback** — a before-tool callback intercepts every query before it reaches Snowflake and blocks `DROP` and `CREATE OR REPLACE` statements outright, regardless of what any agent instructs

The callback in `tools.py` is the single enforcement point for query safety. You can extend it to block any additional patterns your environment requires — for example, preventing writes to specific databases, blocking `TRUNCATE`, or restricting execution to a particular warehouse:

```python
# tools.py — extend the before_tool_callback to add your own rules
def before_tool_callback(query: str) -> str | None:
    forbidden = ["DROP ", "CREATE OR REPLACE"]
    # add your own patterns here:
    # forbidden += ["TRUNCATE ", "DELETE FROM prod."]
    for pattern in forbidden:
        if pattern.upper() in query.upper():
            raise ValueError(f"Query blocked by safety callback: {pattern}")
```

---

## Project Structure

```
frosty/
├── src/
│   ├── agent.py                          # Root agent export (for ADK web)
│   ├── frosty_ai/
│   │   ├── adkrunner.py                  # ADK Runner wrapper
│   │   ├── adksession.py                 # Session management
│   │   ├── adkstate.py                   # State management (user:/app:/temp:)
│   │   └── objagents/
│   │       ├── agent.py                  # Root agent (CLOUD_DATA_ARCHITECT)
│   │       ├── main.py                   # CLI entry point & REPL loop
│   │       ├── prompt.py                 # Manager instructions
│   │       ├── tools.py                  # execute_query, get_session_state, etc.
│   │       ├── config.py                 # Model configuration
│   │       ├── _spinner.py               # Animated terminal spinner
│   │       └── sub_agents/
│   │           ├── administrator/        # 19 admin specialists
│   │           ├── dataengineer/         # 35 data engineering specialists
│   │           ├── governance/           # 8 governance specialists
│   │           ├── securityengineer/     # 14 security specialists
│   │           ├── inspector/            # 54 read-only inspection specialists
│   │           ├── accountmonitor/       # 25 ACCOUNT_USAGE monitoring specialists
│   │           └── research/             # Research & web search agent
│   └── infschema/                        # Snowflake information schema helpers
├── requirements.txt
└── Makefile
```

---

## Enterprise

For enterprise features and managed hosting visit [thegyrus.com](https://www.thegyrus.com).

---

## License

© 2025 Gyrus Inc — [www.thegyrus.com](https://www.thegyrus.com)
