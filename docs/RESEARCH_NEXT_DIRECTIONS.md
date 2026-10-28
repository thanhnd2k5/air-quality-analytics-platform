# Hướng nâng cấp bài tập lớn — nghiên cứu ngày 21/10/2026

> **Cập nhật 28/10/2026:** tài liệu này ghi lại hướng nghiên cứu ngày 21/10. Trạng thái mới nhất nằm ở [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) mục 0: bài toán chính vẫn là phân loại cảnh báo **t+1**; cảnh báo khởi phát đợt trong 6 giờ (cách hiểu C) vẫn là **thí nghiệm, nhóm chưa chốt** đưa thành bài toán chính; trang `/phat-lai` đã bỏ khỏi menu dashboard.

Phạm vi: đọc mã nguồn, báo cáo kết quả, các nhánh thí nghiệm và đối chiếu tài liệu phương pháp. Khóa mô hình không đổi. Demo phát lại lịch sử nằm ở mục 4.

## Hướng đã thống nhất với người dùng — 21/10/2026

**Trạng thái: thí nghiệm đợt 6 giờ đã chạy (21/10/2026). Khóa t+1 giữ nguyên. Demo phát lại từng có tại `/phat-lai` (đã bỏ khỏi menu ngày 28/10).**

Báo cáo đánh giá sạch: `artifacts/classification/evaluation_hygiene/decision_note.md`. Báo cáo đợt: `artifacts/classification/onset_6h/decision_note.md`. Với trần 0,5 cảnh báo nhầm trên mỗi trạm-ngày, quy tắc mức PM2.5(t) ≥ 105 là baseline. HistGB local không vượt baseline đủ 0,05. Thêm bốn đặc trưng lân cận M2 vượt trên 2/3 fold phát triển và trên 2016 H2 (recall đợt 0,693 so với 0,641; lead trung vị 3 giờ so với 1 giờ). M2 không được đưa vào khóa hồi quy.

- Giữ bài toán phân loại vượt ngưỡng tại **t+1** làm kết quả chính hiện tại.
- Ưu tiên cảnh báo **một đợt ô nhiễm khởi phát trong 6 giờ tới**, khi trạm hiện còn dưới ngưỡng. Đây là nhãn theo cửa sổ tương lai, không phải chỉ xét PM2.5 tại đúng t+6.
- Phạm vi giai đoạn đầu chỉ có **cửa sổ 6 giờ**. Đợt được định nghĩa là PM2.5 **≥115 µg/m³ liên tục ít nhất 3 giờ**; thời điểm bắt đầu nằm trong t+1 đến t+6, đợt không cần kết thúc trong cửa sổ này.
- **Chưa dự đoán thời lượng đợt**; chỉ thống kê thời lượng thực tế để phân tích.
- Cửa sổ **3 giờ và 12 giờ** là mở rộng tùy chọn để so sánh độ nhạy nếu kết quả 6 giờ có giá trị, không thuộc phạm vi triển khai ban đầu.
- Trước thí nghiệm, làm chặt cluster chỉ học từ train và chặn nhãn qua ranh giới split. Chốt xử lý thiếu dữ liệu và cửa sổ xác nhận trước khi fit: xác nhận đợt bắt đầu ở t+6 cần quan trắc tới t+8 để đủ 3 giờ liên tiếp.
- Đánh giá theo tỷ lệ đợt được phát hiện, thời gian báo trước, cảnh báo nhầm/trạm-ngày và cảnh báo lặp; so sánh tại cùng mức báo nhầm đã chọn trên dữ liệu phát triển.

Các hướng khác bên dưới vẫn là đề xuất nghiên cứu, không mặc nhiên nằm trong phạm vi vừa thống nhất.

## Nhận định

Hướng có giá trị nhất là làm rõ **hệ thống báo trước được bao nhiêu lần vượt ngưỡng, sớm bao lâu, đổi lại bao nhiêu cảnh báo nhầm**, rồi nối kết quả đó với kho dữ liệu và demo phát lại theo thời gian.

Repo đã có nền tảng rộng: lake, staging, dbt, OLAP, phân loại, hồi quy, phân cụm, dashboard và CDC mô phỏng. Phân loại là bài toán khai phá chính theo đối chiếu yêu cầu học phần trong `docs/PROGRESS.md`; hồi quy là phần bổ trợ.

