# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** Nhóm Nguyễn Trương Công Nhị và Phạm Hoàng Long
**Ngày:** 14/04/2026

> **Hướng dẫn:** So sánh Day 08 (single-agent RAG) với Day 09 (supervisor-worker).
> Phải có **số liệu thực tế** từ trace — không ghi ước đoán.
> Chạy cùng test questions cho cả hai nếu có thể.

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | N/A | 0.51 | N/A | Dựa trên JSONL trace Day 09 |
| Avg latency (ms) | ~1500 | ~15000 | Cao hơn | Đặc biệt có query lên tới 65000ms do MCP/Toolcall chậm |
| Abstain rate (%) | N/A (Trượt nhiều) | 30% | Cải thiện | % câu trả về "không đủ info" chính xác hơn |
| Multi-hop accuracy | Kém (Điểm 2-3) | Tốt (Điểm 5) | Tăng | Phản chiếu qua score của gq03/gq09 |
| Routing visibility | ✗ Không có | ✓ Có route_reason | N/A | |
| Debug time (estimate) | 25 phút | 5 phút | -20p | Thời gian tìm ra 1 bug dựa vào trace state |

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Tốt | Tốt |
| Latency | Thấp | Cao hơn |
| Observation | Nhanh gọn do chỉ gọi LLM 1 lần | Tốn thêm 1 lần LLM call Router |

**Kết luận:** Multi-agent không giúp ích gì cho Accuracy trên các query đơn giản (như FAQ, thông số SLA cơ bản), bù lại làm phình hệ thống và tốn thời gian chạy (latency cao hơn do chi phí overhead định tuyến).

---

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Thường bị thiếu ý | Cực kỳ chính xác |
| Routing visible? | ✗ | ✓ |
| Observation | Chỉ dựa được vào context chunker nên bị miss tài liệu liên quan policy | Thấy rõ pipeline call policy_worker và `check_access_permission`, bổ sung context rõ ràng |

**Kết luận:** Điểm sáng rõ ràng của Multi-Agent. Với gq03 (Level 3 access), nhờ Worker logic tách biệt để gọi MCP Tool mà Agent dễ dàng trích nội dung ẩn đằng sau thay vì chỉ phụ thuộc vào cơ sở dữ liệu Vector.

---

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | Thấp (thường nhét thêm bịa) | Cao, đúng kỳ vọng |
| Hallucination cases | Bịa ra content (ví dụ version 3) | Giảm mạnh |
| Observation | Dễ assume và kết luận dù dữ liệu thiếu | Xử lý triệt để ngoại lệ Flash Sale / Policy v3 trước tháng 02/2026 |

**Kết luận:** Multi-agent đã khắc phục được chứng bệnh "ảo giác" (hallucinations) trong các queries policy bằng cách tách context qua Policy_Tool, giúp Worker Synthesis không phải chịu gánh nặng tự phân tích exception quá khó khăn, đảm bảo tự tin (confidence) tụt xuống và kích hoạt logic Abstain an toàn.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: 25 phút
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic
  → Nếu retrieval sai → test retrieval_worker độc lập
  → Nếu synthesis sai → test synthesis_worker độc lập
Thời gian ước tính: 5 phút
```

**Câu cụ thể nhóm đã debug:** _(Mô tả 1 lần debug thực tế trong lab)_
Với câu `gq03` liên quan quyền cấp Level 3 access, answer đầu ra bị thiếu do context không đủ. Truy lại trace thấy query dính ngẫu nhiên vô `retrieval_worker`. Nhóm fix bằng cách thêm từ khóa `"access level"` và `"Level 3 access"` vào prompt router cho `policy_tool_worker`, giúp sau đó query route chính xác tới tool và parse được data đúng.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa retrieval_worker độc lập |
| A/B test một phần | Khó — phải clone toàn pipeline | Dễ — swap worker (graph node) |

**Nhận xét:**
Multi-agent thực sự thiết kế cho doanh nghiệp khi nhu cầu thêm logic API mới. Graph cho phép cắm-rút module linh hoạt (Plug-and-play).

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 LLM call | 2 LLM calls (1 route + 1 synthesis) |
| Complex query | 1 LLM call | >= 2 LLM calls + MCP calls |
| MCP tool call | N/A | Tốn kém resource và thời gian delay API |

**Nhận xét về cost-benefit:**
Hệ thống Multi-agent đắt gấp đôi Single Agent về call LLM. Cần cân nhắc kỹ: đối với internal support system thì bù trừ bằng tính chính xác có thể chấp nhận được, nhưng nếu deploy public app lượng query lớn sẽ gây cạn kiệt API Budget.

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**
1. Độ tin cậy (Accuracy / Trust) tăng lên rõ rệt trên các truy vấn khó (Multi-hop)
2. Mở rộng cực kỳ dễ dàng (MCP Tools / LangGraph state handling), code module hoá tối đa và nhàn cho Developer khi debug.

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**
1. Chi phí (Cost/Latency): Đắt hơn và chậm hơn hản. Dư thừa đối với các câu FAQ đơn giản.

> **Khi nào KHÔNG nên dùng multi-agent?**
Dự án có ngân sách thấp, giới hạn rate limit chặt chẽ, hoặc app phục vụ user hỏi đáp nhanh các thông tin tĩnh.

> **Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**
Triển khai caching layer trước Supervisor để các query giống nhau (FAQ) trả lời ngay lập tức, tiết kiệm chi phí LLM, cũng như dùng local nhỏ hơn để phân loại ý định (Router).