# Kế hoạch nội dung thuyết trình 30 phút — Air Quality Analytics Platform

Môn INT1422 · Kho dữ liệu và Khai phá dữ liệu. Tài liệu này là **kịch bản nói** cho 31 slide chính
+ 18 slide phụ lục, thiết kế cho 3 người nhưng **sập xuống 1 người vẫn dùng nguyên bộ slide**.

Mọi con số lấy từ `artifacts/` khi soạn (24/10/2026). Nếu chạy lại `python scripts/run_all.py`
trước buổi bảo vệ, đối chiếu lại các số in đậm ở mục 8.

---

## 0. Nguyên tắc trình bày (đọc trước khi tập)

1. **Mồi – lá chắn.** Trên slide chính chỉ nêu *kết luận + một chi tiết chưa mở* (con số, thuật ngữ,
   lựa chọn). Đó là mồi để thầy hỏi câu cấp 1 ("cái này là gì / vì sao / tính thế nào"). Câu trả lời
   đầy đủ nằm ở một slide phụ lục xác định (bảng đối chiếu ở mục 6). Không có mồi nào không có đạn.
2. **Không nhắc thứ không nói được.** Mỗi thuật ngữ / công cụ / con số trên slide phải nói được 2 phút.
   (Đã loại XGBoost/LightGBM khỏi stack vì không dùng tới.)
3. **Cửa cắt.** Các slide đánh dấu *(cửa cắt)* được bỏ khi thiếu giờ mà không phá mạch: 16 (bớt pivot),
   26 (rút demo), 28, 29 — trong đó **S28 cắt mặc định cả khi đủ 30'** (tổng thời lượng tính theo
   từng slide là ~31 phút, xem mục 7). Chúng vẫn nằm trong phụ lục nên không mất nội dung.
4. **Mốc canh giờ khi tập:** phút 10 → đang ở quanh slide 10; phút 20 → quanh slide 22;
   phút 25 → slide 26+. Trễ mốc thì cắt theo cửa cắt, không nói nhanh hơn.
5. Khi bị hỏi: trả lời bằng số thuộc (mục 8), rồi chủ động "*em có chi tiết ở slide phụ lục X*".
   Trong chế độ trình chiếu gõ **số slide + Enter** để nhảy tới ngay.

---

## 1. NGƯỜI A — "Vì sao & dữ liệu" (slide 1–9, ≈ 8 phút)

Khối dễ học nhất: mọi số đều đọc được từ chart/bảng trên slide. Người ít sẵn sàng nhất nhận khối này.

### Slide 1 — Bìa (10")
- **Nói:** chào thầy/cô và các bạn; giới thiệu nhóm và tên đề tài: *"Kho dữ liệu chất lượng không khí
  Bắc Kinh và cảnh báo sớm PM2.5 vượt ngưỡng."*

### Slide 2 — Câu hỏi nghiệp vụ (1')
- **Câu mở:** *"Đề tài của nhóm bắt đầu từ một câu hỏi rất cụ thể của người vận hành."*
- **Nói:** Trung tâm quan trắc mỗi giờ phải quyết: có phát cảnh báo hạn chế hoạt động ngoài trời ở
  trạm này cho **giờ tới** không? Cách làm hiện tại là chờ số đo vượt ngưỡng rồi mới báo — tức luôn
  trễ 1 giờ. Quy mô vấn đề: **PM2.5 trung bình 79,8 µg/m³** trên 12 trạm trong 4 năm;
  **khoảng 1/4 số giờ** có PM2.5 ≥ 115 µg/m³.
- **Câu chuyển:** *"Để trả lời câu hỏi giờ tới một cách tin được, trước hết phải hiểu dữ liệu."*

### Slide 3 — Hai nửa môn học trong một hệ thống (1')
- **Câu mở:** *"Đề tài may mắn ôm trọn hai nửa của học phần."*
- **Nói:** Nửa **kho dữ liệu**: tổ chức 4 năm dữ liệu để phân tích quá khứ ở mọi góc nhìn (OLAP).
  Nửa **khai phá**: học từ quá khứ để dự đoán giờ tới (phân loại cảnh báo). Sơ đồ trên slide là
  toàn luồng: nguồn → lake → staging → kho → mart → khai phá → dashboard.
- **Câu chuyển:** *"Mình đi từ nguồn dữ liệu."*

### Slide 4 — Dữ liệu: hai nguồn mở, có giấy phép (1')
- **Nói:** Nguồn chính **UCI #501** — Beijing Multi-Site Air Quality: **420.768 bản ghi giờ,
  12 trạm, 03/2013–02/2017, 12 thuộc tính** (6 chất ô nhiễm + 5 khí tượng + hướng gió), giấy phép
  CC BY 4.0, có DOI. Nguồn phụ **Open-Meteo** (tái phân tích ERA5, theo giờ, cùng 12 toạ độ):
  lấp chỗ thiếu thời tiết và thêm độ che phủ mây. Không có dữ liệu cá nhân.
