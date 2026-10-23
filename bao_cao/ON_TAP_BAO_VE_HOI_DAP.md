# Ôn tập bảo vệ — Câu hỏi và trả lời mẫu

**Dự án:** Air Quality Analytics Platform — INT1422, Kho dữ liệu và Khai phá dữ liệu.  
**Ngày biên soạn:** 23/10/2026.  
**Mục đích:** luyện giải thích nghiệp vụ, lựa chọn thiết kế và ý nghĩa kết quả; không học thuộc code.

Các câu trả lời dưới đây dựa trên tài liệu, mã nguồn và artifact đang lưu trong repo. Đây là ngân hàng câu hỏi để luyện, không phải dự đoán chắc chắn thầy sẽ hỏi gì. Các kết quả kiểm thử được dẫn là kết quả đã ghi nhận, không phải một lần chạy kiểm thử mới khi soạn tài liệu này.

## Cách học

- Lượt 1: học các câu có dấu **★**, ưu tiên hiểu rồi diễn đạt bằng lời của mình.
- Lượt 2: tự trả lời mỗi câu trong khoảng 30–60 giây; dùng một ví dụ ngay trong dự án.
- Lượt 3: mở dashboard và chỉ ra bằng chứng tương ứng với câu trả lời.
- Khi bị hỏi sâu: trả lời theo thứ tự **mục đích → cách làm → kết quả → giới hạn**.
- Những câu về người phụ trách, đóng góp và việc dùng AI phải sửa theo thực tế của bạn; không nhận phần việc mình chưa làm.

## Bài giới thiệu khoảng một phút

> Thưa thầy, nhóm em xây dựng nền tảng phân tích chất lượng không khí từ dữ liệu 12 trạm tại Bắc Kinh. Nhóm tổ chức dữ liệu theo chuỗi thu thập, lưu trên data lake, chuẩn hóa, nạp vào kho dữ liệu PostgreSQL và tạo các bảng tổng hợp phục vụ phân tích OLAP. Kho giúp so sánh mức ô nhiễm theo thời gian, trạm, quận và hướng gió. Bài toán khai phá chính là phân loại xem PM2.5 của giờ tiếp theo có đạt hoặc vượt ngưỡng 115 microgam trên mét khối hay không. Nhóm so sánh mô hình học máy với cách dự báo giữ nguyên trạng thái hiện tại, thay vì chỉ báo cáo một chỉ số riêng lẻ. Dashboard thể hiện dữ liệu lịch sử, kết quả phân tích và dự đoán. Phạm vi hiện tại là bài tập trên dữ liệu lịch sử và mô phỏng luồng vận hành, chưa phải hệ thống cảnh báo đang kết nối trực tiếp với trạm quan trắc thật.

## A. Bài toán và giá trị nghiệp vụ

### 1. ★ Đề tài giải quyết vấn đề gì?

**Trả lời mẫu:** Dữ liệu quan trắc có nhiều trạm và nhiều mốc thời gian nên nếu chỉ đọc từng file sẽ khó so sánh và theo dõi nhất quán. Nhóm xây dựng một kho chung để trả lời ô nhiễm xảy ra ở đâu, thời điểm nào, đi kèm điều kiện thời tiết nào; đồng thời thử dự đoán khả năng vượt ngưỡng trong giờ tới. Sản phẩm gồm cả nền dữ liệu, chức năng phân tích và kết quả khai phá.

### 2. ★ Ai dùng hệ thống và họ ra quyết định gì?

**Trả lời mẫu:** Đối tượng sử dụng mà nhóm hướng tới là cán bộ phân tích tại đơn vị quan trắc môi trường. Họ có thể xác định trạm hoặc thời điểm cần chú ý, so sánh các khu vực và tham khảo dự đoán để chuẩn bị cảnh báo. Đây là đối tượng nghiệp vụ giả định của đề tài; nhóm chưa triển khai thực tế tại một cơ quan cụ thể hay chứng minh tác động ngoài thực địa.

### 3. Vì sao chọn dữ liệu Bắc Kinh thay vì Việt Nam?

**Trả lời mẫu:** Bộ dữ liệu này có số đo theo giờ, nhiều trạm, nhiều năm và gồm cả chất ô nhiễm lẫn khí tượng nên phù hợp để thực hiện đầy đủ các phần của môn học. Nhóm có thể kiểm chứng xuyên suốt từ tích hợp dữ liệu đến kho, OLAP và khai phá trên cùng một nguồn. Đổi lại, kết quả hiện tại chỉ phản ánh dữ liệu Bắc Kinh; muốn áp dụng cho Việt Nam cần dữ liệu địa phương và đánh giá lại.

### 4. ★ Đầu ra quan trọng nhất của đề tài là gì?

**Trả lời mẫu:** Với môn học này, đầu ra chính là kho dữ liệu có thiết kế rõ ràng, các phép OLAP hoạt động đúng và bài toán phân loại cảnh báo có đánh giá so với baseline. Dashboard giúp trình bày các đầu ra đó. Phân cụm trạm, hồi quy PM2.5 và thí nghiệm cảnh báo đợt là những phần bổ trợ, không thay thế trọng tâm kho dữ liệu và phân loại.

### 5. Nếu chỉ cần vẽ biểu đồ, dùng Excel được không?

**Trả lời mẫu:** Có thể dùng Excel cho một phân tích nhỏ. Giá trị của hệ thống này là chuẩn hóa cách tích hợp nhiều kênh dữ liệu, lưu lịch sử, kiểm tra chất lượng, tái sử dụng cùng định nghĩa chỉ số và tự động chạy lại các bước. Lý do xây kho không chỉ vì hơn 420 nghìn dòng là quá lớn cho Excel, mà vì cần một quy trình phân tích nhất quán và kiểm chứng được.

### 6. ★ Phân tích lịch sử và dự báo khác nhau ở đâu?

**Trả lời mẫu:** Phân tích lịch sử trả lời điều gì đã xảy ra, ví dụ trạm nào có PM2.5 trung bình cao trong mùa đông. Dự báo dùng thông tin đã có tại thời điểm t để suy ra điều chưa quan sát ở t+1. Khi đánh giá dự báo trên lịch sử, nhóm phải giữ đúng thứ tự này, dù trong file gốc đã có sẵn số đo tương lai.

### 7. ★ Tại sao chọn ngưỡng 115 µg/m³? Đó có phải AQI bằng 115 không?

**Trả lời mẫu:** Trong dự án, 115 µg/m³ là ngưỡng nồng độ PM2.5 đã được chốt để định nghĩa bài toán vượt ngưỡng và các đợt ô nhiễm. Con số này là nồng độ, không phải giá trị AQI. Em trình bày nó như quy ước nghiệp vụ của thí nghiệm; việc áp dụng một chuẩn cảnh báo chính thức còn phải đối chiếu chuẩn, thời gian lấy trung bình và địa phương áp dụng. Nếu đổi ngưỡng, nhóm phải tạo lại nhãn và đánh giá lại kết quả.

**Khi bị hỏi thêm:** Nhãn chính của nhóm dùng giá trị theo giờ. Không suy diễn rằng một giá trị theo giờ tương đương trực tiếp với một phân hạng được định nghĩa cho trung bình ngày.

### 8. Hệ thống chứng minh được nguyên nhân gây ô nhiễm không?

