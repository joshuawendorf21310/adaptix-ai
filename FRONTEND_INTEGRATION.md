# Frontend API Integration Examples

This document provides examples of how to integrate with the Adaptix AI Governance Platform APIs from a frontend application.

## Authentication

All API requests require authentication via JWT token in the Authorization header:

```javascript
const headers = {
  'Authorization': `Bearer ${jwtToken}`,
  'Content-Type': 'application/json'
};
```

## Budget Management

### Get Budget Status

```javascript
async function getBudgetStatus(scopeType, scopeValue = null) {
  const params = new URLSearchParams({
    scope_type: scopeType,
    ...(scopeValue && { scope_value: scopeValue })
  });

  const response = await fetch(`/api/v1/budget/status?${params}`, {
    headers
  });

  return await response.json();
}

// Usage
const tenantBudget = await getBudgetStatus('tenant');
const moduleBudget = await getBudgetStatus('module', 'billing');
```

### Create Budget

```javascript
async function createBudget(budgetConfig) {
  const response = await fetch('/api/v1/budget/create', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      scope_type: budgetConfig.scopeType,
      scope_value: budgetConfig.scopeValue,
      period: budgetConfig.period, // 'daily', 'weekly', 'monthly'
      limit_usd: budgetConfig.limitUsd,
      soft_cap_threshold: budgetConfig.softCapThreshold || 0.9,
      hard_cap_enabled: budgetConfig.hardCapEnabled || false,
      alert_enabled: budgetConfig.alertEnabled || true
    })
  });

  return await response.json();
}

// Usage
await createBudget({
  scopeType: 'module',
  scopeValue: 'billing',
  period: 'monthly',
  limitUsd: 1000.0,
  softCapThreshold: 0.85,
  hardCapEnabled: true
});
```

### Get Cost Alerts

```javascript
async function getCostAlerts(unresolvedOnly = true, limit = 50) {
  const params = new URLSearchParams({
    limit: limit.toString(),
    unresolved_only: unresolvedOnly.toString()
  });

  const response = await fetch(`/api/v1/budget/alerts?${params}`, {
    headers
  });

  return await response.json();
}
```

## Review Queue Management

### Get Review Queue

```javascript
async function getReviewQueue(filters = {}) {
  const params = new URLSearchParams({
    limit: filters.limit || 50,
    offset: filters.offset || 0,
    ...(filters.reviewType && { review_type: filters.reviewType }),
    ...(filters.priority && { priority: filters.priority }),
    ...(filters.status && { status: filters.status })
  });

  const response = await fetch(`/api/v1/review/queue?${params}`, {
    headers
  });

  return await response.json();
}

// Usage
const highPriorityReviews = await getReviewQueue({
  priority: 'high',
  status: 'pending'
});
```

### Approve Review

```javascript
async function approveReview(reviewId, notes = null, modifications = null) {
  const response = await fetch(`/api/v1/review/${reviewId}/approve`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      notes,
      modifications
    })
  });

  return await response.json();
}

// Usage
await approveReview(reviewId, 'Approved after verification', {
  reduced_scope: true,
  approved_cost: 50.0
});
```

### Reject Review

```javascript
async function rejectReview(reviewId, rejectionReason, notes = null) {
  const response = await fetch(`/api/v1/review/${reviewId}/reject`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      rejection_reason: rejectionReason,
      notes
    })
  });

  return await response.json();
}
```

### Escalate Review

```javascript
async function escalateReview(reviewId, escalationReason, escalateTo = null) {
  const response = await fetch(`/api/v1/review/${reviewId}/escalate`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      escalation_reason: escalationReason,
      escalate_to: escalateTo
    })
  });

  return await response.json();
}
```

## Billing Intelligence

### Score Claim Readiness

```javascript
async function scoreClaimReadiness(claimData) {
  const response = await fetch('/api/v1/billing-intelligence/claim-readiness', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      claim_data: {
        patient_age: claimData.patientAge,
        service_date: claimData.serviceDate,
        transport_type: claimData.transportType,
        chief_complaint: claimData.chiefComplaint,
        diagnosis_codes: claimData.diagnosisCodes,
        procedure_codes: claimData.procedureCodes,
        mileage: claimData.mileage,
        origin: claimData.origin,
        destination: claimData.destination,
        necessity_documented: claimData.necessityDocumented,
        physician_signature: claimData.physicianSignature,
        patient_signature: claimData.patientSignature
      }
    })
  });

  return await response.json();
}
```

### Assess Denial Risk

```javascript
async function assessDenialRisk(claimData, payerType = null) {
  const response = await fetch('/api/v1/billing-intelligence/denial-risk', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      claim_data: claimData,
      payer_type: payerType
    })
  });

  return await response.json();
}
```

### Generate Medical Necessity Summary

```javascript
async function generateMedicalNecessity(patientData, transportData) {
  const response = await fetch('/api/v1/billing-intelligence/medical-necessity', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      patient_data: patientData,
      transport_data: transportData
    })
  });

  return await response.json();
}
```

## Analytics

### Get ROI Metrics

