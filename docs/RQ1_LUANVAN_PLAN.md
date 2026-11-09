# Kế hoạch hoàn thiện RQ1 ở mức luận văn

- **Nhánh:** `rq1_final_project` (tách từ `rq1-finalize`, 10/11/2026)
- **Bản ghi trước:** `docs/PROGRESS_2026-11-09.md`
- **Nguồn:** nhận xét sáu khoảng trống của Claude Cowork, đã đối chiếu lại với repo
- **Cập nhật 10/11:** B2+ đã làm xong (Mục 2.1); sửa lại chi phí quota và thứ tự (Mục 3);
  thêm mốc 15/12 cho RQ1 + RQ2 (Mục 5)

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

Thứ tự trong bảng là thứ tự ưu tiên theo giá trị; thứ tự **thực hiện** ở Mục 3 khác, vì
held-out phải chạy sau cùng.

**Về quota:** chỉ Perception gọi LLM trong hệ thống đề xuất (1 lượt/kịch bản); Reasoning và
Reflector không tốn lượt nào. Hệ thống đắt là B2 (~3 lượt/kịch bản) và B2+ (~8 lượt/kịch bản,
đo ngày 10/11). Quota hiện có: ~500 lượt/ngày.

| # | Việc | Trạng thái | Quota Gemini | Thay đổi khẳng định nào |
|---|---|---|---|---|
| 1 | B2+ được cấp công cụ kiểm tra hình học | **Xong 10/11** | đã dùng ~385 | Đổi *cách giải thích* kết quả — xem Mục 2.1 |
| 2 | Bộ kiểm tra giữ riêng (held-out) | Chưa | ~40 (đề xuất + B1+) đến ~260 (thêm B2, B2+) cho ~20 kịch bản | Biến 83,3% từ *in-sample* thành *đã xác nhận* |
| 3 | Tổng quan tài liệu | Chưa | 0 | Không đổi số liệu; đổi mức học thuật |
| 4 | Mô hình thứ hai + `temperature > 0` | Chưa | ~126 (3 lượt × 42, chỉ hệ thống đề xuất) + quota nhà cung cấp thứ hai | Thêm khẳng định "độc lập mô hình" |
| 5 | Tự động thu thập tin | Chưa | 0 khi dựng | Lấp đúng câu chữ RQ1 |
| 6 | Hợp lệ ngoại tại (chuyến đi thật) | Chưa | ~15 (đề xuất) cho 10–15 cặp | Mạnh nhất, nhưng cần người dùng thật |

Ước tính "~42 lượt" cho B2+ trong bản đầu của kế hoạch là sai: nó lấy chi phí của hệ thống
đề xuất áp cho B2+.

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

**Kết quả (10/11, chi tiết ở `docs/PROGRESS_2026-11-10.md`):** B2+ né được 61,9% (26/42), so
với 9,5% của B2 (22/0, p = 4,8×10⁻⁷). Nhận xét "baseline yếu" là đúng. Hệ thống đề xuất vẫn cao
hơn (83,3%, 12/3, p = 0,035), nhưng mức ý nghĩa này nhạy với 3 kịch bản (p = 0,146 trong cả hai
phép kiểm tra độ nhạy). Lợi thế vững là đường vòng ngắn hơn khoảng 3 lần (trung vị 0,68 so với
2,35 km, p = 4,9×10⁻⁴) và 1 lượt LLM thay vì ~8.

Hệ quả cho luận văn: định khung lại đóng góp từ "đa tác tử thắng đơn tác tử" thành "tách kiểm
tra và sửa lộ trình ra khỏi LLM". Câu chữ đề xuất ở Mục 4.1 của nhật ký 10/11. Bước tiếp nếu
thầy yêu cầu: B2++ có thêm công cụ ring search, để cô lập nốt phần *sửa*.

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

**Phải chạy sau cùng, trên hệ thống đã đóng băng** (Mục 3). Nếu chạy held-out rồi mới sửa
Perception, con số held-out không còn mô tả hệ thống cuối; chạy lại trên cùng bộ đó thì nó hết
"giữ riêng". Có thể **dựng** bộ held-out sớm, chỉ đừng **chạy** nó sớm.

Held-out cũng là cách duy nhất để chốt câu hỏi còn treo từ B2+: lợi thế tỷ lệ né so với B2+
hiện nhạy với 3 kịch bản, và cần cỡ mẫu lớn hơn.

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

## 3. Thứ tự thực hiện (sửa 10/11)