**Trả lời mẫu:** Chưa. Kho cho phép quan sát sự đi kèm giữa ô nhiễm với mùa, giờ, địa điểm và gió; mô hình tìm quan hệ phục vụ dự đoán. Tương quan hoặc độ quan trọng của đặc trưng chưa chứng minh quan hệ nhân quả. Ví dụ gió yếu đi kèm PM2.5 cao là một kết quả mô tả, không đủ để kết luận đó là nguyên nhân duy nhất.

## B. Dữ liệu và tiền xử lý

### 9. ★ Dữ liệu có bao nhiêu trạm, bao nhiêu bản ghi và thời gian nào?

**Trả lời mẫu:** Nguồn UCI PRSA có 12 trạm tại Bắc Kinh, từ ngày 01/03/2013 đến hết 28/02/2017. Có 420.768 bản ghi giờ-trạm, tương ứng 12 trạm nhân 35.064 mốc giờ. Cần hiểu đây là số dòng quan trắc, không phải 420.768 mốc thời gian khác nhau và cũng không có nghĩa mọi ô đo đều đầy đủ.

### 10. Có những nhóm thuộc tính nào?

**Trả lời mẫu:** Có sáu chất ô nhiễm là PM2.5, PM10, SO2, NO2, CO và O3; các biến khí tượng như nhiệt độ, áp suất, điểm sương, mưa, tốc độ và hướng gió; cùng thông tin trạm và thời gian. Nhóm còn bổ sung dữ liệu thời tiết từ Open-Meteo và suy ra một số thuộc tính như độ ẩm tương đối, mùa, buổi trong ngày.

### 11. ★ Dự án có mấy nguồn dữ liệu? Nguồn database có độc lập với CSV không?

**Trả lời mẫu:** Về kênh tích hợp, dự án có file CSV, database nguồn mô phỏng và API thời tiết. Tuy nhiên, dữ liệu ô nhiễm trong CSV và database cùng xuất phát từ UCI PRSA. Nhóm tách giai đoạn lịch sử qua file và giai đoạn vận hành mô phỏng qua database để minh họa hai cách thu thập. Đây không phải hai mạng quan trắc độc lập; Open-Meteo mới là nguồn bổ sung khí tượng riêng.

**Số liệu đối soát kịch bản File + DB:** File 298.368 dòng, DB 122.400 dòng, tổng vẫn là 420.768. Luồng chạy toàn bộ từ CSV cũng được hỗ trợ; không cộng chồng hai kịch bản thành dữ liệu mới.

### 12. ★ Vì sao cần Open-Meteo? Ghép với dữ liệu trạm như thế nào?

**Trả lời mẫu:** Nhóm dùng Open-Meteo để bổ sung khí tượng và lấp các giá trị thời tiết còn thiếu. Dữ liệu được lấy theo vị trí trạm và ghép theo trạm cùng mốc giờ đã thống nhất múi giờ. Giá trị UCI có sẵn được ưu tiên; giá trị lấp từ nguồn bổ sung có thông tin nguồn để truy vết. Khí tượng tái phân tích không đồng nhất hoàn toàn với phép đo tại trạm nên vẫn có sai khác nguồn.

### 13. ★ Thiếu PM2.5 có điền bằng trung bình hoặc số 0 không?

**Trả lời mẫu:** Trong kho, nhóm giữ PM2.5 thiếu ở dạng NULL và gắn cờ chất lượng. Số 0 là một giá trị đo cụ thể, còn NULL nghĩa là chưa có số đo nên không thể thay thế tùy tiện. Khi tạo dữ liệu học, dòng không có PM2.5 cần thiết tại thời điểm hiện tại hoặc giờ đích bị loại. Một số biến đầu vào khác được điền median tính trên train và có cờ thiếu đi kèm.

### 14. Vì sao không nội suy hết cho dữ liệu đẹp?

**Trả lời mẫu:** PM2.5 có chuỗi thiếu dài tới 343 giờ. Nội suy qua khoảng dài có thể tạo ra xu hướng không quan sát được, làm sai trung bình và nhãn vượt ngưỡng. Nhóm ưu tiên giữ đúng tình trạng dữ liệu hơn là tạo ra bảng không còn ô trống. Với thời tiết, nhóm có nguồn bổ sung để lấp, nhưng vẫn ghi nguồn và thừa nhận sai khác giữa các nguồn.

### 15. Phát hiện trùng, giá trị âm và giá trị rất cao thì xử lý ra sao?

**Trả lời mẫu:** Nhóm kiểm tra tính duy nhất theo trạm và thời gian. Giá trị âm ở các biến không thể âm như nồng độ hoặc tốc độ gió được xem là không hợp lệ và đưa ra luồng cách ly; nhiệt độ âm vẫn hợp lệ. Một số giá trị chạm trần như PM2.5 bằng 999 được giữ lại và gắn cờ nghi ngờ. Giá trị rất cao chưa đủ để kết luận là lỗi, nên nhóm không xóa chỉ vì nó khác thường.

### 16. ★ Làm sao biết kết quả tổng hợp không che mất dữ liệu thiếu?

**Trả lời mẫu:** Bảng tổng hợp lưu cả số giờ trong nhóm và số giờ có PM2.5 hợp lệ. Trung bình chỉ tính trên số đo không NULL; số giờ vượt ngưỡng cũng cần diễn giải cùng mức độ đầy đủ dữ liệu. Khi so sánh các trạm, em phải xem cả mẫu số, tránh coi trạm thiếu dữ liệu là sạch hơn. Có đủ 420.768 dòng không đồng nghĩa có đủ từng giá trị đo.

## C. Luồng hệ thống, cập nhật và vận hành

### 17. ★ Hãy mô tả toàn bộ luồng dữ liệu bằng lời, không đọc tên file.

**Trả lời mẫu:** Nhóm thu thập dữ liệu từ file, database mô phỏng và API; lưu bản gốc trên MinIO; chuẩn hóa và tạo dữ liệu đã xử lý; nạp vào staging trong PostgreSQL. dbt chuyển staging thành bảng chiều, bảng fact và các mart phục vụ từng nhu cầu. Từ kho, nhóm tạo đặc trưng, huấn luyện và đánh giá mô hình; kết quả cần phục vụ được đưa vào mart hoặc artifact, rồi API và dashboard đọc ra.

### 18. ★ Data lake, staging, kho dữ liệu và mart khác nhau thế nào?

**Trả lời mẫu:** Data lake giữ dữ liệu dạng file, bao gồm bản gốc và bản đã xử lý, để truy vết hoặc chạy lại. Staging là vùng tiếp nhận trong cơ sở dữ liệu trước khi áp dụng mô hình phân tích. Kho dữ liệu tổ chức dữ liệu thống nhất theo fact và dimension. Mart là bảng phục vụ một nhu cầu cụ thể, như tổng hợp theo ngày, phân tích đợt ô nhiễm hay hiển thị dự đoán.

### 19. Vai trò của PostgreSQL, MinIO, dbt và Airflow là gì?

**Trả lời mẫu:** MinIO lưu các đối tượng dữ liệu như file CSV, JSON và Parquet. PostgreSQL lưu các bảng staging, kho và mart để truy vấn. dbt định nghĩa các phép biến đổi SQL, quan hệ phụ thuộc và kiểm tra dữ liệu. Airflow điều phối thứ tự chạy và theo dõi các tác vụ. Mỗi thành phần xử lý một nhiệm vụ trong chuỗi, không phải tất cả đều là cơ sở dữ liệu.

