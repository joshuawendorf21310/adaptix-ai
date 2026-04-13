# Adaptix AI - Production Deployment Guide

## Overview

Adaptix AI is now a production-ready AI governance and execution service with complete database persistence, real metrics, and operational readiness.

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ database
- AWS credentials (for Bedrock integration)
- Node.js 18+ (for frontend)

## Environment Configuration

### Backend Environment Variables

Create a `.env` file in the `backend/` directory:

```bash
# Application
ADAPTIX_AI_ENV=production
ADAPTIX_AI_DEBUG=false

# Database (REQUIRED in production)
ADAPTIX_AI_DATABASE_URL=postgresql://user:password@host:5432/adaptix_ai

# Security (REQUIRED in production)
ADAPTIX_AI_JWT_SECRET=<strong-random-secret-minimum-32-chars>
ADAPTIX_AI_ALLOW_DEV_AUTH=false

# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-key>

# Bedrock Configuration
ADAPTIX_AI_BEDROCK_MODEL_ID=claude-3-5-sonnet-20241022-v2:0
ADAPTIX_AI_BEDROCK_MAX_TOKENS=4096
ADAPTIX_AI_BEDROCK_TEMPERATURE=0.3

# Governance & Budget
ADAPTIX_AI_GUARDRAILS_ENABLED=true
ADAPTIX_AI_PII_MASKING_ENABLED=true
ADAPTIX_AI_DAILY_TOKEN_BUDGET=1000000
ADAPTIX_AI_RATE_LIMIT_PER_MINUTE=100

# CORS (comma-separated origins)
ADAPTIX_AI_CORS_ORIGINS=https://your-frontend-domain.com

# Optional: Redis for caching
ADAPTIX_AI_REDIS_ENABLED=false
ADAPTIX_AI_REDIS_URL=redis://localhost:6379

# Optional: EventBridge for async events
ADAPTIX_AI_EVENTBRIDGE_ENABLED=false
```

### Frontend Environment Variables

Create a `.env.local` file in the `frontend/` directory:

```bash
NEXT_PUBLIC_AI_API_BASE=https://your-backend-domain.com
```

## Database Setup

### 1. Create Database

```bash
createdb adaptix_ai
```

### 2. Run Migrations

```bash
cd backend
pip install -e .
alembic upgrade head
```

### 3. Verify Migration

```bash
alembic current
# Should show: 001_initial_schema (head)
```

## Installation

### Backend

```bash
cd backend
python -m pip install -e .
```

### Frontend

```bash
cd frontend
npm install
```

## Running Locally

### Backend

```bash
cd backend
uvicorn core_app.main:app --reload --host 0.0.0.0 --port 8014
```

### Frontend

```bash
cd frontend
npm run dev
# Runs on http://localhost:3003
```

## Production Deployment

### Database Migration Workflow

1. **Before deploying new code:**
   ```bash
   alembic upgrade head
   ```

2. **Rollback if needed:**
   ```bash
   alembic downgrade -1
   ```

3. **Check current version:**
   ```bash
   alembic current
   ```

### Health Checks

- **Liveness:** `GET /health`
- **Readiness:** `GET /health` (check database connection)

### Production Checklist

- [ ] Database is configured and migrated
- [ ] `ADAPTIX_AI_ENV=production`
- [ ] `ADAPTIX_AI_ALLOW_DEV_AUTH=false`
- [ ] JWT secret is strong and secure
- [ ] AWS credentials are configured
- [ ] CORS origins are properly restricted
- [ ] Database connection pool is sized appropriately
- [ ] Logging level is set to INFO or WARNING
- [ ] Health checks are configured in infrastructure

## Initial Data Seeding

### Create Default Policy

```python
from core_app.database import get_db_context
from core_app.services import PolicyService
from uuid import uuid4

tenant_id = uuid4()  # Your tenant ID
admin_user_id = uuid4()  # Admin user ID

with get_db_context() as db:
    policy_service = PolicyService(db)
    policy = policy_service.create_policy(
        tenant_id=tenant_id,
        name="Default AI Policy",
        description="Default governance policy for AI operations",
        pii_masking_enabled=True,
        content_guardrails_enabled=True,
        rate_limit_per_minute=100,
        daily_token_budget=1_000_000,
        created_by=admin_user_id,
    )
    print(f"Created policy: {policy.id}")
```