- **Mồi → lá chắn:** "*hai nguồn ghép với nhau thế nào?*" → **A2**.

### Slide 5 — Chất lượng dữ liệu: quyết định từng cột, không làm đẹp (1'30")
- **Câu mở:** *"Làm sạch trong dự án này là một chuỗi quyết định, không phải làm bảng đẹp."*
- **Nói:** Chart % thiếu theo cột. **CO thiếu nhiều nhất 4,9%**, có chuỗi thiếu liên tục dài tới
  **1.517 giờ** → **không nội suy** (nội suy chuỗi dài = bịa dữ liệu), giữ NULL + cờ chất lượng.
  Thời tiết thiếu rất ít (~0,1%) → lấp từ Open-Meteo, **ghi nguồn từng ô**, sau lấp còn **0 ô thiếu**.
  **60 dòng** chạm trần thiết bị (999 / 10.000) → giữ lại + cờ SUSPECT_CAP. Nguyên tắc ML: median
  điền thiếu chỉ tính trên tập train.
- **Mồi → lá chắn:** "*vì sao không nội suy hết cho đẹp?*" → **A3**.

### Slide 6 — Rời rạc hoá cho phân tích (30")
- **Nói:** Giờ → buổi, ngày → mùa, 16 hướng gió → 4 phần tư → bắc/nam. Đây là các phân cấp sẽ dùng
  lại toàn bộ ở phần kho dữ liệu.

### Slide 7 — Kiến trúc tổng (1'30")
- **Câu mở:** *"Toàn bộ hệ thống trên một trang."*
- **Nói (chỉ theo sơ đồ):** Hai luồng vào: (1) batch: CSV UCI + Open-Meteo → **MinIO data lake**
  (raw → processed Parquet); (2) tác nghiệp: **SQLite** mô phỏng nguồn giao dịch → CDC theo
  watermark → Airflow. Sau đó **PostgreSQL staging** → **dbt** dựng kho (fact + dimension) và
  các **mart** tổng hợp → đặc trưng ML → **dashboard FastAPI + React**. Airflow điều phối, Docker
  đóng gói hạ tầng.
- **Mồi → lá chắn:** "*lake / staging / mart khác nhau thế nào?*", "*4 công cụ kia phải chăng đều
  là database?*" → **A4**.

### Slide 8 — Tái lập được bằng một lệnh (30")
- **Nói:** `python scripts/run_all.py` — **14 bước, chạy lại từ trạng thái trống mất 11,2 phút**,
  mọi bước idempotent (chạy lại không nhân đôi dữ liệu). Đây là lời cam kết: mọi con số hôm nay
  ai cũng tạo lại được.

### Slide 9 — Câu chuyển (10")
- **Nói:** *"Dữ liệu đã nằm đúng chỗ. Câu hỏi tiếp: tổ chức thế nào để phân tích được mọi góc nhìn
  mà vẫn kiểm chứng được? Đó là phần kho dữ liệu."* → trao cho người B.

---

## 2. NGƯỜI B — "Kho dữ liệu & OLAP" (slide 10–19, ≈ 11 phút)

Phần trọng tâm thứ nhất của môn. Demo trực tiếp nằm ở slide 16 — tập trước với Docker đang chạy.

### Slide 10 — Grain: trạm × giờ (1')
- **Câu mở:** *"Quyết định quan trọng nhất khi thiết kế kho là phát biểu grain: một dòng fact là gì."*
- **Nói:** Một dòng = **một trạm tại một giờ**. Chọn độ mịn gốc vì: cuộn từ giờ lên ngày/tháng được,
  ngược lại không; và bài toán cảnh báo giờ tới cần đúng mức giờ. Mọi độ đo, mọi khóa chiều phải
  khớp grain này.
- **Mồi → lá chắn:** "*vì sao không lưu mức ngày cho nhẹ?*" → **A5**.

### Slide 11 — Lược đồ hình sao 4 chiều (1')
- **Nói:** Fact trung tâm `fact_air_quality_hourly` + 4 chiều: **ngày, giờ, trạm, hướng gió**.
  Hướng gió là chiều đặc biệt — nó trả lời câu hỏi **"vì sao"** ô nhiễm đến (điều kiện vận tải
  khí). Thời tiết không làm chiều riêng mà là độ đo trên fact.
- **Mồi → lá chắn:** "*sao không có chiều thời tiết?*" → **A6**.

