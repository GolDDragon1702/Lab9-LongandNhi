# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Nhóm 1  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Shine | Supervisor Owner | shine@company.internal |
| Shine | Worker Owner | shine@company.internal |
| Shine | MCP Owner | shine@company.internal |
| Shine | Trace & Docs Owner | shine@company.internal |

**Ngày nộp:** 14/04/2026  
**Repo:** day09/lab  
**Độ dài khuyến nghị:** 600–1000 từ

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

**Hệ thống tổng quan:**
Kiến trúc nhóm sử dụng là mô hình Supervisor-Worker thông qua StateGraph của LangGraph. Hệ thống có 1 Supervisor nhận queries và quyết định điều phối đến một trong ba branches: Retrieval Worker, Policy Tool Worker, hoặc Human Review (khi có yếu tố rủi ro). Sau khi xử lý lấy các evidences theo từng Worker, mạch luồng sẽ dồn tụ lại bằng Synthesis Worker và đưa ra output trả lời. Kiến trúc này giúp chúng tôi dễ dàng scale-up (như thêm tool lookup cho Policy Worker) mà không lo bị phình Prompt ở Master Node. Truyền tải Context thông qua AgentState chung, lưu toàn bộ event trace log trong property `history`.

**Routing logic cốt lõi:**
> Supervisor của chúng tôi sử dụng LLM Classifier với class Pydantic (Structured Output) nhằm trích xuất routing field. Node Supervisor nhận prompt định hướng các task policy chuyên sâu sang nhánh `policy_tool_worker`, các task lỗi nặng hay cần review thì set flag `risk_high` nhằm đi vào nhánh `human_review` (trigger HITL), và phần lớn default query vào nhánh `retrieval_worker`.

**MCP tools đã tích hợp:**
> Node Policy Tool Worker được quyền trực tiếp gọi hệ thống Server Tools để hỗ trợ trả lời.

- `search_kb`: Công cụ thay thế để tìm lại chunks nếu user hỏi policy nhưng ban đầu Supervisor chưa gửi kèm chunks.
- `get_ticket_info`: Lấy snapshot và tình trạng ticket đang assign để trả lời những ticket case như `P1-LATEST`.
- `check_access_permission`: Tool cấp quyền cho phép truy vấn logic access level, ví dụ cho "Level 2/Level 3 access đối với Employee/Contractor".

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

**Quyết định:** Sử dụng LLM Routing bằng LangChain `with_structured_output` thay cho cơ chế Keyword matching ở AgentState.

**Bối cảnh vấn đề:**
Rất nhiều queries của người dùng hay có câu chữ khó lường (ví dụ mập mờ giữa hỏi chính sách access hay là hỏi emergency). Nếu match keyword đơn thuần thì dễ bị false-route và dẫn tới Synthesis sai hoặc thiếu tool calls. Nhóm cần một cơ chế để Router hiểu ngữ cảnh.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Keyword Matching (if/else) | Nhanh, latency < 10ms, tiết kiệm cost | Dễ sụp đổ với từ đồng nghĩa, khó scale rules |
| LLM-based Classifier | Hiểu sâu ngữ cảnh và linh hoạt | Latency cao (~1000-2000ms), tốn cost |

**Phương án đã chọn và lý do:**
Nhóm ưu tiên LLM-based Classifier (GPT-4o-mini). Vì hệ thống Support IT Helpdesk quan trọng nhất là giải quyết chính xác. 1 câu trả lời sai (vd sai policy do không lấy đúng Exception Document) sẽ gây tốn kém hơn nhiều so với vài nghìn vnđ LLM token chi phí. Hơn nữa, việc trả về schema structured output (có `route_reason`) mang tính self-reflective rất cao cho bước trace lỗi.

**Bằng chứng từ trace/code:**
Trace khi xử lý câu gq02, LLM Router có thể phát hiện đây là refund -> Policy Tool:
```json
"supervisor_route": "policy_tool_worker",
"route_reason": "The task involves assessing a refund request due to a manufacturing defect, which falls under complex rules regarding refunds and policies."
```

---

## 3. Kết quả grading questions (150–200 từ)

**Tổng điểm raw ước tính:** 84 / 96

