# adaptix-ai

**Adaptix AI Governance and Execution Service** - Production-grade AI control plane for prompt governance, policy enforcement, usage accounting, provider routing, founder oversight, and comprehensive billing intelligence. Built on AWS Bedrock as the primary model runtime.

## Overview

Adaptix AI is the authoritative AI orchestration, safety, execution, metering, review, and augmentation platform for all Adaptix domains. It owns Bedrock-based inference routing, prompt governance, policy enforcement, execution safety, model selection, fallback strategy, cost accounting, approval workflows, augmentation logic, AI observability, and AI billing intelligence.

**What Adaptix AI Owns:**
- Bedrock-based AI execution and model routing
- Prompt lifecycle management (versioning, activation, approval)
- Policy enforcement and safety guardrails
- AI execution requests and results
- Usage metering and cost allocation
- Review workflows for high-risk AI operations
- Budget tracking and enforcement
- Billing intelligence (claim readiness, denial risk, medical necessity)
- AI observability and health monitoring
- Audit logging for governance actions

**What Adaptix AI Does NOT Own:**
- Authoritative domain records (CAD, ePCR, CrewLink, Field, Air, Fire, Workforce, TransportLink, Billing, Command)
- Domain-specific business logic and workflows
- Domain data persistence and state management

Adaptix AI may read, enrich, summarize, classify, and evaluate domain data, but authoritative domain records remain in those services.

## Status

**✅ Production Ready** - Comprehensive AI governance platform with 500+ features:

- ✅ AWS Bedrock execution and intelligent model routing
- ✅ Cost-aware, quality-aware, and latency-aware routing
- ✅ Task-type-based model selection with fallback chains
- ✅ Database persistence with migrations
- ✅ Service layer for governance, usage, billing intelligence, and health
- ✅ Real-time metrics from database
- ✅ Prompt versioning, activation, and rollback
- ✅ Policy management, enforcement, and simulation
- ✅ Audit logging for all governance actions
- ✅ Review workflows with assignment and escalation
- ✅ Budget tracking with soft/hard caps and alerts
- ✅ Billing intelligence (claim readiness, denial risk, medical necessity)
- ✅ AI observability with cost spike and quality regression detection
- ✅ System health monitoring
- ✅ Docker deployment support
- ✅ CI/CD pipeline

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Start all services (PostgreSQL, backend, frontend)
docker-compose up

