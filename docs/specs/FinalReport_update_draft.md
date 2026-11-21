# Final Report — nội dung thay thế §3 (bản chờ số Qwen)

> Dán vào `FinalReport_Nhom01.docx`. Ô `⟨Q…⟩` điền khi có kết quả Qwen.
> Ràng buộc 8 trang: §3 cũ chiếm ~1,6 trang (trang 5 giữa → hết trang 6, gồm Bảng 2, Bảng 3, Hình 5);
> §3 mới dưới đây ~1 350 từ + 2 bảng, **bỏ Hình 5**, nên vừa khoảng trống cũ. Trang 8 hiện còn trống
> ~0,8 trang (chỉ có tài liệu [11]–[12]) — đó là phần dự phòng nếu bảng dài hơn.
> Số liệu: `steady_evaluation/runs/*/metrics.recomputed.json`, `BAO_CAO_20261121_*.md`.

## Ngoài §3, các chỗ phải sửa cho khớp (đã viết sẵn ở cuối file)

| Vị trí | Lý do |
|---|---|
| Abstract, câu cuối | Thêm 1 câu số liệu mới |
| §4.1 ý (2), (3), (4) và đoạn "Về mức độ hoàn thiện" | Đang trích số §3 cũ (46 truy vấn, MRR 0,989, injection 3/3, 6/6 kịch bản) |
| §4.2 "Mở rộng đánh giá" | Đã đo đầu-cuối và nhiều tổ hợp → viết lại |
| Tài liệu tham khảo | Không cần thêm (không trích nguồn mới) |

---

## 3. Kết quả thực nghiệm và đánh giá

### 3.1. Môi trường và dữ liệu thực nghiệm

**Công cụ đánh giá.** Nhóm xây dựng bộ đánh giá đầu-cuối `steady_evaluation` gọi trực tiếp API của
hệ thống qua HTTP như một người dùng thật: đăng nhập, tạo ghi chú, chờ worker lập chỉ mục, gọi
`POST /search`, `POST /ai/chat` (SSE) và `POST /ai/page-match`. Mỗi ca được ghi vào nhật ký thô
`raw_results.jsonl` cùng tệp kê khai cấu hình (commit mã nguồn, mã băm bộ dữ liệu, mô hình); mọi chỉ
số trong mục này đều được tính lại từ nhật ký thô và khớp hoàn toàn với số đã lưu. Độ trễ là thời
gian đầu-cuối ở tầng HTTP, đã gồm thời gian gọi mô hình embedding và mô hình sinh.

**Bộ dữ liệu.** 11 tài liệu nguồn gồm 8 bài báo tiếng Việt (VnExpress, dạng HTML) và 3 bài báo khoa
học tiếng Anh dạng văn bản (*Attention Is All You Need*, *LoRA*, *Evaluating Quantized LLMs*), tổng
316 032 ký tự, được chia thành 25 ghi chú không cắt bỏ nội dung. Trên đó có 49 cặp hỏi–đáp kèm đoạn
vàng (gold span): 38 câu có căn cứ, 11 câu không có căn cứ. Mỗi câu được dùng cho cả ba chức năng:
tìm kiếm lai (38 truy vấn), hỏi đáp RAG (49 câu) và PageMatch (49 ca, gồm 38 dương tính và 11 âm
tính). 16 câu hỏi tiếng Việt nhắm vào ba tài liệu tiếng Anh tạo thành nhóm truy xuất đa ngôn ngữ.

**Cấu hình mô hình.** Cùng một phiên bản mã nguồn và bộ dữ liệu, nhóm chạy ⟨Q: 4⟩ tổ hợp mô hình
(Bảng 2). Hai tổ hợp cục bộ chạy qua llama.cpp trên máy cá nhân và chỉ khác nhau ở mô hình
embedding, tạo thành một phép so sánh A/B. Tổ hợp Gemini dùng gói miễn phí của Google AI Studio, giới
hạn 3–5 yêu cầu/phút, và được chạy hai lượt.

**Bảng 2:** Các tổ hợp mô hình đánh giá

| Ký hiệu | Mô hình sinh | Mô hình embedding | Môi trường |
|---|---|---|---|
| L1 | Ternary-Bonsai-2-9B | gte-Qwen2-1.5B-instruct | Cục bộ (llama.cpp) |
| L2 | Ternary-Bonsai-2-9B | Qwen3-Embedding-0.6B | Cục bộ (llama.cpp) |
| G | gemma-4-31b-it | gemini-embedding-001 | Google AI Studio |
| Q | ⟨Q: mô hình sinh⟩ | ⟨Q: embedding⟩ | ⟨Q: môi trường⟩ |