### Slide 12 — Phân cấp → 180 tổ hợp (1')
- **Nói:** 4 phân cấp: ngày→tháng→quý→năm; giờ→buổi; trạm→quận; hướng→phần tư→bắc/nam.
  Tổng tổ hợp mức **5·3·3·4 = 180** (mỗi chiều tính cả mức ALL) — không thể, cũng không cần, tính
  trước hết; chọn theo truy vấn thật.

### Slide 13 — Ba khối tính trước (1')
- **Nói (bảng):** `mart_station_daily` (trạm, ngày) 17.532 dòng — nhỏ hơn fact 24 lần, cho xu hướng;
  `mart_station_monthly` 576 dòng — báo cáo tháng/mùa; `mart_olap_cube` 6.075 dòng — trang OLAP đọc
  vài ms. Tiêu chí chọn: đúng các truy vấn dashboard thật đang phát ra.
- **Mồi → lá chắn:** "*tính trước thì có trả lời được mọi truy vấn không?*" → **A8** (đoạn cuối).

### Slide 14 — CUBE 5 thuộc tính = 32 grouping sets (1')
- **Nói:** Cube tổng hợp theo CUBE(năm, mùa, quận, buổi, phần tư gió): **5 thuộc tính độc lập →
  2⁵ = 32 grouping sets**. Nhấn: số thuộc tính trong CUBE **không bằng** số bảng chiều — 2 thuộc
  tính có thể cùng nằm trong một chiều.
- **Mồi → lá chắn:** "*4 chiều sao ra 32 khối?*" → **A7**.

### Slide 15 — Kiểm chứng 100% (1')
- **Câu mở:** *"Phần nhóm tự hào nhất của kho: mọi ô tính trước đều được kiểm chứng."*
- **Nói:** Script tính lại **từng ô** của 32 khối trực tiếp từ fact rồi so khớp:
  **24.759/24.759 ô đúng = 100%**. Cộng **130 dbt test** (khóa, not-null, khóa ngoại, cube phân
  hoạch fact). Truy vấn được viết lại: thuộc tính nằm trong cube → đọc mart 2–6 ms; thiếu → quét
  fact 130–400 ms.
- **Mồi → lá chắn:** "*kiểm chứng cụ thể thế nào?*" → **A8**.

### Slide 16 — DEMO OLAP trực tiếp (3') — *(cửa cắt: thiếu giờ bỏ bước pivot)*
- **Kịch bản bấm:** mở trang `/olap`, đang xem **Năm × Mùa** (đọc từ cube) → bấm **2015** để
  drill-down sang quý → **roll-up** về năm → lọc quận **Dongcheng** (slice) → thêm Xicheng + 2016
  (dice) → **pivot** đổi hàng/cột. Vừa bấm vừa gọi tên thao tác.
- **Dự phòng:** mất mạng/Docker lỗi → mở `notebooks/olap/olap_demo.ipynb` (output đã chạy sẵn),
  nói như thường.

### Slide 17 — Insight từ dice: gió nam (1')
- **Nói:** Kết quả dice thật: cùng quận lõi đô thị, mùa đông, gió **bắc ~85** vs gió **nam ~133
  µg/m³ (+60%)** — nguồn khí phía nam (Hà Bắc); tỷ lệ giờ vượt ngưỡng tăng **28% → 43%**. Đây là
  giá trị nghiệp vụ của chiều hướng gió. Nếu bị hỏi *"sao biết khí từ Hà Bắc?"*: nói thẳng đây là
  **tương quan theo hướng gió**, dự án không mô phỏng đường vận chuyển khí.

### Slide 18 — Tổng hợp đúng (1')
- **Nói:** Trung bình là độ đo **không cộng**. Mart và cube luôn lưu **sum + count** rồi chia;
  nên cube gộp đúng kể cả khi mức độ thiếu khác nhau giữa các nhóm.
- **Mồi → lá chắn:** "*lấy tổng số giờ bằng SUM cả bảng cube được không?*", "*trung bình của các
  trung bình?*" → **A9**.

### Slide 19 — Câu chuyển (10")
- **Nói:** *"Kho trả lời được 'đã xảy ra gì, vì sao'. Còn câu hỏi đầu bài — 'giờ tới có vượt ngưỡng
  không' — là việc của khai phá dữ liệu."* → trao cho người C.

---

## 3. NGƯỜI C — "Khai phá & vận hành" (slide 20–31, ≈ 12 phút)

Khối khó nhất, chắc chắn bị hỏi sâu nhất — giao người chắc chắn nhất.

