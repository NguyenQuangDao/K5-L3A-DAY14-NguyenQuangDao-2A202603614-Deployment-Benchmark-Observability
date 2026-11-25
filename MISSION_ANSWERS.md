# Day 14 Lab - Mission Answers

**Họ tên:** Nguyen Quang Dao
**MSSV:** 2A202603614

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found (trong `01-localhost-vs-production/develop/app.py`)

1. Hard-code API key: `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`.
2. Hard-code password DB: `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`.
3. Không có config management: `DEBUG = True`, `MAX_TOKENS = 500` viết cứng trong code.
4. Dùng `print()` thay vì logging, và còn in cả secret (`print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`).
5. Không có health check endpoint (`/health`) nên platform không biết khi nào cần restart.
6. Port cứng 8000 (`port=8000`), không đọc biến môi trường `PORT`.
7. Bind `host="localhost"` nên không nhận kết nối từ ngoài container.
8. Bật `reload=True` trong production (chỉ nên dùng khi develop).

### Exercise 1.2: Chạy bản develop

```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
curl -X POST "http://localhost:8000/ask?question=Hello"
```

Output thật:

```
HTTP/1.1 200 OK
server: uvicorn
content-type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Gửi JSON body thay vì query thì bị 422 (đúng như README lưu ý):

```bash
curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
# 422
```

### Exercise 1.3: Bảng so sánh develop vs production

| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config | Hardcode | Env vars | Không lộ secret, cùng image chạy được dev/staging/prod |
| Health check | ❌ | ✅ `/health` + `/ready` | Platform tự restart khi chết, LB bỏ instance chưa sẵn sàng |
| Logging | `print()` | JSON | Structured log dễ parse/search/phân tích |
| Shutdown | Đột ngột | Graceful (lifespan + SIGTERM) | Không mất request đang chạy |
| Port / host | `localhost:8000` cứng | `0.0.0.0` + `PORT` env | Chạy được trong container/cloud |
| Secret | Hardcode trong code | Từ env var | Không lộ khi push lên git |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. **Base image:** `python:3.11` (develop, image đầy đủ ~1GB) / `python:3.11-slim` (production, gọn hơn nhiều).
2. **Working directory:** `/app`.
3. **Tại sao `COPY requirements.txt` đứng trước `COPY . .`:** để Docker cache layer — chỉ khi `requirements.txt` đổi mới cài lại dependencies, còn đổi source không phải cài lại.
4. **CMD vs ENTRYPOINT:** CMD có thể bị override khi `docker run <image> <lệnh>`, ENTRYPOINT là lệnh cố định.

### Exercise 2.2: Build & run develop

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -p 8000:8000 my-agent:develop
curl -X POST "http://localhost:8000/ask?question=What%20is%20Docker"
```

Output thật (bản develop nhận `question` qua **query**):

```
HTTP/1.1 200 OK
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 2.3: Multi-stage build — so sánh kích thước

```bash
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images my-agent:develop my-agent:advanced
```

| Image | Size |
|-------|------|
| Develop (single-stage) | 1.67 GB (~1710 MB) |
| Production (multi-stage) | 265 MB |
| Chênh lệch | giảm ~84.5% |

Giải thích: multi-stage tách stage **builder** (cài compiler/deps) khỏi stage **runtime** (chỉ copy site-packages + source), nên image cuối nhỏ và ít lỗ hổng hơn.

### Exercise 2.4: Docker Compose stack

```
Client → Nginx :80 → agent :8000 → Redis :6379
```

Stack thật gồm 4 service: `nginx` (map 80/443), `agent` (build từ Dockerfile), `redis` (image `redis:7-alpine`, healthy), và `qdrant` (vector DB đi kèm).

```bash
cd 02-docker/production
touch .env.local
docker compose -p k5-day14-docker up -d --build
```

Output thật test qua Nginx (bản production nhận **JSON body**):

```
$ curl http://localhost/health
{"status":"ok","uptime_seconds":15.8,"version":"2.0.0","timestamp":"2026-11-25T12:05:32.126554"}

$ curl -X POST http://localhost/ask -H 'Content-Type: application/json' \
       -d '{"question":"Explain microservices"}'
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Lưu ý đã gặp: gửi `?question=` vào bản production thì `/ask` trả 500 (`JSONDecodeError`) vì endpoint đọc `await request.json()` — bản production dùng JSON body, bản develop mới dùng query.

---

## Part 3: Cloud Deployment

### Exercise 3.1: Deploy chính (Railway) — URL public

- URL: **https://proactive-serenity-production-f89db504.up.railway.app**
- Nền tảng: Railway (project `proactive-serenity` + service Redis cùng project)
- Screenshot: `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`

Kết quả 4 lệnh tự kiểm (đã chạy thật):

| Lệnh | Kỳ vọng | Thực tế |
|---|---|---|
| `GET /health` | 200 | **200** |
| `GET /ready` | 200 | **200** (Redis kết nối) |
| `POST /ask` (không key) | 401 | **401** |
| `POST /ask` (có `X-API-Key`) | 200 | **200** |

4 lệnh tự kiểm (chỉ in mã HTTP):

```bash
BASE=<URL>
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```

### Exercise 3.2: So sánh `railway.toml` vs `render.yaml`