### 20. ★ Có dữ liệu mới thì hệ thống có phải học lại ngay không?

**Trả lời mẫu:** Không nhất thiết. Mô hình đã khóa có thể dùng dữ liệu mới để sinh dự đoán; khi số đo thực tế của giờ đích xuất hiện thì đối soát và theo dõi sai số. Trong kịch bản CDC hiện tại, nhóm làm monitoring, chưa tự động huấn luyện lại hoặc tự đổi mô hình. Huấn luyện lại là một quyết định riêng, cần đánh giá trước khi thay phiên bản đang dùng.

### 21. ★ Watermark CDC là gì và dự án dùng nó ra sao?

**Trả lời mẫu:** Watermark là mốc tiến độ dữ liệu đã xử lý. Kịch bản database của nhóm đọc những dòng có thời gian sự kiện lớn hơn mốc đó, xử lý theo batch rồi tiếp tục tiến mốc. Nhờ vậy có thể minh họa nạp tăng dần thay vì lấy lại toàn bộ lịch sử. Đây là incremental extract theo timestamp trong mô phỏng; không phải cơ chế đọc transaction log để bắt mọi thay đổi của database.

### 22. Nếu bản ghi cũ bị sửa hoặc dữ liệu đến muộn thì watermark có bắt được không?

**Trả lời mẫu:** Với cách chỉ đọc event_time lớn hơn mốc đã xử lý, thay đổi ở thời điểm cũ có thể bị bỏ qua. Đây là giới hạn của kịch bản hiện tại. Muốn xử lý đầy đủ cần bổ sung cơ chế như thời gian cập nhật, đọc lùi một cửa sổ rồi upsert, hoặc CDC theo log, tùy nguồn dữ liệu. Em không khẳng định watermark hiện tại đã xử lý mọi trường hợp update, delete hay dữ liệu đến muộn.

### 23. Chạy lại pipeline có làm nhân đôi số liệu không?

**Trả lời mẫu:** Pipeline có kiểm tra dữ liệu đã tồn tại và cơ chế nạp theo khóa trạm–thời gian để chạy lại không nhân đôi cùng một quan trắc. Kịch bản database có upsert ở staging. Nhóm cũng đối soát tính duy nhất và tổng số dòng. Tính chạy lại an toàn phải được bảo đảm ở từng bước; chỉ có nút retry trong Airflow chưa đủ để kết luận dữ liệu sẽ không trùng.

### 24. ★ Dự án có chạy thời gian thực và lấy số đo hiện nay không?

**Trả lời mẫu:** Chưa. Dữ liệu ô nhiễm là dữ liệu lịch sử; nguồn database và các batch cập nhật dùng để mô phỏng cách hệ thống nhận số đo theo thời gian. Mốc dữ liệu tiến tới đâu thì phần demo mới cho phép dùng thông tin tới đó. Có Airflow hoặc cập nhật dashboard không tự biến dữ liệu lịch sử thành kết nối thời gian thực với trạm quan trắc.

## D. Kho dữ liệu và OLAP — phần trọng tâm môn học

### 25. ★ Vì sao chọn lược đồ hình sao?

**Trả lời mẫu:** Các số đo nằm trong bảng fact trung tâm, còn các góc nhìn phân tích như ngày, giờ, trạm và hướng gió nằm ở các bảng chiều. Cách tổ chức này phù hợp với nhu cầu lọc, nhóm và tổng hợp theo nhiều chiều, đồng thời giúp thống nhất phân cấp và cách đặt tên. Với quy mô bài tập, cấu trúc này cũng dễ giải thích và kiểm chứng.

### 26. ★ Một dòng trong bảng fact biểu diễn cái gì?

**Trả lời mẫu:** Một dòng biểu diễn một trạm tại một mốc giờ. Đây là độ mịn trạm–giờ, với các số đo như PM2.5, PM10 và khí tượng. Ví dụ Dongsi lúc 10 giờ ngày 01/12/2016 là một quan trắc; một trạm khác cùng giờ là một quan trắc khác. Độ mịn không phải một ngày và cũng không phải một chất ô nhiễm trên mỗi dòng.

### 27. Vì sao giữ mức giờ thay vì chỉ lưu mức ngày?

**Trả lời mẫu:** Dữ liệu gốc có mức giờ và bài toán cảnh báo giờ tới cần mức này. Nếu gộp sớm thành ngày, nhóm sẽ mất đỉnh ô nhiễm, chuỗi vượt ngưỡng liên tiếp và sự khác biệt giữa các buổi. Từ giờ có thể tổng hợp lên ngày hoặc tháng; từ trung bình ngày không khôi phục được số đo từng giờ. Các mart theo ngày, tháng giúp truy vấn nhanh mà vẫn giữ fact chi tiết.

### 28. ★ Bốn bảng chiều là gì? Vì sao ngày và giờ tách riêng?

**Trả lời mẫu:** Bốn bảng chiều là ngày, giờ trong ngày, trạm và hướng gió. Chiều ngày chứa các thuộc tính như tháng, quý, năm, mùa; chiều giờ chứa giờ và buổi. Tách ra giúp phân tích cả xu hướng lịch lẫn mẫu trong ngày, ví dụ so sánh buổi tối giữa các mùa. Chiều hướng gió bổ sung góc nhìn về điều kiện đi kèm ô nhiễm, ngoài câu hỏi khi nào và ở đâu.

### 29. Fact và dimension khác nhau thế nào? Cho ví dụ measure.

**Trả lời mẫu:** Fact ghi nhận sự kiện quan trắc và các giá trị đo; dimension mô tả bối cảnh để lọc hoặc nhóm sự kiện. Ví dụ PM2.5 là một độ đo, còn tên trạm, quận, tháng và buổi là thuộc tính phân tích. Mã trạm là khóa liên kết, không phải đại lượng có ý nghĩa để cộng hay lấy trung bình.

### 30. ★ PM2.5 có cộng được không? Vì sao không lấy trung bình của các trung bình?

**Trả lời mẫu:** Cộng nồng độ qua nhiều giờ không cho ra nồng độ đại diện có ý nghĩa như trung bình. Khi tổng hợp lại các nhóm, phải dùng tổng giá trị chia tổng số đo hợp lệ, hoặc trung bình có trọng số theo số đo. Ví dụ nhóm A có 24 số đo, trung bình 100; nhóm B có 6 số đo, trung bình 200. Trung bình chung là (24×100 + 6×200)/30 = 120, không phải 150. Vì vậy mart lưu thêm count và cube lưu sum cùng count.

### 31. ★ Năm thao tác OLAP là gì? Minh họa ngay trên đề tài.

**Trả lời mẫu:**

| Thao tác | Ý nghĩa | Ví dụ trong đề tài |
|---|---|---|
| Roll-up | Tổng hợp lên mức khái quát hơn | Từ PM2.5 theo tháng lên theo quý hoặc năm |
| Drill-down | Xem xuống mức chi tiết hơn | Từ năm xuống quý rồi tháng |
| Slice | Cố định một giá trị của một thuộc tính | Chỉ xem quận Dongcheng |
| Dice | Chọn một vùng dữ liệu bằng nhiều điều kiện | Xem mùa đông, một số quận và nhóm gió nam |
| Pivot | Đổi bố trí các chiều trên bảng | Đổi hàng là trạm/cột là tháng thành hàng là tháng/cột là trạm |

