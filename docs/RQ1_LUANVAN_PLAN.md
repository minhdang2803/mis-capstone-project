# Kế hoạch hoàn thiện RQ1 ở mức luận văn

- **Nhánh:** `rq1_final_project` (tách từ `rq1-finalize`, 10/11/2026)
- **Bản ghi trước:** `docs/PROGRESS_2026-11-09.md`
- **Nguồn:** nhận xét sáu khoảng trống của Claude Cowork, đã đối chiếu lại với repo

## 0. Phân biệt hai mức, trước khi làm bất cứ việc nào ở đây

Sáu khoảng trống này được đánh giá theo **RQ1 của đề cương luận văn**, không phải RQ1 của
đồ án môn học. Hai mức khác nhau, và bản thảo hiện tại đã nói rõ điều đó ở Mục 1.4: đồ án
môn học chỉ nhận phần H1, còn RQ2–RQ3 của đề cương luận văn nằm ngoài phạm vi.

Hệ quả về thứ tự: **không việc nào dưới đây là điều kiện để nộp đồ án môn học.** Đồ án đã
quá hạn (mốc 05/11, nay 10/11) và chỗ chặn duy nhất của nó là điền tên và MSSV vào trang
Lời cam đoan. Nộp đồ án trước, rồi mới mở nhánh này. Nếu gộp hai việc thì khoản nợ 5 ngày
sẽ thành vài tuần.

Mọi mục dưới đây đều **đúng ở mức luận văn** — không có mục nào nên bỏ.

## 1. Tổng hợp sáu khoảng trống, sắp lại theo chi phí/giá trị

Thứ tự này khác thứ tự của bản nhận xét gốc, vì có hai mục rẻ hơn nhiều so với vẻ ngoài
của nó, và một mục đắt hơn.

| # | Việc | Chi phí | Quota Gemini | Thay đổi khẳng định nào |
|---|---|---|---|---|
| 1 | B2+ được cấp công cụ kiểm tra hình học | ~2 giờ | ~42 lượt | Chặn được câu "baseline yếu" — đổi *cách giải thích* kết quả |
| 2 | Bộ kiểm tra giữ riêng (held-out) | ~1 ngày | ~84 lượt | Biến 83,3% từ *in-sample* thành *đã xác nhận* |
| 3 | Tổng quan tài liệu | ~2 ngày, 0 quota | 0 | Không đổi số liệu; đổi mức học thuật |
| 4 | Mô hình thứ hai + `temperature > 0` | ~3 ngày | ~430 lượt | Thêm khẳng định "độc lập mô hình" |
| 5 | Tự động thu thập tin | ~3–5 ngày | 0 khi dựng | Lấp đúng câu chữ RQ1 |
| 6 | Hợp lệ ngoại tại (chuyến đi thật) | ~1 tuần+ | ~40 lượt | Mạnh nhất, nhưng cần người dùng thật |

Mục 1 và 2 nên làm trước: rẻ nhất mà đụng trực tiếp vào hai câu hỏi dễ bị chất vấn nhất.

## 2. Chi tiết từng mục, kèm những gì repo đã có sẵn

### 2.1 B2+ cấp công cụ kiểm tra hình học (ưu tiên 1)

Nhận xét gốc đặt mục này thứ tư; thực ra nó **rẻ nhất và đáng làm nhất**.

Hiện trạng đã kiểm: `app/agents/single_agent.py:32` đặt `max_steps = 6`, và B2 chỉ được
bind hai công cụ `geocode_street` và `get_route` (`single_agent.py:62`). Nó **không** được
cấp `find_violations` — tức chính phép kiểm tra hình học mà Reflector dùng.

Đây đúng là chỗ hội đồng sẽ nhắm vào: B2 thua vì kiến trúc đơn tác tử, hay vì nó không có
cách nào tự biết lộ trình còn cắt vùng ngập? Chừng nào chưa trả lời thì 83,3% so với 9,5%
vẫn có thể bị quy là so với baseline bị buộc tay.

