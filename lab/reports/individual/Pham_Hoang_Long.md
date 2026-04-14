# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Phạm Hoàng Long  
**Vai trò trong nhóm:** Worker Owner (Phụ trách Sprint 2 & 3)  
**Ngày nộp:** 14/04/2026  

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

**Module/file tôi chịu trách nhiệm:**
- Thư mục workers: `workers/policy_tool.py`, `workers/retrieval.py`, `workers/synthesis.py`
- Setup MCP Server: file `mcp_server.py`

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Tôi là người phát triển hệ sinh thái "Worker" để thực thi các chỉ thị được định tuyến từ module "Supervisor" do bạn Nhi phụ trách. Khâu của Nhi là bộ não đưa ra quyết định (route), nhưng nếu các policy tool hoặc MCP server của tôi không hoạt động chính xác thì luồng thực thi sau đó sẽ đứt gãy. Kết quả chạy của Worker (như `policy_result`, `mcp_tools_used`) là "nhiên liệu" để phần `Synthesis` tổng hợp trả về câu trả lời hoàn chỉnh cho người dùng.

**Bằng chứng:**
Tôi đã cài đặt thành công cấu trúc tool registry trong `mcp_server.py` và logic kiểm tra rule-based policy tại file `workers/policy_tool.py`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Thiết kế hệ thống mock MCP Server theo dạng In-Process Call thông qua cơ chế `dispatch_tool()` và cấu trúc `TOOL_SCHEMAS`, thay vì triển khai ngay một HTTP/FastAPI Server thực sự cho bài Lab mô phỏng (Sprint 3).

**Lý do:**
Việc khởi tạo một network server HTTP thực tế để tuân thủ 100% Client-Server architecture ở mức Lab này sẽ chiếm nhiều thời gian setup và debug. Quyết định định nghĩa các Schema Tool chuẩn (như `search_kb`, `get_ticket_info`) theo chuẩn MCP vào chung một file Python và import module xử lý giúp chúng ta có cơ chế mô phỏng MCP rất bám sát thực tế, dễ dàng pass qua Agent mà vẫn giảm được độ trễ phát triển. Về sau, chỉ việc chuyển đổi endpoint sang gọi HTTP là được.

**Trade-off đã chấp nhận:**
Sự đánh đổi ở đây là chúng ta tạm thời mất đi khả năng Distributed. Tool không chạy độc lập ở một process khác, do đó nếu logic lấy ticket bị treo, toàn bộ worker script sẽ treo theo thay vì time-out như gọi API thực.

**Bằng chứng từ trace/code:**
Trong `workers/policy_tool.py`, tôi đã cài đặt:
```python
def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    # TODO Sprint 3: Thay bằng real MCP client nếu dùng HTTP server
    from mcp_server import dispatch_tool
    result = dispatch_tool(tool_name, tool_input)
    # ... mapping JSON output
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Logic Policy Analysis ban đầu không thể phân tích đúng các trường hợp loại trừ (Exceptions) như Flash Sale hay Key kỹ thuật số, khiến hệ thống cho rằng policy hoàn tiền khả dụng (policy_applies = True) ngay cả với các trường hợp bị cấm.

**Symptom (pipeline làm gì sai?):**
Nếu khách hàng chat "Tôi muốn hoàn tiền sản phẩm Flash Sale này", hệ thống phân tích chunk văn bản, thấy nói về điều kiện hoàn trả chung chung và liền phê duyệt yêu cầu. Việc này có thể gây thiệt hại trực tiếp cho doanh nghiệp.

**Root cause:**
Lỗi do module `policy_tool.py` trước đây chưa quét để "Deny-first" cho các trường hợp loại trừ. Mô hình hoặc logic lúc đó dựa quá nhiều vào keyword "hoàn tiền" mà bỏ lơ tính cảnh báo rủi ro cao của những từ khoá về ngoại lệ.

**Cách sửa:**
Tôi đã tiêm (inject) hệ thống phân nhóm Rule-based exception. Hệ thống sẽ quét câu lệnh đầu vào và context chunk để ưu tiên phát hiện flag nguy hiểm (`"flash sale"`, `"kỹ thuật số"`). Khi dính flag, mảng `exceptions_found` sẽ thêm phần tử và tự động gạt cờ `policy_applies = False`.

**Bằng chứng trước/sau:**
```python
# Mã nguồn được điều chỉnh tại workers/policy_tool.py
if "flash sale" in task_lower or "flash sale" in context_text:
    exceptions_found.append({
        "type": "flash_sale_exception",
        "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
        "source": "policy_refund_v4.txt",
    })
policy_applies = len(exceptions_found) == 0
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**
Tôi tổ chức phần định nghĩa Tool (Tool Schema) và dữ liệu mô phỏng (Mock Data) rất rõ ràng. Cấu trúc `TOOL_SCHEMAS` giúp toàn bộ Agent System hoặc bất kì framework nào khác gọi linh hoạt các function mà không cần hard-code hàm Python.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Ở hàm `analyze_policy` của `policy_tool.py`, tôi mới chủ yếu dùng Rule-based (chuỗi `.lower()` in text) để check exception thay vì tích hợp LLM làm classification. Khả năng mở rộng còn hạn chế nếu sau này có hàng chục exception phức tạp.

**Nhóm phụ thuộc vào tôi ở đâu?**
Nhi hoàn toàn cần các Output tiêu chuẩn từ Worker (đặc biệt là dict chứa `policy_result` và kết quả truy vấn Ticket) trả về trong Node Graph. Nếu hàm của tôi bug gãy Schema, cả Data Pipeline sẽ chết ngang.

**Phần tôi phụ thuộc vào thành viên khác:**
Tôi cần bộ route của Nhi cấp thông tin đúng (ví dụ: `needs_tool=True` hoặc truyền context chunk sạch) thì hệ Worker này mới chạy mượt mà theo flow.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ dành 1 giờ để tách mock client `mcp_server.py` sang chạy trên server HTTP thực sự bằng thư viện FastAPI và build kết nối chuẩn Model Context Protocol (bắt đầu gọi qua LAN thay vì thư viện import trực tiếp do cùng thư mục). Thời gian còn lại tôi sẽ cấu trúc hoá hàm `analyze_policy` thành một node query LLM mini dùng prompt check ngoại lệ.
