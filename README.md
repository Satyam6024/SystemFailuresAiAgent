# System Failures AI Agent

An autonomous **AI First Responder** that diagnoses complex system failures in real-time using multi-agent reasoning. When a production alert fires, four specialized AI agents investigate logs, metrics, and deployments in parallel — then collaborate to identify the root cause, generate an RCA report, and trigger automated remediation.

## How It Works

```
Alert Fires ──> Commander creates investigation plan
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   Logs Agent   Metrics Agent  Deploy Agent
   (forensics)  (telemetry)    (history)
        └───────────┼───────────┘
                    ▼
            Commander synthesizes
            findings & determines
               root cause
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
    High Confidence      Low Confidence
    → Auto Rollback      → Report Only
          └─────────┬─────────┘
                    ▼
             RCA Report
          (Markdown + PDF)
```

### The Four Agents

| Agent | Role | What It Analyzes |
|-------|------|-----------------|
| **Commander** | Orchestrator | Creates investigation plan, synthesizes findings, makes decisions |
| **Logs Agent** | Forensic Expert | Application logs, stack traces, error correlations |
| **Metrics Agent** | Telemetry Analyst | CPU, memory, latency (p99), error rates, connection pools |
| **Deploy Agent** | Historian | CI/CD deployments, config changes, timing correlations |

### Demo Scenario: Latent Configuration Bug

1. **Trigger**: Checkout service p99 latency spikes to 2000ms
2. **Investigation**: Agents discover DB connection timeout errors correlated with a config deployment 15 minutes prior that reduced the connection pool from 100 to 10
3. **Outcome**: Full RCA report generated + automatic rollback triggered via GitHub Actions

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Groq API (`llama-3.3-70b-versatile`) |
| Agent Orchestration | LangGraph (parallel fan-out/fan-in) |
| API | FastAPI + async SQLAlchemy |
| Database | SQLite (local) / PostgreSQL (Docker/prod) |
| UI | Streamlit (5 pages, interactive) |
| Reports | Jinja2 templates + xhtml2pdf |
| Remediation | GitHub Actions workflow dispatch |
| Monitoring | Prometheus + Grafana |
| Infrastructure | Docker Compose / AWS ECS Fargate |
| Tests | pytest (147 tests) |

## Project Structure

```
SystemFailuresAiAgent/
├── src/
│   ├── agents/              # AI agent implementations
│   │   ├── commander.py     # Orchestrator (detect, plan, decide, act, report)
│   │   ├── logs_agent.py    # Log forensics agent
│   │   ├── metrics_agent.py # Telemetry analysis agent
│   │   ├── deploy_agent.py  # Deployment history agent
│   │   └── tools.py         # Shared agent tools (log search, metric query, etc.)
│   ├── graph/
│   │   └── investigation.py # LangGraph state machine definition
│   ├── core/
│   │   ├── models.py        # Pydantic data models (Alert, Finding, RCAReport, etc.)
│   │   ├── state.py         # LangGraph state TypedDict with parallel-safe reducers
│   │   ├── config.py        # Settings (pydantic-settings, SFA_ env prefix)
│   │   ├── runner.py        # InvestigationRunner (async lock, one-at-a-time)
│   │   ├── rate_limiter.py  # Token bucket rate limiter for Groq API
│   │   └── logging.py       # Structured logging (structlog)
│   ├── data/
│   │   ├── scenarios.py     # 4 failure scenarios with correlated mock data
│   │   ├── mock_generator.py# MockDataGenerator factory
│   │   └── topology.py      # Service dependency graph (8 microservices)
│   ├── api/
│   │   ├── app.py           # FastAPI application factory
│   │   ├── schemas.py       # Request/response Pydantic schemas
│   │   ├── dependencies.py  # Dependency injection (DB session, runner)
│   │   └── routes/          # REST endpoints (alerts, investigations, reports, metrics)
│   ├── db/
│   │   ├── models.py        # SQLAlchemy ORM model (InvestigationRecord)
│   │   ├── engine.py        # Async engine + session factory
│   │   └── repository.py    # CRUD operations
│   ├── reports/
│   │   ├── generator.py     # Jinja2-based RCA markdown renderer
│   │   ├── pdf_exporter.py  # Markdown → HTML → PDF (xhtml2pdf)
│   │   └── templates/       # Jinja2 template + CSS
│   ├── remediation/
│   │   └── github_actions.py# GitHub Actions rollback trigger
│   └── ui/
│       ├── app.py           # Streamlit main app
│       ├── pages/           # 5 pages (Dashboard, Investigation, History, Config, Live Monitor)
│       └── components/      # Reusable UI components (charts, CoT graph, API client)
├── tests/
│   ├── unit/                # 8 test files — models, config, rate limiter, scenarios, reports, etc.
│   └── integration/         # 3 test files — DB repository, API endpoints, full graph flow
├── docker/
│   ├── api.Dockerfile       # FastAPI image
│   ├── ui.Dockerfile        # Streamlit image
│   ├── prometheus/          # Prometheus scrape config
│   └── grafana/             # Auto-provisioned datasource + dashboard
├── infra/aws/
│   ├── cloudformation.yml   # Full AWS stack (VPC, RDS, ECS Fargate, ALB, ECR)
│   └── deploy.sh            # One-command deployment script
├── .github/workflows/
│   ├── ci-cd.yml            # CI/CD pipeline (test → build → deploy)
│   └── rollback.yml         # Service rollback workflow (triggered by agent)
├── docker-compose.yml       # 6 services: PostgreSQL, API, UI, Prometheus, Grafana, pgAdmin
├── pyproject.toml           # Dependencies, build config, pytest config
└── main.py                  # CLI entry point
```

