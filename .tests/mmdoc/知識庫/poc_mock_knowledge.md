# MM-Agent PoC 模擬知識擴展

**創建日期**: 2026-02-01
**創建人**: Daniel Chung
**版本**: 1.0

---

## 1. 概述

本文件包含 MM-Agent PoC 所需的**模擬知識**，用於演示自然語言查詢能力。

**策略**：基於現有 60 chunks 知識，添加模擬的業務場景知識，快速提升 PoC 演示效果。

---

## 2. 訂單流程知識

### 2.1 出貨訂單查詢流程 (AXMT520)

```markdown
## 出貨訂單查詢流程

### 1. 查詢條件
- 客戶代碼 (Customer Code)
- 出貨日期範圍（如：本月、上週、特定日期）
- 狀態：已確認、待出貨、已出貨

### 2. 查詢流程

#### Step 1: 驗證客戶代碼
```
1. 系統驗證客戶代碼是否存在
2. 確認客戶授權狀態
3. 獲取客戶基本信息（名稱、聯絡人）
```

#### Step 2: 查詢 COPTC 表（訂單頭）
```
1. 篩選條件：
   - 客戶代碼 = @CustomerCode
   - 出貨日期 BETWEEN @StartDate AND @EndDate
   - 訂單狀態 IN ('已確認', '待出貨', '已出貨')
2. 排序：出貨日期 DESC
3. 限制：最近 100 筆訂單
```

#### Step 3: 查詢 COPTD 表（訂單身）
```
1. 關聯條件：coptd.coptc_id = coptc.cp01
2. 篩選條件：
   - 物品料號 IN (@ItemNumbers)
   - 出貨數量 > 0
3. 排序：物料代碼、出貨數量
```

#### Step 4: 查詢 img_file 表（庫存檢查）
```
1. 關聯條件：
   - img_file.img01 = coptd.cp02
2. 檢查：
   - 庫存數量 >= 訂單數量
   - 庫存狀態 = '可用'
3. 警告條件：
   - 如果庫存不足，返回不足數量
```

#### Step 5: 結果輸出
```
1. 訂單頭信息
   - 訂單號、客戶代碼、出貨日期、總金額

2. 訂單身信息
   - 物料料號、物料名稱、訂單數量、單價、小計金額

3. 庫存狀態
   - 可用、不足數量、警訊信息

4. 按客戶代碼分組
```

### 3. SQL 範例

#### 範例 1: 查詢客戶 D003 本月的出貨訂單
```sql
SELECT
  coptc.cp01 AS 訂單號,
  coptc.cp02 AS 客戶代碼,
  coptc.cp03 AS 出貨日期,
  coptc.cp04 AS �狀態,
  SUM(coptd.cp05) AS 總數量,
  SUM(coptd.cp05 * coptd.cp06) AS 總金額
FROM coptc_file
LEFT JOIN coptd_file ON coptc.cp01 = coptd.coptc_id
WHERE
  coptc.cp02 = 'D003'
  AND coptc.cp03 >= '2026-02-01'
  AND coptc.cp03 <= '2026-02-28'
  AND coptc.cp04 IN ('已確認', '待出貨', '已出貨')
GROUP BY
  coptc.cp01, coptc.cp02, coptc.cp03, coptc.cp04
ORDER BY coptc.cp03 DESC
```

#### 範例 2: 查詢訂單明細（含庫存檢查）
```sql
SELECT
  coptd.coptc_id AS 訂單號,
  coptd.cp02 AS 物料料號,
  ima.ima02 AS 物料名稱,
  coptd.cp05 AS 訂單數量,
  img.img10 AS 庫存數量,
  CASE
    WHEN img.img10 >= coptd.cp05 THEN '充足'
    ELSE CONCAT('不足 ', (coptd.cp05 - img.img10))
  END AS 庫存狀態,
  coptd.cp06 AS 單價,
  coptd.cp05 * coptd.cp06 AS 小計金額
FROM coptd_file
LEFT JOIN img_file ON img_file.img01 = coptd.cp02
LEFT JOIN ima_file ON ima_file.ima01 = coptd.cp02
WHERE
  coptd.coptc_id IN (
    SELECT cp01 FROM coptc_file
    WHERE cp02 = 'D003'
    AND cp03 >= '2026-02-01'
    AND cp03 <= '2026-02-28'
    AND cp04 IN ('已確認', '待出貨', '已出貨')
  )
ORDER BY
  coptd.cp02