| | Railway | Render |
|---|---|---|
| Format | TOML | YAML |
| Build | `[build] builder = "DOCKERFILE"` | `runtime: docker` trong Blueprint |
| Health check | `[deploy] healthcheckPath = "/health"` | `healthCheckPath: /health` |
| Port | App tự đọc biến `$PORT` do platform cấp | Render cấp `PORT` |
| Secret | Đặt qua `railway variables set` (dashboard) | Khai báo `envVars` với `generateValue: true` / `sync: false` |
| Redis | Tạo service Redis riêng, trỏ `REDIS_URL` | Phải tự khai báo service Redis trong `render.yaml` |

Điểm khác cốt lõi: Railway cấu hình tối giản (chủ yếu qua CLI/dashboard), Render dùng file Blueprint khai báo hạ tầng dạng IaC và bắt buộc secret không ghi thẳng giá trị.

### Exercise 3.3: Pipeline CI/CD Cloud Run

`cloudbuild.yaml` chạy tuần tự: (1) `test` — cài deps + chạy pytest; (2) `build` — `docker build` image tag `$COMMIT_SHA` và `latest`, dùng layer cache; (3) `push` — đẩy image lên Container Registry; (4) `deploy` — `gcloud run deploy` với `min-instances=1`, `max-instances=10`, secret lấy từ Secret Manager. `service.yaml` khai báo thêm autoscaling, probe `/health` và `/ready`.

---

## Part 4: API Security

### Exercise 4.1: API key authentication

Bản develop bật bằng `AGENT_API_KEY=secret-key-123 python app.py`. Header `X-API-Key` phải trùng `AGENT_API_KEY`; thiếu/sai → 401, đúng → 200.

Output thật:

```
# Không có key
HTTP/1.1 401 Unauthorized

# Có key đúng (X-API-Key: secret-key-123)
HTTP/1.1 200 OK

# Key sai
403
```

### Exercise 4.2: JWT authentication

Lấy token đúng endpoint/account:

```bash
curl -i -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"student","password":"demo123"}'
```

`student` giới hạn 10 request/phút. Token nhận được có độ dài 168 ký tự.

```
# Không có token
401

# Có Authorization: Bearer <token>
200
```

### Exercise 4.3: Rate limiting

```bash
for i in $(seq 1 14); do
  curl -i -s -X POST http://localhost:8000/ask \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question":"test"}'
done
```

Kết quả thật (limit 10 req/phút cho `student`):

```
200 200 200 200 200 200 200 200 200 429 429 429 429 429
```

Response 429 có header `Retry-After: 59`. (Token đã che khi dán bài.)

### Exercise 4.4: Cost guard

Cộng dồn chi phí (tính theo token) vào Redis; nếu vượt `DAILY_BUDGET_USD` / `MONTHLY_BUDGET_USD` → **402**. Cần cả rate limit và cost guard vì: rate limit bảo vệ *tốc độ* (chặn spam), cost guard bảo vệ *tiền* (chặn cháy ngân sách kể cả khi gọi chậm).

---

## Part 5: Scaling & Reliability

- **Liveness `/health`** = process còn sống; trả 200 kể cả khi Redis chết.
- **Readiness `/ready`** = sẵn sàng nhận traffic; 503 khi Redis không kết nối được.
- **Stateless:** state lưu trong Redis, không lưu trong RAM, vì mỗi instance có bộ nhớ riêng nên scale ngang sẽ mất state.

```bash
cd 05-scaling-reliability/production
touch .env.local
docker compose -p k5-day14-scaling up -d --build --scale agent=3
python test_stateless.py
docker compose -p k5-day14-scaling down
```

Output thật của `test_stateless.py` (5 câu trong cùng session, đi qua 3 instance khác nhau):

```
Request 1: [instance-b3781a]   Q: What is Docker?
Request 2: [instance-fce106]   Q: Why do we need containers?
Request 3: [instance-5d562a]   Q: What is Kubernetes?
Request 4: [instance-b3781a]   Q: How does load balancing work?
Request 5: [instance-fce106]   Q: What is Redis used for?
------------------------------------------------------------
Total requests: 5
Instances used: {'instance-5d562a', 'instance-fce106', 'instance-b3781a'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

Kết luận: 3 instance khác nhau phục vụ 5 request nhưng history vẫn đủ 10 message → state nằm trong Redis chứ không trong RAM từng instance. Nếu lưu RAM, các request rơi vào instance khác sẽ không thấy history cũ.

---

## Part 6: Final Project — Output `check_production_ready.py`

Đã chạy đầy đủ trên máy có Docker. Kết quả:

```
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

Image đo được: **56 MB** (< 500 MB). `docker stop`: exit code 0 trong **0.6s**.

Đã deploy chính code này lên Railway và chạy `check_production_ready.py --public-url <URL>` → **`PASS 12/12`**, `42/42 checks passed` (thêm check Public URL `/health` → 200).

---

## AI log

- Hỏi: hướng dẫn/viết code cho Part 6 (`06-lab-complete/`) và chạy benchmark Part 7.
- Nhận: gợi ý code cho `app/config.py`, `app/redis_client.py`, `app/auth.py`, `app/rate_limiter.py`, `app/cost_guard.py`, `app/main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`; cách chạy load test/eval.
- Tự kiểm tra: tự chạy `python check_production_ready.py` → `PASS 12/12`; tự chạy `load_test.py` và `eval/run_eval.py`, đọc lại từng file code và giải thích được từng endpoint/cấu hình.
