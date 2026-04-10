<div align="center">

```
███████╗██████╗  ██████╗ ███████╗████████╗██╗   ██╗
██╔════╝██╔══██╗██╔═══██╗██╔════╝╚══██╔══╝╚██╗ ██╔╝
█████╗  ██████╔╝██║   ██║███████╗   ██║    ╚████╔╝
██╔══╝  ██╔══██╗██║   ██║╚════██║   ██║     ╚██╔╝
██║     ██║  ██║╚██████╔╝███████║   ██║      ██║
╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝      ╚═╝
                    ╰─ by Gyrus Inc ─╯
```

**An open-source, self-hosted agentic framework that turns plain English into Snowflake operations.**

[![License](https://img.shields.io/badge/license-©%202025%20Gyrus%20Inc-blue)](#license)
[![Python](https://img.shields.io/badge/python-3.11.10-blue?logo=python)](https://www.python.org/)
[![Models](https://img.shields.io/badge/models-Claude%20%7C%20Gemini%20%7C%20OpenAI-green)](#model-provider)
[![Agents](https://img.shields.io/badge/agents-153%20specialists-orange)](#architecture)
[![Snowflake](https://img.shields.io/badge/built%20for-Snowflake-29B5E8?logo=snowflake)](https://www.snowflake.com/)

[**Quick Start**](#quick-start) · [**Features**](#spotlight-features) · [**Architecture**](#architecture) · [**Setup**](#setup) · [**Safety**](#safety) · [**Contributing**](#contributing) · [**Discord**](https://discord.gg/GpgVzJ6ku) · [**Get in Touch**](#get-in-touch)

If you find Frosty useful, please consider giving it a ⭐ — it helps others discover the project!

</div>

---

## What is Frosty?

Frosty is a **153-agent system** built by [Gyrus Inc](https://www.thegyrus.com) that lets you manage your entire Snowflake environment in plain English — from querying data to administering security policies.
Learn more at https://www.thegyrus.com

```
"who are my top 10 customers by revenue last quarter?"
  → Returns a Markdown table, powered by live SQL

"set up MFA for all users without it"
  → Generates and runs the ALTER statements, with your approval

"why is my warehouse spend up 40% this month?"
  → Queries ACCOUNT_USAGE and gives you an itemized breakdown
```

Unlike other AI tooling for Snowflake, **you host it, you own it, and you pay nothing beyond your LLM tokens** — no additional SaaS platform, no per-seat fees, no extra subscriptions.

<img width="1469" height="265" alt="image" src="https://github.com/user-attachments/assets/38e3aa56-65ab-4ef0-adb9-72af683f9625" />


---

## Why Frosty?

Building a real-time ingestion pipeline with 100 Snowflake objects — tables, streams, tasks, stages, roles, and policies — is a significant engineering undertaking. Frosty compresses that effort from weeks to under an hour.

Beyond building infrastructure, Frosty helps you get the most out of Snowflake across the full lifecycle:
- **Security hardening** (password policies, network rules, MFA enforcement) — so your environment is production-ready from day one
- **Cost governance** (warehouse sizing, credit monitoring, spend alerts) — so you have full visibility and control over your Snowflake spend as you scale
- **Data governance** (tagging, masking policies, row-level access) — so the right people see the right data, with full audit trails

All from natural language, in minutes.

| | |
|---|---|
| 🏠 **Self-hosted** | Agents run in your environment. Credentials never leave your machine. Every line of logic is readable and modifiable. |
| 🔁 **Bring your own model** | Works with OpenAI, Anthropic Claude, and Google Gemini out of the box. Swap in a single `.env` line — no code changes. |
| 🎯 **Purpose-built for Snowflake** | 153 specialist agents cover the full surface area: data engineering, administration, security, governance, cost monitoring, and read-only inspection. |
| 🛡️ **Safe by design** | `DROP` is unconditionally blocked in code. `CREATE OR REPLACE` requires explicit terminal approval. No parallel execution — one object at a time, in dependency order. |
| 🔍 **Context-aware** | The INSPECTOR_PILLAR (56 read-only agents) maps your live environment before any plan is executed — no assumptions, no hallucinated object names. |
| 💬 **Natural language all the way** | Query data, profile tables, generate synthetic rows, build Streamlit dashboards, and inspect costs — all from plain English. |

> Want to see it in action? [Schedule a demo →](mailto:priyank@thegyrus.com)
>
> ##### Example Snapshot of Insepctor Pillar
> <img width="1469" height="456" alt="image" src="https://github.com/user-attachments/assets/d3af4740-9092-43ef-9b0b-c8e5fd567cad" />


---

## Quick Start

```bash
git clone https://github.com/MalviyaPriyank/frosty.git
cd frosty
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, fill in your Snowflake credentials and model API key (see [Configure](#configure)), then:

```bash
python -m src.frosty_ai.objagents.main
```

> Full setup details — MFA, model providers, observability — are in [Setup](#setup) below.

---

## Safety

Frosty enforces two independent safeguards before any query reaches Snowflake.

### Layer 1 — Agent instructions (prompt-level)

Every agent prefers `CREATE IF NOT EXISTS` or `ALTER` over `CREATE OR REPLACE`. `DROP` is forbidden outright. Agents may generate `CREATE OR REPLACE` only when explicitly requested or when no alternative exists — and even then, execution gates it with a human approval prompt.

### Layer 2 — `execute_query` safety gate (code-level)

A hard-coded check in `tools.py` intercepts every call before it reaches Snowflake:

- **`DROP`** — blocked unconditionally. No prompt, no override.
- **`CREATE OR REPLACE`** — execution pauses. The full statement is shown in a red panel; you type `yes` or `no` to proceed or abort.

```
User request
     │
     ▼
Agent generates SQL
     │
     ▼  execute_query safety gate (tools.py)
     │   ├─ contains "DROP"?              → hard blocked, never reaches Snowflake
     │   ├─ contains "CREATE OR REPLACE"? → paused, user approval prompt shown
     │   │       ├─ user types "yes"      → passed through
     │   │       └─ user types "no"       → blocked, agent tries alternative
     │   └─ clean                         → passed through
     │
     ▼
execute_query() → Snowflake
```

Because Layer 2 is **code, not a prompt**, it cannot be bypassed by prompt injection or model drift.

You can extend the gate in `tools.py` to block any additional patterns your environment requires:

```python
# Add to the hard-block section (alongside DROP):
_hard_blocked = ["DROP ", "TRUNCATE ", "DELETE FROM prod."]
for pattern in _hard_blocked:
    if pattern.upper() in query.upper():
        return {"success": False, "query": query,
                "message": f"Query blocked: '{pattern.strip()}' is not permitted."}
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    CLI  (Rich + prompt_toolkit)                  │
└────────────────────────────────┬─────────────────────────────────┘
                                 │ user message
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│               CLOUD_DATA_ARCHITECT  (Manager)                    │
│   Classifies intent · produces execution plan · delegates        │
│   one task at a time · validates every step via state            │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┬───┘
       ▼          ▼          ▼          ▼          ▼          ▼
  DATA        ADMIN     SECURITY  GOVERNANCE  INSPECTOR  ACCOUNT
  ENGINEER              ENGINEER              PILLAR     MONITOR
  34 spec    16 spec    14 spec    8 spec     56 spec    25 spec
       └──────────┴──────────┴──────────┴──────────┴──────────┘
                                 │
                                 ▼
                          execute_query()  ──►  Snowflake
                                                    │
                                                    ▼
                                        app:TASKS_PERFORMED
                                (each completed task appended to state)
```

### Agent Pillars

| Pillar | Role | Specialists |
|---|---|---|
| **CLOUD_DATA_ARCHITECT** | Manager — plans, routes, validates | — |
| **DATA_ENGINEER** | Physical data layer orchestrator | 34 |
| **ADMINISTRATOR** | Identity, compute, RBAC | 16 |
| **SECURITY_ENGINEER** | Network & auth security | 14 |
| **GOVERNANCE_SPECIALIST** | Tags, policies, data access | 8 |
| **INSPECTOR_PILLAR** | Read-only infrastructure inspection | 56 |
| **ACCOUNT_MONITOR** | Cost, billing, audit & operational health | 25 |
| **RESEARCH_AGENT** | Web search & knowledge cache — shared fallback | — |

### How It Works

1. **You type** a natural language request (e.g. *"Set up a data pipeline for S3 CSV ingestion"*)
2. **The Manager** classifies intent, inspects your live infrastructure via the INSPECTOR_PILLAR, and produces an execution plan
3. **Pillar agents** receive delegated tasks one at a time and produce their own detailed sub-plans
4. **Specialist agents** generate and execute Snowflake DDL via `execute_query`
5. **After every step**, the Manager validates success via `get_session_state` before proceeding
6. **SQL panels** display every executed statement in real time
7. **On exit**, all queries are saved to a `.sql` file

---

## Spotlight Features

### 🔍 Natural Language Data Queries

Ask questions about your Snowflake data in plain English and get SQL-powered answers — no SQL knowledge required.

```
"how many orders did we get last month?"
"show me the top 10 customers by revenue"
"what's the average order value by region?"
```

The `DATA_ANALYST` specialist discovers your schema, generates accurate Snowflake SQL from full column context, enforces a **read-only safety gate** (rejects any non-SELECT statement), and returns a plain-English answer with Markdown tables.

Trigger phrases: *"how many"*, *"show me"*, *"top N"*, *"compare"*, *"query my data"*, *"what's the revenue"*

#### Business Rules — Make Queries Smarter

By default the analyst infers SQL purely from schema metadata. Add **business rules** to make it significantly more accurate — metric definitions, canonical date columns, standard filters, and join keys specific to your data model.

Generate a first draft automatically:

```
"generate my business rules draft for MY_DB.SALES"
```

This inspects your `INFORMATION_SCHEMA`, identifies metric candidates, date columns, enum candidates, and join keys, then writes a draft to `skills/snowflake-data-analyst/references/business-rules.md`. Open it, fill in your real definitions:

```markdown
## Metric Definitions
- **Revenue**: SUM(ORDER_VALUE) WHERE STATUS IN ('COMPLETED', 'SHIPPED')
- **Active customers**: COUNT(DISTINCT CUSTOMER_ID) WHERE LAST_ORDER_DATE >= DATEADD('day', -90, CURRENT_DATE())

## Canonical Date Columns
- ORDERS: use ORDER_DATE (not CREATED_AT or UPDATED_AT)

## Standard Filters
- ORDERS: always exclude test orders — WHERE IS_TEST = FALSE

## Common Table Joins
- ORDERS → CUSTOMERS: JOIN ON ORDERS.CUSTOMER_ID = CUSTOMERS.ID
```

Ask *"what was last month's revenue?"* and Frosty uses your exact metric definition — not a raw column sum.

---

### 📊 Data Profiling

Get a comprehensive statistical report on any table in seconds — no SQL required.

```
"profile the ORDERS table in MY_DB.SALES"
```

The `DATA_PROFILER` runs a **single SQL pass** across all columns (not one query per column), keeping credit usage minimal even on wide tables. Output is a 4-section Markdown report covering table summary, column profiles, value distributions, and data quality flags.

| Flag | Condition |
|---|---|
| ⚠️ High null rate | `null_pct > 20%` |
| ⚠️ All-null column | `null_pct = 100%` |
| ⚠️ Constant column | `distinct_count = 1` |
| ℹ️ High-cardinality ID | `distinct ≈ total_rows` |

Trigger phrases: *"profile"*, *"check data quality"*, *"show null rates"*, *"analyze distribution"*, *"explore table"*

---

### 🧪 Stored Procedure Validation

Frosty never writes a stored procedure directly. Every new or updated procedure goes through a mandatory two-step flow.

**Step 1 — Validation (dry run, always rolled back)**

The procedure is created under a unique throwaway name, called with sample args inside a transaction, then **always rolled back** — pass or fail. Nothing persists in Snowflake. Syntax errors and runtime failures are caught here before the real procedure is touched.

**Step 2 — Real creation**

Only after validation passes does `execute_query` run the actual statement. If `CREATE OR REPLACE` is needed, the standard approval prompt fires before execution.

If validation fails 5 consecutive times, the `RESEARCH_AGENT` is automatically invoked to look up the latest Snowflake SQL docs from the web (with session caching to avoid duplicate fetches), then retries with fresh knowledge. If it still cannot produce a valid procedure after research-backed retries, it stops and reports clearly for manual review.

---

### 🧬 Synthetic Data Generation

Populate any table with realistic sample data — Frosty inspects the table structure first and generates contextually appropriate values.

```
"populate ORDERS table with 10 rows"
```

`DESCRIBE TABLE` is the single source of truth — column names are never invented. Values are domain-aware: `EMAIL` columns get valid email addresses, `STATUS` columns get enum-appropriate values, `VARIANT` columns get minimal valid JSON.

---

### 🌐 Web Search & Research Agent

Specialist agents follow a two-step knowledge hierarchy before generating any DDL or query.

**Step 1 — SKILL.md reference** (when `USE_SKILLS=true`, the default)
Each specialist has a curated reference doc covering every supported parameter, its default value, and when to use it — producing accurate, non-bloated DDL without hallucinating unsupported syntax.

**Step 2 — RESEARCH_AGENT fallback**
If the specialist cannot resolve something from its reference docs, it delegates to the RESEARCH_AGENT for live web lookup. Results are persisted to `app:RESEARCH_RESULTS` in session state — the same answer is never fetched twice within a session.

```
  Gemini models  →  google_search (built-in grounding)
  All others     →  DuckDuckGo · top 5 results (configurable in research/tools.py)
```

##### Example Snapshot of web search 
<img width="1437" height="799" alt="image" src="https://github.com/user-attachments/assets/c4c29858-4257-413f-92e6-0a5e7ad0208e" />


---

### 🤔 Thinking & Reasoning (Gemini only)

When using Gemini models, every agent uses `ThinkingConfig` to reason silently before responding — improving decision quality for complex DDL and multi-step plans without surfacing the thinking to the user.

| Agent level | Thinking budget |
|---|---|
| Manager + pillar agents | 1,024 tokens |
| Specialist agents | 512 tokens |
| Streamlit pipeline sub-agents | 256 tokens |

---

### 🖥️ Streamlit App Generation (Gemini only)

The Streamlit pipeline uses ADK's `BuiltInCodeExecutor` to validate generated Python code in a sandbox before returning it. Syntax errors and import failures are caught before any deployment step.

> **Note:** `BuiltInCodeExecutor` is Gemini-native and cannot be combined with other tools. With OpenAI or Anthropic models this pipeline is non-functional. To support other providers, replace it in `streamlit/code_generator/agent.py` with a custom `CodeExecutor` (e.g. a subprocess or Docker runner).

---

### 💾 Chat History & Persistent Sessions

By default Frosty uses ADK's `InMemorySessionService` — full conversation context is held in memory for the session and lost on exit.

**Persist session history** — swap to `DatabaseSessionService` in `adksession.py`:

```python
from google.adk.sessions import DatabaseSessionService
session_service = DatabaseSessionService(db_url="sqlite:///frosty_sessions.db")
# or: db_url="postgresql://user:pass@host/dbname"
```

**Add long-term memory** — plug in a `memory_service` in `adkrunner.py` to offload conversation summaries to an external store, freeing the context window for the current task:

```python
from google.adk.memory import VertexAiMemoryBankService
runner = ADKRunner(
    agent=agent,
    app_name=app_name,
    session_service=session_service,
    memory_service=VertexAiMemoryBankService(...),
)
```

Any class implementing ADK's `BaseMemoryService` works — PostgreSQL, Redis, a vector database, or any other backend.

---

## Snowflake Objects Supported

<details>
<summary><strong>Data Engineering — 34 object types</strong></summary>

Databases · Schemas · Tables · Views · Materialized Views · Semantic Views · External Tables · Hybrid Tables · Iceberg Tables · Dynamic Tables · File Formats · External Stages · Internal Stages · External Volumes · Streams · Tasks · Stored Procedures · User-Defined Functions · External Functions · Sequences · Cortex Search · Snowpipe · COPY INTO · Event Tables · Storage Lifecycle Policies · Snapshots · Snapshot Policies · Snapshot Sets · Streamlit Apps · Models · Datasets · Data Metric Functions · Notebooks · Sample Data

</details>

<details>
<summary><strong>Administration — 16 object types</strong></summary>

Users · Roles · Database Roles · Warehouses · Compute Pools · Resource Monitors · Notification Integrations (Email, Azure Event Grid, Google Pub/Sub, Webhook) · Failover Groups · Replication Groups · Organization Profiles · Connections · Application Packages · Image Repositories · Services · Provisioned Throughput · Alerts

</details>

<details>
<summary><strong>Security — 14 object types</strong></summary>

Authentication Policies · Password Policies · Network Rules · Network Policies · Security Integrations (External API Auth, AWS IAM, External OAuth) · API Integrations (Amazon API Gateway) · External Access Integrations · Session Policies · Packages Policies · Secrets · Aggregation Policies · Join Policies

</details>

<details>
<summary><strong>Governance — 8 object types</strong></summary>

Tags · Contacts · Masking Policies · Privacy Policies · Projection Policies · Row Access Policies · Data Exchanges · Listings

</details>

<details>
<summary><strong>Account Monitoring — 25 views across 6 domains</strong></summary>

**Query & Access** — Access History · Copy History · Load History · Login History · Query History  
**Warehouse & Compute** — Automatic Clustering · Data Transfer History · Metering Daily History · Warehouse Events History · Warehouse Metering History  
**Task Automation** — Alert History · Materialized View Refresh · Serverless Task History · Task History  
**Storage** — Pipes · Stages · Storage Usage · Table Storage Metrics  
**Security & Identity** — Grants to Roles · Grants to Users · Roles · Sessions · Users  
**Infrastructure** — Databases · Schemata

</details>

---

## Setup

### Prerequisites

- Python 3.11.10
- A Snowflake account 
- An API key for your chosen model provider

### Install

```bash
git clone https://github.com/MalviyaPriyank/frosty.git
cd frosty
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

Create a `.env` file in the project root by copying the provided template:

```bash
cp .env.example .env
```

Then fill in your values — refer to `.env.example` for all available variables and their descriptions.

#### Snowflake Connection

| Variable | Required | Description |
|---|---|---|
| `SNOWFLAKE_USER_NAME` | **Yes** | Your Snowflake login username |
| `SNOWFLAKE_USER_PASSWORD` | **Yes** | Your Snowflake password |
| `SNOWFLAKE_ACCOUNT_IDENTIFIER` | **Yes** | Account identifier (e.g. `xy12345.us-east-1`) |
| `SNOWFLAKE_AUTHENTICATOR` | No | Auth method — see MFA section below |
| `SNOWFLAKE_ROLE` | No | Default role (e.g. `SYSADMIN`); uses account default if unset |
| `SNOWFLAKE_WAREHOUSE` | No | Default warehouse; uses account default if unset |
| `SNOWFLAKE_DATABASE` | No | Default database context; uses account default if unset |

#### MFA & Session Caching

Set `SNOWFLAKE_AUTHENTICATOR=username_password_mfa` to enable Snowflake's MFA flow.

- **DUO Push** — Snowflake sends a push notification on the first query. Approve it in the DUO app; the CLI resumes automatically.
- **TOTP** — The CLI pauses and displays a `TOTP passcode:` prompt (hidden input). Enter the code from your authenticator app and press Enter.

<img width="712" height="125" alt="image" src="https://github.com/user-attachments/assets/2a665795-8d8e-4923-8389-425deb6b7f15" />


Frosty maintains a process-level session cache. Before every tool call the cached session is validated with `SELECT 1` — if Snowflake has closed the connection, a fresh session is opened automatically.

| Authenticator value | When to use |
|---|---|
| *(unset)* | Standard username + password |
| `username_password_mfa` | DUO push or TOTP |
| `externalbrowser` | SSO / Okta — opens a browser tab (**untested**, requires SAML IdP configured in Snowflake) |

#### Application Identity

| Variable | Required | Description |
|---|---|---|
| `APP_USER_NAME` | **Yes** | Display name shown in the session (e.g. your name) |
| `APP_USER_ID` | **Yes** | Unique user ID for session tracking (e.g. `user_001`) |
| `APP_NAME` | **Yes** | Application name for session scoping (e.g. `frosty`) |

#### Model Provider

| Variable | Required | Description |
|---|---|---|
| `MODEL_PROVIDER` | No | `google` (default) · `openai` · `anthropic` · `ollama` |
| `GOOGLE_API_KEY` | If `google` | API key for Gemini models |
| `OPENAI_API_KEY` | If `openai` | API key for OpenAI models |
| `ANTHROPIC_API_KEY` | If `anthropic` | API key for Claude models |
| `MODEL_PRIMARY` | No | Override the fast model. Defaults: `gemini-2.5-flash` · `gpt-4o-mini` · `claude-3-5-haiku-20241022` |
| `MODEL_THINKING` | No | Override the reasoning model. Defaults: `gemini-2.5-pro-preview-03-25` · `gpt-4o` · `claude-3-5-sonnet-20241022` |
| `OLLAMA_API_BASE` | If `ollama` | Ollama host URL (default: `http://localhost:11434`) |

Frosty supports **OpenAI**, **Claude**, **Gemini**, and **Ollama** out of the box. Any model supported by Google ADK can also be used — see the [ADK Models documentation](https://google.github.io/adk-docs/agents/models/).

#### Moltbook

| Variable | Required | Description |
|---|---|---|
| `MOLTBOOK_API_KEY` | No | API key for your agent's [Moltbook](https://moltbook.com) profile — allows your Frosty instance to interact with other agents in the ecosystem |

#### Debug & Feature Flags

| Variable | Default | Description |
|---|---|---|
| `FROSTY_DEBUG` | `0` | Set to `1` to print agent thinking, tool calls, and payloads |
| `USE_SKILLS` | `true` | Agents consult SKILL.md reference docs before generating DDL. Set `false` to rely on model knowledge only (fewer tokens, slightly faster) |

#### Observability (OpenTelemetry + Grafana Cloud)

Built-in OpenTelemetry instrumentation — **off by default**, zero overhead when disabled. Set `OTEL_ENABLED=true` to export to any OTLP-compatible backend (Grafana Cloud, Tempo, Jaeger, etc.).

| Signal | What is captured |
|---|---|
| **Traces** | Root span per user request; span per agent model call; span per Snowflake query (with `db.statement`, `db.user`, `db.rows_returned`) |
| **Metrics** | `frosty.queries.total`, `frosty.queries.errors`, `frosty.agent.invocations`, `frosty.query.duration_ms` |
| **Logs** | All Python loggers bridged to the OTLP log exporter |

| Variable | Required | Description |
|---|---|---|
| `OTEL_ENABLED` | No | `true` to enable, `false` to disable (default) |
| `OTEL_SERVICE_NAME` | No | Service name in Grafana (default: `frosty`) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | If enabled | Your OTLP gateway URL |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | No | `http/protobuf` (required for Grafana Cloud) |
| `OTEL_EXPORTER_OTLP_HEADERS` | If enabled | Auth header — use `Basic%20` instead of `Basic ` for Python |

**Grafana Cloud setup:**
1. Go to your stack → **Details** → **OpenTelemetry**
2. Generate a token with `metrics:write`, `logs:write`, `traces:write` scopes
3. Copy the endpoint URL and `Authorization=Basic%20<token>` header value

**Viewing data:**
```
Traces  → Explore → Tempo       → Service name: frosty_open_source
Metrics → Explore → Prometheus  → search "frosty_"
Logs    → Explore → Loki        → Label: service_name = frosty_open_source
```

> Metrics are exported on a 60-second interval. Use `exit` (not Ctrl+C) to trigger a graceful flush of buffered spans.

![Frosty trace waterfall in Grafana Tempo](docs/images/grafana_trace_waterfall.png)

#### Example `.env`

```env
# --- Snowflake ---
SNOWFLAKE_USER_NAME=john.doe
SNOWFLAKE_USER_PASSWORD=your_password
SNOWFLAKE_ACCOUNT_IDENTIFIER=xy12345.us-east-1

# SNOWFLAKE_AUTHENTICATOR=username_password_mfa   # uncomment for DUO/TOTP
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
# MODEL_PROVIDER=ollama
# OLLAMA_API_BASE=http://localhost:11434
# MODEL_PRIMARY=ollama/gemma4:e2b

# --- Observability / Grafana Cloud (optional) ---
# OTEL_ENABLED=true
# OTEL_SERVICE_NAME=frosty_open_source
# OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-us-east-3.grafana.net/otlp
# OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
# OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20<your-base64-token>
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

All 153 specialist agents load **lazily** — nothing is imported at startup. A background thread walks the agent tree level by level and imports each level in parallel, so agents warm up progressively while you work.

The first time a pillar is invoked in a session it may feel slightly slower; the CLI will show: *"Loading {agent} for the first time in this session..."* Within a couple of minutes all agents are pre-warmed and subsequent calls are instant.

Measure import times from the project root:
```bash
python time_imports.py
```

---

## CLI Features

| Feature | Description |
|---|---|
| **Boxed input** | `prompt_toolkit` framed text input with cyan border |
| **Animated spinner** | Braille frames tracking the active agent |
| **Response panels** | Markdown-rendered AI responses in blue panels |
| **SQL panels** | Syntax-highlighted executed queries in green panels (monokai theme) |
| **Question panels** | Clarifying questions surfaced in yellow panels |
| **Object counter** | Live terminal title + inline `[● Objects created: N]` counter |
| **Session export** | All executed SQL written to `queries/session_<timestamp>.sql` on exit |
| **Debug mode** | `FROSTY_DEBUG=1` to print agent thinking, tool calls, and payloads |

---

## Project Structure

```
frosty/
├── src/
│   ├── agent.py                          # Root agent export (for ADK web)
│   └── frosty_ai/
│       ├── adkrunner.py                  # ADK Runner wrapper
│       ├── adksession.py                 # Session management
│       ├── adkstate.py                   # State management (user:/app:/temp:)
│       ├── telemetry.py                  # OpenTelemetry setup — opt-in via OTEL_ENABLED
│       └── objagents/
│           ├── agent.py                  # Root agent (CLOUD_DATA_ARCHITECT)
│           ├── main.py                   # CLI entry point & REPL loop
│           ├── prompt.py                 # Manager instructions
│           ├── tools.py                  # execute_query, get_session_state, etc.
│           ├── config.py                 # Model configuration
│           ├── _spinner.py               # Animated terminal spinner
│           └── sub_agents/
│               ├── administrator/        # 16 admin specialists
│               ├── dataengineer/         # 34 data engineering specialists
│               ├── governance/           # 8 governance specialists
│               ├── securityengineer/     # 14 security specialists
│               ├── inspector/            # 56 read-only inspection specialists
│               ├── accountmonitor/       # 25 ACCOUNT_USAGE monitoring specialists
│               └── research/             # Research & web search agent
└── infschema/                            # Snowflake information schema helpers
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Framework | Google ADK 1.18+; OpenAI, Claude, Gemini (2.5 Flash / 2.5 Pro) + [more](https://google.github.io/adk-docs/agents/models/) |
| Snowflake | snowflake-snowpark-python, snowflake-connector-python |
| Terminal UI | Rich 13+, prompt_toolkit 3+ |
| Validation | Pydantic 2.5+ |
| Utilities | croniter, python-dateutil, GitPython |
| Observability | OpenTelemetry SDK + OTLP HTTP exporter; Grafana Cloud (Tempo · Mimir · Loki) |

---

## Community

Join our [Discord](https://discord.gg/GpgVzJ6ku) to ask questions, share what you've built, and connect with other Frosty users.

FrostyAI is on [Moltbook](https://www.moltbook.com) — the social network for AI agents.

- **Profile:** [moltbook.com/u/frostyai](https://www.moltbook.com/u/frostyai)
- **Snowflake community:** [moltbook.com/m/snowflakedb](https://www.moltbook.com/m/snowflakedb) — open to anyone working with Snowflake

Frosty can interact with Moltbook directly from the CLI. Set `MOLTBOOK_API_KEY` in your `.env` to enable:

| Prompt | What happens |
|---|---|
| `"Post to Moltbook about the table I just created"` | Creates a post in m/snowflakedb |
| `"Check Moltbook and reply to any comments on my posts"` | Reads home dashboard, fetches comments, replies |
| `"What's trending on Moltbook?"` | Fetches the hot feed |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for a guide on adding specialist agents, new pillars, custom safety rules, ADK Skills, and extending Frosty with other ADK capabilities. A sample `snowflake-naming-conventions` skill is included in `skills/` as a starting point.

---

## Build Your Own Frosty

Frosty is designed to be extended. Fork it, specialize it for your domain — retail, finance, healthcare, logistics — and give your agent a social identity on **[Moltbook](https://moltbook.com)**, the social network for AI agents, where it can discover and interact with other agents in the ecosystem.

Whether it's a finance-focused Snowflake bot, a security-hardening specialist, or a fully custom data platform agent — the architecture is yours to build on.

If you build on Frosty, we'd love it if your agent tags **[#Frosty](https://moltbook.com/u/frostyai)** on its Moltbook profile — it helps the community find and connect with agents in the Frosty ecosystem.

Share what you build: [priyank@thegyrus.com](mailto:priyank@thegyrus.com)

---

## Enterprise

For enterprise features and managed hosting — including persistent sessions and long-term memory out of the box — visit [thegyrus.com](https://www.thegyrus.com) or [get in touch](#get-in-touch).

---

## Get in Touch

Interested in a demo, want to discuss your Snowflake setup, or just have questions?

- 📧 General enquiries: [info@thegyrus.com](mailto:info@thegyrus.com)
- 📧 Priyank (co-founder): [priyank@thegyrus.com](mailto:priyank@thegyrus.com)
- 📅 Book a call: [Schedule time with Priyank](https://calendar.app.google/LtgREjn9kx1zNqn1A)

---

## License

© 2025 Gyrus Inc — [www.thegyrus.com](https://www.thegyrus.com)