```

### 4. 注意事項

1. **權限驗證**：查詢前需驗證用戶是否有權訪問該客戶數據
2. **數據一致性**：COPTC 和 COPTD 的關聯欄位必須一致
3. **庫存鎖定**：查詢時可能需要鎖定庫存，避免併發
4. **性能優化**：對大數據量查詢，建議添加索引
```

## 3. 訂價單查詢知識

### 3.1 �價單查詢流程 (AXMT420)

```markdown
## �價單查詢流程

### 1. 查詢條件
- 物料料號 (Part Number, PN)
- 查詢範圍：最新價格、歷史價格、有效期間

### 2. 查詢流程

#### Step 1: 查詢 RVB 表（訂價單）
```
1. 篩選條件：
   - 物料料號 = @PartNumber
2. 排序：生效日期 DESC (最新的在前)
3. 限制：最近 10 筆訂價記錄
4. 條件：
   - rvb01 = '有效' (批准狀態)
   - rvb05 >= @StartDate (生效日期)
   - rvb06 <= @EndDate (失效日期，如果存在)
```

#### Step 2: 價格有效性檢查
```
1. 檢查生效日期 (rvb05)
2. 檢查失效日期 (rvb06)
3. 檢查批准狀態 (rvb01)
4. 確認是否在有效期內
```

#### Step 3: 獲取最新批准價格
```
1. 選擇最新的有效價格
2. 提取關鍵信息：
   - 單價 (rvb02)
   - 幅度 (rvb03)
   - 幣度單位 (rvb04)
   - 生效日期 (rvb05)
   - 失效日期 (rvb06)
```

#### Step 4: 結果輸出
```
1. 最新批准價格
2. 有效期間
3. 價格歷史（最近 10 筆）
4. 供應商信息
```

### 3. SQL 範例

#### 範例 1: 查詢料號 10-0001 的最新訂價
```sql
SELECT
  rvb.rvb01 AS 單價,
  rvb.rvb02 AS 幅度,
  rvb.rvb03 AS 單價單位,
  rvb.rvb04 AS 生效日期,
  rvb.rvb05 AS 失效日期,
  rvb.rvb06 AS 批准狀態,
  rvb.rvb07 AS 供應商代碼
FROM rvb_file
WHERE
  rvb.rvb08 = '10-0001'
  AND rvb.rvb01 = '有效'
  AND (
    rvb.rvb04 <= CURRENT_DATE
    OR rvb.rvb05 IS NULL
  )
ORDER BY
  rvb.rvb04 DESC
LIMIT 1
```

#### 範例 2: 查詢料號 10-0001 的訂價歷史
```sql
SELECT
  rvb.rvb01 AS 單價,
  rvb.rvb02 AS 幅度,
  rvb.rvb03 AS 單價單位,
  rvb.rvb04 AS 生效日期,
  rvb.rvb05 AS 失效日期,
  rvb.rvb06 AS 批准狀態,
  rvb.rvb07 AS 供應商代碼,
  ROW_NUMBER() OVER (
    ORDER BY rvb.rvb04 DESC
  ) AS 排名
FROM rvb_file
WHERE
  rvb.rvb08 = '10-0001'
ORDER BY
  rvb.rvb04 DESC
LIMIT 10
```

### 4. 價格策略知識

### 4.1 A 類物料價格策略

```markdown
## A 類物料價格策略

### 1. 價格分級
- **A 類**：高價值物料，價格敏感度高
- **管控方式**：嚴格價格控制
- **審批流程**：三級審批

### 2. 價格計算規則
```
1. 基準價 = 供應商報價 * (1 + 管理費用比率)
2. 最低價 = MIN(供應商報價)
3. 最高價 = MIN(供應商報價 * (1 + 允許比率))
4. 目標價格 = (最低價 + 最高價) / 2
```

### 3. 採購閾值
- 單價 <= 目標價格 → 自動批准
- 單價 > 目標價格 → 需要高級審批

### 4. 異差異常檢測
- 單價與歷史價格差異 > 20% → 人工審核
- 單價與市場價格差異 > 30% → 異異告警
```

## 4. 生產進度查詢知識

### 4.1 生產進度查詢流程 (ASFT301)

```markdown
## 生產進度查詢流程

### 1. 查詢條件
- SO (銷售訂單號)
- SO Line (銷售訂單明細)
- Order Batch (訂單批次)
- 查詢範圍：當前狀態、預計完成時間

### 2. 查詢流程

#### Step 1: 查詢 SO (銷售訂單)
```
1. 查詢條件：SO 號號 = @SOCode
2. 獲取 SO 基本信息：
   - 客戶代碼
   - �單日期
   - 預計交期
   - SO 狀態
```

