# Day 12 Lab - Mission Answers

**Student Name:** Ha Vu Anh  
**Student ID:** 2A202600571  
**Date:** 12/06/2026  

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
Trong code của phiên bản basic (`01-localhost-vs-production/develop/app.py`), có các anti-patterns sau:
1. **Hardcoded API Key (`openai_api_key = "sk-..."`):** Khoá bí mật (secrets) được ghi trực tiếp trong mã nguồn, dễ bị lộ khi commit code lên GitHub.
2. **Fixed Port (`port=8000`):** Port chạy ứng dụng bị cố định cứng. Trên môi trường cloud, port thường được cấp phát động qua biến môi trường `PORT`.
3. **Hardcoded Debug Mode (`debug=True`):** Bật chế độ debug ở production có thể làm lộ thông tin hệ thống nhạy cảm (stack trace) khi có lỗi.
4. **Không có Health Check (`/health`, `/ready`):** Các nền tảng Container Orchestrator (như K8s, Cloud Run) không thể giám sát trạng thái sống/chết của container để tự khởi động lại khi gặp sự cố.
5. **Không xử lý Graceful Shutdown:** Ứng dụng kết thúc đột ngột khi nhận tín hiệu SIGTERM/SIGINT, làm ngắt quãng các request đang xử lý dở dang và có thể gây lỗi dữ liệu.
6. **Sử dụng print() thay cho Structured Logging:** Ghi log bằng hàm `print()` thông thường gây khó khăn cho việc thu thập, tìm kiếm và phân tích log tự động (như ELK, Grafana Loki).

### Exercise 1.3: Comparison table

| Feature | Develop (Basic) | Production (Advanced) | Why Important? (Tại sao quan trọng?) |
|---------|---------|------------|----------------|
| **Config** | Hardcode trong code | Đọc từ Environment Variables (`.env`) | Dễ dàng thay đổi cấu hình giữa các môi trường (Dev/Staging/Prod) mà không cần sửa code; bảo mật secrets. |
| **Health Check** | Không hỗ trợ | Có endpoint `/health` & `/ready` | Giúp Load Balancer và Cloud Platform biết khi nào container chạy tốt để định tuyến traffic, và restart container khi bị treo. |
| **Logging** | Dùng `print()` | Dùng JSON Structured Logging | Giúp hệ thống quản lý log tập trung dễ dàng parse, lọc, và tìm kiếm thông tin lỗi nhanh chóng. |
| **Shutdown** | Tắt đột ngột | Xử lý tín hiệu `SIGTERM` (Graceful) | Cho phép ứng dụng hoàn thành các request đang chạy và đóng các kết nối tới DB/Redis an toàn trước khi tắt hoàn toàn. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. **Base image:** `python:3.11-slim` (Một phiên bản Linux Debian tối giản được cài sẵn Python 3.11, giúp giảm dung lượng image).
2. **Working directory:** `/app` (Thư mục làm việc mặc định bên trong container nơi code được sao chép và thực thi).
3. **Tại sao COPY requirements.txt trước?:** Để tận dụng cơ chế Docker cache layer. Docker sẽ chỉ build lại layer cài đặt dependencies khi file `requirements.txt` có sự thay đổi, giúp tăng tốc độ build đáng kể.
4. **CMD vs ENTRYPOINT khác nhau thế nào?:** 
   - `ENTRYPOINT` định nghĩa câu lệnh cố định sẽ luôn được chạy khi container start (ví dụ: `uvicorn`).
   - `CMD` định nghĩa các tham số mặc định truyền vào `ENTRYPOINT` (hoặc câu lệnh mặc định nếu không khai báo ENTRYPOINT). Các tham số này có thể dễ dàng bị ghi đè (override) khi chạy lệnh `docker run`.

### Exercise 2.3: Image size comparison
Sau khi build thử cả 2 image:
- **Develop (Single-stage, full base):** ~920 MB
- **Production (Multi-stage, slim base):** ~280 MB
- **Difference:** Giảm khoảng **70%** dung lượng image.

*Giải thích:* Multi-stage build cho phép chia làm 2 giai đoạn: Giai đoạn 1 (Builder) cài đặt các công cụ build nặng (gcc, compilers) để build bánh xe (wheels); Giai đoạn 2 (Runtime) chỉ copy kết quả compiled package sang một base image slim mới, bỏ lại toàn bộ compiler và cache của pip.