```javascript
async function getROIMetrics(module = null, lookbackDays = 30) {
  const params = new URLSearchParams({
    lookback_days: lookbackDays.toString(),
    ...(module && { module })
  });

  const response = await fetch(`/api/v1/analytics/roi-metrics?${params}`, {
    headers
  });

  return await response.json();
}

// Usage
const billingROI = await getROIMetrics('billing', 30);
```

### Analyze Denial Patterns

```javascript
async function analyzeDenialPatterns(lookbackDays = 30, minOccurrences = 3) {
  const params = new URLSearchParams({
    lookback_days: lookbackDays.toString(),
    min_occurrences: minOccurrences.toString()
  });

  const response = await fetch(`/api/v1/analytics/denial-patterns?${params}`, {
    headers
  });

  return await response.json();
}
```

### Get Cost Optimization Recommendations

```javascript
async function getCostOptimizationRecommendations(lookbackDays = 7) {
  const params = new URLSearchParams({
    lookback_days: lookbackDays.toString()
  });

  const response = await fetch(`/api/v1/analytics/cost-optimization?${params}`, {
    headers
  });

  return await response.json();
}
```

## Alerting & Observability

### Detect Cost Spike

```javascript
async function detectCostSpike(module = null, lookbackHours = 24, spikeThreshold = 2.0) {
  const response = await fetch('/api/v1/alerts/detect/cost-spike', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      module,
      lookback_hours: lookbackHours,
      spike_threshold: spikeThreshold
    })
  });

  return await response.json();
}
```

### Get Active Alerts

```javascript
async function getActiveAlerts(severity = null, alertType = null, limit = 50) {
  const params = new URLSearchParams({
    limit: limit.toString(),
    ...(severity && { severity }),
    ...(alertType && { alert_type: alertType })
  });

  const response = await fetch(`/api/v1/alerts/active?${params}`, {
    headers
  });

  return await response.json();
}
```

### Resolve Alert

```javascript
async function resolveAlert(alertId, resolutionNotes = null) {
  const response = await fetch(`/api/v1/alerts/${alertId}/resolve`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      resolution_notes: resolutionNotes
    })
  });

  return await response.json();
}
```

## React Component Examples

### Budget Status Dashboard

```jsx
import React, { useEffect, useState } from 'react';

function BudgetStatusDashboard() {
  const [budgets, setBudgets] = useState([]);
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    async function loadData() {
      const [tenantBudget, billingBudget, alertsData] = await Promise.all([
        getBudgetStatus('tenant'),
        getBudgetStatus('module', 'billing'),
        getCostAlerts(true, 10)
      ]);

      setBudgets([tenantBudget, billingBudget]);
      setAlerts(alertsData.alerts);
    }

    loadData();
  }, []);

  return (
    <div className="budget-dashboard">
      <h2>Budget Status</h2>
      {budgets.map((budget, i) => (
        <div key={i} className="budget-card">
          <h3>{budget.scope_type === 'tenant' ? 'Tenant Budget' : `${budget.scope_value} Module`}</h3>
          <div className="budget-progress">
            <div className="progress-bar" style={{ width: `${budget.utilization_pct}%` }} />
          </div>
          <p>${budget.consumed_usd.toFixed(2)} / ${budget.limit_usd.toFixed(2)}</p>
          <p>{budget.utilization_pct.toFixed(1)}% utilized</p>
        </div>
      ))}

      <h2>Active Alerts</h2>
      {alerts.map(alert => (
        <div key={alert.id} className={`alert alert-${alert.severity}`}>
          <h4>{alert.title}</h4>
          <p>{alert.message}</p>
        </div>
      ))}
    </div>
  );
}
```

### Review Queue Component

```jsx
import React, { useEffect, useState } from 'react';

function ReviewQueue() {
  const [reviews, setReviews] = useState([]);

  useEffect(() => {
    loadReviews();
  }, []);

  async function loadReviews() {
    const data = await getReviewQueue({ status: 'pending' });
    setReviews(data.items);
  }

  async function handleApprove(reviewId) {
    await approveReview(reviewId, 'Approved from queue');
    loadReviews(); // Refresh
  }

  async function handleReject(reviewId) {
    const reason = prompt('Rejection reason:');
    if (reason) {
      await rejectReview(reviewId, reason);
      loadReviews(); // Refresh
    }
  }

  return (
    <div className="review-queue">
      <h2>Review Queue</h2>
      {reviews.map(review => (
        <div key={review.id} className="review-item">
          <div className="review-header">
            <span className={`priority-${review.priority}`}>{review.priority}</span>
            <span>{review.review_type}</span>
          </div>
          <p>{review.review_reason}</p>
          <div className="review-actions">
            <button onClick={() => handleApprove(review.id)}>Approve</button>
            <button onClick={() => handleReject(review.id)}>Reject</button>
          </div>
        </div>
      ))}
    </div>
  );
}
```

## Error Handling

Always handle API errors appropriately:

```javascript
async function apiCall(url, options) {
  try {
    const response = await fetch(url, options);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'API request failed');
    }

    return await response.json();
  } catch (error) {
    console.error('API Error:', error);
    // Show user-friendly error message
    alert(`Error: ${error.message}`);
    throw error;
  }
}
```