Em cần chỉ được thao tác trên trang OLAP, không chỉ đọc định nghĩa.

### 32. Roll-up khác GROUP BY thông thường ở đâu?

**Trả lời mẫu:** Về nghiệp vụ, roll-up là chuyển từ mức chi tiết lên mức tổng hợp theo một phân cấp, như tháng lên quý. GROUP BY là một công cụ SQL để tạo kết quả đó. Cần phân biệt thao tác OLAP roll-up với cú pháp SQL ROLLUP: cú pháp ROLLUP có thể sinh nhiều mức tổng phụ trong cùng một truy vấn. Dùng GROUP BY theo năm vẫn có thể thực hiện ý nghĩa roll-up dù không viết từ khóa ROLLUP.

### 33. ★ Có bốn chiều sao lại có cube năm thuộc tính và 32 khối con?

**Trả lời mẫu:** Bốn chiều là bốn bảng dimension của lược đồ sao. Cube được tính trên năm thuộc tính phân tích: năm, mùa, quận, buổi và phần tư hướng gió. Năm và mùa cùng thuộc chiều ngày. GROUP BY CUBE xét giữ hoặc tổng hợp mỗi thuộc tính nên có 2^5 = 32 grouping sets. Vì vậy số thuộc tính đưa vào CUBE không bắt buộc bằng số bảng chiều.

**Khi bị hỏi về con số 180:** Tài liệu thiết kế còn tính 180 tổ hợp mức theo các phân cấp chính đã chọn: (4+1)(2+1)(2+1)(3+1). Đó là cách đếm theo mức phân cấp, khác với 32 grouping sets trên năm thuộc tính cụ thể; dự án không tính trước toàn bộ 180 khối.

### 34. Tại sao phải tính trước mart/cube? Có luôn trả lời được mọi truy vấn không?

**Trả lời mẫu:** Các nhóm tổng hợp thường dùng được tính trước để dashboard đọc nhanh và tái sử dụng cùng định nghĩa chỉ số. Nhưng cube chỉ chứa những thuộc tính đã chọn. Nếu truy vấn cần một thuộc tính chi tiết không có trong cube thì API phải truy vấn fact và các dimension. Bản chi tiết vẫn là nền để trả lời linh hoạt và kiểm chứng các bảng tổng hợp.

### 35. Vì sao không SUM toàn bộ bảng cube để lấy tổng số giờ?

**Trả lời mẫu:** Cùng một quan trắc góp vào nhiều grouping sets, nên cộng tất cả các dòng cube sẽ đếm lặp. Phải chọn đúng khối con theo grouping_id hoặc cuboid rồi mới tổng hợp. Một ô tổng hợp ALL cũng cần được phân biệt với dữ liệu thuộc tính thực sự thiếu; thông tin grouping giúp xác định thuộc tính nào đã được cuộn lên.

### 36. ★ Nhóm chứng minh kho và OLAP đúng bằng cách nào?

**Trả lời mẫu:** Nhóm kiểm tra khóa duy nhất, khóa ngoại, số dòng và các quy tắc chất lượng bằng dbt test. Với OLAP, nhóm tính lại tổng và số đếm từ fact rồi đối chiếu từng ô của các khối đã tính trước. Tài liệu ghi nhận 130 dbt test đạt và 24.759 ô đối chiếu khớp. Đây là bằng chứng cho các điều kiện đã kiểm tra, không có nghĩa mọi khả năng sai của dữ liệu hoặc phân tích đều bị loại bỏ.

## E. Phân loại cảnh báo — bài toán khai phá chính

### 37. ★ Bài toán khai phá chính là phân loại hay hồi quy?

**Trả lời mẫu:** Bài toán chính là phân loại nhị phân: giờ tiếp theo có PM2.5 đạt hoặc vượt 115 µg/m³ hay không. Hồi quy dự đoán giá trị PM2.5 cụ thể là phân tích bổ trợ. Cả hai có thể cùng hiển thị trên dashboard nhưng khác đầu ra, cách chọn mô hình và thước đo đánh giá.

### 38. ★ Đầu vào, đầu ra và nhãn của mô hình là gì?

**Trả lời mẫu:** Đầu vào gồm thông tin của trạm tại thời điểm t và quá khứ: PM2.5 hiện tại, các độ trễ, biến động gần đây, khí tượng, một số chất ô nhiễm khác và thuộc tính thời gian. Đầu ra phân loại là điểm xác suất cho lớp vượt ngưỡng và quyết định có/không theo ngưỡng điểm. Nhãn được tạo từ số đo thật tại t+1: nếu PM2.5(t+1) ≥ 115 thì bằng 1, còn lại bằng 0.

### 39. ★ Đã biết PM2.5 hiện tại rồi, cần mô hình làm gì?

**Trả lời mẫu:** Ngưỡng hiện tại chỉ cho biết trạm đang ở trạng thái nào. Mục tiêu là dự đoán trạng thái giờ tiếp theo, đặc biệt lúc nồng độ sắp chuyển qua ngưỡng. Tuy vậy hiện tại là một tín hiệu rất mạnh, nên nhóm phải so mô hình với persistence. Mô hình chỉ đáng chú ý nếu kết quả cải thiện so với cách đơn giản đó, chứ không phải vì dùng thuật toán phức tạp.

### 40. ★ Baseline persistence và majority là gì?

**Trả lời mẫu:** Majority luôn chọn lớp phổ biến là không vượt ngưỡng. Persistence giả định giờ tới giống hiện tại: nếu hiện tại đã đạt 115 thì báo giờ tới vượt ngưỡng, nếu chưa thì báo không. Với hồi quy, persistence dự đoán giá trị giờ tới bằng chính PM2.5 hiện tại. Hai baseline giúp kiểm tra xem mô hình học máy thực sự mang lại điều gì.

### 41. ★ Vì sao chia train, validation, test theo thời gian?

**Trả lời mẫu:** Dự báo thực tế phải dùng quá khứ để dự đoán tương lai. Nhóm dùng train từ 03/2013 đến hết 2015, validation là nửa đầu 2016 và test là nửa cuối 2016. Nếu trộn ngẫu nhiên các giờ gần nhau, dữ liệu rất giống nhau có thể xuất hiện ở cả hai phía, khiến đánh giá dễ lạc quan. Train dùng học mô hình; validation dùng lựa chọn; test dùng báo cáo kết quả của lần đánh giá đã chốt.

### 42. Dữ liệu gốc đến 02/2017, sao test kết thúc ở 12/2016?

**Trả lời mẫu:** Phạm vi kho và phạm vi đánh giá mô hình không cần trùng hoàn toàn. Kho giữ toàn bộ dữ liệu gốc; lịch chia tập ML đã chốt kết thúc ở 2016, còn hai tháng 2017 không thuộc test chính. Em không nói mô hình đã được đánh giá trên toàn bộ giai đoạn của kho chỉ vì dashboard có dữ liệu tới 2017.

### 43. ★ Rò rỉ dữ liệu là gì? Có thể xảy ra ở đâu trong dự án?

