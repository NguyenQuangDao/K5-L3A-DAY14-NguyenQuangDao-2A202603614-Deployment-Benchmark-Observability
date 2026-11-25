# Benchmark & Observability Report — Day 14

> Mọi con số dưới đây lấy từ report JSON/CSV thật, không ước lượng.

**Họ tên:** Nguyen Quang Dao
**Ngày chạy:** 2026-11-25
**Môi trường:** macOS (Apple Silicon), Docker Desktop 4 CPU / 8GB RAM

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Ở tải vừa p50 ~190–200 ms, p95 ~220–250 ms; ngưỡng 500 ms chừa dư địa cho tail latency |
| Error rate `/ask` | < 2 % | Mock LLM ~1% lỗi upstream; 2% giữ error budget mà không báo động ồn |
| Accuracy trên golden dataset | ≥ 80 % | Là ngưỡng quality gate chặn regression; bản fix đạt 100% |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.86 | 194.7 | 228.6 | 1702.6 | 0.00% | PASS |
| 10 | 41.11 | 190.5 | 222.6 | 1705.4 | 0.00% | PASS |
| 50 | 103.42 | 200.4 | 253.1 | 1719.6 | 0.00% | PASS |
| 100 | 46.49 | 671.6 | 4224.4 | 4714.3 | 0.00% | FAIL (p95) |

**Nhận xét:** RPS tăng từ 1→50 nhưng **không tuyến tính** và tới concurrency 100 thì RPS giảm còn ~46, p95 tăng vọt lên >4s. Nguyên nhân: mock LLM chạy async nhưng CPU/event loop bị bão hoà khi 100 request cạnh tranh, latency phình lên do queue.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 190.3 | 218.7 | 229.6 |
| 0.03 (mặc định) | 226.1 | 221.7 | 1701.6 |
| 0.1 | 330.6 | 1692.3 | 1711.0 |

**Nhận xét:** `p99` nhạy nhất với request chậm: slow rate chỉ 3% đã làm p99 nhảy từ ~230ms lên ~1.7s trong khi avg chỉ tăng ~36ms. Vì vậy **SLO không nên đặt theo average** — average che giấu nhóm user chịu tail latency.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.7 | 108.8 | 113.7 |
| Tổng cost (USD) | 0.000412 | 0.000758 | 0.000790 |
| Cost / câu đúng (USD) | 0.00041175 | 0.00003607 | 0.00003436 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Thêm entry `["jwt","api key"]` vào `KNOWLEDGE_BASE` mô tả JWT là token có chữ ký, có thời điểm hết hạn |
| scaling-03 | cpu, memory, custom metrics | Thêm entry `["hpa","kubernetes","autoscal"]` mô tả HPA scale theo CPU, memory, custom metrics |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

v2 (có retrieval/RAG) dùng **~2 lần token mỗi câu** (108.8 vs 57.7) và latency tăng nhẹ, nhưng accuracy tăng từ 4.3% lên 91.3%. Quan trọng hơn, **cost trên mỗi câu trả lời đúng** của v2 rẻ hơn ~11 lần (0.00003607 vs 0.00041175), nên tăng chi phí tổng là đáng giá.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals) → `screenshots/grafana-dashboard.png`
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian) → `screenshots/jaeger-slow-trace.png`
- [x] Một trace lỗi trong Jaeger (có event `exception`) → `screenshots/jaeger-error-trace.png`
- [x] Trang Alerts của Prometheus với ≥2 alert đang **firing** → `screenshots/prometheus-alert-firing.png`

Ảnh dashboard chụp lúc đang chạy Locust: p95 ≈ 296 ms, error rate 0.69%, ~18.5 req/s, Instances up = 2, LLM cost (1h) ≈ $0.276, panel "Requests/s theo status" có cả 200 và 503.

### 4.1b Trả lời Exercise 7.4

1. **p95 và avg, khoảng cách giữa chúng:** trên dashboard p95 ≈ 296 ms trong khi p50 ≈ 200 ms. Khoảng cách lớn chứng tỏ tail latency: một nhóm nhỏ request bị `MOCK_SLOW_RATE` đẩy lên ~1.7s, còn đa số vẫn nhanh. Average sẽ nằm đâu đó ở giữa và che mất nhóm user chịu chậm — đó là lý do đọc p95/p99 chứ không đọc avg.
2. **Nginx có chia đều traffic cho 2 instance?** Có — panel "Requests/s theo instance" cho thấy 2 đường gần bằng nhau (~7.5 req/s mỗi instance khi tổng ~15 req/s), vì `proxy_pass http://agent:8000` với `resolve` phân phối round-robin.
3. **Vì sao input tokens/s > output tokens/s?** Prompt gửi lên gồm cả system prompt + context retrieval + câu hỏi (69 token), còn câu trả lời lấy từ knowledge base ngắn hơn (31 token) — với RAG, phần input luôn phình to vì nhét tài liệu vào prompt.
4. **`curl http://localhost:8080/metrics` trả gì, vì sao?** Trả **404**. Nginx có `location = /metrics { return 404; }` để không lộ metric (route, lưu lượng, chi phí) ra Internet; chỉ Prometheus scrape trực tiếp `agent:8000` trong mạng nội bộ.

Bằng chứng: `curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/metrics` → `404`.

### 4.1c Quality gate trong CI (Exercise 7.3)

`eval/run_eval.py` trả **exit code 1** khi accuracy < `--min-accuracy` hoặc có regression so với `--baseline`, nên dùng trực tiếp để chặn merge:

```yaml
name: quality-gate
on: [pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run agent v2 and eval
        working-directory: 06-lab-complete/benchmark-observability/develop
        run: |
          pip install -r requirements.txt
          AGENT_VERSION=v2 MOCK_ERROR_RATE=0 python app.py &
          sleep 3
          python eval/run_eval.py --url http://localhost:8000 \
            --min-accuracy 1.0 --out reports/eval_ci.json
```

Bước cuối fail ⇒ job fail ⇒ PR bị chặn merge. Đã kiểm chứng thật:

- `run_eval.py --min-accuracy 1.0 --baseline reports/eval_v2.json` (agent v2 sau khi sửa KB) → `Quality gate ... ✅ PASS`, **exit code 0**.
- `run_eval.py --min-accuracy 1.0 --baseline reports/eval_v2.json` (agent v1) → accuracy 4.3%, **20 câu bị regression**, `Quality gate ... ❌ FAIL`, **exit code 1**. Đây chính là tín hiệu CI dùng để chặn merge.

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | AgentHighErrorRate | ~4 phút (241s tính từ lúc bắt đầu tạo tải; rule `for: 1m`) | Error rate |
| B | `MOCK_SLOW_RATE=0.3` | AgentHighLatencyP95 (cùng lúc AgentHighErrorRate) | 2 phút 14s từ lúc tạo tải (3m55s từ lúc đổi config; rule `for: 2m`) | Latency p95 |
| C | `LLM_MODEL=mock-llm-large` | LLMCostBurnRateHigh | 2 phút 19s từ lúc tạo tải (2m45s từ lúc đổi config) | Cost burn rate USD/giờ |
| D | `docker pause` 1 instance | AgentInstanceDown | 41s (rule `for: 30s`) | Instances up |
| E | `AGENT_VERSION=v1` | (không alert) — đã chạy tải 40 user và xác nhận danh sách firing rỗng | — | Retrieval hit ratio / bảng version |

Thời điểm firing lấy bằng cách poll `GET /api/v1/alerts` mỗi 5–6 giây trong lúc chạy Locust. Ảnh `prometheus-alert-firing.png` chụp đúng lúc **AgentHighErrorRate** và **AgentHighLatencyP95** cùng FIRING (nhóm `agent-slo` hiện "FIRING (2)").

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Bằng **eval chất lượng / giám sát mô hình**: hạ tầng metrics (latency, error, cost) không đo được câu trả lời đúng/sai. Cần golden dataset eval chạy trong CI trước deploy, và theo dõi retrieval hit ratio + đối chiếu version đang phục vụ.

### 4.3 Debug bằng trace

- `trace_id`: `ca1992cf7805471dddf9b1e8fcb8d1d8`
- Tổng thời gian: **1705.2** ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (**1686.8** ms, 98.9%); `agent.retrieve_context` chỉ 16.6ms (1.0%)
- Trace lỗi (dùng cho `jaeger-error-trace.png`): `trace_id` `67ab3400e0554f1b051798e61d18f0c2`, `POST /ask` trả **503**, span `chat mock-llm-small` có event `exception` (`LLMError: Upstream LLM error: 503 Service Unavailable (mock)`), duration 90.5ms.
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T13:04:01.232778+00:00", "level": "INFO", "service": "observable-agent", "instance": "49c5cf165131", "event": "llm_call", "trace_id": "ca1992cf7805471dddf9b1e8fcb8d1d8", "span_id": "844cfbde2c33e7a9", "request_id": "2f7d17e71ecb", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 83, "output_tokens": 44, "cost_usd": 3.9e-05, "llm_ms": 1686.5}
{"ts": "2026-11-25T13:04:01.233235+00:00", "level": "INFO", "service": "observable-agent", "instance": "49c5cf165131", "event": "http_request", "trace_id": "ca1992cf7805471dddf9b1e8fcb8d1d8", "span_id": "844cfbde2c33e7a9", "request_id": "2f7d17e71ecb", "method": "POST", "route": "/ask", "status": 200, "ms": 1704.6}
```

Dòng log của trace lỗi (grep cùng `trace_id`):

```json
{"ts": "2026-11-25T13:03:57.126940+00:00", "level": "INFO", "service": "observable-agent", "instance": "c62c5ca0c23c", "event": "llm_error", "trace_id": "67ab3400e0554f1b051798e61d18f0c2", "span_id": "bbdec85a1a92dfb6", "request_id": "398007300e40", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
{"ts": "2026-11-25T13:03:57.127249+00:00", "level": "INFO", "service": "observable-agent", "instance": "c62c5ca0c23c", "event": "http_request", "trace_id": "67ab3400e0554f1b051798e61d18f0c2", "span_id": "bbdec85a1a92dfb6", "request_id": "398007300e40", "method": "POST", "route": "/ask", "status": 503, "ms": 90.1}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 60.27 | 200 | 240 | 1700 | 66 |
| 3 | 59.41 | 200 | 230 | 1700 | 76 |

**Giải thích kết quả:** Scale từ 1 → 3 instance gần như **không cải thiện p95/p99** (vẫn ~230/1700 ms) vì nút thắt là **latency của mock LLM** (`MOCK_SLOW_RATE` tạo ~3% request chậm ~1.7s), không phải thiếu CPU/instance. Thêm instance chỉ giúp khi event loop/queue bão hoà, không rút ngắn được thời gian của từng call LLM.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. Average che giấu tail latency; phải đo p95/p99 và đặt SLO theo percentile.
  2. Eval + quality gate bắt được regression về chất lượng mà metrics hạ tầng không thấy.
  3. Metrics, traces, logs liên kết với nhau qua `trace_id` để truy từ dashboard → trace → log.

- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - Alert cho retrieval hit ratio (phát hiện KB hỏng), synthetic check từ bên ngoài để bắt lỗi ở tầng LB/504, và alert gửi qua Alertmanager tới Slack/PagerDuty.