### Slide 20 — Bài toán phân loại (1')
- **Nói:** Nhãn **y = 1 nếu PM2.5(t+1h) ≥ 115 µg/m³** (ngưỡng đợt ô nhiễm đã khoá từ phân tích
  EDA). **49 đặc trưng**, mọi đặc trưng chỉ dùng thông tin **biết tại thời điểm t**: PM2.5 hiện tại,
  độ trễ 1–24 giờ, xu hướng, các chất khác, khí tượng, giờ/tháng/mùa, trạm, cụm trạm.
- **Mồi → lá chắn:** "*115 là gì, có phải AQI 115 không?*" → **A1**.

### Slide 21 — Chia tập theo thời gian & chống rò rỉ (1')
- **Câu mở:** *"Với dữ liệu thời gian, cách chia tập quyết định kết quả có tin được không."*
- **Nói (timeline):** train 03/2013–12/2015: **276.380 dòng** (25,2% nhãn 1); val 01–06/2016:
  **47.338 dòng** (15,8%); test 07–12/2016: **48.781 dòng** (23,9%). Chọn độ sâu cây và ngưỡng
  xác suất **chỉ trên val**; test dùng đúng một lần để báo cáo. Median điền thiếu fit trên train.
- **Mồi → lá chắn:** "*vì sao không k-fold?*", "*rò rỉ ở đâu?*" → **A12**.

### Slide 22 — Baseline (1')
- **Nói:** Majority: accuracy **0,761 nhưng F1 = 0** — không phát được cảnh báo nào (bẫy accuracy
  với lớp thiểu số ~24%). Persistence (PM2.5 hiện tại ≥ 115): F1 **0,914** — baseline mạnh vì hai
  giờ liên tiếp tương quan cao. Mô hình phải chứng minh giá trị **thêm** trên baseline này.

### Slide 23 — Kết quả 4 mô hình (1'30")
- **Nói (bảng + ma trận nhầm lẫn):** Cây quyết định (entropy) F1 **0,921**;
  **HistGradientBoosting F1 0,927** (precision 0,926, recall 0,928, ROC-AUC 0,993) — mô hình khoá,
  ngưỡng xác suất 0,50. So persistence: giờ ô nhiễm bị bỏ sót (FN) **1.000 → 838**, cảnh báo nhầm
  (FP) **999 → 865**.
- **Mồi → lá chắn:** "*vì sao chọn cây & boosting?*" → A12 cuối; "*ngưỡng 115 với ngưỡng 0,50?*" → A13.

### Slide 24 — Giá trị thật: báo trước được (1')
- **Câu mở:** *"F1 +0,013 nghe nhỏ — giá trị thật nằm ở thứ persistence không làm được."*
- **Nói:** Trong **1.000 giờ đang sạch nhưng giờ sau vượt ngưỡng** (lúc đợt ô nhiễm bắt đầu — thời
  điểm cần cảnh báo nhất), mô hình báo trước **304 lần = 30,4%**, persistence **0% theo định nghĩa**.
  Kiểm định McNemar trên từng giờ test: **b = 594** giờ chỉ mô hình đúng, **c = 298** giờ chỉ
  persistence đúng, **p ≈ 5×10⁻²³** — khác biệt có ý nghĩa thống kê.
- **Mồi → lá chắn:** "*McNemar là gì, đủ để triển khai?*" → **A13**.

### Slide 25 — Tầm dự báo (1')
- **Nói (chart):** F1 test theo tầm: 1h **0,914 → 0,927** (+0,013); 3h **0,806 → 0,832** (+0,026);
  6h **0,702 → 0,745** (+0,043). Càng cần báo sớm, mô hình càng có lợi thế. **12/12 trạm** đều
  F1 cao hơn persistence.

### Slide 26 — DEMO /canh-bao + /phat-lai (2') — *(cửa cắt: rút còn /canh-bao)*
- **Kịch bản:** `/canh-bao`: hai ma trận nhầm lẫn cạnh nhau (mô hình vs cách hiện tại), dòng thời
  gian xác suất tại một trạm — xanh = cảnh báo đúng, vàng = báo nhầm, đỏ = bỏ sót. `/phat-lai`:
  kéo mốc thời gian, hệ thống phát dự đoán cho giờ đích, **số đo thật chỉ hiện khi mốc dữ liệu đã
  đi qua** — minh hoạ "dự đoán trước, đối soát sau". Nói rõ: F1 cao trong cửa sổ demo không phải
  bằng chứng cho độ tốt của mô hình (cửa sổ chọn nhiều giờ ô nhiễm).
- **Dự phòng:** ảnh chụp màn hình đã lưu trong slide.