**Tiêu chí đánh giá.** Tìm kiếm: Recall@5 và MRR tính theo tài liệu chứa đoạn vàng. Hỏi đáp RAG: tỉ
lệ trích dẫn hợp lệ (câu trả lời có ít nhất một chỉ số `[n]` và mọi chỉ số đều trỏ tới nguồn đã trả
về), Token-F1 so với đoạn vàng (chỉ số phụ, đo trùng từ), tỉ lệ từ chối đúng trên câu không có căn
cứ. PageMatch: Hit@5, Precision@5 và tỉ lệ báo động giả (FPR) trên ca âm tính. Ca bị lỗi phía nhà
cung cấp AI được tách riêng, không tính vào chỉ số chất lượng.

### 3.2. Kết quả định lượng

**Bảng 3:** Kết quả đầu-cuối theo tổ hợp mô hình

| Chỉ số | L1 | L2 | G (lượt 1) | G (lượt 2) | Q |
|---|---:|---:|---:|---:|---:|
| Tìm kiếm Recall@5 | 0,711 | 0,974 | 1,000 | 1,000 | ⟨Q⟩ |
| Tìm kiếm MRR | 0,680 | 0,934 | 0,987 | 0,987 | ⟨Q⟩ |
| Tìm kiếm p50 (ms) | 194 | 110 | 596 | 617 | ⟨Q⟩ |
| RAG hoàn thành / 38 | 38 | 38 | 15 | 11 | ⟨Q⟩ |
| RAG trích dẫn hợp lệ | 0,737 | 0,842 | 0,800* | 0,636* | ⟨Q⟩ |
| RAG Token-F1 | 0,163 | 0,177 | 0,225* | 0,199* | ⟨Q⟩ |
| RAG từ chối đúng | 9/11 | 9/11 | 3/4* | 1/1* | ⟨Q⟩ |
| RAG p50 (ms) | 3 332 | 2 645 | 21 527 | 24 014 | ⟨Q⟩ |
| PageMatch lỗi / 49 | 0 | 0 | 36 | 19 | ⟨Q⟩ |
| PageMatch Hit@5 | 0,790 | 0,571 | – | – | ⟨Q⟩ |
| PageMatch Precision@5 | 0,275 | 0,170 | – | – | ⟨Q⟩ |
| PageMatch FPR | 0,50 | 0,50 | – | – | ⟨Q⟩ |

\* Tính trên các câu hoàn thành; các câu còn lại lỗi do máy chủ Google trả HTTP 503.
– Không đủ ca hợp lệ để chấm.

Ở cả bốn lượt chạy, bước nạp dữ liệu đạt 11/11 tài liệu sẵn sàng, 25/25 ghi chú được lập chỉ mục,
100% ký tự được đưa vào chỉ mục. Ở hai lượt Gemini, vị trí của tài liệu đúng trùng khớp ở cả 38/38
truy vấn, cho thấy bước truy xuất có tính tái lập.

### 3.3. Phân tích và thảo luận kết quả

**Mô hình embedding quyết định chất lượng truy xuất.** Giữ nguyên mô hình sinh, chỉ đổi embedding từ
gte-Qwen2-1.5B (L1) sang Qwen3-Embedding-0.6B (L2) nâng Recall@5 từ 0,711 lên 0,974 và MRR từ 0,680
lên 0,934, dù mô hình mới nhỏ hơn. Toàn bộ 11 truy vấn trượt của L1 đều thuộc nhóm hỏi tiếng Việt
trên tài liệu tiếng Anh (Recall@5 nhóm này chỉ 5/16, trong khi nhóm HTML tiếng Việt đạt 22/22); L2 nâng
nhóm này lên 15/16. Như vậy điểm nghẽn không nằm ở thuật toán tìm kiếm lai hay kích thước ghi chú mà
ở khả năng đa ngôn ngữ của embedding. Với gemini-embedding-001, Recall@5 đạt 1,000 và MRR 0,987.

**Truy xuất tốt kéo theo câu trả lời tốt.** Khi Recall@5 tăng, tỉ lệ trích dẫn hợp lệ của RAG tăng từ
0,737 (L1) lên 0,842 (L2); ở L1, các câu không trích dẫn chủ yếu là câu từ chối vì không lấy được ngữ
cảnh, đúng với nhận định của Gao và cộng sự [10] rằng chất lượng RAG phụ thuộc trước hết vào bước
truy xuất. Cả hai tổ hợp cục bộ từ chối đúng 9/11 câu không có căn cứ. Token-F1 thấp (0,16–0,23) vì
câu trả lời diễn đạt lại thay vì chép nguyên đoạn vàng; đây chỉ là chỉ số phụ.

