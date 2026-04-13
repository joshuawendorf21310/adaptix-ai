# adaptix-ai

**Adaptix AI Governance and Execution Service** - Production-ready AI control plane for prompt governance, policy enforcement, usage accounting, provider routing, and founder oversight.

## Status

**✅ Production Ready** - Core transformation from shell to production complete:

- ✅ Database persistence with migrations
- ✅ Service layer for governance, usage, and health
- ✅ Real-time metrics from database
- ✅ Prompt versioning and activation
- ✅ Policy management and enforcement
- ✅ Audit logging for all governance actions
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

## Documentation

- **[Deployment Guide](DEPLOYMENT.md)** - Complete production deployment instructions
- **[Database Migrations](backend/alembic/README.md)** - Migration management
- **[API Documentation](http://localhost:8014/docs)** - Swagger UI (when running)

## Architecture

### Backend (`/backend`)
- **FastAPI** application with SQLAlchemy ORM
- **PostgreSQL** database with Alembic migrations
- **AWS Bedrock** integration for AI execution
- **Service layer:** Audit, Prompt, Policy, Usage, System Health
- **API routers:** Authentication, Governance, Health, Founder

### Frontend (`/frontend`)
- **Next.js 15** with React 19
- **App Router** for modern routing
- **Founder AI dashboard** for governance oversight
- **Policies management** interface
- **Prompt editor** and review queue

## Key Features

### Governance
- Prompt definition, versioning, and activation
- Policy management with revision history
- Guardrails and PII masking enforcement
- Manual review workflow for high-risk operations
- Immutable audit logging

### Usage & Metering
- Token consumption tracking
- Cost estimation and budgeting
- Performance metrics (latency percentiles)
- Usage breakdown by module and task type
- Daily/weekly/monthly aggregations

### System Health
- Component health monitoring (database, providers)
- Provider connectivity checks
- Performance degradation detection
- Active incident tracking

### Security
- Environment-specific authentication
- Dev mode JWT (development only)
- Production OAuth/OIDC ready
- Role-based access control
- Audit trail for security events

## Environment Variables

See `.env.example` files in `backend/` and `frontend/` for all configuration options.

**Critical for Production:**
- `ADAPTIX_AI_ENV=production`
- `ADAPTIX_AI_DATABASE_URL` (required)
- `ADAPTIX_AI_JWT_SECRET` (required)
- `ADAPTIX_AI_ALLOW_DEV_AUTH=false`
- AWS credentials for Bedrock

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

## Repository History

This repository was bootstrapped as part of the Adaptix polyrepo migration on 2026-04-08. It serves as the authoritative source for:
- AI inference orchestration
- Prompt governance and management
- Guardrails and policy enforcement
- Augmentation truth and model routing

## Contributing

1. Create feature branch from `main`
2. Make changes with tests
3. Run linters and tests
4. Submit pull request

## License

Proprietary - Adaptix Platform