### Slide 27 — Luồng CDC: hệ thống "sống" (1')
- **Nói (sơ đồ):** SQLite nguồn tác nghiệp → đọc **tăng dần theo watermark** (chỉ lấy bản ghi sau
  mốc) → Airflow DAG → MinIO → upsert staging. Idempotency bằng load_registry (đối chiếu object
  key + sha256 + row_count). Mỗi batch nạp xong còn được **chấm MAE đối soát với số đo thật,
  vượt 12 µg/m³ thì bật cờ giám sát**. Nói thẳng giới hạn: watermark bắt được **insert mới**; bản ghi cũ bị
  **sửa/xoá sau khi mốc đã đi qua thì không bắt được** — cần đối soát lại theo partition.
- **Mồi → lá chắn:** "*bản ghi cũ bị sửa thì sao?*", "*chạy lại có nhân đôi không?*",
  "*vượt ngưỡng MAE rồi làm gì?*" → **A14**.

### Slide 28 — Thí nghiệm cảnh báo 6 giờ (1') — *(cửa cắt)*
- **Nói:** Câu hỏi mở rộng: đang sạch, có đợt (≥3 giờ liên tục vượt ngưỡng) bắt đầu trong t+1→t+6
  không. Mô hình có đặc trưng trung vị các trạm lân cận: bắt **506/730 đợt = 69,3%**; luật đơn giản
  "hiện tại ≥ 105": **468/730 = 64,1%**; **trung vị thời gian báo trước 3 giờ** so với 1 giờ; trần
  cảnh báo nhầm **0,5/ngày-trạm** chọn trên validation. Ghi rõ: thí nghiệm riêng, chưa thay mô hình t+1.
- **Mồi → lá chắn:** "*định nghĩa đợt?*", "*vì sao kiểm tra tới t+8?*" → **A15**.

### Slide 29 — Phân tích bổ trợ (1') — *(cửa cắt)*
- **Nói:** Hồi quy PM2.5 t+1 (dự báo số): **MAE 8,87 µg/m³** — sai số tuyệt đối trung bình, không
  phải trần sai số từng dự báo. Phân cụm: mỗi trạm thành một vector hồ sơ → K-Means, thử K=2,3,4;
  **K=2, silhouette 0,664**, cụm 9 trạm + 3 trạm; địa lý chỉ dùng đối chiếu, không đưa vào đặc trưng.

### Slide 30 — Khuyến nghị & hạn chế (1')
- **Nói:** Nên làm: (1) cảnh báo theo **xác suất mô hình**, không chờ số đo vượt; (2) ưu tiên mùa
  đông, buổi tối, khi có gió nam; (3) cần báo sớm 3–6 giờ → chấp nhận precision thấp hơn để recall
  cao. Hạn chế nói thật: test chỉ 6 tháng cuối 2016, dữ liệu lịch sử; +0,013 F1 ở 1 giờ là khiêm
  tốn; ngưỡng 115 vốn là ngưỡng 24 giờ áp cho từng giờ.

### Slide 31 — Kết (10")
- **Nói:** cảm ơn, mời hỏi đáp. *"Nhóm có chuẩn bị thêm slide chi tiết phía sau, rất mong các câu
  hỏi."*

---

## 4. PHỤ LỤC (slide 32–49) — chỉ mở khi bị hỏi

Slide **A0** ngay sau slide 31: mục lục phụ lục (cụm → số slide) để gõ số nhảy nhanh.
Mỗi slide dưới viết đúng cấu trúc câu trả lời được hỏi: *dự án dùng gì → nghĩa là gì → vì sao.*