**Trả lời mẫu:** Rò rỉ là việc dùng thông tin chưa thể có tại thời điểm dự đoán hoặc thông tin của tập đánh giá để lựa chọn mô hình. Ví dụ đưa PM2.5(t+1) vào đầu vào, nội suy bằng tương lai, điền thiếu bằng median toàn bộ dữ liệu, hay dùng cả thời lượng cuối cùng của một đợt chưa kết thúc. Nhóm thiết kế lag và rolling theo quá khứ, tách đầu vào khỏi nhãn và dùng thống kê train cho bước điền thiếu.

**Điểm cần nói trung thực:** Việc thiết kế để tránh rò rỉ không đồng nghĩa đã chứng minh quy trình hoàn hảo. Rà soát sau đó có phát hiện điểm ở biên split; xem câu 48.

### 44. Vì sao chọn cây quyết định và HistGradientBoosting?

**Trả lời mẫu:** Cây quyết định cho nhóm một mô hình tương đối dễ trình bày bằng các điều kiện tách. HistGradientBoosting kết hợp nhiều cây để học quan hệ phi tuyến và tương tác giữa các thuộc tính. Nhóm so sánh chúng với cùng lịch chia dữ liệu và baseline; mô hình khóa được chọn theo F1 trên validation trong các mô hình đã học. Kết luận chỉ áp dụng cho những phương án đã thử, không phải thuật toán tốt nhất cho mọi dữ liệu.

### 45. ★ Vì sao không chỉ dùng accuracy? Precision, recall, F1 nói điều gì?

**Trả lời mẫu:** Số giờ không vượt ngưỡng nhiều hơn, nên mô hình luôn báo không vẫn đạt accuracy khoảng 76,1% trên test nhưng bỏ sót tất cả giờ vượt ngưỡng. Precision cho biết trong các giờ phát cảnh báo có bao nhiêu giờ đúng; recall cho biết trong các giờ thực sự vượt ngưỡng có bao nhiêu giờ được bắt. F1 là trung bình điều hòa của precision và recall. Nhóm dùng F1 làm tiêu chí chính, đồng thời xem báo nhầm và bỏ sót.

**Công thức khi thầy hỏi:** Precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = 2PR/(P+R). F1 không phải accuracy.

### 46. ★ Kết quả chính là gì và cải thiện bao nhiêu?

**Trả lời mẫu:** Trên tập test đã công bố, HistGB có precision khoảng 0,926, recall 0,928 và F1 0,927. Persistence có F1 khoảng 0,914. Chênh lệch F1 khoảng 0,013, tương đương 1,3 điểm phần trăm khi biểu diễn F1 theo phần trăm. Đây là cải thiện có giới hạn trên một baseline mạnh, không phải mức tăng hàng chục phần trăm. Theo bảng đếm, báo nhầm giảm từ 999 xuống 865 và bỏ sót giảm từ 1.000 xuống 838.

**Đọc đúng số:** 0,927 là F1, không phải phát hiện được 92,7% tất cả các đợt ô nhiễm. Các số đếm ở đây có đơn vị giờ-trạm.

### 47. Nếu F1 cao, mô hình có bắt tốt lúc bắt đầu ô nhiễm không?

**Trả lời mẫu:** Chưa thể kết luận như vậy. F1 toàn bộ còn gồm nhiều giờ ô nhiễm đã kéo dài, vốn tương đối dễ đoán từ hiện tại. Với 1.000 trường hợp hiện tại dưới ngưỡng nhưng giờ sau vượt ngưỡng trong test, mô hình công bố phát hiện 304, tức 30,4%; persistence không phát hiện được vì hiện tại còn sạch. Đây là lý do nhóm phân tích riêng tình huống chuyển trạng thái.

**Phân biệt:** 1.000 trường hợp này không phải mẫu số 730 đợt của thí nghiệm khởi phát trong sáu giờ; hai bài toán khác định nghĩa và quần thể đánh giá.

### 48. ★ Có thể khẳng định hoàn toàn không rò rỉ và test chưa bao giờ bị dùng lại không?

**Trả lời mẫu:** Em không khẳng định tuyệt đối. Quy trình ban đầu chọn mô hình và ngưỡng trên validation, rồi công bố test. Rà soát sau đó phát hiện 9 dòng train và 12 dòng validation có giờ nhãn vượt qua biên split. Thử loại các dòng này và học lại cho F1 test khoảng 0,926 thay vì 0,927; artifact khóa được giữ nguyên và kết quả rà soát được ghi riêng. Các thí nghiệm tiếp theo cũng đã dùng giai đoạn 2016 H2 từng được xem trước, nên không gọi nó là tập kiểm tra hoàn toàn mới chưa từng đụng tới.

**Nếu thầy hỏi cách làm chặt hơn:** Giữ toàn bộ cửa sổ nhãn bên trong split, fit các bước tiền xử lý trên train tương ứng và dành một giai đoạn chưa dùng cho lần xác nhận mới. Những fold cũ tái dùng dữ liệu đã điền thiếu không được mô tả như toàn bộ pipeline đã fit lại độc lập.

### 49. ★ Ngưỡng 115 và ngưỡng 0,50 khác nhau thế nào? Có giảm ngưỡng để bắt nhiều hơn được không?

**Trả lời mẫu:** 115 là ngưỡng nồng độ để định nghĩa nhãn thật. 0,50 là ngưỡng trên điểm xác suất của mô hình để quyết định phát cảnh báo. Có thể hạ ngưỡng điểm để thường bắt nhiều trường hợp hơn, nhưng báo nhầm cũng có thể tăng; cần đo trên validation và chọn theo yêu cầu vận hành. Điểm 0,8 của mô hình chưa tự chứng minh rằng trong thực tế cứ mười lần như vậy sẽ có đúng tám lần vượt ngưỡng nếu chưa kiểm tra hiệu chuẩn.

### 50. Báo nhầm và bỏ sót, cái nào nghiêm trọng hơn? Kiểm định thống kê có đủ để triển khai không?

**Trả lời mẫu:** Điều đó phụ thuộc mục đích cảnh báo. Bỏ sót làm mất cơ hội chuẩn bị; báo nhầm nhiều gây tốn nguồn lực và giảm niềm tin. Nhóm chưa lượng hóa đầy đủ chi phí thực tế của hai loại lỗi nên không khẳng định ngưỡng hiện tại tối ưu cho vận hành. Báo cáo có kiểm định McNemar so sánh sai khác giữa mô hình và persistence, nhưng ý nghĩa thống kê chưa thay thế được đánh giá chi phí, thời gian báo trước và hiệu quả ngoài thực tế. Dữ liệu theo thời gian còn có phụ thuộc nên cần thận trọng khi suy rộng ý nghĩa của kiểm định.

## F. Hồi quy PM2.5 — phân tích bổ trợ

### 51. Dự báo PM2.5 cụ thể khác phân loại cảnh báo thế nào?

**Trả lời mẫu:** Hồi quy trả ra một con số, ví dụ dự đoán PM2.5 giờ tới là 120 µg/m³. Phân loại trả ra điểm và quyết định liệu giờ tới có vượt ngưỡng hay không. Một mô hình có sai số trung bình nhỏ vẫn có thể phân loại sai quanh ngưỡng. Vì vậy nhóm báo cáo riêng kết quả hồi quy và phân loại, không lấy MAE để chứng minh F1 cao hoặc ngược lại.

