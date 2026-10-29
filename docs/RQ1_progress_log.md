# Nhật ký tiến độ RQ1: Multi-Agent Traffic Routing (ngập lụt TP.HCM)

- **Ngày ghi:** 23/10/2026 (cập nhật lần 3, sau khi benchmark 20 kịch bản cũ hoàn thành lúc 03:38)
- **Nhánh:** `rq1-finalize` (các thay đổi **chưa commit**)
- **Mốc nộp báo cáo RQ1 cho thầy:** 05/11/2026 (còn 13 ngày)
- **Nguồn nghiên cứu:** notebook Gemini "Final capstone project" (`60481fcd-a403-461a-afc4-cc88f206987e`), gồm đề cương, tài liệu RQ1 và nguồn GitHub (#9)
- **Lưu ý bảo mật:** file này không chứa API key. Key Gemini mới đã từng được dán vào cuộc trò chuyện, nên sau đồ án hãy tạo key mới.

---

## Bối cảnh ban đầu

Repo `final_capstone_project` là backend cho RQ1: hệ thống đa tác tử (Perception, Reasoning, Reflector) né điểm ngập ở TP.HCM, dùng FastAPI và LangGraph. Notebook chứa nghiên cứu, đề cương và benchmark. Yêu cầu từ đề cương: so sánh định lượng giữa OSRM thuần, single-agent LLM và hệ thống đề xuất.

**Phát hiện khi rà soát ban đầu (trước khi sửa):**
1. Routing là **giả lập** (nội suy đường thẳng, gắn nhãn "OSRM_v5.24"), `OSRM_SERVER_URL` không được dùng.
2. Detour của Reflector là một độ lệch cố định `+0.008, -0.008` so với điểm ngập đầu tiên, không phụ thuộc hình học.
3. "Baseline 2" chỉ là pipeline cũ tắt reflection, không phải single-agent LLM.
4. B1 được chấm bằng ground truth, còn B2 và hệ thống đề xuất chấm bằng điểm ngập do chính chúng nhận diện nên phép so sánh không công bằng.
5. `extraction_accuracy` luôn bằng 1.0 khi có kết quả, không so với ground truth.
6. Độ trễ ~0,2 ms trong CSV cho thấy Gemini không được gọi (luôn rơi về gazetteer). Nguyên nhân: key Gemini cũ đã bị Google thu hồi vì lộ trong lịch sử git (`.env.example` ở commit đầu).
7. LangGraph có trong `requirements.txt` nhưng không được dùng (workflow là vòng `while`).
8. Bộ dữ liệu 20 kịch bản, ít hơn mức 30–50 của đề cương.

---

## 1. Những việc đã làm

### Quyết định đã chốt cùng bạn
- Phase 0 dùng `data/scenarios.json` hiện có, không dùng `scenario.txt` từ notebook.
- Dùng **Docker OSRM cục bộ** làm mặc định. OSRM là mã nguồn mở nên không có "server OSRM thật" để mua. Máy chủ demo công khai không dành cho production.
- Reflector dùng **Chiến lược B** (waypoint đi vòng được tính toán) làm lõi. **Chiến lược A** (chọn tuyến thay thế của OSRM) chỉ dùng làm ablation **B1+**.
- Theo đề cương có **2 baseline + 1 hệ thống đề xuất** (không phải "3 baseline"):
  - B1: OSRM thuần
  - B2: single-agent LLM
  - Proposed: Perception → Reasoning → Reflector
  - B1+ (ablation, ngoài đề cương): Perception + tuyến thay thế OSRM, không có Reflector
- Giữ nguyên Gemini nhưng chọn model rẻ nhất: `gemini-3.1-flash-lite` (xác nhận trên AI Studio: 15 RPM, 500 RPD, 250K TPM). Không chuyển sang Claude vì Claude API cũng tính phí.
- Kịch bản tổng hợp (`synthetic`) chỉ là phụ; số liệu chính phải dựa trên tin thật.

### Phase 0: Chuẩn bị
- Tạo nhánh `rq1-finalize`.
- Tạo `.venv/` (Python 3.13) vì `venv/` cũ trỏ tới Python 3.14 không còn tồn tại.
- Thêm `tests/smoke_check.py`: kiểm tra OSRM và Gemini, có retry, báo lỗi rõ ràng, không im lặng.

### Phase 1: OSRM thật
- `docker-compose.yml`, `scripts/setup_osrm.sh`: tải extract OSM Việt Nam (~330 MB), cắt theo bounding box TP.HCM, build dữ liệu OSRM (MLD). RAM đỉnh ~330 MB.
- OSRM chạy tại `localhost:5001` (cổng 5000 bị AirPlay của macOS chiếm).
- `app/services/osrm_service.py` viết lại: route thật, alternatives, `snap_to_road` (`/nearest`), retry, cache trên đĩa, lỗi `OSRMError` rõ ràng.
- Đổi dòng `OSRM_SERVER_URL` trong `.env` sang `http://localhost:5001`.

### Phase 2: Reflector thật
- `app/core/geometry.py`: khoảng cách điểm tới **đoạn thẳng** của polyline (không chỉ tới đỉnh).
- `app/agents/reflector.py`: kiểm tra theo đoạn, waypoint vuông góc với tuyến và nằm ngoài vùng ngập, snap vào đường, thử phía ngược lại và margin lớn hơn ở các lần sau, sắp xếp waypoint theo thứ tự dọc tuyến, giữ tuyến tốt nhất, sửa lỗi `reflection_count` vượt `max_reflections`, log giải thích được.

### Phase 3: Benchmark
- `app/services/evaluation.py`: judge chung dựa trên `ground_truth_hazards`; precision, recall, grounding; kiểm tra kịch bản khả thi.
- `app/agents/single_agent.py`: B2 thật (một LLM với hai tool `geocode_street`, `get_route`, không verifier).
- `app/services/baselines.py`: B1 và B1+.
- `tests/run_rq1_experiment.py`: 4 hệ thống, nhiều lần chạy, độ lệch chuẩn, độ trễ trung bình và p95, tỉ lệ dưới 3,5 giây, path overhead, chế độ strict (dừng nếu Gemini hoặc OSRM không hoạt động), ghi `perception_source` từng dòng. Xuất `data/results_rq1.csv` và `data/results_rq1_summary.json` **khi chạy xong**.

### Phase 5–7: LangGraph, tài liệu, triển khai
- `StateGraph` thật trong `workflow_service.py`, giữ nguyên chữ ký hàm.
- README viết lại; `Dockerfile`, `docker-compose.prod.yml` (Caddy → backend → OSRM), `.env.example` chỉ có giá trị mẫu; `/health` báo trạng thái OSRM; lỗi OSRM trả 503; CORS cấu hình bằng `CORS_ORIGINS`.

### Xử lý Gemini API
- Key mới có dạng `AQ.` (định dạng "auth key" mới của AI Studio, không còn `AIza`). Lần đầu bị dán lẫn một ký tự thừa; sau khi ghi lại sạch thì xác thực được.
- `gemini-2.5-flash` trong đề cương không còn dành cho người dùng mới → đổi model (cần ghi chú trong luận văn). `gemini-3.6-flash` bị giới hạn 20 request/ngày ở gói miễn phí → chuyển sang `gemini-3.1-flash-lite` (500 RPD).
- `app/services/llm.py`: retry với backoff cho 503/429 theo phút, **fail nhanh** khi hết quota ngày, bộ giãn cách 4,5 giây giữa các lần gọi (`GEMINI_MIN_INTERVAL_S`), thời gian chờ được **trừ khỏi độ trễ**; benchmark dừng sạch nếu hết quota ngày.
- Đã chạy **9 test perception thật đều pass** với `gemini-3.1-flash-lite`.

### Cập nhật mới: Geocoding fallback (Nominatim/Photon)
- Kiểm tra thật cho thấy hai dịch vụ kết nối được nhưng **trả tọa độ sai mà không báo** (ví dụ "Lê Cơ" ra một đường ở Tân Nhựt, "Hoàng Quốc Việt" ra một văn phòng ở Tân Bình).
- Đã sửa `app/services/geocoding_service.py`: chỉ nhận kết quả là **đường** (`highway`), **tên khớp**, **nằm trong khung TP.HCM**; hai dịch vụ phải **khớp nhau** (≤2 km); không chắc thì trả `None` và ghi log; có cache, giãn cách 1,1 giây cho Nominatim, trả về `geocode_source`, `geocode_confidence`, `address_hint`.
- Perception ghi log "Could not locate '...' reliably; hazard skipped" khi không định vị được.

### Cập nhật mới: Dữ liệu
- **`data/news_candidates.json`**: 41 bài báo thật đã **mở từng bài để xác minh ngày đăng, tên đường, trích đoạn** (35 sự kiện khác nhau; 24 bài từ 2022 trở lên; 37 bài có ít nhất 1 đường trong gazetteer). Bài báo tổng hợp có nhiều trang hiển thị **ngày giả**, nên không tin ngày hiển thị ở trang tổng hợp. Không lấy 2 bài không mở được và bài không nêu tên đường.
- **Gazetteer** `data/hcmc_flood_blackspots.json`: **78 → 126 điểm** (thêm 48, phiên bản 1.1.0) bằng `scripts/expand_gazetteer.py`, từ các danh sách chính thức (CSGT 06/10/2026, Sở Xây dựng 23 tuyến triều cường, VnExpress, VOH, Tuổi Trẻ…) và các bài đã xác minh. Mỗi điểm mới có `sources`, nguồn tọa độ, `address_hint`, `needs_review`. Đã **loại tay 5 điểm khớp nhầm** (Tố Hữu, Thích Quảng Đức, Huỳnh Văn Nghệ, Cây Trâm, Bình Lợi). **8 điểm cần xem lại** (chỉ một dịch vụ trả lời). 11 đường chưa có tọa độ tin cậy được ghi ở `data/gazetteer_unresolved.json`. Bản sao lưu gốc nằm ở thư mục tạm của phiên làm việc.
- **`data/scenarios_v2.json`**: **50 kịch bản**, tạo bằng `scripts/build_scenarios_from_news.py`, validator 0 lỗi và 0 cảnh báo về kịch bản không thể thắng hoặc không phân biệt được hệ thống. Thành phần: 5 kịch bản cũ giữ nguyên + 14 kịch bản cũ tạo lại điểm đi/đến (giữ điểm gốc ở `original_origin/destination`) + 31 kịch bản mới từ tin tức (16 từ 2022 trở lên; 6 cần xem lại). Bị loại 4 tin (N01, N08, N11, N20) và 1 kịch bản cũ (#20) do giới hạn `--max 50`.
- Các file kịch bản hiện có: `scenarios.json` (20, gốc, chưa sửa), `scenarios_extended.json` (40, gồm 20 tổng hợp), `scenarios_v2.json` (50, tin thật).
- `scripts/validate_scenarios.py`, `scripts/generate_scenarios.py` (tổng hợp) cũng đã có.

### Test
- **54 test pass, 2 bỏ qua** (2 test cần Gemini thật, bật bằng `RUN_LLM_TESTS=1`). Test perception mặc định không gọi mạng; `tests/conftest.py` tắt giãn cách LLM trong unit test. Có test cho geometry, reflector, evaluation, geocoding (mock Nominatim/Photon), single-agent, workflow, API, client OSRM, retry LLM.

### Phát hiện về dữ liệu gốc (`scenarios.json`, 20 kịch bản)
- **5 kịch bản không thể thắng** (#1, 2, 7, 9, 15): điểm đi hoặc đến nằm trong vùng ngập của ground truth.
- **10 kịch bản không phân biệt được hệ thống** (#4, 8, 11, 12, 13, 16, 17, 18, 19, 20): OSRM thuần đã né hết vùng ngập.
- `scenarios_v2.json` đã xử lý cả hai vấn đề này.

### Benchmark đã hoàn thành (23/10, 02:36–03:38)
- `tests/run_rq1_experiment.py --runs 3` trên **`scenarios.json` (20 kịch bản cũ, 15 khả thi)**, `gemini-3.1-flash-lite`, chế độ strict. **240 dòng, 0 lỗi**, mọi dòng perception là `gemini`.
- Kết quả trên 15 kịch bản khả thi (né ngập / độ trễ TB / độ trễ p95 / dưới 3,5 giây):

| Hệ thống | Né ngập (khả thi) | Né ngập (tất cả 20) | Độ trễ TB | p95 | Dưới 3,5 s |
|---|---|---|---|---|---|
| B1: OSRM thuần | 66,7% (10/15) | 50% | 6 ms | 10 ms | 100% |
| B2: Single-agent LLM | 60,0% (9/15) | 45% | 35,0 s | 73,0 s | 0% |
| Đề xuất | **86,7% (13/15)** | 65% | 12,2 s | 29,7 s | 15% |
| B1+ (ablation) | 66,7% (10/15) | 50% | 10,6 s | 28,5 s | 20% |

- **Đọc kết quả:** đề xuất vượt cả hai baseline và đi vòng ít hơn (+0,33 km so với B1, B2 +2,33 km). B1+ bằng B1, nên phần cải thiện đến từ vòng reflection, không phải từ việc chọn tuyến thay thế của OSRM.
- **Hạn chế:** chênh lệch là 3 kịch bản (13/15 so với 10/15), chưa đủ cho kết luận thống kê. Độ lệch chuẩn giữa 3 lần chạy bằng 0; cần kiểm tra lại bằng cách so từng dòng CSV. Độ trễ vượt mục tiêu 3,5 giây rất xa.
- `data/results_rq1.csv` và `data/results_rq1_summary.json` đã là **kết quả mới** (trước đó là file router giả, không còn dùng).
- Chỉ là bộ cũ, **không dùng làm số liệu cho thầy**. Số liệu chính thức chạy trên `scenarios_v2.json`.

### Bài học kỹ thuật cần nhớ
- `docker compose logs --since <thời gian>` **không lọc đúng** theo mốc thời gian, nên không dùng để đếm tiến độ; đếm theo dấu thời gian từng dòng. Lần đầu mình ước lượng sai "còn 2 phút" vì lẫn các yêu cầu cũ.
- Chạy benchmark qua `| grep -v ...` khiến output bị đệm đến khi kết thúc. Lần sau chạy với `python -u` và ghi ra file log (ví dụ `... 2>&1 | tee run.log`) để xem được tiến độ.
- Trang tổng hợp tin tức hiển thị ngày giả; luôn đọc ngày trong bài.

---

## 2. Những việc chưa làm

- Chưa chạy benchmark trên `scenarios_v2.json` (số liệu chính thức).
- Chưa kiểm tra độ lệch chuẩn bằng 0 giữa các lần chạy.
- Chưa phân tích từng kịch bản thất bại của hệ thống đề xuất (2 kịch bản chưa né được trong 15 kịch bản khả thi).
- Độ trễ chưa đạt mục tiêu 3,5 giây; chưa có cache trích xuất.
- Chưa **kiểm tra bằng mắt**: 6 kịch bản mới `needs_review`, đoạn trích (chưa so nguyên văn với bài gốc), 8 điểm gazetteer `needs_review`, 11 đường chưa có tọa độ.
- Chưa thay `scenarios.json` bằng bản v2 (chờ bạn đồng ý; kịch bản cũ #20 đang bị cắt, dùng `--max 51` để giữ).
- Chưa **commit** và merge nhánh `rq1-finalize` vào `main`.
- Chưa cập nhật nguồn #9 (GitHub) và kết quả vào notebook (cần bạn đồng ý).
- Chưa xóa key cũ khỏi lịch sử git (cần force-push; key cũ đã bị thu hồi nên rủi ro thấp).
- Chưa thử `docker-compose.prod.yml` trên server thật.
- Chưa xử lý tuyến quay đầu bất thường quanh waypoint, và vùng ngập chồng nhau (ví dụ kịch bản cũ #3).
- Chưa có danh sách đầy đủ 122 điểm ngập của CSGT (nằm trong ảnh infographic của Tuổi Trẻ, cần bạn chép thành văn bản).
- Chưa có cache kết quả trích xuất Gemini; chưa làm xác thực API key và rate limiting cho app mobile (RQ3).

---

## 3. Những việc cần làm

**Ưu tiên cao (trước 05/11):**
1. ~~Chờ benchmark hiện tại xong~~ **Đã xong** (xem mục Benchmark ở phần 1). Việc còn lại: phân tích 2 kịch bản đề xuất chưa né được và kiểm tra độ lệch chuẩn bằng 0.
2. Xem lại dữ liệu `scenarios_v2.json`: các mục `needs_review`, so vài đoạn trích với bài gốc.
3. **Chạy benchmark trên `scenarios_v2.json`** (`--runs 1`, ~300 request); để sang ngày mai vì quota 500 RPD của hôm nay gần hết. Các ngày sau chạy thêm để có nhiều lần lặp.
4. Phân tích kịch bản thất bại: lỗi do trích xuất, do hình học, hay không thể né. Tách báo cáo tin thật mới (≥2022) và tin cũ.
5. Cải thiện Reflector nếu kết quả cho thấy cần (gộp vùng chồng nhau, phát hiện tuyến quay đầu, thử 3–4 lần reflection, chọn phía thông minh hơn), có tách tập dev/test.
6. Chốt số liệu, viết báo cáo RQ1: kiến trúc, thiết kế thực nghiệm, kết quả, phân tích thất bại, giới hạn.

**Ưu tiên trung bình:**
7. Độ trễ (mục tiêu 3,5 giây): cache trích xuất theo bản tin, rút gọn prompt; nếu vẫn vượt thì báo cáo trung thực.
8. Ghi vào luận văn: đổi model so với đề cương và lý do; profile `car` của OSRM không mô phỏng xe máy; ngày OSM extract; tọa độ gazetteer chỉ là một điểm trên đường.
9. Gửi danh sách 122 điểm của CSGT để mở rộng gazetteer lên 150+; xác nhận tọa độ 11 đường chưa giải quyết.
10. Commit, merge vào `main`; cập nhật nguồn #9 trong notebook.

**Sau RQ1:** triển khai thật (VPS, tên miền) cho RQ3; thêm xác thực API key và rate limiting; tự host geocoder.

---

## 4. Đánh giá khả thi

**Ước lượng mức độ hoàn thành (của mình, không phải số đo chính xác):**

| Hạng mục | Lần trước | Hiện tại |
|---|---|---|
| Phần code hệ thống | ~85–90% | **~92%** |
| Dữ liệu | ~60% | **~75%** |
| Thực nghiệm và bằng chứng cho luận văn | ~35–40% | **~50%** (đã có kết quả bộ 20 kịch bản cũ; chưa có số liệu v2) |
| Toàn bộ RQ1 | ~65–70% | **~75–78%** |

**Khả năng nộp báo cáo RQ1 ngày 05/11:** **khả thi, có điều kiện** (còn 12 ngày). Điều kiện: có số liệu v2 đủ lần lặp, phân tích được các kịch bản thất bại, và trình bày trung thực giới hạn về độ trễ và cỡ mẫu. Điều kiện này khả thi nếu không mở thêm phạm vi.

*Thuận lợi:* code gần xong; có 50 kịch bản tin thật hợp lệ; geocoding đã đáng tin hơn; quota đủ cho khoảng một lần chạy v2 mỗi ngày.

*Điều kiện:*
- Kết quả benchmark trên v2 phải hợp lý. Chưa thể hứa hệ thống đề xuất vượt baseline cho tới khi có số liệu.
- Bạn xem lại dữ liệu cần kiểm tra bằng mắt; không có bước này thì số liệu có nguy cơ sai sót.
- Quota Gemini giới hạn số lần chạy: tối đa khoảng 3–4 lần lặp trên v2 trước hạn.
- Chấp nhận một báo cáo trung thực, có giới hạn rõ, hơn là cố đạt kết quả đẹp.

**Lịch gợi ý:**

| Thời gian | Việc |
|---|---|
| 23/10 | Đọc kết quả benchmark cũ (20 kịch bản); xem lại dữ liệu v2 |
| 24/10 | Chạy benchmark v2 (`--runs 1`) |
| 25–27/10 | Chạy lặp thêm mỗi ngày; phân tích kịch bản thất bại |
| 28/10–02/11 | Chỉnh Reflector nếu cần, chốt số liệu, viết báo cáo |
| 03–04/11 | Đệm cho sự cố, kiểm tra lần cuối |
| 05/11 | Nộp |

**Rủi ro chính:**
- Kết quả không như kỳ vọng (vẫn có thể là báo cáo hợp lệ, cần trao đổi với thầy).
- Độ trễ vượt 3,5 giây (thử nghiệm cho 4–12 giây, chủ yếu là thời gian gọi Gemini).
- Gemini quá tải (503), đổi model hoặc quota bất ngờ.
- Dữ liệu: đoạn trích chưa kiểm tra nguyên văn, điểm đi/đến tạo tự động, tọa độ chỉ là một điểm trên đường, 15 trong 31 tin mới là tin cũ (2011–2021).
- Thời gian dành cho RQ2, RQ3 và phần viết có thể nhiều hơn dự kiến.

---

## 5. Cần làm gì tiếp theo

**Việc kế tiếp ngay (theo thứ tự):**
1. ~~Chờ benchmark nền kết thúc~~ **Đã xong.** Đã đọc kết quả: 240 dòng, 0 lỗi, perception luôn là `gemini`.
2. Mở `data/results_rq1.csv` và lọc các dòng `PROPOSED` có `judge_safe=False` trên kịch bản khả thi để tìm nguyên nhân (trích xuất, hình học, hay không thể né).
3. Bạn xem lại các mục `needs_review` và đoạn trích trong `scenarios_v2.json`.
4. Quyết định thay `scenarios.json` bằng v2, và có giữ kịch bản cũ #20 hay không.
5. Ngày mai (sau khi quota đặt lại): chạy benchmark v2.
6. Commit nhánh `rq1-finalize` khi bạn đồng ý, và quyết định có cập nhật notebook hay không.

**Lệnh hữu ích:**

```bash
docker compose up -d osrm                                   # bật OSRM
.venv/bin/python tests/smoke_check.py                       # kiểm tra OSRM và Gemini
.venv/bin/python -m pytest -q tests                         # test offline (54 pass)
RUN_LLM_TESTS=1 .venv/bin/python -m pytest tests/test_perception.py   # test Gemini thật
.venv/bin/python scripts/validate_scenarios.py data/scenarios_v2.json
.venv/bin/python scripts/build_scenarios_from_news.py --max 51        # tạo lại v2 (giữ kịch bản cũ #20)
.venv/bin/python scripts/expand_gazetteer.py                # mở rộng gazetteer (chạy lại được)
.venv/bin/python -u tests/run_rq1_experiment.py --scenarios data/scenarios_v2.json --runs 1 2>&1 | tee run_v2.log
```

**Nhắc nhở:** nếu key bị lộ, hãy tạo key mới ngay sau đồ án và tuyệt đối không commit `.env`.
