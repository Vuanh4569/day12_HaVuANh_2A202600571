# Deployment Information

## Public URL
https://soothing-benevolence-production-f174.up.railway.app

## Platform
Railway

## Test Commands

### 1. Health Check
```bash
curl -i https://soothing-benevolence-production-f174.up.railway.app/health
```
**Expected Response:**
```json
HTTP/1.1 200 OK
content-type: application/json

{
  "status": "ok",
  "version": "1.0.0",
  "environment": "production",
  "uptime_seconds": 124.5,
  "total_requests": 15,
  "timestamp": "2026-06-12T08:45:18.205626+00:00"
}
```

### 2. Readiness Check
```bash
curl -i https://soothing-benevolence-production-f174.up.railway.app/ready
```
**Expected Response:**
```json
HTTP/1.1 200 OK
content-type: application/json

{"ready": true}
```

### 3. API Test (Without Authentication)
```bash
curl -i -X POST https://soothing-benevolence-production-f174.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?"}'
```
**Expected Response:**
```json
HTTP/1.1 401 Unauthorized
content-type: application/json

{"detail":"Invalid or missing API key. Include header: X-API-Key: <key>"}
```

### 4. API Test (With Authentication)
```bash
curl -i -X POST https://soothing-benevolence-production-f174.up.railway.app/ask \
  -H "X-API-Key: dev-key-change-me-in-production" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?"}'
```
**Expected Response:**
```json
HTTP/1.1 200 OK
content-type: application/json

{
  "question": "What is Docker?",
  "answer": "Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!",
  "model": "gpt-4o-mini",
  "timestamp": "2026-06-12T08:46:12.049014+00:00"
}
```

### 5. Rate Limiting Test (20 requests per minute limit)
```bash
for i in {1..25}; do 
  curl -s -o /dev/null -w "Request $i: %{http_code}\n" -X POST https://soothing-benevolence-production-f174.up.railway.app/ask \
    -H "X-API-Key: dev-key-change-me-in-production" \
    -H "Content-Type: application/json" \
    -d '{"question": "hi"}'
done
```
**Expected Output:**
```text
Request 1: 200
Request 2: 200
...
Request 19: 200
Request 20: 429
Request 21: 429
```

---

## Environment Variables Set on Railway
- `PORT` = `8000`
- `ENVIRONMENT` = `production`
- `AGENT_API_KEY` = `dev-key-change-me-in-production`
- `JWT_SECRET` = `dev-jwt-secret-change-in-production`
- `REDIS_URL` = `redis://default:password@your-redis-railway-host:6379/0`
- `DAILY_BUDGET_USD` = `5.0`
- `RATE_LIMIT_PER_MINUTE` = `20`
- `LOG_LEVEL` = `INFO`

---

## Screenshots
- [Deployment Dashboard](screenshots/dashboard.png)
- [Service Running](screenshots/running.png)
- [Test Results](screenshots/test.png)
