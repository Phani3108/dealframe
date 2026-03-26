# DealFrame API Reference

## Base URL

```
http://localhost:8000
```

Interactive documentation:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Authentication

All authenticated endpoints require a Bearer token:

```
Authorization: Bearer <jwt_token>
```

Get a token:
```http
POST /api/v1/auth/login
Content-Type: application/json

{"username": "analyst@example.com", "password": "..."}
```

Response:
```json
{"access_token": "eyJ...", "token_type": "bearer", "role": "analyst"}
```

---

## Core Endpoints

### Upload & Process Video

```http
POST /api/v1/process
Content-Type: multipart/form-data

file=@meeting.mp4
```

Response:
```json
{"job_id": "abc-123", "status": "pending"}
```

### Get Job Result

```http
GET /api/v1/process/{job_id}
```

Response:
```json
{
  "job_id": "abc-123",
  "status": "completed",
  "result": {
    "transcript": "...",
    "segments": [
      {
        "topic": "Pricing discussion",
        "start_time": 12.5,
        "end_time": 45.2,
        "sentiment": "negative",
        "risk_score": 0.72,
        "objections": ["too expensive"],
        "intent": "price_negotiation"
      }
    ]
  }
}
```

### Semantic Search

```http
POST /api/v1/search
Content-Type: application/json

{"query": "pricing objection", "top_k": 10}
```

---

## Intelligence

### Get Objections

```http
GET /api/v1/intelligence/objections?top_n=10
```

### Risk Summary

```http
GET /api/v1/intelligence/risk-summary
```

### Pattern Mining

```http
GET /api/v1/patterns?pattern_type=objection_risk
GET /api/v1/patterns/summary
```

### Call Diffing

```http
GET /api/v1/diff/{job_a}/{job_b}
GET /api/v1/diff/jobs
```

### Live Copilot

```http
POST /api/v1/copilot/analyze
Content-Type: application/json

{"transcript_so_far": "The customer said they think the price is too high..."}
```

---

## Annotations

```http
GET    /api/v1/annotations?job_id=abc-123
POST   /api/v1/annotations
GET    /api/v1/annotations/{id}
PUT    /api/v1/annotations/{id}
DELETE /api/v1/annotations/{id}
POST   /api/v1/annotations/{id}/resolve
GET    /api/v1/annotations/summary?job_id=abc-123
GET    /api/v1/annotations/export?job_id=abc-123
```

### Create Annotation

```http
POST /api/v1/annotations
Content-Type: application/json

{
  "job_id": "abc-123",
  "segment_index": 2,
  "start_word": 10,
  "end_word": 25,
  "label": "objection",
  "comment": "Customer objects to timeline"
}
```

---

## Active Learning

```http
GET  /api/v1/active-learning/queue?status=pending
GET  /api/v1/active-learning/metrics
POST /api/v1/active-learning/{id}/claim
POST /api/v1/active-learning/{id}/approve
POST /api/v1/active-learning/{id}/correct
POST /api/v1/active-learning/{id}/reject
GET  /api/v1/active-learning/gate
GET  /api/v1/active-learning/export
```

---

## Admin

```http
GET  /api/v1/admin/stats
GET  /api/v1/admin/tenants
POST /api/v1/admin/tenants
GET  /api/v1/admin/users
GET  /api/v1/admin/roles
GET  /api/v1/admin/permissions/{role}
GET  /api/v1/admin/settings
```

---

## Audit

```http
GET /api/v1/audit?user_id=...&action=...&resource_type=...&limit=50&offset=0
GET /api/v1/audit/stats
```

---

## Health Probes

```http
GET /health       # Basic health
GET /health/live  # Liveness (always 200 if app is up)
GET /health/ready # Readiness (checks DB connection)
```

---

## Python SDK

```python
from temporalos_sdk import DealFrameClient

client = DealFrameClient("http://localhost:8000", api_key="your-token")

# Upload and process
job = client.upload("meeting.mp4")
result = client.wait_for_result(job.job_id)

# Access structured intelligence
for segment in result.segments:
    print(f"{segment['topic']}: risk={segment.get('risk_score', 0)}")

# Search across all videos
hits = client.search("pricing objection")

# Live coaching
signals = client.analyze_live("The customer mentioned the competitor...")
```
