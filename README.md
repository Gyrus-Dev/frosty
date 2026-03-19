# Frosty AI

**Frosty** is an AI-powered Snowflake management CLI built by [Gyrus Inc](https://www.thegyrus.com). It uses a multi-agent hierarchy powered by Google ADK to plan, execute, and validate Snowflake DDL operations through natural language — directly from your terminal.

Frosty supports **OpenAI**, **Claude**, and **Gemini** models out of the box. Any other model that Google ADK supports can also be used — refer to the [Google ADK Models documentation](https://google.github.io/adk-docs/agents/models/) for the full list.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLI  (Rich + prompt_toolkit)                 │
│   FROSTY banner  ·  boxed input  ·  spinner  ·  SQL/response panels │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ user message
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CLOUD_DATA_ARCHITECT  (Manager)                  │
│  Strategic planner — classifies intent, produces execution plan,    │
│  delegates one task at a time, validates every step via state       │
└───┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┘
    │          │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌──────┐ ┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  DATA  │ │ADMIN │ │SECURITY│ │GOVERNANCE│ │INSPECTOR │ │ACCOUNT   │
│ENGINEER│ │      │ │ENGINEER│ │          │ │ PILLAR   │ │MONITOR   │
└───┬────┘ └──┬───┘ └───┬────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
    │         │         │           │             │             │
    ▼         ▼         ▼           ▼             ▼             ▼
 35 specialists  19 specialists  14 specialists  8 specialists  54 specialists  25 specialists
 (see below)     (see below)     (see below)     (see below)    (see below)     (see below)
    │
    ▼
 execute_query()  ──►  Snowflake (Snowpark)
                           │
                           ▼
                    app:TASKS_PERFORMED  ◄──  get_session_state()
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
| **RESEARCH_AGENT** | Web search & knowledge cache | — |

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

Create a `.env` file in the project root. Set the API key for your chosen model provider:

```env
# Google Gemini (default)
GOOGLE_API_KEY=your_google_api_key

# OpenAI (if using OpenAI models)
# OPENAI_API_KEY=your_openai_api_key

# Anthropic Claude (if using Claude models)
# ANTHROPIC_API_KEY=your_anthropic_api_key

SNOWFLAKE_ACCOUNT=your_account_identifier
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
```

### Run

```bash
python -m src.frosty_ai.objagents.main
```

Enable debug output:
```bash
FROSTY_DEBUG=1 python -m src.frosty_ai.objagents.main
```

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

## License

© 2025 Gyrus Inc — [www.thegyrus.com](https://www.thegyrus.com)