**Đánh đổi ở PageMatch.** Cùng một embedding phục vụ cả tìm kiếm và PageMatch, nhưng L2 làm Hit@5 của
PageMatch giảm từ 0,790 xuống 0,571 và Precision@5 từ 0,275 xuống 0,170, trong khi FPR giữ ở 0,50. Ngưỡng
cosine 0,35 của PageMatch được hiệu chỉnh cho một phân bố điểm tương đồng cụ thể, nên cần hiệu chỉnh
lại theo từng mô hình embedding thay vì dùng chung một giá trị.

**Độ tin cậy của nhà cung cấp AI.** Với Gemini, 60–71% câu RAG và 39–73% ca PageMatch thất bại vì máy
chủ Google trả lỗi 503 cho gemma-4-31b-it, dù đã giãn nhịp còn 3–5 yêu cầu/phút. Hệ thống xử lý đúng
thiết kế: trả `AI_UNAVAILABLE` và hoàn trả hạn mức token đã giữ chỗ, không làm mất dữ liệu. Tuy nhiên
các chỉ số chất lượng RAG và PageMatch của Gemini dựa trên ít mẫu nên không dùng để so sánh trực tiếp.
Mô hình cục bộ không gặp lỗi nào và nhanh hơn khoảng 8 lần ở RAG (p50 2,6 giây so với 21,5 giây).
⟨Q: 1–2 câu đặt Q cạnh L2 và G, ví dụ "Tổ hợp Q đạt Recall@5 …, trích dẫn hợp lệ …"⟩

**Giới hạn của thực nghiệm.** Bộ dữ liệu gồm 49 câu hỏi do nhóm tự gán nhãn trên 11 tài liệu; mỗi
tổ hợp cục bộ chỉ chạy một lượt. Trích dẫn hợp lệ chỉ kiểm tra chỉ số nguồn tồn tại, chưa kiểm chứng
nguồn có thực sự hỗ trợ ý; phát hiện từ chối dựa trên heuristic ở câu đầu. Đợt đánh giá này không đo
lại chức năng tóm tắt và khả năng chống prompt injection.

---

## Các câu sửa kèm (ngoài §3)

**Abstract — thay câu cuối** ("Kết quả thực nghiệm khẳng định…") bằng:
> Đánh giá đầu-cuối trên 49 câu hỏi và 11 tài liệu song ngữ với ⟨Q: 4⟩ tổ hợp mô hình cho thấy tìm kiếm
> lai đạt Recall@5 từ 0,974 đến 1,000 khi dùng mô hình embedding phù hợp, và mô hình chạy cục bộ cho
> phép vận hành ổn định, không phụ thuộc giới hạn của nhà cung cấp AI.

**§4.1 ý (2)** — thay câu số liệu cuối bằng:
> Trên 38 truy vấn của bộ dữ liệu song ngữ, hệ thống đạt Recall@5 = 1,000 với gemini-embedding-001 và
> 0,974 với Qwen3-Embedding-0.6B chạy cục bộ.

**§4.1 ý (3)** — thay "Trên 20 ca kiểm thử, Recall@5 đạt 1,000 và không có báo động giả ở các ca âm
tính." bằng:
> Trên 49 ca đầu-cuối, Hit@5 đạt 0,790 với tổ hợp cục bộ L1; ngưỡng lọc cần hiệu chỉnh theo từng mô
> hình embedding.

**§4.1 ý (4)** — thay bằng:
> (4) Hỏi đáp RAG có trích dẫn và cơ chế chịu lỗi: tỉ lệ trích dẫn hợp lệ đạt 0,842 và từ chối đúng
> 9/11 câu không có căn cứ với mô hình cục bộ; khi nhà cung cấp AI trả lỗi, hệ thống trả
> AI_UNAVAILABLE và hoàn trả hạn mức đúng thiết kế.

**§4.1 đoạn "Về mức độ hoàn thiện…"** — thay phần "Thực nghiệm cũng chỉ ra những điểm chưa đạt: …" bằng:
> Thực nghiệm cũng chỉ ra những điểm chưa đạt: Precision@5 của PageMatch còn thấp (0,170–0,275) và
> nhạy với mô hình embedding; truy xuất đa ngôn ngữ phụ thuộc mạnh vào embedding; gói miễn phí của
> nhà cung cấp AI không đủ ổn định cho đánh giá quy mô lớn.

**§4.2 "Mở rộng đánh giá"** — thay bằng:
> Mở rộng đánh giá. Bổ sung truy vấn và trang web thu từ người dùng thật, chạy lặp nhiều lượt cho mỗi
> tổ hợp mô hình, chấm ngữ nghĩa câu trả lời bằng người hoặc LLM thay cho Token-F1, và đo lại tóm tắt
> cùng các ca prompt injection trên bộ dữ liệu mới.