#### Step 2: 查詢 SO Line (銷售訂單明細)
```
1. 關聯條件：so_line.so_id = so.id
2. 獲取 SO Line 明細：
   - 物料料號
   - 數量
   - 單價
   - 交期
```

#### Step 3: 查詢 Order Batch (訂單批次)
```
1. 關聯條件：order_batch.so_line_id = so_line.id
2. 獲取批次信息：
   - 批次號
   - 數量
   - 生產工單號
   - 卡在的製程
```

#### Step 4: 查詢卡在的製程
```
1. 根據工單號查詢製程
2. 獲取製程信息：
   - 製程站點名稱
   - 當前進度
   - 預計完成日期
   - 實際完成日期
```

### 3. SQL 範例

#### 範例 1: 查詢 SO 的生產進度
```sql
SELECT
  so.id AS SO號,
  so.so02 AS 客戶代碼,
  so.so04 AS 訂單日期,
  so.so05 AS 預計交期,
  so.so06 AS SO 狀態,
  so_line.id AS SO Line 號號,
  so_line.sld01 AS 物料料號,
  so_line.sld02 AS 數量,
  so_line.sld03 AS 單價,
  order_batch.ob01 AS 批次號,
  order_batch.ob02 AS 數量,
  order_batch.ob03 AS 工單號,
  order_batch.ob04 AS 卡在製程,
  order_batch.ob05 AS 當前進度,
  order_batch.ob06 AS 預計完成日期
FROM so_file AS so
LEFT JOIN so_line_file AS so_line ON so_line.so_id = so.id
LEFT JOIN order_batch_file AS order_batch ON order_batch.sld_id = so_line.id
WHERE
  so.id = @SOCode
ORDER BY
  so_line.id, order_batch.ob01
```

## 5. 庫存管理知識擴展

### 5.1 安全庫存規則

```markdown
## 安全庫存規則

### 1. 庫存分級
- **A 類物料**：高價值，安全庫存為 30 天用量
- **B 類物料**：中價值，安全庫存為 15 天用量
- **C 類物料**：低價值，安全庫存為 7 天用量

### 2. 庫存預警規則
```
1. 低庫存預警：
   - 當前庫存 <= 3 天用量 → 發送預警通知
   - 當前庫存 <= 0 → 發送緊急通知

2. 高庫存預警：
   - 當前庫存 >= 60 天用量 → 發送預警通知
   - 當前庫存 >= 90 天用量 → 發送呆滯風險警告

3. 庫存異常預警：
   - 庫存變化率 > 50% → 發送異常警報
```

### 3. 庫存調整操作

#### R (Reject, 拒退) 操作
```
1. 拒退數量 = 採收數量 - 實際合格數量
2. 拒退原因：品質問題、規格不符、包裝損壞
3. 處理方式：
   - 更新庫存數量
   - �錄到調整日誌
   - 通知供應商
```

#### W (Warning, 警告) 操作
```
1. 警告類型：低庫存、高庫存、庫存異常
2. 警告級別：一般、重要、緊急
3. 處理方式：
   - 自動生成調整建議
   - 通知庫管員
   - �錄到調整日誌
```

### 4. SQL 範例

#### 範例 1: 查詢庫存不足的物料
```sql
SELECT
  img.img01 AS 物料料號,
  ima.ima02 AS 物料名稱,
  img.img10 AS 當前庫存,
  img.img11 AS 安全庫存,
  CASE
    WHEN img.img10 <= img.img11 * 0.3 THEN '緊急不足'
    WHEN img.img10 <= img.img11 * 0.5 THEN '低庫存'
    WHEN img.img10 >= img.img11 * 2 THEN '高庫存'
    ELSE '正常'
  END AS 庫存狀態
FROM img_file AS img
LEFT JOIN ima_file AS ima ON ima.ima01 = img.img01
WHERE
  img.img10 <= img.img11 * 0.5
ORDER BY
  (img.img10 / img.img11) ASC
```

## 6. 出貨商品與價格查詢知識

### 6.1 出貨商品價格查詢 (AXMT520)

```markdown
## 出貨商品與價格查詢

### 1. 查詢條件
- 客戶代碼
- 出貨日期範圍
- 查詢所有商品的最新價格

### 2. 查詢流程

#### Step 1: 查詢客戶的所有出貨訂單
```
1. 關聯 COPTC (訂單頭) 和 COPTD (訂單身)
2. 提取所有物料的出貨數量
3. 按物料料號分組
```