### 52. ★ MAE khoảng 8,87 có nghĩa gì? Có phải mọi dự báo chỉ sai tối đa 8,87 không?

**Trả lời mẫu:** MAE là trung bình độ lệch tuyệt đối giữa dự đoán và số đo thật. Mô hình hồi quy HistGB v2 đang khóa có MAE test khoảng 8,87 µg/m³, so với persistence khoảng 9,78. Đây là trung bình trên tập test, không phải sai số tối đa hay khoảng bảo đảm cho từng giờ. Một số giờ biến động mạnh vẫn có thể sai rất lớn.

### 53. Mô hình hồi quy v2 cải thiện gì so với bản đầu?

**Trả lời mẫu:** V2 bổ sung thông tin như mức thay đổi PM2.5 gần nhất, PM10, CO, NO2 hiện tại và các độ trễ, cùng trạng thái đợt được tính tới hiện tại. MAE test của bản khóa trước khoảng 9,14 và v2 khoảng 8,87. V2 đã được đưa vào phiên bản hồi quy đang dùng; tuy nhiên không vì cải thiện chỉ số chung mà kết luận nó tốt hơn ở mọi mùa hoặc mọi trạm.

### 54. Tại sao đôi khi đường dự báo trông giống đường thực tế? Có phải lấy kết quả thật để vẽ không?

**Trả lời mẫu:** Dự báo một giờ có tín hiệu mạnh từ PM2.5 hiện tại nên đường dự đoán có thể khá sát. Khi xem lịch sử, dashboard vẽ cả dự đoán và số đo thực tế để đối chiếu, nhưng đầu vào dự đoán phải chỉ dùng thông tin tới giờ phát dự đoán. Em cần phân biệt giờ gốc t và giờ đích t+1, đồng thời dùng baseline để xem mô hình có chỉ đang bám theo giá trị cũ hay không.

### 55. Dấu cảnh báo độ tin cậy có bảo đảm biết trước lúc nào dự báo sai không?

**Trả lời mẫu:** Không. Phần rà soát độ tin cậy cho thấy những giờ PM2.5 đổi nhanh hoặc lệch nhiều so với các trạm lân cận có tỷ lệ sai số lớn cao hơn bình thường trên train và validation. Đó là dấu để chú ý rủi ro, không phải chứng nhận một dự báo chắc chắn sai hoặc đúng. Phần này không đổi mô hình hồi quy khóa và chưa được đánh giá trên test trong thí nghiệm đó.

## G. Phân cụm trạm và diễn giải kết quả

### 56. ★ Nhóm phân cụm cái gì: các giờ hay các trạm?

**Trả lời mẫu:** Nhóm phân cụm 12 trạm, mỗi trạm là một dòng đặc trưng tổng hợp. Các thuộc tính gồm mức và biến động ô nhiễm, đặc trưng theo mùa, tỷ lệ giờ vượt ngưỡng và đặc điểm đợt ô nhiễm. Không phải nhóm đưa hơn 420 nghìn dòng giờ vào K-Means để phân cụm giờ. Cửa sổ hồ sơ trạm của bản khóa là từ 03/2013 tới hết 2016.

### 57. Vì sao chuẩn hóa và chọn K = 2?

**Trả lời mẫu:** Các đặc trưng khác đơn vị và thang đo nên nhóm dùng StandardScaler trước K-Means để tránh thuộc tính có giá trị lớn chi phối khoảng cách. Trong các K đã thử là 2, 3 và 4, K = 2 cho silhouette tốt nhất, khoảng 0,664. Nhóm còn kiểm tra độ ổn định theo seed và đối chiếu phân cụm phân cấp. Đây là lựa chọn phù hợp trong phạm vi thử nghiệm, không phải bằng chứng chỉ tồn tại đúng hai kiểu trạm trong tự nhiên.

### 58. Hai cụm có ý nghĩa gì? Có dùng vị trí địa lý để ép ra kết quả không?

**Trả lời mẫu:** Nhóm diễn giải sau khi phân cụm: một cụm gồm 9 trạm có mức ô nhiễm tương đối cao hơn, cụm còn lại gồm Changping, Huairou và Dingling có mức tương đối thấp hơn. Tên cụm là nhãn mô tả, không phải phân hạng an toàn. Phiên bản này không đưa tọa độ, quận hay mã trạm vào đặc trưng K-Means; nhóm dùng địa lý để đối chiếu kết quả, không để ép mô hình tách theo quận.

### 59. Phân cụm có chắc làm mô hình dự báo tốt hơn không? Dùng cả giai đoạn có rò rỉ không?

**Trả lời mẫu:** Không thể suy ra lợi ích dự báo chỉ vì các cụm có vẻ hợp lý. Hồ sơ cả giai đoạn phù hợp để mô tả lịch sử; nếu đưa cụm vào dự báo thì cần fit trên train để tránh nhìn tương lai. Nhóm đã kiểm tra lại theo cửa sổ train và thấy phân nhóm không đổi trong các cửa sổ đã thử. So sánh có và không có cluster_id ở cùng ngưỡng cũng không cho thấy lợi ích rõ rệt cho phân loại; nhóm không nhận công cải thiện mà dữ liệu chưa chứng minh.

## H. Đợt ô nhiễm, cảnh báo sáu giờ và phát lại

### 60. ★ Một giờ vượt ngưỡng và một đợt ô nhiễm khác nhau thế nào?

**Trả lời mẫu:** Một giờ vượt ngưỡng chỉ cần PM2.5 của giờ đó đạt ít nhất 115. Trong dự án, một đợt tại trạm cần ít nhất ba giờ liên tục đạt ngưỡng này; thiếu số đo sẽ làm gián đoạn chuỗi xác nhận. Cảnh báo t+1 dự đoán trạng thái của một giờ, không tự khẳng định sẽ có một đợt kéo dài. Dự án còn có phân tích sự kiện nhiều trạm với quy ước đồng thời ít nhất 6 trạm, cần phân biệt với đợt tại một trạm.

### 61. Thí nghiệm khởi phát trong sáu giờ dự đoán điều gì? Vì sao kiểm tra tới t+8?

**Trả lời mẫu:** Nó chỉ xét thời điểm hiện tại còn dưới ngưỡng và hỏi có đợt kéo dài ít nhất ba giờ bắt đầu trong t+1 đến t+6 hay không. Nếu đợt bắt đầu muộn nhất ở t+6 thì phải xem thêm t+7 và t+8 mới xác nhận đủ ba giờ. Đây là cửa sổ dùng tạo nhãn khi đánh giá; dự đoán tại t vẫn không được nhìn các giờ tương lai đó. Nhãn chỉ được giữ nếu toàn bộ cửa sổ cần thiết còn trong split.

### 62. ★ Kết quả sáu giờ là gì? Có phải dự báo trước được sáu giờ không?

**Trả lời mẫu:** Ở giai đoạn 2016 H2 đã từng được dùng trong các quyết định trước, mô hình có đặc trưng lân cận phát hiện 506/730 đợt, recall khoảng 69,3%; luật mức hiện tại với ngưỡng 105 phát hiện 468/730, khoảng 64,1%. Trung vị thời gian báo trước trong các đợt phát hiện được là 3 giờ so với 1 giờ. Nói “trong sáu giờ tới” là khoảng thời gian tìm khởi phát, không có nghĩa mọi đợt đều được báo trước đúng sáu giờ.

