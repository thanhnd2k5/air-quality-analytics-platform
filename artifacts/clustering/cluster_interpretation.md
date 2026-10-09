# Phase 9e – Cluster interpretation

**Lock:** KMeans, K=2, `random_state=42`, feature set `v1_1_1_label_by_pm25`  
**Window:** 2013-03-01 → 2016-12-31  
**Nguồn:** `cluster_lock.json`, `cluster_profiles.csv`, `mart.mart_station_cluster`

Nhãn kỹ thuật `cluster_0` / `cluster_1` được đặt tên mô tả:

| cluster_id | cluster_label | Ý nghĩa ngắn |
|------------|---------------|--------------|
| 0 | `elevated_core` | Ô nhiễm cao hơn, nhiều episode hơn — chủ yếu vành đai đô thị / lõi Bắc Kinh (+ Shunyi) |
| 1 | `cleaner_outskirts` | Ô nhiễm thấp hơn — vành đai ngoại ô phía bắc (Changping, Huairou, Dingling) |

---

## Cluster 0 – `elevated_core` (9 trạm)

**Trạm:** Aotizhongxin, Dongsi, Guanyuan, Gucheng, Nongzhanguan, Shunyi, Tiantan, Wanliu, Wanshouxigong

**Profile (trung bình nhóm):**

- Mean PM2.5 ≈ **82.8** µg/m³ (median ≈ 59)
- Mean NO₂ ≈ **55.6**, CO ≈ **1282** — đồng vận hành với PM cao hơn nhóm kia
- % giờ PM2.5 ≥ 115 ≈ **25%**; episode trung bình ≈ **544**/trạm trong window
- Mùa đông rõ ràng xấu hơn (mean winter ≈ **101**) so với hè (≈ **68**)

**Insight:** Nhóm “nóng” của mạng lưới — phù hợp dashboard tô màu / filter và feature `cluster_id` khi forecast muốn bắt hiệu ứng vùng đô thị dày đặc hơn.

---

## Cluster 1 – `cleaner_outskirts` (3 trạm)

**Trạm:** Changping, Dingling, Huairou

**Profile (trung bình nhóm):**

- Mean PM2.5 ≈ **68.7** µg/m³ (median ≈ 45)
- NO₂ / CO thấp hơn rõ (≈ **34.5** / **1013**)
- O₃ hơi cao hơn nhóm 0 (≈ **62.9** vs 56.5) — pattern thường gặp vùng ít NOx hơn
- % giờ ≥ 115 ≈ **20%**; ít episode hơn (≈ **400**/trạm)

**Insight:** Nhóm ngoại ô sạch hơn tương đối; vẫn có mùa đông xấu nhưng mức nền thấp hơn lõi đô thị.

---

## Cluster vs district

Clustering **không** dùng `district` / tọa độ — chỉ so sau để kiểm tra có trùng địa lý không.

| District | Số trạm | Cluster assignment |
|----------|---------|-------------------|
| Chaoyang | 2 | cả hai → elevated_core (Aotizhongxin, Nongzhanguan) |
| Dongcheng | 2 | cả hai → elevated_core |
| Xicheng | 2 | cả hai → elevated_core |
| Haidian | 1 | elevated_core (Wanliu) |
| Shijingshan | 1 | elevated_core (Gucheng) |
| Shunyi | 1 | elevated_core (Shunyi) — **ngoại thành nhưng profile gần nhóm đô thị** |
| Changping | 2 | cả hai → cleaner_outskirts (Changping, Dingling) |
| Huairou | 1 | cleaner_outskirts |

**Kết luận:** Cluster gần với “lõi/vành đô thị vs ngoại ô phía bắc”, nhưng **không đồng nhất district**. Điểm nổi bật: **Shunyi** ở quận ngoại thành nhưng rơi vào nhóm elevated — profile ô nhiễm gần các trạm lõi hơn là Huairou/Dingling. Vì vậy `cluster_id` bổ sung (không thay thế) `district` / `station_key` cho P10.

---

## Chất lượng phân cụm (nhắc lại P9c)

- Silhouette K=2 ≈ **0.66** (cao hơn K=3/4 rõ)
- Ward hierarchical cùng K=2: **agreement 1.0** với KMeans
- Seed 42 / 0 / 123: assignment ổn định

Với n=12, K=2 là lựa chọn dễ giải thích và ổn định; không cần GMM cho lock hiện tại.

---

## Dùng ở phase sau

- **P10:** join `mart.mart_station_cluster` → categorical / one-hot `cluster_id` (cùng grain station, không leakage thời gian)
- **P11:** map / legend theo `cluster_label`; so sánh KPI theo cụm