Cách làm: thêm biến thể **B2+** bind thêm một công cụ `check_route_safety` bọc
`find_violations` (`app/agents/reflector.py`), và nâng `max_steps` lên 10–12 để nó có chỗ
lặp. Chạy trên đúng 42 kịch bản cũ.

Hai kết quả đều dùng được, nên đây là việc không thể lỗ:

- B2+ vẫn thua rõ → luận điểm kiến trúc được củng cố mạnh hơn hẳn hiện nay;
- B2+ bắt kịp → phát hiện thật, và phải báo cáo: đóng góp nằm ở *công cụ hình học*, không
  phải ở việc tách tác tử. Thà tự tìm ra còn hơn bị hỏi ở buổi bảo vệ.

### 2.2 Bộ kiểm tra giữ riêng (ưu tiên 2)

Bản thảo **đã tự nêu giới hạn này** ở Mục 3.7, nên không phải phát hiện mới — nhưng ở mức
luận văn thì nêu giới hạn là chưa đủ, phải lấp.

Tin tốt đã kiểm được: **không cần thu thập dữ liệu mới.**

- `data/hcmc_flood_blackspots.json` có **118 điểm**, trong khi 42 kịch bản chỉ dùng
  **57 điểm khác nhau** → còn **61 điểm chưa dùng**.
- `data/news_candidates.json` có **13 bài** mà `streets_already_in_scenarios` là `false`.
- `scripts/build_scenarios_from_news.py` đã tự dựng kịch bản từ nguồn tin, có `--seed` và
  `--out`.

Cạm bẫy phải tránh: **đổi `--seed` không tạo ra held-out set.** Nó chỉ xáo lại cặp điểm
đi–đến trên cùng tập vùng ngập cũ; thiết kế v2 đã nhìn thấy những vùng ngập đó rồi. Held-out
thật phải lấy từ 61 điểm chưa dùng và 13 bài chưa dùng.

Việc cần làm: dựng ~15–20 kịch bản chỉ từ nguồn chưa dùng, chạy
`scripts/validate_scenarios.py` để lọc kịch bản không khả thi hoặc không phân biệt được,
rồi chạy benchmark **một lần, không chỉnh gì sau khi xem kết quả**. Con số đó là con số
được báo cáo. Nếu tỷ lệ né tụt nhiều so với 83,3% thì đó là phát hiện, không phải thất bại.

### 2.3 Tổng quan tài liệu (ưu tiên 3 — làm song song, không tốn quota)

Mục này không phụ thuộc mục nào khác và không cần Gemini, nên xen vào giữa các lần chạy
benchmark. Cần bổ sung: Zheng et al. (2024) (đã có trong đề cương, chưa vào bài), các công
trình nền về DSS, và **nhóm định tuyến tránh ngập không dùng LLM** — nhóm cuối là quan
trọng nhất vì nó mới dựng được đúng đường cơ sở để nói đóng góp của LLM nằm ở đâu.

Lưu ý giữ nguyên quy trình đối chiếu trích dẫn của phiên 09/11: mỗi mục mới phải xác nhận
nơi xuất bản thật, đừng tin BibTeX. Bài học MAS4POI (một lần kết luận sai "chưa xuất bản")
còn nguyên giá trị.

### 2.4 Mô hình thứ hai và `temperature > 0` (ưu tiên 4)

Hiện trạng: `app/services/llm.py` gắn chặt với Gemini — `TRANSIENT_MARKERS` là mã lỗi
Gemini, `_throttle()` đặt theo quota phút của Gemini, `settings.py` chỉ có `GEMINI_MODEL`.
`temperature = 0.0` còn ghi cứng tại `perception.py:90` và `single_agent.py:72`.

Nên làm hai phần tách rời, vì phần sau rẻ hơn phần trước nhiều:

1. **`temperature > 0`** — chỉ cần đưa temperature thành tham số cấu hình rồi chạy lặp
   3 lần ở temperature 0,3 trên cùng 42 kịch bản (~126 lượt). Việc này lấp đúng câu "chưa
   làm" mà bản thảo đang tự thừa nhận ở Mục 5.2.