Các kết quả hiện có:

| Bằng chứng trong repo | Ý nghĩa với hướng tiếp theo |
|---|---|
| HistGB phân loại: F1 test 0,927, persistence 0,914 | Cải thiện có thật trên bảng kết quả đã lưu, nhưng cần đánh giá độ bất định và quy trình chống rò rỉ |
| Báo trước 304/1.000 lần từ dưới 115 sang vượt ngưỡng | Onset recall chỉ 30,4%; còn nhiều dư địa ở mục tiêu cảnh báo sớm |
| Phân loại h=3 và h=6 đã có F1 0,832 và 0,745 | Không coi việc thêm hai tầm này là đóng góp mới; cần đo sự kiện, lead time và false alarms |
| Hồi quy M0 MAE 8,872; M2 spatial 8,574 | Thông tin lân cận có tiềm năng, nhưng kết quả này chưa chứng minh cải thiện cho phân loại |
| Với actual ≥500, M2 MAE 50,81 so với M0 43,44 | Trung bình tốt hơn chưa đủ để thay mô hình đang khóa |
| PBL, upwind, robust median đã có quyết định đóng/giữ M2; EDGAR là EDA_ONLY | Ưu tiên câu hỏi mới thay vì thử tiếp các biến thể trên cùng test |

Nguồn: `artifacts/classification/classification_report.md`, `artifacts/forecasting/spatial_calendar_ablation/decision_note.md`, các `decision_note.md` của PBL/upwind/robust spatial và `artifacts/edgar_poc/poc_summary.md`.

## 1. Ưu tiên nền tảng: làm chặt đánh giá

### Cluster dùng thông tin sau giai đoạn train

`sql/clustering/station_pollution_profile.sql` tính profile từ 03/2013 đến hết 12/2016. `sql/forecasting/extract_forecast_base.sql` join cluster đó; `src/forecasting/constants.py` đưa `cluster_id` vào features, và classification dùng lại bộ features v2. Trong khi đó, train kết thúc 31/12/2015.

Đây là đường đưa thông tin tổng hợp của thời kỳ validation/test vào đầu vào học máy. Chưa đo được mức ảnh hưởng đến metrics; không suy ra toàn bộ cải thiện là do leakage. Cách xử lý:

- Giữ cluster toàn kỳ cho EDA.
- Với ML, fit profile, scaler và clustering chỉ trên train của từng fold.
- Chạy thêm đối chứng bỏ `cluster_id`, vì đã có `station_key`.
- Dùng cùng tập dòng và cùng quy trình sạch để so các mô hình.

Nguyên tắc fit mọi bước học từ dữ liệu chỉ trên training được nêu trong [scikit-learn: Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html).

### Nhãn đi qua ranh giới split

`build_feature_matrix_v2` gán split bằng `event_time_local`; `add_alert_target` dịch target sang t+h nhưng giữ nguyên split. Vì vậy các origin cuối train/validation có thể lấy nhãn từ kỳ sau. Với h=6, cửa sổ bị ảnh hưởng dài hơn h=1.

Phải loại các origin có target vượt mốc nhãn được phép dùng khi fit/tune. Nếu nhãn mới nhìn cả cửa sổ t+1…t+h, kiểm tra toàn bộ cửa sổ. Với 12 trạm, chia fold theo timestamp dùng chung cho tất cả trạm; không áp dụng máy móc `gap=h` theo số dòng. [TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) cung cấp cơ chế chia theo thời gian và gap, nhưng dữ liệu nhiều trạm cần bộ chia phù hợp.

### Bất định và việc sử dụng test nhiều lần

McNemar hiện tính trên từng station-hour. Các giờ liền nhau và các trạm trong cùng đợt ô nhiễm có phụ thuộc, nên p-value rất nhỏ chưa đủ làm bằng chứng duy nhất.