# Backend: http://localhost:8014
# Frontend: http://localhost:3003
# Database: localhost:5432
```

### Manual Setup

**Backend:**
```bash
cd backend
pip install -e .
cp .env.example .env
# Edit .env with your configuration
alembic upgrade head
uvicorn core_app.main:app --reload --port 8014
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local with backend URL
npm run dev
```

## Architecture

### Backend (`/backend`)
- **FastAPI** application with SQLAlchemy ORM
- **PostgreSQL** database with Alembic migrations
- **AWS Bedrock** as primary AI execution runtime
- **Service layer:** Audit, Prompt, Policy, Usage, Budget, Review, Billing Intelligence, Alerting, System Health
- **API routers:** Authentication, Governance, Health, Founder, Billing Intelligence

### Frontend (`/frontend`)
- **Next.js 15** with React 19
- **App Router** for modern routing
- **Founder AI dashboard** for governance oversight
- **Policies management** interface
- **Prompt editor** and review queue
- **Billing intelligence dashboards**

## Key Features

### AWS Bedrock Execution & Model Routing
- **Bedrock as primary runtime**: First-class support for Claude 3.5 Sonnet, Opus, and Haiku models
- **Intelligent routing**: Task-type-based, cost-aware, quality-aware, and latency-aware model selection
- **Module-specific overrides**: Different models for different domains (billing, command, field, etc.)
- **Fallback chains**: Automatic failover to alternative models on error
- **Model allowlists/denylists**: Control which models can be used
- **Circuit breaker**: Resilience pattern for degraded provider states
- **Abstraction layer**: Bedrock is the production target but code is not locked to Bedrock

### Prompt Governance & Lifecycle
- **Prompt definitions and versions**: Named prompts with full revision history
- **Version activation/deactivation**: Only one version active at a time
- **Approval workflows**: Review and approve prompt changes before production
- **Rollback capability**: Revert to previous versions safely
- **Change tracking**: Complete audit trail of prompt modifications
- **Guardrails metadata**: PHI masking and content guardrails per prompt
- **Review requirements**: Flag prompts requiring manual review

### Policy Enforcement & Safety
- **Policy management**: Define governance policies with revision history
- **Content guardrails**: PHI detection, financial mutation blocking, claim submission blocking
- **Rate limiting**: Per-tenant and per-module rate limits
- **Budget enforcement**: Daily and monthly token budgets
- **Review thresholds**: Confidence-based review triggers
- **Policy simulation**: Dry-run mode for testing policy changes
- **Policy drift detection**: Alert when policy behavior changes unexpectedly
- **Compliance rules**: Medical accuracy checks, hallucination detection

### Review Workflows
- **Review queue management**: Queue items for manual review based on risk
- **Assignment and escalation**: Assign reviews to specific reviewers, escalate stale items
- **Approval/rejection/changes**: Full workflow with audit trails
- **Review metrics**: Track approval rates, review times, backlog size
- **Domain-specific reviews**: Billing, compliance, PHI, and high-risk content reviews
- **Before/after comparison**: View AI output with context

### Usage Accounting & Billing Intelligence
- **Token consumption tracking**: Input, output, and total tokens per request
- **Cost estimation**: Real-time cost tracking based on Bedrock pricing
- **Performance metrics**: Latency percentiles (P50, P95, P99)
- **Usage breakdowns**: By module, task type, model, and time period
- **Daily/weekly/monthly aggregations**: Pre-computed rollups for fast queries

### Budget Tracking & Enforcement
- **Multi-scope budgets**: Tenant-level, module-level, and task-type-level budgets
- **Soft and hard caps**: Warning thresholds and hard stops
- **Real-time consumption**: Track spend against budgets in real-time
- **Cost alerts**: Automatic alerts for budget violations
- **Budget periods**: Daily, weekly, monthly, quarterly, annual budgets
- **Pre-execution checks**: Prevent executions that would exceed hard caps

### Billing-Specific AI Logic
- **Claim readiness scoring**: 0-100 score with specific issues identified
- **Denial risk analysis**: Flag high-risk claims with denial triggers
- **Medical necessity summaries**: Generate justification narratives
- **Documentation completeness**: Identify missing PCR elements
- **Coding support**: Suggest ICD-10 and CPT code improvements
- **Payer rule explanations**: Explain payer-specific requirements
- **Charge capture assistance**: Detect missing billable services

### AI Observability & Health
- **Component health monitoring**: Database, Bedrock, policy services, review queues
- **Provider connectivity checks**: Real-time Bedrock availability
- **Cost spike detection**: Alert on unusual cost increases
- **Latency regression detection**: Alert on performance degradation
- **Quality regression detection**: Alert on increased error rates
- **Task failure clustering**: Detect patterns in failures
- **Dashboards**: Model usage, policy violations, prompt performance, costs

### Cross-Domain AI Enablement
- **ePCR/Field**: Narrative generation, chart QA, NEMSIS hints, contradiction detection
- **Billing**: Claim readiness, denial risk, medical necessity, coding support
- **Transport/Flow**: Scheduling optimization, bottleneck analysis, medical necessity
- **Crew/Workforce**: Coverage analysis, fatigue analysis, staffing risk
- **Air**: Mission briefs, weather summaries, flight risk, checklist anomalies
- **Fire**: Incident summaries, inspection deficiencies, NERIS scoring
- **Command/Founder**: Executive summaries, trend intelligence, investor summaries

### Security, Privacy & Audit
- **Immutable audit logging**: All governance actions, executions, and reviews
- **PHI detection and redaction**: Automatic PHI masking in inputs and outputs
- **Role-based access control**: Admin, reviewer, and user roles
- **Tenant isolation**: Multi-tenancy with strict data separation
- **Encryption posture**: Assumes encryption at rest and in transit
- **Security event auditing**: Track admin actions and policy violations

## Environment Variables

See `.env.example` files in `backend/` and `frontend/` for all configuration options.

**Critical for Production:**
- `ADAPTIX_AI_ENV=production`
- `ADAPTIX_AI_DATABASE_URL` (required)
- `ADAPTIX_AI_JWT_SECRET` (required)
- `ADAPTIX_AI_ALLOW_DEV_AUTH=false`
- AWS credentials for Bedrock (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
- `ADAPTIX_AI_BEDROCK_REGION` (default: us-east-1)

**Model Routing Configuration:**
- `ADAPTIX_AI_BEDROCK_MODEL_ID` - Default model
- `ADAPTIX_AI_BEDROCK_MODEL_COMMAND` - Override for Command module
- `ADAPTIX_AI_BEDROCK_MODEL_BILLING` - Override for Billing module
- `ADAPTIX_AI_BEDROCK_ALLOWED_MODELS` - Comma-separated allowlist
- `ADAPTIX_AI_BEDROCK_DENIED_MODELS` - Comma-separated denylist
- `ADAPTIX_AI_BEDROCK_FALLBACK_ENABLED` - Enable fallback chains (default: true)

**Budget Configuration:**
- `ADAPTIX_AI_TENANT_DAILY_BUDGET_USD` - Default tenant daily budget
- `ADAPTIX_AI_BUDGET_HARD_CAP_ENABLED` - Enable hard caps (default: false)
- `ADAPTIX_AI_BUDGET_ALERT_ENABLED` - Enable budget alerts (default: true)

## Development

```bash
# Run backend tests
cd backend
pytest

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Frontend development
cd frontend
npm run dev
```

## API Documentation

When running locally, interactive API documentation is available at:
- **Swagger UI**: http://localhost:8014/docs
- **ReDoc**: http://localhost:8014/redoc

### Key Endpoints

**Billing Intelligence:**
- `POST /api/billing/claim-readiness` - Score claim readiness
- `POST /api/billing/denial-risk` - Assess denial risk
- `POST /api/billing/medical-necessity` - Generate medical necessity summary
- `POST /api/billing/documentation-completeness` - Analyze PCR completeness
- `POST /api/billing/coding-support` - Get coding improvement suggestions

**Budget Management:**
- `GET /api/budget/status` - Get budget status
- `POST /api/budget/create` - Create new budget
- `GET /api/budget/alerts` - Get cost alerts

**Review Queue:**
- `GET /api/review/queue` - Get review queue items
- `POST /api/review/{id}/approve` - Approve review item
- `POST /api/review/{id}/reject` - Reject review item
- `POST /api/review/{id}/escalate` - Escalate review item

**Observability:**
- `GET /api/alerts/active` - Get active alerts
- `POST /api/alerts/detect-cost-spike` - Run cost spike detection
- `POST /api/alerts/detect-quality-regression` - Run quality regression detection

## Billing Intelligence Details

Adaptix AI provides comprehensive billing intelligence features:

### Claim Readiness Scoring
- Scores claims 0-100 based on completeness and compliance
- Identifies missing required fields
- Flags documentation gaps
- Provides actionable recommendations
- Always requires human review before submission

### Denial Risk Analysis
- Assesses likelihood of claim denial
- Identifies specific denial triggers
- Flags payer-specific concerns
- Highlights medical necessity gaps
- Suggests mitigation actions

### Medical Necessity Summaries
- Generates clinical justification narratives
- Explains why ambulance transport was necessary
- Documents why alternatives were unsuitable
- Provides suggested documentation language
- Marked as augmentation (non-authoritative)

### Documentation Completeness
- Analyzes PCR documentation for billing readiness
- Identifies missing elements (signatures, narratives, times)
- Flags weak or unclear documentation
- Provides specific improvement recommendations

### Coding Support
- Reviews ICD-10 and CPT codes for accuracy
- Suggests alternative codes with justifications
- Identifies opportunities for increased specificity
- Recommends additional documentation for better coding

**Important**: All billing AI outputs are marked as augmentation and require human review. Adaptix AI assists but does not make autonomous billing decisions.

## Repository History

This repository was bootstrapped as part of the Adaptix polyrepo migration on 2026-04-08. It serves as the authoritative source for:
- AI inference orchestration
- Prompt governance and management
- Guardrails and policy enforcement
- Augmentation truth and model routing
- Billing intelligence and support

## Contributing

1. Create feature branch from `main`
2. Make changes with tests
3. Run linters and tests
4. Submit pull request

## License

Proprietary - Adaptix Platform
