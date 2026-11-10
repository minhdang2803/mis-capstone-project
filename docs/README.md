# RQ1 ở mức luận văn — nhánh `rq1_final_project`

Nhánh này nâng RQ1 từ đồ án MIS lên mức luận văn. Report đồ án MIS đã chốt ngày 11/11/2026 và
không sửa thêm. Mọi thay đổi ở đây chỉ đi vào chương RQ1 của luận văn, viết trong 7–15/12/2026.

Chi tiết từng việc ở [`RQ1_LUANVAN_PLAN.md`](RQ1_LUANVAN_PLAN.md); báo cáo B2+ ở
[`PROGRESS_2026-11-10.md`](PROGRESS_2026-11-10.md).

## Hai tài liệu, hai phiên bản

| | Report đồ án MIS | Chương RQ1 luận văn |
|---|---|---|
| Trạng thái | Chốt 11/11/2026 | Viết 7–15/12/2026 |
| Hệ thống | v2, benchmark ngày 30/10/2026 | Bản đóng băng sau buổi gặp thầy (dự kiến 17–22/11) |
| Baseline | B1, B2, B1+ (ablation) | B1, B2, B2+, B1+ (B2++ nếu thầy yêu cầu) |
| Số liệu | `data/results_rq1_v2_reflector2.csv` (168 dòng) | Chạy lại toàn bộ trên bản đóng băng, cộng held-out |
| Nơi viết | [Doc Claude Docs](https://claude.ai/artifact/JgNiYTXcuEiq1Z46xk8kzz) | Bản sao mới của doc MIS — không sửa lên bản đã nộp |

## Sáu khoảng trống và trạng thái

Sắp theo ưu tiên của kế hoạch, không theo thứ tự trong nhận xét gốc. Held-out chạy sau cùng,
trên bản đã đóng băng.

| Ưu tiên | Khoảng trống | Việc làm | Trạng thái | Kế hoạch |
|---|---|---|---|---|
| 1 | B2 có thể là baseline yếu | B2+: B2 có thêm công cụ `check_route_safety` (phép kiểm tra hình học của Reflector) | **Xong 10/11** | §2.1 |
| 2 | Chưa có bộ kiểm tra giữ riêng | 15–20 kịch bản từ 61 điểm ngập và 13 bài báo chưa dùng; chạy **một lần** | Chưa — 30/11–6/12 | §2.2 |
| 3 | Tổng quan tài liệu mỏng | Mở rộng Chương 2 | Chưa — làm được ngay, không tốn quota | §2.3 |
| 4 | Một LLM, chưa đo `temperature > 0` | 3 lượt `temperature > 0` và một mô hình thứ hai | Chưa — 30/11–6/12 | §2.4 |
| 5 | Chưa tự động thu thập tin | Lớp lấy tin cho 8 đầu báo, hoặc sửa câu chữ RQ1 — chờ thầy chốt | Chưa | §2.5 |
| 6 | Cặp điểm đi–đến do dựng | 10–15 cặp đi–đến thật | Chưa | §2.6 |

## Kết quả B2+ (42 kịch bản, chạy 10/11/2026)

| Hệ thống | Né ngập | Recall trích xuất | Lượt LLM / kịch bản |
|---|---|---|---|
| B2 | 4/42 (9,5%) | 0,80 | ~3 |
| B1+ | 12/42 (28,6%) | 0,95 | 1 |
| B2+ | 26/42 (61,9%) | 0,92 | ~8 |
| Proposed | 35/42 (83,3%) | 0,95 | 1 |

- **B2 đúng là baseline yếu.** B2+ hơn B2 ở 22 kịch bản, kém ở 0 (McNemar p = 4,8×10⁻⁷).
- **Proposed hơn B2+ nhưng chưa có ý nghĩa thống kê.** 12/3, p = 0,035, không qua ngưỡng
  Bonferroni α/4 = 0,0125 mà report MIS dùng (thêm B2+ thì thành α/5 = 0,01). Trên 37 kịch bản
  B2+ đọc đủ tin, p = 0,146.
- **Lợi thế vững là đường vòng và chi phí.** Trên 23 kịch bản cả hai cùng giải, trung vị đường
  vòng là 0,68 km (Proposed) so với 2,35 km (B2+); B2+ dài hơn ở 20/23 (sign test p = 4,9×10⁻⁴).
  Proposed gọi LLM 1 lần, B2+ khoảng 8 lần.
- **B2+ giải được 3 kịch bản Proposed không giải được.** #7 và #39: Perception không nhận tên
  địa điểm phi tên đường. #34: có đường vòng sạch 3,95 km nằm ngoài tầm ring search.

Chạy lại (tốn khoảng 350 lượt Gemini; cần OSRM đang chạy):

```bash
docker compose up -d osrm
.venv/bin/python tests/run_rq1_experiment.py --scenarios data/scenarios_v2.json \
    --systems B1_OSRM,B2PLUS_VERIFIER --out data/results_rq1_v2_b2plus.csv
.venv/bin/python scripts/compare_b2plus.py
```

## Viết lại gì khi chuyển report MIS thành chương RQ1

- [ ] Tạo bản sao doc MIS làm doc mới; bản đã nộp giữ nguyên.
- [ ] Thay toàn bộ số liệu Chương 5 bằng kết quả trên bản đóng băng; held-out thành một mục riêng.
- [ ] Viết lại các câu "B2 dùng chung công cụ" ở Mục 2.3, Mục 3.2 (đoạn trước Bảng 3.1 và chuỗi
      so sánh) và Mục 4.6; thêm B2+ vào Bảng 3.1. Gạch đầu dòng "B2 không có bước kiểm định
      hình học" ở Mục 6.4 của report MIS được B2+ trả lời, nên chuyển từ giới hạn sang kết quả.
- [ ] Chốt với thầy B2+ là baseline chính hay phân tích phụ. Nếu là baseline chính thì H1 với
      B2+ hiện chưa đạt (p = 0,035); lập luận phải dựa trên đường vòng và chi phí LLM, hoặc cần
      thêm kịch bản để đủ lực kiểm định.
- [ ] Viết lại câu kết luận "Perception chuyên trách nâng recall từ 0,80 lên 0,95": B2+ đạt 0,92
      mà không có tác tử Perception riêng, nên phần lớn mức tăng có thể đến từ việc buộc tác tử
      đọc hết tin chứ không hẳn từ việc tách vai.
- [ ] Đóng góp (Tóm tắt, Mục 1.6, Kết luận): giữ ý "kiểm định bằng hình học thay vì bằng LLM",
      chuyển trọng tâm sang "tách việc kiểm tra và sửa lộ trình ra khỏi LLM".
- [ ] Trần 38/42 ở Mục 5.4: viết lại `routing_ceiling.py`, commit, chạy lại, rồi bỏ chú thích
      "script chưa có trong mã nguồn".
- [ ] Mục 6.3–6.4: giới hạn nào đã lấp (held-out, `temperature > 0`, mô hình thứ hai, cặp điểm
      thật, thu thập tin) thì chuyển thành kết quả; giới hạn còn lại giữ nguyên.
- [ ] Chương 2: tổng quan tài liệu mở rộng (ưu tiên 3).

## Mốc thời gian

| Thời gian | Việc |
|---|---|
| ~16–17/11 | Gặp thầy: chốt §2.5, mô hình thứ hai, B2++, mức yêu cầu cho §2.6 |
| 17–22/11 | Sửa hệ thống (Perception cho #7, #39; cache Perception), chạy lại 42 kịch bản, **đóng băng** |
| 23–29/11 | RQ2 trên bản đóng băng; lớp thu thập tin; dựng (chưa chạy) held-out |
| 30/11–6/12 | Held-out chạy một lần; `temperature > 0`; mô hình thứ hai |
| 7–15/12 | Viết chương RQ1 và dự phòng cho vòng sửa của thầy |

Đến 15/12/2026: RQ1 hoàn chỉnh, RQ2 đạt 70–80% (định nghĩa cụ thể ở §5 của kế hoạch).

## Tệp trên nhánh này

| Tệp | Nội dung |
|---|---|
| `docs/RQ1_LUANVAN_PLAN.md` | Kế hoạch chi tiết sáu khoảng trống, thứ tự thực hiện, RQ2 |
| `docs/PROGRESS_2026-11-10.md` | Báo cáo B2+: thiết kế, kết quả, câu trả lời khi bảo vệ |
| `app/agents/single_agent.py` | B2 và B2+ (`verify=True`) |
| `tests/run_rq1_experiment.py` | Hệ `B2PLUS_VERIFIER`, chỉ chạy khi gọi tên qua `--systems` |
| `tests/test_single_agent.py` | Kiểm thử B2 và B2+ |
| `scripts/compare_b2plus.py` | So sánh B2+ với B2, B1+, Proposed |
| `data/results_rq1_v2_b2plus.csv`, `..._summary.json` | Kết quả B2+ |