#### Step 2: 查詢每個物料的最新訂價
```
1. 關聯 RVB (訂價單)
2. 查詢每個物料的最新批准價格
3. 篩選條件：
   - rvb01 = '有效'
   - rvb04 <= CURRENT_DATE
```

#### Step 3: �詢最終價格
```
1. 優先使用訂單中的單價
2. 如果沒有訂價，使用 RVB 的最新價格
3. 如果都沒有，使用歷史平均價格
```

### 3. SQL 範例

#### 範例 1: 查詢客戶所有出貨商品的價格
```sql
WITH delivery_items AS (
  SELECT
    coptd.cp02 AS 物料料號,
    SUM(coptd.cp05) AS 出貨數量,
    coptd.cp06 AS 訂單單價
  FROM coptc_file
  JOIN coptd_file ON coptd.coptc_id = coptc.cp01
  WHERE
    coptc.cp02 = @CustomerCode
    AND coptc.cp04 IN ('已確認', '待出貨', '已出貨')
  GROUP BY coptd.cp02, coptd.cp06
),
latest_quotes AS (
  SELECT
    rvb.rvb08 AS 物料料號,
    rvb.rvb02 AS 最新單價,
    rvb.rvb04 AS 生效日期
  FROM rvb_file
  WHERE
    rvb.rvb08 IN (SELECT DISTINCT 物料料號 FROM delivery_items)
    AND rvb.rvb01 = '有效'
    AND rvb.rvb04 <= CURRENT_DATE
)
SELECT
  delivery_items.物料料號,
  delivery_items.出貨數量,
  COALESCE(delivery_items.訂單單價, latest_quotes.最新單價, NULL) AS 最終價格,
  delivery_items.訂單單價 AS �訂價來源
FROM delivery_items
LEFT JOIN latest_quotes ON latest_quotes.物料料號 = delivery_items.物料料號
ORDER BY
  delivery_items.物料料號
```

## 7. 價價與訂價單比對知識

### 7.1 價格比對規則

```markdown
## 價格比對規則

### 1. 比對類型
- **同料號比對**：同一物料在不同訂價單的價格
- **同供應商比對**：同一供應商的價格趨勢
- **時間序列比對**：價格隨時間的變化趨勢

### 2. 比對方法

#### 同料號比對
```
1. 提取該料號的所有訂價單記錄
2. 按時間排序
3. �詢價格變化：
   - 最新價格
   - 最高價格
   - 最低價格
   - 平均價格
   - 標準差
```

#### 價格異常檢測
```
1. 價格波動超過 20% → 異異告警
2. 價格波動超過 30% → 異異報告
3. 價格波動超過 50% → 嚴重異常警告

4. 通知相關人員：
   - 採購人員
   - 庫管員
   - 主管
```

### 3. SQL 範例

#### 範例 1: 查詢料號的價格比對
```sql
SELECT
  rvb.rvb01 AS 價格狀態,
  rvb.rvb02 AS 單價,
  rvb.rvb03 AS 單價單位,
  rvb.rvb04 AS 生效日期,
  rvb.rvb07 AS 供應商代碼,
  ROW_NUMBER() OVER (
    PARTITION BY rvb.rvb08
    ORDER BY rvb.rvb04 DESC
  ) AS 排名
FROM rvb_file
WHERE
  rvb.rvb08 = @PartNumber
ORDER BY
  rvb.rvb08, rvb.rvb04 DESC
```

#### 範例 2: 查詢尚未在訂價單中的訂單
```sql
WITH priced_items AS (
  SELECT DISTINCT coptd.cp02 AS 物料料號
  FROM coptc_file
  JOIN coptd_file ON coptd.coptc_id = coptc.cp01
),
all_items AS (
  SELECT DISTINCT coptd.cp02 AS 物料料號
  FROM coptc_file
  JOIN coptd_file ON coptd.coptc_id = coptc.cp01
)
SELECT
  all_items.物料料號,
  COUNT(rvb.rvb08) AS 價格記錄數,
  MAX(rvb.rvb04) AS 最新價格日期
FROM all_items
LEFT JOIN rvb_file AS rvb ON rvb.rvb08 = all_items.物料料號
GROUP BY
  all_items.物料料號
HAVING
  COUNT(rvb.rvb08) = 0 OR MAX(rvb.rvb04) < CURRENT_DATE - 180
ORDER BY
  all_items.物料料號
```

---

**文檔創建日期**: 2026-02-01
**創建人**: Daniel Chung
**版本**: 1.0
