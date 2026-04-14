# System Architecture — Lab Day 09 (Routing Decisions Log)

**Nhóm:** Nhóm 1  
**Ngày:** 14/04/2026  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

> Mô tả ngắn hệ thống của nhóm: chọn pattern gì, gồm những thành phần nào.

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):**
Hỗ trợ chia nhỏ các logic phức tạp thành các module có chức năng chuyên biệt. Việc điều phối các truy vấn dễ dàng hơn bằng cơ chế Route định tuyến (Supervisor -> Worker), giúp tăng tính modular, dễ dàng mở rộng thêm các Worker mới khi có requirement (như thêm tool mới). Không những vậy, pattern này giúp dễ dàng tích hợp HITL (Human-in-the-loop) với các tác vụ high-risk.

---

## 2. Sơ đồ Pipeline

**Sơ đồ thực tế của nhóm:**

```text
User Request
     │
     ▼
┌──────────────┐  (LLM Router + Structured Output)
│  Supervisor  │  ← quyết định route_decision, route_reason, risk_high, needs_tool
└──────┬───────┘
       │
   [route_decision]
       ├─────────────────────┬────────────────────┐
       │                     │                    │
       ▼                     ▼                    ▼
Retrieval Worker      Policy Tool Worker     Human Review
  (evidence)         (policy check + MCP)      (HITL)
       │                     │                    │
       └─────────┬───────────┴────────────────────┘
                 │
                 ▼
           Synthesis Worker
             (answer + cite)
                 │
                 ▼
              Output
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích câu hỏi đầu vào để định tuyến đến Worker phù hợp nhất |
| **Input** | `task` (câu hỏi của user) |
| **Output** | `supervisor_route`, `route_reason`, `risk_high`, `needs_tool` |
| **Routing logic** | Sử dụng LLM (`gpt-4o-mini`) kết hợp `with_structured_output` class RouterDecision để phân tích intent |
| **HITL condition** | Trigger nếu `risk_high=True` hoặc bắt gặp chuỗi báo lỗi lạ (e.g. `err-`) cần Human Approval |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Tính toán vectors query và trích xuất tài liệu (chunks) tương đồng nhất |
| **Embedding model** | `LocalEmbedder` |
| **Top-k** | 3 |
| **Stateless?** | Yes |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Áp dụng rules động (dynamic rules) dựa trên ngữ cảnh để kiểm tra các policy exception |
| **MCP tools gọi** | `search_kb`, `get_ticket_info`, `check_access_permission` |
| **Exception cases xử lý** | Flash Sale, sản phẩm kỹ thuật số/đã kích hoạt (không được hoàn tiền), thay đổi version chính sách (v3 vs v4) trước/sau 01/02/2026 |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | `gpt-4o-mini` |
| **Temperature** | 0.1 |
| **Grounding strategy** | Chỉ dựa vào context chunk (strict evidence), liệt kê policy exception. Yêu cầu trích dẫn rõ nguồn dạng `[tên_file]` |
| **Abstain condition** | Nếu không có context hoặc evidence sai với task, trả về string "Không đủ thông tin trong tài liệu nội bộ" và confidence thấp |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| search_kb | query, top_k | chunks, sources |
| get_ticket_info | ticket_id | ticket details |
| check_access_permission | access_level, requester_role | can_grant, approvers, notes |
| *Tương lai* | *TBD* | *TBD* |

---

## 4. Shared State Schema

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| task | str | Câu hỏi đầu vào | supervisor đọc |
| supervisor_route | str | Worker được chọn | supervisor ghi |
| route_reason | str | Lý do route | supervisor ghi |
| retrieved_chunks | list | Evidence từ retrieval | retrieval ghi, synthesis đọc |
| policy_result | dict | Kết quả kiểm tra policy | policy_tool ghi, synthesis đọc |
| mcp_tools_used | list | Tool calls đã thực hiện | policy_tool ghi |
| final_answer | str | Câu trả lời cuối | synthesis ghi |
| confidence | float | Mức tin cậy | synthesis ghi |
| hitl_triggered | bool | Cờ đánh dấu HITL (Human Review) | human_review ghi |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó — không rõ lỗi ở đâu | Dễ hơn — test từng worker độc lập (có log riêng) |
| Thêm capability mới | Phải sửa toàn prompt, dễ gây phình | Khai báo thêm worker/MCP tool riêng biệt |
| Routing visibility | Không có | Có route_reason trong trace, thể hiện rõ intent hiểu |
| Resource management | Gọi tất cả tools 1 lúc (dư thừa) | Chỉ gọi call cần thiết thông qua định tuyến |

**Nhóm điền thêm quan sát từ thực tế lab:**
Pipeline mới mang lại trải nghiệm debug vô cùng nhàn. Chỉ cần nhìn qua file state log `.json` có thể biết chính xác câu nào bị lạc đường (lỗi supervisor) hay lỗi do sai data (lỗi worker) dựa trên record của `workers_called` và `mcp_tools_used`.

---

## 6. Giới hạn và điểm cần cải tiến

1. Thời gian phản hồi (latency) bị tăng so với day 8 do tốn thêm 1 nhịp gọi LLM tại Supervisor trước khi đến bước Worker và Synthesis.
2. Quản lý trạng thái (`AgentState`) bắt đầu trở nên phức tạp và to đùng khi thêm nhiều history và log vào state qua từng Edge.
3. Khi policy ngày một phức tạp, việc hard-code exception logic trong `policy_tool.py` có thể gây khó khăn trong maintainance. Cần chuyển hướng sang LLM-based policy evaulation toàn diện hơn.