| # | Chủ đề lá chắn | Câu hỏi nó đỡ | Nội dung trả lời mẫu |
|---|---|---|---|
| A1 | Ngưỡng 115 | "Vì sao 115? Phải AQI không?" | 115 µg/m³ = ranh giới dải "ô nhiễm trung bình" theo quy chuẩn AQI Trung Quốc cho PM2.5 (khác AQI = 115); khoá từ phân tích đợt ô nhiễm Phase 8c; đợt tại trạm cần ≥3h liên tục ≥115. |
| A2 | Ghép 2 nguồn | "Open-Meteo ghép thế nào?" | Cùng 12 toạ độ, cùng giờ. Quy tắc resolve: UCI ưu tiên, OM chỉ lấp khi UCI null, **ghi nguồn từng ô**; cloud_cover chỉ có ở OM; RH suy từ TEMP+DEWP (không lấy RH của OM). Script fill-rate đối soát tỷ lệ lấp thật. |
| A3 | Vì sao không nội suy | "Điền hết cho đẹp đi?" | Chuỗi thiếu CO dài 343–1.517h: nội suy chuỗi dài = bịa dữ liệu, tạo đợt giả. Giữ NULL + cờ; COUNT(cột) ≠ COUNT(*); NULL không phải 0. ML: median fit trên train, không nhìn val/test. |
| A4 | Vai trò từng lớp & công cụ | "Lake/staging/mart khác gì? Đều là database à?" | Lake (MinIO) = object storage giữ raw/processed nguyên vẹn; staging = vùng tiếp nhận có cấu trúc, đối soát nguồn; DWH (PostgreSQL) = fact/dimension phục vụ phân tích; mart = tập con phục vụ một nhu cầu. MinIO = object storage, PostgreSQL = RDBMS, dbt = khung biến đổi SQL (ELT), Airflow = điều phối — không phải tất cả là database. |
| A5 | Vì sao grain giờ | "Lưu mức ngày cho nhẹ?" | Grain gốc: giờ→ngày cuộn được, ngược lại mất thông tin vĩnh viễn; bài toán t+1 cần mức giờ; đổi grain sang ngày thì mất biến động trong ngày (giờ cao điểm buổi tối) — thứ mô hình đang dùng. |
| A6 | Vì sao không dim_weather | "Thời tiết sao không thành chiều?" | Thời tiết là điều kiện đo cùng sự kiện tại grain trạm×giờ → là **độ đo** trên fact, một nguồn sự thật. Nếu cần phân tích riêng hồ sơ thời tiết theo thời gian → dựng fact riêng, không nhét chiều. |
| A7 | 4 chiều mà 32 khối | "Khối nào ra đâu?" | CUBE(năm, mùa, quận, buổi, phần tư gió): mỗi thuộc tính giữ-lại-hoặc-cuộn-lên-ALL → 2⁵ = 32 grouping sets. 180 = tổ hợp **mức phân cấp**, mỗi chiều **tính cả mức ALL**: 5 = ngày/tháng/quý/năm/ALL, 3 = giờ/buổi/ALL, 3 = trạm/quận/ALL, 4 = hướng/phần tư/bắc-nam/ALL — số khác số grouping sets; năm+mùa cùng nằm trong dim_date. |
| A8 | Kiểm chứng kho | "Làm sao biết khối đúng?" | Script chạy lại GROUPING SETS từng khối trực tiếp từ fact, so từng ô: 24.759/24.759 = 100%. 130 dbt test: khóa duy nhất, not-null, FK, cube phân hoạch fact (mỗi dòng fact đóng góp đúng 1 lần vào mỗi grouping set). Không phải mọi truy vấn dùng được khối: thiếu 1 thuộc tính là quét fact (130–400ms). |
| A9 | Tổng hợp đúng | "SUM cube? Trung bình của trung bình?" | SUM cả bảng cube đếm cùng một quan trắc nhiều lần (mỗi dòng nằm trong nhiều grouping set). Gộp trung bình: tổng giá trị / tổng số đo hợp lệ — ví dụ 24×100 + 6×200 = 3.600/30 = 120, không phải 150. |
| A10 | Kiến trúc OLAP của dự án | "Nhóm dùng kiến trúc lưu trữ gì?" | Dự án dùng **ROLAP**: dữ liệu quan hệ trong PostgreSQL, tổng hợp bằng SQL + khối tính trước trong mart. Chưa cần MOLAP (engine ma trận đa chiều riêng) vì 420 nghìn dòng và 5 thuộc tính cube PostgreSQL xử lý trong vài ms. Nếu 100 trạm × 10 năm → cân nhắc columnar/MPP/Spark. |
| A11 | Khóa & SCD | "Dùng khóa gì? Trạm đổi quận thì sao?" | Hiện dùng khóa tự nhiên/biện minh: station_key = station_id, date_key = YYYYMMDD, time_key = 0–23, wind 0 = không rõ — hợp lý vì chiều tĩnh, nguồn duy nhất, không có thành viên thay đổi. Nếu thuộc tính chiều thay đổi (trạm đổi quận) → cần surrogate key + **SCD type 2** (bản ghi mới + valid_from/valid_to) để lịch sử fact không bị viết lại. |
| A12 | K-fold & rò rỉ | "Sao không k-fold? Rò rỉ ở đâu? 420.768 sao còn 372.499?" | Dữ liệu giờ liên tục: random split cho giờ láng giềng (gần như trùng nhau) vào cả train lẫn test → kết quả lạc quan. Chia theo thời gian: train → val → test, chọn siêu tham số trên val, test dùng một lần. **Vì sao 372.499 ≠ 420.768:** cửa sổ ML chốt 03/2013–12/2016 (01–02/2017 nằm ngoài ML — dùng cho đối soát CDC, xem A14); dòng nào thiếu nhãn PM2.5(t+1) hoặc không đủ chuỗi 24 giờ trước (lag 1–24h + trung bình trượt) bị loại — mỗi giờ thiếu làm gãy chuỗi nên kéo theo loại cả những giờ ngay sau nó. Rò rỉ đã rà: cửa sổ rolling/nhãn không tràn qua biên split (phát hiện và refit, F1 0,926 so với 0,927 — nói thật, không khẳng định hoàn hảo). Cây & HistGB: dễ giải thích + mạnh trên bảng dữ liệu đặc trưng đã dựng; HistGB = boosting (cây yếu tuần tự sửa lỗi trước), histogram bin cho nhanh. |
| A13 | McNemar & ngưỡng kép | "McNemar là gì? 115 với 0,50?" | McNemar so hai mô hình trên **cùng tập test** chỉ xét các cặp disagree: b = 594 giờ chỉ mô hình đúng, c = 298 chỉ persistence đúng, p ≈ 5×10⁻²³ → khác biệt thật. Nhưng ý nghĩa thống kê ≠ đủ triển khai (test 6 tháng, dữ liệu lịch sử). Hai ngưỡng khác nhau: **115** tạo nhãn từ nồng độ; **0,50** là ngưỡng xác suất ra quyết định — dịch được (0,45 của cây) để đổi recall/precision theo giá của FN vs FP. |
| A14 | CDC chi tiết | "Sửa/xoá bản ghi cũ? Nhân đôi? Vượt ngưỡng MAE?" | Watermark = mốc event_time đã nạp; mỗi lần chỉ lấy bản ghi sau mốc → bắt insert. Sửa/xoá sau mốc **không** bắt được → phương án: đối soát sha256 từng batch hoặc load lại partition. Không nhân đôi: upsert theo khóa grain + load_registry (object key + sha256 + schema_version + row_count khớp thì skip). **Giám sát MAE từng batch:** mỗi batch CDC chấm MAE với số đo thật, ngưỡng 12 µg/m³; vượt ngưỡng chỉ **bật cờ (monitor_only)** — mô hình khoá, không tự retrain. Tổng hợp: MAE 9,41 µg/m³ trên 111.944 giờ, chấm liên tục từ 01/2016 tới 28/02/2017 — cao hơn 8,87 của tập test vì đối soát chạy trên dòng thời gian vận hành, không phải một tập test cố định. |
| A15 | Đợt & thí nghiệm 6h | "Đợt là gì? t+8 để làm gì?" | Đợt tại trạm: ≥3 giờ liên tiếp ≥115 (thiếu số đo gián đoạn chuỗi); đa trạm: ≥6 trạm cùng lúc. Thí nghiệm: hiện tại sạch, hỏi có đợt bắt đầu trong t+1→t+6 không — đợt bắt đầu muộn nhất t+6 cần xem tới t+8 mới đủ 3 giờ; nhãn chỉ giữ khi cửa sổ nằm trong split; trần 0,5 FP/ngày-trạm chọn trên val. Replay: F1 cao trong demo không phải bằng chứng (cửa sổ chọn nhiều giờ ô nhiễm). |
| A16 | Hồi quy & phân cụm | "MAE nghĩa gì? Phân cụm cái gì?" | MAE 8,87 µg/m³ = trung bình sai số tuyệt đối (cùng đơn vị), không phải trần sai số từng dự báo. Phân cụm: đối tượng là **12 trạm** (mỗi trạm 1 vector hồ sơ), không phải 420k giờ; chuẩn hoá trước K-Means; K=2 silhouette 0,664 cao nhất trong K=2,3,4; cụm 9+3; silhouette đo tách cụm theo đặc trưng, không phải accuracy; địa lý không đưa vào đặc trưng. |
| A17 | Demo 3' & tái lập | "Chạy lại được không? Mất mạng?" | Luồng demo 3': `/` (quy mô) → `/olap` (1 roll-up + 1 slice) → `/canh-bao` (nhãn, baseline, kết quả) → `/phat-lai` (dự đoán/đối soát). Mất mạng: notebook OLAP đã chạy output + ảnh chụp. Tái lập: `run_all.py` 14 bước, 11,2 phút từ trống, idempotent. |