**Giới hạn cần nói:** Đây là thí nghiệm riêng, cải thiện không đồng đều theo mùa và trạm, và chưa thay mô hình phân loại t+1 đang khóa.

### 63. Vì sao không chỉ so thí nghiệm sáu giờ với persistence? 0,5 báo nhầm/ngày là gì?

**Trả lời mẫu:** Vì chỉ xét lúc hiện tại dưới ngưỡng, persistence sẽ không cảnh báo nên là baseline quá yếu cho bài toán này. Nhóm so thêm luật mức hiện tại và xu hướng; luật mức được chọn phát cảnh báo khi PM2.5 hiện tại từ 105 trở lên. Ngưỡng mô hình được chọn trên validation dưới trần trung bình 0,5 thời điểm cảnh báo nhầm trên mỗi ngày-trạm đủ điều kiện, rồi đem sang đánh giá. Đây không phải tỷ lệ 50% báo nhầm, cũng không phải bảo đảm từng ngày đều có nhiều nhất một cảnh báo nhầm.

### 64. ★ Trang phát lại chứng minh điều gì? Tại sao ẩn số đo thực tế ở tương lai?

**Trả lời mẫu:** Trang phát lại minh họa mô hình t+1 đã khóa hoạt động khi dữ liệu lịch sử được đưa tới từng batch. Tại mốc hiện tại, hệ thống phát dự đoán cho giờ đích; số đo thật và thông tin hậu kiểm chỉ hiện khi mốc dữ liệu đã bao phủ giờ đích đó. Cách này giúp giải thích dự đoán trước, đối soát sau. Cửa sổ demo có nhiều giờ đã ô nhiễm nên F1 rất cao trong demo không được dùng như bằng chứng mô hình mới tốt hơn kết quả toàn tập.

## I. Dashboard, giới hạn và bảo vệ đóng góp

### 65. ★ Nếu thầy yêu cầu demo trong ba phút, em đi theo luồng nào?

**Trả lời mẫu:** Em mở tổng quan để nêu quy mô và khoảng thời gian; sang OLAP thực hiện một ví dụ roll-up hoặc slice; sang cảnh báo giải thích nhãn, baseline và một kết quả chính. Nếu còn thời gian, em mở phát lại để minh họa thời điểm dự đoán và khi nào biết kết quả thật. Mỗi màn hình phải trả lời một câu hỏi nghiệp vụ, tránh chỉ bấm qua các biểu đồ.

**Các trang thực tế:** `/`, `/olap`, `/canh-bao`, `/phat-lai`; phần bổ trợ có `/tram`, `/dot-o-nhiem`, `/thoi-tiet`, `/du-bao`, `/ban-do`.

### 66. ★ Thầy chọn ngày mà không có dự đoán thì có phải hệ thống lỗi không?

**Trả lời mẫu:** Chưa chắc. Cần xem khoảng ngày, trạm và giai đoạn train/validation/test đang chọn có giao nhau không, đồng thời kiểm tra giờ đó có đủ dữ liệu để tạo đặc trưng và nhãn hay không. Kho có dữ liệu đến 2017 nhưng test chính kết thúc ở 2016. Ví dụ chọn test mà lọc ngày thuộc 2015 sẽ không có điểm dự đoán tương ứng; không có kết quả trong một bộ lọc không tự chứng minh API hỏng.

### 67. Làm sao chứng minh dự án chạy lại được? Nếu demo không có mạng thì sao?

**Trả lời mẫu:** Repo có script điều phối chạy toàn bộ, cấu hình môi trường mẫu, kiểm tra dữ liệu và artifact kết quả. Log tiến độ ghi nhận một lần chạy từ đầu đạt 14/14 bước, cùng các kiểm tra kho và mô hình. Lần đầu cần mạng để tải nguồn và gọi API; trước buổi bảo vệ phải kiểm tra dữ liệu, container và dashboard trên máy sẽ dùng. Nếu demo trực tiếp gặp sự cố, notebook OLAP có output và artifact báo cáo là bằng chứng dự phòng, nhưng em phải nói rõ đó là kết quả đã lưu.

### 68. ★ Hạn chế lớn nhất là gì? Có dùng thực tế ngay được không?

**Trả lời mẫu:** Dữ liệu lịch sử chỉ có 12 trạm ở một thành phố; kết quả tốt trong giai đoạn đã đánh giá chưa bảo đảm cho hiện tại hoặc địa phương khác. Nhóm còn hạn chế về dữ liệu thiếu, khả năng phát hiện chuyển trạng thái, sai số khi biến động mạnh, tính độc lập của đánh giá sau nhiều thí nghiệm và xử lý dữ liệu đến muộn. Muốn vận hành thật cần nguồn cập nhật ổn định, đánh giá trên giai đoạn mới, giám sát chất lượng và chốt quy trình cảnh báo với người dùng.

**Nếu được hỏi phát triển tiếp:** Em ưu tiên kiểm chứng trên dữ liệu mới và làm rõ hiệu quả cảnh báo trước khi thêm thuật toán phức tạp.

### 69. ★ Em trực tiếp làm phần nào? Có dùng AI thì đóng góp của em ở đâu?

**Khung trả lời — bắt buộc điền theo thực tế:** Em trực tiếp phụ trách **[phần việc thật]**, sản phẩm là **[bảng/trang/tài liệu/chức năng]**. Em giải thích được đầu vào, quy tắc xử lý và cách kiểm tra đầu ra của phần đó. Em dùng AI để hỗ trợ **[việc thật đã dùng]**, sau đó kiểm tra bằng **[bằng chứng thật: truy vấn đối soát, test, đọc tài liệu, demo]**. Phần **[phần chưa tự làm hoặc chưa nắm]** em ghi rõ mức độ tham gia.

**Chuẩn bị bằng chứng:** Chọn một quyết định bạn hiểu, một ví dụ dữ liệu bạn lần theo được và một kiểm tra bạn giải thích được. Không tạo lịch sử đóng góp hay kể một lỗi “tự sửa” nếu việc đó không xảy ra.

### 70. ★ Nếu thầy hỏi “kết luận đề tài của em là gì?”, trả lời thế nào?

**Trả lời mẫu:** Nhóm đã xây dựng được chuỗi dữ liệu từ thu thập đến kho và dashboard, với thiết kế trạm–giờ và các thao tác OLAP được đối soát. Phân loại t+1 cải thiện F1 so với baseline persistence trên tập test đã công bố, nhưng khả năng bắt thời điểm bắt đầu vượt ngưỡng còn hạn chế. Các phân tích bổ trợ giúp hiểu đặc trưng trạm và rủi ro dự báo. Kết quả chứng minh tính khả thi trong phạm vi bài tập lịch sử; nhóm chưa coi đây là hệ thống cảnh báo thực tế đã được xác nhận ngoài môi trường triển khai.

## J. Tờ ghi nhớ nhanh trước khi vào phòng

### Những con số nên nhớ