Đề xuất paired block bootstrap theo các khối giờ liên tiếp, giữ toàn bộ trạm trong mỗi khối; chọn độ dài khối bằng dữ liệu phát triển và kiểm tra độ nhạy. Báo cáo khoảng tin cậy cho chênh lệch F1, onset recall và MAE. [Tài liệu arch về time-series bootstrap](https://bashtage.github.io/arch/bootstrap/timeseries-bootstraps.html) mô tả các phương pháp lấy mẫu theo khối.

Test H2/2016 đã được dùng để phân tích nhiều nhánh. Các phát hiện mới trên đó nên gọi là khám phá. Dùng backtest theo nhiều mốc thời gian để kiểm tra độ ổn định; chỉ gọi một kỳ là holdout mới nếu thực sự chưa dùng để ra quyết định. Jan–Feb/2017 đã xuất hiện trong sensitivity cũ, nên không mặc nhiên gọi là tập chưa từng xem.

## 2. Ưu tiên đóng góp chính: cảnh báo sớm theo sự kiện

Câu hỏi đã chốt cho giai đoạn đầu: **Khi trạm hiện còn dưới ngưỡng, trong 6 giờ tới có bắt đầu một đợt ô nhiễm kéo dài ít nhất 3 giờ không?**

Phân biệt ba mục tiêu:

1. Hiện có: PM2.5 tại đúng t+h có vượt 115 không.
2. Mở rộng: có ít nhất một lần vượt ngưỡng trong cửa sổ tương lai không.
3. Mục tiêu theo đợt: có khởi phát đợt vượt ngưỡng liên tục ít nhất 3 giờ không.

Ba nhãn này không tương đương. Chốt một nhãn chính, quy tắc gộp đợt, xử lý thiếu dữ liệu và thời gian xác nhận trước khi fit. Một lần chuyển từ dưới sang trên ngưỡng hiện tại chưa chắc là khởi đầu đợt đủ 3 giờ.

Đánh giá:

- Tỷ lệ đợt được báo trước và phân bố thời gian báo trước.
- Precision của cảnh báo khởi phát, số đợt báo nhầm trên mỗi trạm-ngày có đủ dữ liệu.
- Số cảnh báo lặp cho cùng một đợt, tỷ lệ đợt bỏ sót.
- Kết quả theo trạm, mùa và mức nghiêm trọng; công bố cả các đợt không được phát hiện.

Baseline nên có persistence và quy tắc ngoại suy xu hướng đơn giản được chọn trên validation. Persistence có onset recall bằng 0 theo định nghĩa khi điều kiện là hiện tại dưới ngưỡng, nên chỉ so với baseline này sẽ chưa đủ mạnh.

Thí nghiệm nhỏ đầu tiên: classifier local hiện tại so với classifier thêm bốn spatial features của M2, với quy trình đánh giá đã sửa. Đây là giả thuyết chưa kiểm chứng: hiệu quả hồi quy của M2 không chuyển tự động sang hiệu quả cảnh báo.

Tiêu chí thành công: phát hiện nhiều đợt hơn ở cùng mức cảnh báo nhầm đã chốt trước, ổn định qua các fold. Không đặt mục tiêu tăng recall bằng mọi giá.

## 3. Làm xác suất cảnh báo có ý nghĩa

Ngưỡng 0,50 hiện được chọn theo F1 validation. Có thể phát triển thành quyết định dựa trên chi phí bỏ sót và báo nhầm:

- Vẽ reliability diagram, đo Brier score và log loss.
- Nếu cần, hiệu chỉnh xác suất trên giai đoạn riêng sau train; tách giai đoạn chọn ngưỡng hoặc dùng dự đoán ngoài mẫu theo thời gian.
- So các kịch bản chi phí giả định, chẳng hạn bỏ sót đắt gấp 2 hoặc 5 lần báo nhầm; ghi rõ đây là giả định của bài.
- Chọn ngưỡng trên dữ liệu phát triển, rồi khóa khi đánh giá.

Scikit-learn phân biệt việc dự đoán xác suất với quyết định chọn nhãn trong [tuning decision threshold](https://scikit-learn.org/stable/modules/classification_threshold.html). [Probability calibration](https://scikit-learn.org/stable/modules/calibration.html) giải thích kiểm tra xác suất; Brier score không đo riêng calibration, nên cần xem cả biểu đồ độ tin cậy.

Sản phẩm demo: chọn mức ưu tiên tránh bỏ sót, xem số báo nhầm và số đợt phát hiện tương ứng trên validation. Trang test dùng chính sách đã khóa.

## 4. Nối DWH, CDC và mô hình thành một demo xuyên suốt

Repo đã có CDC mô phỏng và batch MAE monitoring. Phần tiếp theo nên là phát lại một giai đoạn lịch sử theo từng batch:

**Dữ liệu đến → lưu kho → tạo đặc trưng → dự đoán → ghi cảnh báo → quan trắc tương lai đến → chấm kết quả.**

Mỗi dự đoán lưu origin time, target time, watermark dữ liệu, model version và thời điểm sinh dự đoán. Actual chỉ được gắn để đánh giá sau khi quan trắc tương ứng đến. Khi phát lại, cần kiểm tra luồng chấm điểm tuân thủ watermark, ngay cả khi kho cục bộ đã chứa toàn bộ lịch sử.

Dashboard hiển thị:

- Trạm nào đang cần chú ý, xác suất vượt ngưỡng và trạng thái dữ liệu.
- Timeline actual/prediction/cảnh báo, thời điểm phát và thời điểm bắt đầu đợt.
- KPI theo batch, số trạm đủ dữ liệu và chênh lệch so với persistence.
- Truy vết một cảnh báo về mart, fact và dữ liệu nguồn.

Đây là cách chứng minh các phần của môn học phục vụ cùng một câu hỏi. Nhãn giao diện phải ghi rõ phát lại dữ liệu lịch sử. Cờ `suspect_spatiotemporal` hiện dùng t+1 nên chỉ hiện trong phần hậu kiểm; không đưa vào đầu vào dự đoán tại t.

## 5. Nếu còn thời gian nghiên cứu: khoảng dự báo

Hồi quy hiện trả một giá trị. Có thể thử quantile regression hoặc adaptive conformal để cung cấp khoảng dự báo, rồi đo:

- Coverage thực nghiệm và độ rộng khoảng.
- Coverage theo trạm, mùa, giờ tăng nhanh và đợt cực đoan.
- Sai lệch khi quan trắc đến chậm hoặc phân phối thay đổi.

Conformal thông thường dựa vào giả định exchangeability; không khẳng định bảo đảm 90% cho mọi trạm/mùa trên chuỗi thời gian. [Zaffran et al., ICML 2022](https://proceedings.mlr.press/v162/zaffran22a.html) nghiên cứu adaptive conformal cho dữ liệu thời gian. Phải cập nhật phần hiệu chỉnh chỉ bằng residual đã quan sát được ở thời điểm hiện tại.

Đây là nhánh bổ trợ, sau phần phân loại và kiểm chứng.

## Thứ tự triển khai đề xuất

| Thứ tự | Công việc | Đầu ra cụ thể |
|---|---|---|
| 1 | Sửa quy trình đánh giá, audit cluster và split | Đã có `artifacts/classification/evaluation_hygiene/decision_note.md` |
| 2 | Phân tích cảnh báo khởi phát từ dự đoán có sẵn | Gộp vào thí nghiệm nhãn đợt, không chấm lại dự đoán t+1 |
| 3 | Một thí nghiệm classifier local/spatial + chính sách ngưỡng | Đã có `artifacts/classification/onset_6h/decision_note.md` |
| 4 | Demo replay có truy vết | Đã có `artifacts/classification/replay/decision_note.md` và trang `/phat-lai` |
| 5 | Khoảng dự báo nếu còn nguồn lực | Coverage/width và đánh giá theo nhóm |

Nếu chỉ làm một gói nâng cấp: **quy trình đánh giá sạch + cảnh báo sớm theo đợt + demo replay**.

Trong báo cáo, có thể dùng trường hợp M2 giảm MAE trung bình nhưng làm xấu đợt cực đoan để giải thích lựa chọn mô hình. Đây là kết quả nghiên cứu có giá trị dù không promote. Đồng thời giữ ngưỡng 115 µg/m³ là ngưỡng thực nghiệm theo giờ của bài, tránh đồng nhất với chỉ số AQI chính thức hay hướng dẫn sức khỏe.