**Câu pipeline xử lý tốt nhất:**
- ID: `gq03` — Lý do tốt: Truy vấn yêu cầu quyền Level 3 đa diện nhiều document. Nhóm điều hướng hoàn hảo qua Policy Tool Worker và MCP Server (`check_access_permission`) để nhận đủ dữ liệu và trả lời đầy đủ số lượng (3 người) cùng thông tin (IT Security là cao nhất). Confidence 0.59.

**Câu pipeline fail hoặc partial:**
- ID: `gq10` — Fail ở đâu: Thông tin policy hoàn tiền ngoại lệ với Flash Sale được LLM truy xuất chính xác rằng KHÔNG hoàn tiền, nhưng lại miss mất việc exception ghi đè và nhắc sai duration yêu cầu hoàn trả (hiện ra 7 ngày thay vì 5 ngày).
  Root cause: Context của Policy có chứa 7 ngày default, còn LLM Synthesis không cover triệt để thông số query.

**Câu gq07 (abstain):** Nhóm xử lý thế nào?
Cho `gq07` (tiền phạt vi phạm), AgentState không thể tìm ra kết quả trong ChromaDB do thiếu docs phạt tiền. Synthesis Worker xử lý đúng theo Abstain rule -> trả về "Không đủ thông tin trong tài liệu nội bộ" => Confidence tụt xuống 0.3.

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 2 workers không? Kết quả thế nào?
Có ghi nhận 2 workers trong pipeline (`human_review` route và sau đó redirect sang `retrieval_worker`). Do tính emergency "P1", `risk_high` trở thành true và kích hoạt HITL. Sau review tự động, nó lấy SLA. Tuy nhiên, kết quả trả lời mảng (2) Access Level 2 vẫn miss do context retrieval ko rẽ nhánh Tool để kiểm tra Role exception.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

**Metric thay đổi rõ nhất (có số liệu):**
Latency là thứ hiển nhiên nhất đổi mặt khi chuyển. Tại Day 08 lab, answer average dưới 2s. Tại lab chạy JSONL này (Day 09), Avg Latency nhảy lên trung bình 4500ms, cá biệt với case gọi 2 workers timeout dẫn tới delay 56000ms+ (65s cho gq02).

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**
Sự minh bạch (Transparency). Trace file là 1 phép màu. Dựa vào `route_reason` và chuỗi `history`, toàn bộ vòng đời Agent chạy trong pipeline sáng tỏ như ban ngày. Khi debug không cần console line by line mà chỉ việc nhúng thẳng state dict vào log.

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**
Truy vấn đơn giản (ví dụ "SLA ticket P1 là bao lâu?"). Single-agent có thể bắn prompt gộp cực nhanh để trả về, trong khi hệ thống Multi-Agent của lab làm cho truy vấn chui qua LLM Supervisor, nhả json rồi lại nạp cho LLM Synthesis. Quá rườm rà không cần thiết.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Shine | Cài đặt Supervisor node và logic | 1 |
| Shine | Implement Retrieval / Policy Worker | 2 |
| Shine | Mock system MCP Tools | 3 |
| Shine | Evaluate Trace và tài liệu | 4 |

**Điều nhóm làm tốt:**
Kiến trúc luồng (Graph configuration) được tổ chức file riêng cực kì sạch sẽ, state flow qua nodes chạy trơn tru tuyệt đối ko bị Crash key_error giữa chừng. Logic check edge cases cho HITL trigger tốt.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**
Phần Synthesis chưa refine nhắc nhở Abstain triệt để, thành ra LLM thỉnh thoảng vẫn huyên thuyên trả sai thông tin thay vì nói không biết đối với case thiếu context multi-hop.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**
Chúng tôi sẽ refine lại component AgentState và lược bỏ bớt các log property thừa gây cồng kềnh file, thay vào đó dùng Event Store chuyên dụng.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

Tôi sẽ tối ưu lại `retrieval_worker.py` bổ sung multi-query retrieval. Dựa vào trace của câu gq09, hệ thống không phát hiện policy phụ do query ghép quá dài, một query decomposition cho task tìm kiếm từ Supervisor sẽ tăng vọt accuracy cho các cases cross-doc tương tự.
