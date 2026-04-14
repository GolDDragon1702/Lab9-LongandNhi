# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Shine  
**Vai trò trong nhóm:** Supervisor Owner  
**Ngày nộp:** 14/04/2026  

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

**Module/file tôi chịu trách nhiệm:**
- File chính: `graph.py` (Supervisor Orchestrator)
- Functions tôi implement: `supervisor_node(...)`, `route_decision(...)`, và framework routing của LangGraph

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Tôi là người tạo ra "bộ não" điều phối của toàn bộ quy trình RAG Pipeline Multi-Agent này. Nhờ có `supervisor_node` thiết lập đúng state `needs_tool` và định tuyến ra `supervisor_route`, các output state của tôi trực tiếp nuôi (feed) nhánh đầu vào cho `workers/policy_tool.py` (Worker Owner) và `workers/retrieval.py`. Nếu Supervisor phân loại sai intent ngay từ nhịp đập tiên phong, toàn bộ Worker phía sau sẽ đổ vỡ vì chạy không đúng tool và sai function.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**
Trong `graph.py`, đoạn cài đặt `structured_llm` Langchain model (dùng Pydantic `RouterDecision`) ghi nhận công việc cấu trúc hoá output do tôi triển khai.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Sử dụng Pydantic Model (`RouterDecision`) để bọc Structred Output cho LLM Supervisor thay vì để Router trả về raw text và parse JSON thủ công bằng Regex.

**Lý do:**
Việc xử lý "Mạn đàm tự do" của LLM rất khó dự đoán trong production, đặc biệt OpenAIGenerator thi thoảng sẽ rào trước sau. Pydantic Model kết hợp `with_structured_output(...)` trực tiếp force LLM Call mapping 4 tham số: `route`, `route_reason`, `needs_tool`, `risk_high` trở thành JSON Schema valid 100%.

**Trade-off đã chấp nhận:**
Chúng ta chấp nhận phụ thuộc (Lock-in) vào các Model support Function Calling / JSON mode mạnh mẽ (GPT-4o-mini). Do đó không dễ dàng đem code này thay trực tiếp bằng mô hình Local Mistral 7B nhỏ lẻ được. Giá cả (cost/query) cũng là 1 rào cản.

**Bằng chứng từ trace/code:**
Code do tôi cài đặt:
```python
class RouterDecision(BaseModel):
    route: Literal["retrieval_worker", "policy_tool_worker", "human_review"] = Field(...)
    route_reason: str = Field(...)
    needs_tool: bool = Field(...)
    risk_high: bool = Field(...)

structured_llm = llm.with_structured_output(RouterDecision)
decision: RouterDecision = structured_llm.invoke([{"role": "system", "content": prompt}])
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Supervisor bỏ qua Human in the Loop (HITL) khi user yêu cầu thông tin về những lỗi chưa từng được known error "err-xxx" ở document, do LLM từ chối định khoản rủi ro.

**Symptom (pipeline làm gì sai?):**
Khi task request một "Err-" chưa biết, Supervisor vẫn trả `route="retrieval_worker"` và `risk_high=False`, Retrieval Worker không tìm thấy chunk, Output trả về "Không tìm thấy". Điều này trái với requirement là Error lạ phải được gửi sang Human Review cho admin.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**
Lỗi ở Routing (`graph.py`). Prompt của Supervisor chưa đủ sức mạnh để khiến mô hình GPT-4o-mini coi các cụm từ "err-" ngẫu nhiên (chỉ là text vô hại) trở thành rủi ro cao. LLM thiên vị việc "đơn giản hóa task cứu trợ thành lookup doc".

**Cách sửa:**
Tôi áp dụng hard-override bằng code Python bên dưới call của LLM. Trực tiếp parse if string "err-" tồn tại và route `human_review` bất cấp LLM trả lời là gì.

**Bằng chứng trước/sau:**
```python
# Sửa chữa chèn thêm:
if decision.risk_high and "err-" in task.lower() and decision.route != "human_review":
    decision.route = "human_review"
    decision.route_reason += " (Forced human review due to unknown error)"
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**
Tôi đã thiết kế lớp phủ LangGraph Edge rõ ràng, định tuyến Conditionally 1 cách thông minh mà không gây vòng lặp vô hạn.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Do Router hiện nay quá phụ thuộc vào LLM Call, pipeline thực tế bị cản trở bởi tốc độ. Nếu có thể tích hợp Cache vào node Supervisor cho các câu hỏi phổ biến, sẽ tối ưu resource hơn rất nhiều.

**Nhóm phụ thuộc vào tôi ở đâu?**
Sự gắn kết của Graph API (`app.invoke()`). Các thành viên Worker không thể ráp vào kiến trúc nếu Graph Node không build thành công.

**Phần tôi phụ thuộc vào thành viên khác:**
Tôi cần Worker Owner hoàn thiện các parameter outputs của `AgentState` như `retrieved_chunks` và `policy_result` để Synthesis Worker nhận Input hoạt động mượt mà ở bước cuối con đường.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ tích hợp `LangSmith` vào hệ thống Trace. Dựa vào các trace gq01 -> gq10 dạng JSON tĩnh hiện tại là quá trình debug hơi thủ công, nếu dùng session của LangSmith, tôi có thể Visualize Dashboard cho toàn bộ các Event và Cost trên từng Node Supervisor nhanh hơn rất nhiều lần.
