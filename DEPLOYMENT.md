# Deployment Information

## Public URL

**https://proactive-serenity-production-f89db504.up.railway.app**

## Platform

Railway (project `proactive-serenity`, service `proactive-serenity` + Redis)

## Test Commands

### Health Check

```bash
curl https://proactive-serenity-production-f89db504.up.railway.app/health
# Expected: {"status":"ok"}   (thực tế: 200)
```

### Readiness Check

```bash
curl https://proactive-serenity-production-f89db504.up.railway.app/ready
# Expected: {"ready":true}   (thực tế: 200, Redis đã kết nối)
```

### API Test (with authentication)

```bash
curl -X POST https://proactive-serenity-production-f89db504.up.railway.app/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
# Expected: 200
# {"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. ..."}
```

### Auth required (no key)

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST https://proactive-serenity-production-f89db504.up.railway.app/ask \
  -H "Content-Type: application/json" -d '{"question":"Hello"}'
# Expected: 401
```

## Environment Variables Set

- `PORT` (Railway cấp)
- `ENVIRONMENT`
- `REDIS_URL` (= `${{Redis.REDIS_URL}}`, tham chiếu service Redis trong project)
- `AGENT_API_KEY`
- `RATE_LIMIT_PER_MINUTE`
- `DAILY_BUDGET_USD`

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