---

## 5. Bảng mồi → lá chắn (kiểm tra chéo trước buổi nói)

| Mồi trên slide chính | Câu hỏi kỳ vọng | Lá chắn |
|---|---|---|
| S4: "lấp từ Open-Meteo" | Ghép 2 nguồn thế nào? | A2 |
| S5: "giữ NULL + cờ" | Vì sao không nội suy? | A3 |
| S7: sơ đồ 4 công cụ | Đây đều là database à? | A4 |
| S10: "độ mịn gốc" | Vì sao không mức ngày? | A5 |
| S11: sao 4 chiều | Sao không chiều thời tiết? | A6 |
| S14: "32 grouping sets" | 4 chiều sao 32? | A7 |
| S15: "24.759/24.759" | Kiểm chứng thế nào? | A8 |
| S18: "sum + count" | SUM cube? Trung bình của trung bình? | A9 |
| S10–15 (ngữ cảnh) | Nhóm dùng kiến trúc OLAP gì? Khóa gì? SCD? | A10, A11 |
| S21: "theo thời gian", ba số dòng | Vì sao không k-fold? 420.768 sao còn 372.499? | A12 |
| S24: "p ≈ 5×10⁻²³" | McNemar là gì? Ngưỡng 115 vs 0,50? | A13 |
| S27: "watermark", "chấm MAE từng batch" | Sửa/xoá cũ thì sao? Nhân đôi? Vượt ngưỡng MAE? | A14 |
| S28: "≥3h liên tục, t+8" | Đợt là gì? Kiểm tra tới đâu? | A15 |
| S29: "MAE 8,87, K=2" | MAE nghĩa gì? Phân cụm cái gì? | A16 |