| Nội dung | Con số / cách nói đúng |
|---|---|
| Dữ liệu kho | 12 trạm; 420.768 dòng giờ-trạm; 03/2013–02/2017 |
| Độ mịn fact | Một trạm tại một mốc giờ |
| Bảng chiều | Ngày, giờ, trạm, hướng gió |
| Kịch bản File + DB | 298.368 + 122.400 = 420.768; DB mô phỏng từ cùng UCI |
| Nhãn chính | PM2.5(t+1) ≥ 115 µg/m³ |
| Đợt ô nhiễm tại trạm | Ít nhất 3 giờ liên tiếp đạt ngưỡng 115 |
| Lịch chia ML | Train đến hết 2015; val 2016 H1; test 2016 H2 |
| Số dòng ma trận ML chính | 372.499; khác số dòng fact vì có điều kiện tạo đặc trưng và nhãn |
| HistGB phân loại, bản khóa | Test F1 ≈ 0,927; persistence ≈ 0,914 |
| Báo nhầm / bỏ sót, bản khóa | HistGB 865 / 838; persistence 999 / 1.000 |
| Chuyển từ dưới lên vượt ngưỡng ở t+1 | Bản khóa bắt 304/1.000 trường hợp; không gọi là mọi đợt |
| Rà soát nhãn ở biên split | Bỏ 9 dòng train và 12 dòng val, refit: test F1 ≈ 0,926; ghi riêng |
| Hồi quy đang khóa | HistGB v2, test MAE ≈ 8,87 µg/m³; persistence ≈ 9,78 |
| Phân cụm | 12 hồ sơ trạm, K = 2; cụm 9 và 3 trạm |
| Cube đã tính | 5 thuộc tính, 32 grouping sets; không phải 32 bảng dimension |
| Kiểm chứng kho đã ghi nhận | 130 dbt test đạt; 24.759 ô tổng hợp đối chiếu khớp |
| Thí nghiệm khởi phát trong 6h | Spatial 506/730 đợt; luật mức 468/730; trung vị lead 3h và 1h trong các đợt phát hiện |

### Mười cách nói cần sửa trước khi bảo vệ

| Tránh nói | Nên nói |
|---|---|
| “Đây là dữ liệu realtime của Bắc Kinh.” | “Đây là dữ liệu lịch sử, có mô phỏng tiếp nhận tăng dần.” |
| “Có ba bộ dữ liệu ô nhiễm độc lập.” | “Có ba kênh tích hợp; File và DB ô nhiễm cùng xuất phát từ UCI.” |
| “AQI bằng 115.” | “Ngưỡng nồng độ PM2.5 là 115 µg/m³ trong nhãn dự án.” |
| “F1 92,7% tức bắt được 92,7% mọi đợt.” | “F1 là thước đo ở mức giờ-trạm; đợt cần đánh giá riêng.” |
| “MAE 8,87 nghĩa là sai tối đa 8,87.” | “Đó là sai số tuyệt đối trung bình trên test.” |
| “Mô hình dự báo trước sáu giờ.” | “Mô hình hỏi đợt có khởi phát trong sáu giờ tới; thời gian báo trước thay đổi.” |
| “Không có NULL nên dữ liệu tốt.” | “Cần giữ đúng ý nghĩa số đo thiếu và kiểm tra chất lượng.” |
| “Thêm phân cụm chắc chắn làm dự báo tốt hơn.” | “Phải đo đóng góp bằng so sánh có/không có đặc trưng cụm.” |
| “Test chưa từng được dùng trong nghiên cứu sau này.” | “Các kết quả sau dùng lại giai đoạn đã xem nên có giới hạn đánh giá.” |
| “Dùng AI nên em không biết phần đó.” | “Em nêu đúng phần được hỗ trợ và giải thích phần mình đã kiểm chứng.” |

### Ba tình huống hỏi nối tiếp để tự luyện

**Tình huống 1 — thầy hỏi giá trị mô hình:**

1. PM2.5 hiện tại đã biết rồi, vì sao cần mô hình?
2. Vậy baseline của em mạnh đến đâu?
3. Cải thiện 0,013 F1 có đáng dùng không?
4. Tại sao bắt lúc bắt đầu vượt ngưỡng chỉ được 30,4%?
5. Em cần thêm bằng chứng gì trước khi triển khai?

**Tình huống 2 — thầy hỏi kho dữ liệu:**

1. Một dòng fact là gì?
2. Tại sao không gộp theo ngày cho nhẹ?
3. Trung bình tháng có lấy trung bình các ngày được không?
4. Bốn chiều mà cube lại có năm thuộc tính là thế nào?
5. Em chứng minh cube không tính sai bằng cách nào?

**Tình huống 3 — thầy hỏi tính thực tế:**

1. Database nguồn có phải cơ sở dữ liệu quan trắc thật không?
2. Watermark khác đọc toàn bộ bảng ở đâu?
3. Một bản ghi hôm qua sửa lại thì em có bắt được không?
4. Khi dữ liệu mới đến, mô hình có tự học lại không?
5. Trang phát lại cho xem điều gì và chưa chứng minh được điều gì?

## K. Nguồn đối chiếu trong repo

Các đường dẫn dưới đây tính từ thư mục gốc dự án. Khi tài liệu kế hoạch cũ khác trạng thái hiện tại, đối chiếu artifact khóa và ghi chú quyết định tương ứng; giữ rõ kết quả chính và kết quả thí nghiệm.

| Nội dung | Tài liệu / artifact |
|---|---|
| Tổng quan, cách chạy và đối chiếu yêu cầu môn học | `README.md` |
| Thiết kế kho, grain, phân cấp, cube, OLAP | `docs/DW_DESIGN.md` |
| Dữ liệu thiếu, nguồn bổ sung, cờ chất lượng | `docs/DATA_PREPROCESSING.md` |
| File + database mô phỏng + watermark | `docs/OPERATIONAL_DB_INGESTION_DESIGN.md` |
| Bằng chứng kiểm thử và tiến độ đã ghi nhận | `docs/PROGRESS.md` |
| Phân loại chính và confusion matrix | `artifacts/classification/classification_report.md`, `artifacts/classification/model_lock.json` |
| Rà soát biên split, fit cụm và giới hạn đánh giá | `artifacts/classification/evaluation_hygiene/decision_note.md` |
| Khởi phát trong sáu giờ | `artifacts/classification/onset_6h/decision_note.md` |
| Demo phát lại | `artifacts/classification/replay/decision_note.md` |
| Hồi quy đang khóa | `artifacts/forecasting/model_lock.json` |
| Dấu rủi ro dự báo | `artifacts/forecasting/reliability/decision_note.md` |
| Phân cụm đang khóa | `artifacts/clustering/cluster_lock.json` |
| Định nghĩa đợt và sự kiện nhiều trạm | `artifacts/eda/episode_lock_summary.json` |
| Kiểm chứng OLAP | `artifacts/dwh/olap_checks.json` |
| Kiểm tra cách cube và mart lưu độ đo | `dbt/air_quality_dbt/models/marts/mart_olap_cube.sql`, `mart_station_daily.sql` cùng thư mục |
| Các trang dashboard thực có | `dashboard/web/src/App.tsx` |
| Điền đóng góp thật và khai báo AI | `bao_cao/BANG_PHAN_CONG.md`, `bao_cao/KHAI_BAO_AI.md` |

**Mục tiêu khi học xong:** Bạn có thể giải thích một ví dụ từ số đo gốc đến kho, một thao tác OLAP, một dự đoán và cách kiểm tra đúng/sai; đồng thời nói rõ giới hạn mà kết quả hiện tại chưa trả lời được.