### Exercise 2.4: Docker Compose stack
- **Các services được start:** `agent` (API application), `redis` (database lưu session/rate limiting), `nginx` (reverse proxy kiêm load balancer).
- **Cách các services giao tiếp:** Nginx mở cổng công khai `80` nhận traffic từ client. Nginx định tuyến các request đến các container `agent` theo cơ chế Round Robin. Các agent lưu trữ và lấy dữ liệu phiên làm việc từ container `redis` thông qua mạng nội bộ Docker (mặc định cổng `6379`).
- **Sơ đồ kiến trúc (Architecture Diagram):**
  ```
  Client (Port 80) ──> [ Nginx Load Balancer ]
                                │ (Round-Robin)
                   ┌────────────┼────────────┐
                   ▼            ▼            ▼
               [ Agent 1 ]  [ Agent 2 ]  [ Agent 3 ]
                   │            │            │
                   └────────────┼────────────┘
                                ▼
                       [ Redis (Port 6379) ]
  ```

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- **URL:** [https://soothing-benevolence-production-f174.up.railway.app](https://soothing-benevolence-production-f174.up.railway.app)
- **Screenshot:** [Link dashboard](screenshots/dashboard.png) (Tham khảo trong repo)

### Exercise 3.2: Deploy Render (Comparison)
- **So sánh `render.yaml` và `railway.toml`:**
  - `railway.toml` dùng để cấu hình chi tiết cách Railway build và start ứng dụng đơn lẻ (build command, watch paths, start command).
  - `render.yaml` (Render Blueprints) theo chuẩn Infrastructure as Code (IaC), cho phép khai báo toàn bộ hệ thống gồm nhiều service liên kết với nhau (ví dụ: khai báo Web Service chạy cùng lúc với Database PostgreSQL và Redis kèm cấu hình biến môi trường tự động liên kết).

---

## Part 4: API Security

### Exercise 4.1-4.3: Test results

Dưới đây là kết quả kiểm tra API Security chạy thử cục bộ trên máy:

*   **Không truyền API Key (X-API-Key):** Trả về `401 Unauthorized`
    ```json
    HTTP/1.1 401 Unauthorized
    content-type: application/json
    
    {"detail":"Invalid or missing API key. Include header: X-API-Key: <key>"}
    ```

*   **Truyền đúng API Key:** Trả về `200 OK`
    ```json
    HTTP/1.1 200 OK
    content-type: application/json
    
    {
      "question": "What is Docker?",
      "answer": "Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!",
      "model": "gpt-4o-mini",
      "timestamp": "2026-06-12T08:41:38.049014+00:00"
    }
    ```

*   **Gọi liên tục để kiểm tra Rate Limiting (Giới hạn 20 req/min):**
    ```
    Request 1: 200 OK
    ...
    Request 19: 200 OK
    Request 20: 429 Too Many Requests (Rate limit exceeded)
    Request 21: 429 Too Many Requests
    ```

### Exercise 4.4: Cost guard implementation
- **Cách tiếp cận:** Sử dụng cơ sở dữ liệu Redis để lưu trữ lượng chi phí tích luỹ trong ngày của mỗi user dưới dạng key: `budget:{user_id}:{today}`.
- Mỗi khi có request gửi đến `/ask`, hệ thống ước lượng số token của câu hỏi (ở đây là `tổng số từ * 2`).
- Phí dự tính = `(input_tokens / 1000) * 0.00015` (phí OpenAI gpt-4o-mini).
- Hệ thống gọi hàm `check_budget(user_id)` để so sánh tổng chi phí đã dùng cộng với chi phí ước lượng mới có vượt quá budget quy định (`DAILY_BUDGET_USD` mặc định là `$5.0`). Nếu vượt quá, trả về lỗi `402 Payment Required`.
- Sau khi nhận kết quả từ LLM, hệ thống tính toán chi phí token trả về và cộng dồn vào Redis bằng lệnh `incrbyfloat` đồng thời đặt thời gian hết hạn cho key là 25 giờ (`expire`).

---

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes
1. **Liveness & Readiness Probes (Health checks):**
   - Endpoint `/health` kiểm tra xem container ứng dụng có đang sống không.
   - Endpoint `/ready` ping tới Redis. Nếu kết nối tới Redis bị gián đoạn, ứng dụng trả về status `503 Service Unavailable`, báo cho Load Balancer ngắt routing traffic tới instance lỗi này.
2. **Graceful Shutdown:** 
   - Đăng ký lắng nghe tín hiệu `SIGTERM`. Khi container bị dừng, biến trạng thái `_is_ready` chuyển thành `False` lập tức (để liveness/readiness probe trả về lỗi và Load Balancer không đẩy request mới về container này nữa).
   - Container sẽ đợi tối đa 30 giây để xử lý nốt các request hiện tại trước khi tắt hoàn toàn các kết nối DB/Redis.
3. **Stateless Design:**
   - Loại bỏ lưu trữ history trong bộ nhớ RAM (In-memory dict). Toàn bộ lịch sử hội thoại được đẩy sang cơ sở dữ liệu tập trung Redis.
   - Nhờ đó, nếu chạy song song 3 instance (Agent 1, Agent 2, Agent 3) thông qua Nginx Load Balancer, request của một user có thể được xử lý bởi bất kỳ instance nào mà không lo bị mất lịch sử chat.