2. **Mô hình thứ hai** — cần một lớp trừu tượng provider trước đã. Đây là phần tốn công
   thật, và quota là hạn chế cứng: free tier Gemini đã phải pacing 4,5 s/lượt.

Khi báo cáo, đừng gộp hai phần: biến động do temperature và khác biệt giữa hai mô hình là
hai nguồn khác nhau.

### 2.5 Tự động thu thập tin (ưu tiên 5)

Đây là khoảng trống nằm trong chính câu chữ RQ1, nhưng **nhỏ hơn bản nhận xét ngụ ý.** Đã
kiểm: khâu tin → kịch bản **đã tự động** (`scripts/build_scenarios_from_news.py`), và khâu
bóc tách, hợp nhất đã là Perception. Chỗ thiếu chỉ là **lớp lấy tin**, tức thứ sinh ra
`data/news_candidates.json` — hiện do người làm thủ công.

Phạm vi thật: fetch RSS/trang chuyên mục của 8 đầu báo đã dùng (SGGP 10 bài, Tiền Phong 6,
VOV 4, VietnamPlus 4, VOH 3, VietNamNet 3, VnExpress 2, Nông nghiệp & Môi trường 2), lọc
trùng, rồi đổ vào đúng schema 17 trường hiện có. Phần khó không phải code mà là **nhiễu**:
tin ngập lụt lẫn tin thời tiết chung, và tin cũ (dữ liệu hiện trải từ 2011 đến 2026).

Quyết định cần bạn chọn, vì nó ảnh hưởng đề cương:

- **Dựng lớp thu thập** — giữ nguyên câu chữ RQ1 đã được duyệt. Tôi nghiêng về hướng này:
  sửa RQ1 trong đề cương đã duyệt thì phải xin ý kiến giảng viên hướng dẫn, và chữ "tự động
  thu thập" là một phần của tính mới mà đề tài đang dựa vào.
- **Sửa câu chữ RQ1** cho khớp những gì đã làm — rẻ hơn, nhưng thu hẹp đóng góp và cần
  giảng viên đồng ý.

### 2.6 Hợp lệ ngoại tại (ưu tiên 6)

Mạnh nhất về mặt thuyết phục, đắt nhất về mặt tổ chức, và là mục duy nhất phụ thuộc người
ngoài. Hiện cặp điểm đi–đến do `find_trip()` dựng ra (`build_scenarios_from_news.py:67`).

Bước trung gian đáng giá, làm được ngay mà không cần tuyển người dùng: lấy một nhóm nhỏ
(10–15) **cặp đi–đến thật** — tuyến đi làm, đi học quen thuộc của chính bạn và vài người
quen — rồi chạy trên đó. Chưa phải nghiên cứu người dùng, nhưng đủ để bỏ được chữ "toàn bộ
cặp điểm đều do dựng ra" khỏi phần mối đe dọa tính hợp lệ.

## 3. Thứ tự đề nghị

1. Nộp đồ án môn học (ngoài nhánh này).
2. Mục 2.1 — B2+ cấp công cụ hình học.
3. Mục 2.2 — held-out set.
4. Mục 2.3 — tổng quan tài liệu, xen vào giữa các lần chạy.
5. Quyết định ở Mục 2.5, vì nó có thể cần ý kiến giảng viên hướng dẫn, nên hỏi sớm.
6. Mục 2.4, rồi 2.6.

## 4. Ghi chú còn nợ từ phiên trước, vẫn áp dụng ở nhánh này

- `routing_ceiling.py` chưa từng được commit; con số trần 38/42 hiện không tái tạo được từ
  repo. Nếu nhánh này còn dẫn con số đó thì phải viết lại script.
- Cache Perception là **đúng** cho RQ2 và cho held-out run, dù sai cho việc đo biến động
  LLM. Đừng mang kết luận 30/10 sang.
- `#7` và `#39` thất bại vì Perception không nhận tên địa điểm phi tên đường. Nếu lớp thu
  thập tin ở Mục 2.5 được dựng, sửa luôn chỗ này vì cùng vùng code.