Bản đầu đặt held-out ở vị trí thứ hai. Thứ tự đó sai khi hệ thống còn sẽ thay đổi (sửa
Perception cho #7, #39). Nguyên tắc mới:

1. **Đóng băng trước, đánh giá sau.** Mọi thay đổi làm đổi hành vi hệ thống vào trước; sau đó
   khóa lại, và mọi thực nghiệm báo cáo chạy trên bản đã khóa.
2. **Đóng băng mô hình vùng ngập** (hình tròn 350 m) cho cả học kỳ này. Chuyển sang mô hình
   theo đoạn đường sẽ đổi mọi con số RQ1. Nếu làm thì để học kỳ sau, coi như phiên bản mới và
   chạy lại toàn bộ.
3. Lớp thu thập tin **không** đổi hành vi hệ thống trên dữ liệu benchmark (tin đầu vào cố
   định), nên làm song song được bất cứ lúc nào.

| Thời gian | Việc |
|---|---|
| 11/11 | Nộp đồ án môn học (ngoài nhánh này); email hẹn thầy, gửi kèm kế hoạch này và nhật ký 10/11 |
| ~16–17/11 | Gặp thầy: chốt Mục 2.5 (dựng lớp thu thập hay sửa câu chữ RQ1), có cần mô hình thứ hai và B2++ không, mức yêu cầu cho Mục 2.6, và các thay đổi hệ thống cho bản cuối |
| 17–22/11 | Thay đổi hệ thống (Perception nhận tên địa điểm cho #7, #39; cache Perception), chạy lại 42 kịch bản cho bản mới, rồi **đóng băng** |
| 23–29/11 | RQ2 trên bản đã đóng băng (Mục 5); lớp thu thập tin song song; dựng (chưa chạy) held-out |
| 30/11–6/12 | Held-out — chạy **một lần**; `temperature > 0`; mô hình thứ hai |
| 7–15/12 | Viết, và dự phòng cho vòng sửa của thầy — không cắt tuần này |

Tổng quan tài liệu (Mục 2.3) làm rải rác suốt, xen vào lúc chờ benchmark. 15/11 là Chủ nhật,
nên buổi gặp sớm nhất là thứ Hai 16/11; gửi email hẹn sớm.

## 4. Ghi chú còn nợ từ phiên trước, vẫn áp dụng ở nhánh này

- `routing_ceiling.py` chưa từng được commit; con số trần 38/42 hiện không tái tạo được từ
  repo. Nếu nhánh này còn dẫn con số đó thì phải viết lại script.
- Cache Perception là **đúng** cho RQ2 và cho held-out run, dù sai cho việc đo biến động
  LLM. Đừng mang kết luận 30/10 sang.
- `#7` và `#39` thất bại vì Perception không nhận tên địa điểm phi tên đường. Nếu lớp thu
  thập tin ở Mục 2.5 được dựng, sửa luôn chỗ này vì cùng vùng code.

## 5. RQ2 trong cùng mốc 15/12 (mục tiêu 70–80%)

Người dùng chốt (10/11): đến 15/12 thì RQ1 hoàn chỉnh, RQ2 đạt 70–80%. Đề tài kéo dài hai học
kỳ, còn một học kỳ (4 tháng) để hoàn tất; RQ3 thuộc học kỳ sau.

**RQ2 rẻ hơn vẻ ngoài.** RQ2 là ablation số vòng phản tư, mà vòng phản tư không gọi LLM. Mỗi
mức chỉ tốn ~42 lượt cho Perception, gần như 0 khi có cache Perception. Runner đã có
`--max-reflections`. Phần lớn công sức nằm ở phân tích và viết.

Định nghĩa "70–80%" thành việc cụ thể, để đến 15/12 biết đã đạt hay chưa:

- **Xong trước 15/12:** chạy 0/1/2 vòng (thêm 3, 4 nếu cần thấy điểm bão hòa) trên bản đã đóng
  băng; 40 kịch bản (bỏ #7, #39) hoặc 42 nếu đã sửa Perception; kiểm định thống kê; một mục Kết
  quả viết xong.
- **Để học kỳ sau:** thảo luận sâu, phân tích lỗi, chạy RQ2 trên held-out.

Bẫy đã biết (từ nhật ký 09/11): #7 và #39 dừng ở 0 vòng vì Perception không trả về gì, không
phải vì không cần phản tư. Để nguyên thì đường cong bão hòa bị lệch.