### Seed Sample Prompts

```python
from core_app.services import PromptService

with get_db_context() as db:
    prompt_service = PromptService(db)

    # Create a prompt
    prompt = prompt_service.create_prompt(
        tenant_id=tenant_id,
        name="Incident Summary",
        use_case="Generate incident summaries for command staff",
        description="Summarizes incident details for situational awareness",
        owner="Command Module",
        created_by=admin_user_id,
    )

    # Create a version
    version = prompt_service.create_version(
        prompt_id=prompt.id,
        tenant_id=tenant_id,
        prompt_text="Summarize the following incident: {context}",
        guardrails_enabled=True,
        pii_masking_enabled=True,
        created_by=admin_user_id,
    )

    # Activate the version
    prompt_service.activate_version(
        version_id=version.id,
        tenant_id=tenant_id,
        activated_by=admin_user_id,
    )
```

## Monitoring & Observability

### Key Metrics to Monitor

1. **Usage Metrics:**
   - Daily token consumption
   - Request volume by module
   - Cost accumulation
   - Error rates

2. **Performance Metrics:**
   - P50, P95, P99 latency
   - Database query performance
   - Provider response times

3. **Health Metrics:**
   - Component status (database, bedrock, redis)
   - Active alerts
   - System degradation events

### Audit Log Review

Query recent governance events:

```python
from core_app.services import AuditService

with get_db_context() as db:
    audit_service = AuditService(db)
    events = audit_service.get_recent_governance_events(
        tenant_id=tenant_id,
        limit=50,
    )
    for event in events:
        print(f"{event.created_at}: {event.event_type} - {event.summary}")
```

## Troubleshooting

### Database Connection Issues

If you see "database_not_configured" or connection errors:

1. Verify `ADAPTIX_AI_DATABASE_URL` is set
2. Check database is accessible
3. Verify credentials are correct
4. Check firewall/security group rules

### Provider Health Issues

If Bedrock shows as unhealthy:

1. Verify AWS credentials are configured
2. Check AWS region is correct
3. Verify IAM permissions for Bedrock
4. Check network connectivity to AWS

### Empty Metrics

If dashboards show zeros:

1. Database is connected but empty (truthful zero state)
2. No executions have been recorded yet
3. Seed sample data or wait for real usage

## Security Considerations

1. **Never commit secrets** to version control
2. **Rotate JWT secrets** regularly
3. **Use environment-specific secrets** (dev vs production)
4. **Enable audit logging** in production
5. **Review audit logs** regularly for anomalies
6. **Restrict CORS origins** to known domains
7. **Use SSL/TLS** for all connections
8. **Keep dependencies updated** for security patches

## Performance Tuning

### Database Connection Pool

Adjust based on concurrency:

```bash
ADAPTIX_AI_DATABASE_POOL_SIZE=20
ADAPTIX_AI_DATABASE_MAX_OVERFLOW=10
```

### Rate Limiting

Adjust per tenant or globally:

```bash
ADAPTIX_AI_RATE_LIMIT_PER_MINUTE=100
```

### Bedrock Configuration

Tune for your workload:

```bash
ADAPTIX_AI_BEDROCK_MAX_TOKENS=4096
ADAPTIX_AI_BEDROCK_TEMPERATURE=0.3
ADAPTIX_AI_BEDROCK_TIMEOUT=60
ADAPTIX_AI_BEDROCK_MAX_RETRIES=3
```

## Backup & Recovery

### Database Backups

Regular PostgreSQL backups are critical:

```bash
# Backup
pg_dump adaptix_ai > backup_$(date +%Y%m%d).sql

# Restore
psql adaptix_ai < backup_20260413.sql
```

### Migration Rollback

If a migration causes issues:

```bash
# Rollback one version
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>
```

## Support & Documentation

- **Repository:** https://github.com/joshuawendorf21310/adaptix-ai
- **Issues:** Report issues on GitHub
- **Migrations:** See `backend/alembic/README.md`
- **Models:** See `backend/core_app/models/`
- **Services:** See `backend/core_app/services/`