---

## 6. Bộ số phải thuộc (không nhìn slide cũng nói được)

**Dữ liệu:** 420.768 giờ · 12 trạm · 03/2013–02/2017 · PM2.5 TB 79,8 µg/m³ · ~1/4 giờ ≥ 115 ·
CO thiếu 4,9% (chuỗi 343–1.517h) · 60 dòng cờ trần · run_all 14 bước / 11,2 phút.

**Kho:** grain trạm×giờ · 4 chiều · 180 tổ hợp · CUBE 5 thuộc tính = 32 grouping sets ·
marts 17.532 / 576 / 6.075 · kiểm chứng 24.759/24.759 = 100% · 130 dbt test · cube 2–6 ms vs
fact 130–400 ms · gió nam mùa đông 85 → 133 µg/m³ (+60%), vượt ngưỡng 28 → 43%.

**Khai phá:** split 276.380 (25,2%) / 47.338 (15,8%) / 48.781 (23,9%) · F1: majority 0,000
(accuracy 0,761) — persistence 0,914 — cây 0,921 — HistGB 0,927 (AUC 0,993, cutoff 0,50) ·
FN 1.000 → 838 · FP 999 → 865 · onset 304/1.000 = 30,4% vs 0% · McNemar b=594, c=298,
p ≈ 5×10⁻²³ · tầm 1/3/6h: +0,013 / +0,026 / +0,043 · 12/12 trạm.

**Vận hành & bổ trợ:** 6h: 506/730 (69,3%) vs luật 105: 468/730 (64,1%) · trung vị báo trước 3h ·
trần 0,5 FP/ngày-trạm · MAE hồi quy 8,87 µg/m³ · CDC đối soát MAE 9,41 (111.944 giờ), ngưỡng cờ 12 µg/m³ · K-Means K=2, silhouette 0,664, cụm 9+3.

---

## 7. Kịch bản co giãn & chế độ 1 người

- **Đủ 30':** nói như kịch bản trên nhưng **bỏ sẵn S28** — tổng thời lượng tính theo từng slide là
  ~31 phút, giữ đủ cả S28 lẫn S29 là quá giờ. Hết sớm thì nói lại S28 (tóm tắt nội dung còn ở lá chắn A15).
- **Còn ~24':** cắt cửa cắt S16-pivot (−30"), S26 rút demo (−1'), bỏ S28 (−1'), bỏ S29 (−1').
- **Chỉ 1 người lên:** nói liền 31 slide — các câu chuyển ở S9/S19 vẫn giữ nguyên như "phần tiếp
  theo". Tập với mốc: phút 10 ở S10, phút 20 ở S22. Uống nước sẵn ở S9 và S19 (điểm nghỉ tự nhiên).
- **Kéo thêm người vào lúc chót:** họ nhận khối A (S1–9, thuộc trong 1–2 buổi) hoặc chỉ S1–2 + S30–31
  (~3 phút nói). Khối B và C giữ cho người chắc nhất.
- Nếu thầy yêu cầu mỗi thành viên nói phần mình: phân công khối A/B/C trùng khối đã commit trên Git.

## 8. Việc cần làm trước buổi nói

1. Điền tên nhóm/số nhóm/thành viên vào slide 1 và 31; đồng bộ với `BANG_PHAN_CONG.md`.
2. Chạy lại `run_all.py` nếu dữ liệu đổi → đối chiếu bộ số ở mục 6.
3. Tập demo S16 và S26 tối thiểu 3 lần với Docker đang chạy; thử kịch bản fallback notebook 1 lần.
4. Xoá / sửa mọi chỗ còn nhắc XGBoost, LightGBM trong tài liệu + slide.
5. Tập chéo: một người làm "thầy" hỏi hết bảng mục 5, người nói chỉ được mở đúng slide lá chắn.