## Getting Started

### Prerequisites

- **Python 3.13+**
- **uv** package manager — [install uv](https://docs.astral.sh/uv/getting-started/installation/)
- **Groq API key** — [get one free](https://console.groq.com/keys)

### 1. Clone and Install

```bash
git clone https://github.com/Satyam6024/SystemFailuresAiAgent.git
cd SystemFailuresAiAgent
uv sync --extra dev
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
SFA_GROQ_API_KEY=your_groq_api_key_here
```

Optional settings:

```env
SFA_GROQ_MODEL=llama-3.3-70b-versatile
SFA_DATABASE_URL=sqlite+aiosqlite:///./sfa.db
SFA_CONFIDENCE_THRESHOLD_FOR_ACTION=0.7
SFA_GITHUB_TOKEN=ghp_your_token          # For auto-rollback
SFA_GITHUB_ROLLBACK_REPO=user/repo       # For auto-rollback
```

### 3. Run Tests

```bash
uv run pytest tests/ -v
```

All 147 tests should pass.

### 4. Run Locally

Open two terminals:

```bash
# Terminal 1 — API server
uv run uvicorn src.api.app:create_app --factory --port 8000

# Terminal 2 — Streamlit UI
uv run streamlit run src/ui/app.py
```

Open **http://localhost:8501** in your browser.

### 5. Run a Demo

1. Go to the **Investigation** page
2. Select `latent_config_bug` scenario
3. Click **Start Investigation**
4. Watch the agents investigate in real-time (~15-30 seconds)
5. View the root cause analysis, agent findings, and chain-of-thought graph
6. Download the PDF report

## Running with Docker Compose

Spins up 6 services: PostgreSQL, FastAPI API, Streamlit UI, Prometheus, Grafana, and pgAdmin.

```bash
# 1. Create your env file
cp .env.docker .env.docker.local
# Edit .env.docker.local and set SFA_GROQ_API_KEY

# 2. Build and start
docker compose --env-file .env.docker.local up --build
```

| Service | URL | Credentials |
|---------|-----|-------------|
| Streamlit UI | http://localhost:8501 | — |
| FastAPI API | http://localhost:8000 | — |
| API Docs (Swagger) | http://localhost:8000/docs | — |
| Grafana | http://localhost:3000 | admin / admin |
| pgAdmin | http://localhost:5050 | admin@example.com / admin |
| Prometheus | http://localhost:9090 | — |

## Deploying to AWS (ECS Fargate)

The infrastructure is defined as a CloudFormation stack that creates: VPC with public/private subnets, Application Load Balancer, ECS Fargate cluster (API + UI services), RDS PostgreSQL, ECR repositories, Secrets Manager, and CloudWatch logs.

### Prerequisites

- AWS CLI configured with appropriate permissions
- Docker installed

### Option A: One-Command Deploy

```bash
chmod +x infra/aws/deploy.sh
./infra/aws/deploy.sh --stack-name sfa-prod --region us-east-1
```

This script will:
1. Deploy the CloudFormation stack
2. Build Docker images
3. Push to ECR
4. Update ECS services

### Option B: Step-by-Step

```bash
# 1. Deploy the infrastructure
aws cloudformation deploy \
  --template-file infra/aws/cloudformation.yml \
  --stack-name sfa-prod \
  --region us-east-1 \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides EnvironmentName=sfa-prod

# 2. Store your Groq API key
aws secretsmanager put-secret-value \
  --secret-id sfa-prod/groq-api-key \
  --secret-string "your_groq_api_key" \
  --region us-east-1

# 3. Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# 4. Build and push images
docker build -f docker/api.Dockerfile -t <account-id>.dkr.ecr.us-east-1.amazonaws.com/sfa-prod-api:latest .
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/sfa-prod-api:latest

docker build -f docker/ui.Dockerfile -t <account-id>.dkr.ecr.us-east-1.amazonaws.com/sfa-prod-ui:latest .
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/sfa-prod-ui:latest

# 5. Force new ECS deployment
aws ecs update-service --cluster sfa-prod-cluster --service sfa-prod-api --force-new-deployment
aws ecs update-service --cluster sfa-prod-cluster --service sfa-prod-ui --force-new-deployment

# 6. Get the URL
aws cloudformation describe-stacks --stack-name sfa-prod \
  --query "Stacks[0].Outputs[?OutputKey=='ALBURL'].OutputValue" --output text
```

### CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/ci-cd.yml`) automatically:
1. **On every push/PR**: Runs linter + 147 tests
2. **On push to main**: Builds Docker images, pushes to ECR, deploys to ECS

To enable, add the `AWS_ROLE_ARN` secret in your GitHub repo settings (Settings > Secrets > Actions).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/alert` | Trigger a new investigation |
| `GET` | `/api/v1/investigations` | List all investigations |
| `GET` | `/api/v1/investigations/{id}` | Get investigation details |
| `GET` | `/api/v1/investigations/{id}/report` | Get RCA report (markdown) |
| `GET` | `/api/v1/investigations/{id}/report/pdf` | Download RCA report (PDF) |
| `GET` | `/health` | Health check + running status |
| `GET` | `/metrics` | Prometheus metrics |

## Failure Scenarios

| Scenario | Trigger | Root Cause |
|----------|---------|------------|
| `latent_config_bug` | Checkout p99 latency spike | DB pool config reduced from 100 to 10 connections |
| `memory_leak` | Inventory service OOM | Memory leak in inventory-service after code deploy |
| `cascading_failure` | Multi-service errors | PostgreSQL overload cascading to dependent services |
| `traffic_spike` | API gateway rate limiting | Sudden 10x traffic surge overwhelming all services |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit UI (:8501)                  │
│  Dashboard │ Investigation │ History │ Config │ Monitor  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI API (:8000)                     │
│  /alert │ /investigations │ /report │ /health │ /metrics│
└────────┬─────────────────────────────────┬──────────────┘
         │                                 │
┌────────▼────────┐               ┌────────▼────────┐
│   LangGraph     │               │   PostgreSQL    │
│  Investigation  │               │   (SQLite dev)  │
│     Graph       │               └─────────────────┘
│                 │
│  detect → plan  │
│     ↓           │
│  ┌───┬───┬───┐  │──── Groq API (llama-3.3-70b)
│  │Log│Met│Dep│  │
│  └─┬─┴─┬─┴─┬─┘  │
│    └───┼───┘    │
│  decide → act   │──── GitHub Actions (rollback)
│     ↓           │
│   report        │──── Jinja2 + xhtml2pdf
└─────────────────┘
```

## License

This project is for educational and demonstration purposes.