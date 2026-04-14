# Data Agent 測試情境集 (500+ Test Scenarios)

**版本**: 1.0.0  
**生成日期**: 2026-04-13  
**測試範圍**: da_tables/da_expressions Pipeline  
**涵蓋領域**: TRADE, SALES, MANUFACTURING, QUALITY, BASE, MANAGEMENT

---

## 測試情境總覽

| 領域 | 情境數量 | 涵蓋表格數 |
|------|---------|-----------|
| TRADE | 120 | 42 |
| SALES | 90 | 43 |
| MANUFACTURING | 110 | 61 |
| QUALITY | 100 | 65 |
| BASE | 50 | 32 |
| MANAGEMENT | 50 | 19 |
| **總計** | **520** | **262** |

---

## TRADE 領域測試情境 (120 scenarios)

### ERP_1: 報價單 (Quotes)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T001 | 顯示所有報價單 | ERP_1_default | simple_filter | records 數量 > 0, table_key=ERP_1 |
| T002 | 今天的報價單有哪些 | ERP_1_default | simple_filter | date_filter 包含 today |
| T003 | 本週新增的報價單 | ERP_1_default | simple_filter | date_range 為本週 |
| T004 | 客戶 A 公司的所有報價單 | ERP_1_default | simple_filter | customer_filter 存在 |
| T005 | 報價金額超過 10 萬的案件 | ERP_1_default | simple_filter | amount_filter >= 100000 |
| T006 | 統計本月報價單總金額 | ERP_1_default | aggregate | aggregation_type=sum, field=amount |
| T007 | 各業務員的報價單數量 | ERP_1_default | aggregate | group_by=sales_person, count |
| T008 | 尚未轉單的報價單 | ERP_1_default | simple_filter | status_filter=pending |
| T009 | 報價單 Q202604001 的詳細資料 | ERP_1_detail | simple_filter | doc_no=Q202604001 |
| T010 | 最近 30 天報價趨勢 | ERP_1_default | time_series | date_range=30days, group_by_date |

### ERP_2: 訂購單 (Orders)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T011 | 列出所有訂購單 | ERP_2_default | simple_filter | table_key=ERP_2 |
| T012 | 今日新增訂單 | ERP_2_default | simple_filter | date=today |
| T013 | 本月訂單總額 | ERP_2_default | aggregate | sum(amount), month=current |
| T014 | 客戶 B 公司的未出貨訂單 | ERP_2_default | simple_filter | customer=B, status=pending |
| T015 | 交期在本週的訂單 | ERP_2_default | simple_filter | delivery_date in this_week |
| T016 | 逾期未交訂單清單 | ERP_2_default | simple_filter | delivery_date < today, status!=completed |
| T017 | 各產品線訂單數量統計 | ERP_2_default | aggregate | group_by=product_line, count |
| T018 | 訂單 O202604001 的出貨進度 | ERP_2_detail | simple_filter | doc_no=O202604001 |
| T019 | 本季訂單金額排名前 10 客戶 | ERP_2_default | aggregate | group_by=customer, order_by=sum(amount) desc, limit=10 |
| T020 | 比較本月與上月訂單量 | ERP_2_default | time_series | compare month-over-month |

### ERP_3: 內部領用單 (Internal Requisition)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T021 | 顯示所有內部領用單 | ERP_3_default | simple_filter | table_key=ERP_3 |
| T022 | 生產部門本月領用紀錄 | ERP_3_default | simple_filter | department=生產, month=current |
| T023 | 物料 M001 的領用歷史 | ERP_3_default | simple_filter | material_code=M001 |
| T024 | 今天的領用單 | ERP_3_default | simple_filter | date=today |
| T025 | 各部門領用數量統計 | ERP_3_default | aggregate | group_by=department, sum(quantity) |
| T026 | 尚未核准的領用單 | ERP_3_default | simple_filter | approval_status=pending |
| T027 | 本週領用金額超過 5 萬的單據 | ERP_3_default | simple_filter | amount > 50000, week=current |
| T028 | 領用單 IR202604001 詳情 | ERP_3_detail | simple_filter | doc_no=IR202604001 |
| T029 | 各月份領用趨勢分析 | ERP_3_default | time_series | group_by=month, sum(amount) |
| T030 | 研發部門最常領用的前 5 項物料 | ERP_3_default | aggregate | department=研發, group_by=material, order_by=count desc, limit=5 |

### ERP_4: 詢價單 (RFQ)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T031 | 所有詢價單列表 | ERP_4_default | simple_filter | table_key=ERP_4 |
| T032 | 本週發出的詢價單 | ERP_4_default | simple_filter | week=current |
| T033 | 供應商 S001 的詢價紀錄 | ERP_4_default | simple_filter | supplier_code=S001 |
| T034 | 等待報價的詢價單 | ERP_4_default | simple_filter | status=waiting_quote |
| T035 | 本月詢價單數量 | ERP_4_default | aggregate | count, month=current |
| T036 | 各採購員的詢價統計 | ERP_4_default | aggregate | group_by=purchaser, count |
| T037 | 詢價單 RFQ202604001 的回覆情況 | ERP_4_detail | simple_filter | doc_no=RFQ202604001 |
| T038 | 已逾期未回覆的詢價單 | ERP_4_default | simple_filter | reply_deadline < today, status=waiting |
| T039 | 物料 M002 的詢價歷史 | ERP_4_default | simple_filter | material_code=M002 |
| T040 | 本季詢價單轉換率 | ERP_4_default | aggregate | conversion_rate calculation |

### ERP_5: 收貨單 (Receiving)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T041 | 今天的收貨紀錄 | ERP_5_default | simple_filter | date=today |
| T042 | 本週收貨統計 | ERP_5_default | aggregate | week=current, count |
| T043 | 供應商 S002 的收貨明細 | ERP_5_default | simple_filter | supplier_code=S002 |
| T044 | 尚未完成驗收的收貨單 | ERP_5_default | simple_filter | inspection_status=pending |
| T045 | 收貨單 RCV202604001 詳情 | ERP_5_detail | simple_filter | doc_no=RCV202604001 |
| T046 | 本月各供應商收貨金額 | ERP_5_default | aggregate | group_by=supplier, sum(amount), month=current |
| T047 | 有品質異常的收貨單 | ERP_5_default | simple_filter | quality_issue=true |
| T048 | 原料 M003 的收貨歷史 | ERP_5_default | simple_filter | material_code=M003 |
| T049 | 本月收貨趨勢 | ERP_5_default | time_series | month=current, group_by_date |
| T050 | 收貨數量與採購單差異 > 10% 的案件 | ERP_5_default | simple_filter | variance > 0.1 |

### ERP_6: 特採單 (Special Purchase)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T051 | 所有特採單清單 | ERP_6_default | simple_filter | table_key=ERP_6 |
| T052 | 本月特採案件 | ERP_6_default | simple_filter | month=current |
| T053 | 尚未結案的特採單 | ERP_6_default | simple_filter | status=open |
| T054 | 特採單 SP202604001 的審核狀態 | ERP_6_detail | simple_filter | doc_no=SP202604001 |
| T055 | 各品質工程師處理的特採數量 | ERP_6_default | aggregate | group_by=qe, count |
| T056 | 本年度特採金額統計 | ERP_6_default | aggregate | sum(amount), year=current |
| T057 | 供應商 S003 的特採紀錄 | ERP_6_default | simple_filter | supplier_code=S003 |
| T058 | 等待品保主管核准的特採單 | ERP_6_default | simple_filter | approval_level=qa_manager, status=pending |
| T059 | 本季特採原因分析 | ERP_6_default | aggregate | group_by=reason, count, quarter=current |
| T060 | 特採頻率最高的前 10 項物料 | ERP_6_default | aggregate | group_by=material, order_by=count desc, limit=10 |

### ERP_7: 進貨退出單 (Purchase Return)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T061 | 本月進貨退出單 | ERP_7_default | simple_filter | month=current |
| T062 | 供應商 S004 的退貨紀錄 | ERP_7_default | simple_filter | supplier_code=S004 |
| T063 | 本年度退貨金額統計 | ERP_7_default | aggregate | sum(amount), year=current |
| T064 | 退貨原因分類統計 | ERP_7_default | aggregate | group_by=return_reason, count |
| T065 | 進貨退出單 PR202604001 詳情 | ERP_7_detail | simple_filter | doc_no=PR202604001 |
| T066 | 尚未取得退款的退貨單 | ERP_7_default | simple_filter | refund_status=pending |
| T067 | 本季退貨率分析 | ERP_7_default | aggregate | return_rate calculation, quarter=current |
| T068 | 物料 M004 的退貨歷史 | ERP_7_default | simple_filter | material_code=M004 |
| T069 | 各月退貨趨勢 | ERP_7_default | time_series | group_by=month, count |
| T070 | 退貨金額最高的前 5 供應商 | ERP_7_default | aggregate | group_by=supplier, order_by=sum(amount) desc, limit=5 |

### ERP_8: 配貨揀貨單 (Pick List)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T071 | 今天的揀貨單 | ERP_8_default | simple_filter | date=today |
| T072 | 尚未完成的揀貨作業 | ERP_8_default | simple_filter | status=in_progress |
| T073 | 揀貨員 W001 今日任務 | ERP_8_default | simple_filter | picker_id=W001, date=today |
| T074 | 本週揀貨效率統計 | ERP_8_default | aggregate | week=current, avg(picking_time) |
| T075 | 配貨揀貨單 PL202604001 詳情 | ERP_8_detail | simple_filter | doc_no=PL202604001 |
| T076 | 緊急訂單的揀貨單 | ERP_8_default | simple_filter | priority=urgent |
| T077 | 各倉庫揀貨數量統計 | ERP_8_default | aggregate | group_by=warehouse, sum(quantity) |
| T078 | 本月揀貨錯誤率 | ERP_8_default | aggregate | error_rate calculation, month=current |
| T079 | 揀貨時間超過 2 小時的單據 | ERP_8_default | simple_filter | picking_time > 120 |
| T080 | 客戶訂單 O202604001 的揀貨進度 | ERP_8_default | simple_filter | order_no=O202604001 |

### ERP_9: 銷貨單 (Sales Invoice)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T081 | 本月銷貨單清單 | ERP_9_default | simple_filter | month=current |
| T082 | 今日銷售金額 | ERP_9_default | aggregate | sum(amount), date=today |
| T083 | 客戶 C001 的銷貨紀錄 | ERP_9_default | simple_filter | customer_code=C001 |
| T084 | 尚未收款的銷貨單 | ERP_9_default | simple_filter | payment_status=unpaid |
| T085 | 銷貨單 SI202604001 詳情 | ERP_9_detail | simple_filter | doc_no=SI202604001 |
| T086 | 各業務員本月業績 | ERP_9_default | aggregate | group_by=sales_person, sum(amount), month=current |
| T087 | 本年度銷售趨勢 | ERP_9_default | time_series | year=current, group_by=month, sum(amount) |
| T088 | 產品 P001 的銷售統計 | ERP_9_default | aggregate | product_code=P001, sum(quantity) |
| T089 | 逾期應收帳款清單 | ERP_9_default | simple_filter | due_date < today, payment_status=unpaid |
| T090 | 本月銷售金額排名前 10 客戶 | ERP_9_default | aggregate | group_by=customer, order_by=sum(amount) desc, limit=10, month=current |

### ERP_10: 銷貨退回單 (Sales Return)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T091 | 本月銷貨退回單 | ERP_10_default | simple_filter | month=current |
| T092 | 客戶 C002 的退貨紀錄 | ERP_10_default | simple_filter | customer_code=C002 |
| T093 | 退貨原因統計 | ERP_10_default | aggregate | group_by=return_reason, count |
| T094 | 銷貨退回單 SR202604001 詳情 | ERP_10_detail | simple_filter | doc_no=SR202604001 |
| T095 | 尚未處理的退貨單 | ERP_10_default | simple_filter | status=pending |
| T096 | 本季退貨金額統計 | ERP_10_default | aggregate | sum(amount), quarter=current |
| T097 | 產品 P002 的退貨率 | ERP_10_default | aggregate | product_code=P002, return_rate |
| T098 | 本年度各月退貨趨勢 | ERP_10_default | time_series | year=current, group_by=month, count |
| T099 | 退貨金額最高的前 5 客戶 | ERP_10_default | aggregate | group_by=customer, order_by=sum(amount) desc, limit=5 |
| T100 | 品質問題導致的退貨案件 | ERP_10_default | simple_filter | return_reason=quality_issue |

### ERP_11: 進貨檢驗紀錄(IQC) (Inbound Inspection)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T101 | 今天的 IQC 檢驗紀錄 | ERP_11_default | simple_filter | date=today |
| T102 | 本週不合格案件 | ERP_11_default | simple_filter | result=fail, week=current |
| T103 | 供應商 S005 的檢驗合格率 | ERP_11_default | aggregate | supplier_code=S005, pass_rate |
| T104 | IQC 紀錄 IQC202604001 詳情 | ERP_11_detail | simple_filter | doc_no=IQC202604001 |
| T105 | 尚未完成檢驗的收貨單 | ERP_11_default | simple_filter | inspection_status=pending |
| T106 | 本月檢驗合格率 | ERP_11_default | aggregate | pass_rate, month=current |
| T107 | 各檢驗員的檢驗數量 | ERP_11_default | aggregate | group_by=inspector, count |
| T108 | 物料 M005 的檢驗歷史 | ERP_11_default | simple_filter | material_code=M005 |
| T109 | 本季不合格原因分析 | ERP_11_default | aggregate | group_by=fail_reason, count, quarter=current |
| T110 | 檢驗時間超過 24 小時的案件 | ERP_11_default | simple_filter | inspection_duration > 24 |

### ERP_12: 進貨單 (Purchase Order Receipt)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T111 | 本月進貨單清單 | ERP_12_default | simple_filter | month=current |
| T112 | 今日進貨金額 | ERP_12_default | aggregate | sum(amount), date=today |
| T113 | 供應商 S006 的進貨明細 | ERP_12_default | simple_filter | supplier_code=S006 |
| T114 | 進貨單 POR202604001 詳情 | ERP_12_detail | simple_filter | doc_no=POR202604001 |
| T115 | 各採購員本月進貨統計 | ERP_12_default | aggregate | group_by=purchaser, sum(amount), month=current |
| T116 | 本年度進貨趨勢 | ERP_12_default | time_series | year=current, group_by=month, sum(amount) |
| T117 | 原料 M006 的進貨歷史 | ERP_12_default | simple_filter | material_code=M006 |
| T118 | 尚未付款的進貨單 | ERP_12_default | simple_filter | payment_status=unpaid |
| T119 | 本月進貨金額排名前 10 供應商 | ERP_12_default | aggregate | group_by=supplier, order_by=sum(amount) desc, limit=10, month=current |
| T120 | 比較本月與上月進貨金額 | ERP_12_default | time_series | compare month-over-month, sum(amount) |

### ERP_13: 採購單 (Purchase Order)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| T121 | 所有採購單列表 | ERP_13_default | simple_filter | table_key=ERP_13, 新格式驗證 |
| T122 | 本週新增採購單 | ERP_13_default | simple_filter | week=current |
| T123 | 供應商 S007 的採購訂單 | ERP_13_default | simple_filter | supplier_code=S007 |
| T124 | 尚未到貨的採購單 | ERP_13_default | simple_filter | receiving_status=pending |
| T125 | 採購單 PO202604001 詳情 | ERP_13_detail | simple_filter | doc_no=PO202604001, 新格式 |
| T126 | 本月採購金額統計 | ERP_13_default | aggregate | sum(amount), month=current |
| T127 | 各採購員的採購金額排名 | ERP_13_default | aggregate | group_by=purchaser, order_by=sum(amount) desc |
| T128 | 交期逾期的採購單 | ERP_13_default | simple_filter | delivery_date < today, status!=completed |
| T129 | 原料 M007 的採購歷史 | ERP_13_default | simple_filter | material_code=M007 |
| T130 | 本年度各月採購趨勢 | ERP_13_default | time_series | year=current, group_by=month, sum(amount) |

---

## SALES 領域測試情境 (90 scenarios)

### RAGICPURCHASING_1: 詢價單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| S001 | 顯示所有採購詢價單 | RAGICPURCHASING_1_default | simple_filter | table_key=RAGICPURCHASING_1 |
| S002 | 本週發出的詢價 | RAGICPURCHASING_1_default | simple_filter | week=current |
| S003 | 供應商 V001 的詢價紀錄 | RAGICPURCHASING_1_default | simple_filter | vendor_code=V001 |
| S004 | 等待報價的詢價單數量 | RAGICPURCHASING_1_default | aggregate | status=pending, count |
| S005 | 詢價單 RG_RFQ001 詳情 | RAGICPURCHASING_1_detail | simple_filter | doc_no=RG_RFQ001 |
| S006 | 本月詢價轉換率 | RAGICPURCHASING_1_default | aggregate | conversion_rate, month=current |
| S007 | 各採購人員詢價統計 | RAGICPURCHASING_1_default | aggregate | group_by=purchaser, count |
| S008 | 已逾期未回覆詢價 | RAGICPURCHASING_1_default | simple_filter | reply_deadline < today, status=waiting |
| S009 | 本季詢價金額統計 | RAGICPURCHASING_1_default | aggregate | sum(amount), quarter=current |
| S010 | 物料類別 C001 的詢價趨勢 | RAGICPURCHASING_1_default | time_series | category=C001, group_by=month |

### RAGICPURCHASING_3: 供應商評鑑

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| S011 | 所有供應商評鑑紀錄 | RAGICPURCHASING_3_default | simple_filter | table_key=RAGICPURCHASING_3 |
| S012 | 本年度供應商評鑑結果 | RAGICPURCHASING_3_default | simple_filter | year=current |
| S013 | 供應商 V002 的評鑑歷史 | RAGICPURCHASING_3_default | simple_filter | vendor_code=V002 |
| S014 | 評鑑不合格的供應商 | RAGICPURCHASING_3_default | simple_filter | result=fail |
| S015 | 評鑑紀錄 EVA001 詳情 | RAGICPURCHASING_3_detail | simple_filter | doc_no=EVA001 |
| S016 | 各供應商平均評分 | RAGICPURCHASING_3_default | aggregate | group_by=vendor, avg(score) |
| S017 | 本季評鑑完成率 | RAGICPURCHASING_3_default | aggregate | completion_rate, quarter=current |
| S018 | 尚未評鑑的供應商清單 | RAGICPURCHASING_3_default | simple_filter | evaluation_status=pending |
| S019 | 評分低於 70 分的供應商 | RAGICPURCHASING_3_default | simple_filter | score < 70 |
| S020 | 各評鑑項目平均分數 | RAGICPURCHASING_3_default | aggregate | group_by=evaluation_item, avg(score) |

### RAGICPURCHASING_5: 請購單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| S021 | 本月請購單清單 | RAGICPURCHASING_5_default | simple_filter | month=current |
| S022 | 尚未核准的請購單 | RAGICPURCHASING_5_default | simple_filter | approval_status=pending |
| S023 | 部門 D001 的請購紀錄 | RAGICPURCHASING_5_default | simple_filter | department_code=D001 |
| S024 | 請購單 PR001 詳情 | RAGICPURCHASING_5_detail | simple_filter | doc_no=PR001 |
| S025 | 緊急請購單 | RAGICPURCHASING_5_default | simple_filter | urgency=urgent |
| S026 | 各部門請購金額統計 | RAGICPURCHASING_5_default | aggregate | group_by=department, sum(amount) |
| S027 | 本週請購數量 | RAGICPURCHASING_5_default | aggregate | count, week=current |
| S028 | 請購金額超過 5 萬的案件 | RAGICPURCHASING_5_default | simple_filter | amount > 50000 |
| S029 | 本年度各月請購趨勢 | RAGICPURCHASING_5_default | time_series | year=current, group_by=month, count |
| S030 | 已核准但尚未採購的請購單 | RAGICPURCHASING_5_default | simple_filter | approval_status=approved, purchase_status=pending |

### RAGICSALES_1: 生產履歷查詢

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| S031 | 產品 P003 的生產履歷 | RAGICSALES_1_default | simple_filter | product_code=P003 |
| S032 | 批號 B202604001 的完整履歷 | RAGICSALES_1_detail | simple_filter | batch_no=B202604001 |
| S033 | 本月生產履歷紀錄 | RAGICSALES_1_default | simple_filter | month=current |
| S034 | 原料來源追溯查詢 | RAGICSALES_1_default | simple_filter | trace_type=raw_material |
| S035 | 客訴案件相關批號 | RAGICSALES_1_default | simple_filter | complaint_related=true |
| S036 | 各生產線履歷紀錄數 | RAGICSALES_1_default | aggregate | group_by=production_line, count |
| S037 | 本週新增履歷 | RAGICSALES_1_default | simple_filter | week=current |
| S038 | 供應商 S008 原料的使用紀錄 | RAGICSALES_1_default | simple_filter | supplier_code=S008 |
| S039 | 本季履歷建檔完整率 | RAGICSALES_1_default | aggregate | completeness_rate, quarter=current |
| S040 | 特定日期生產的產品批號 | RAGICSALES_1_default | simple_filter | production_date=2026-04-10 |

### RAGICSALES_2: 活動展覽

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| S041 | 本年度活動展覽清單 | RAGICSALES_2_default | simple_filter | year=current |
| S042 | 即將舉辦的展覽 | RAGICSALES_2_default | simple_filter | event_date >= today, status=upcoming |
| S043 | 活動 E001 詳細資料 | RAGICSALES_2_detail | simple_filter | event_code=E001 |
| S044 | 本季參展費用統計 | RAGICSALES_2_default | aggregate | sum(cost), quarter=current |
| S045 | 各業務區域活動數量 | RAGICSALES_2_default | aggregate | group_by=region, count |
| S046 | 展覽效益分析 | RAGICSALES_2_default | aggregate | sum(leads), sum(sales) |
| S047 | 尚未結案的活動 | RAGICSALES_2_default | simple_filter | status=in_progress |
| S048 | 本月活動行程 | RAGICSALES_2_default | simple_filter | month=current |
| S049 | 活動預算執行率 | RAGICSALES_2_default | aggregate | budget_execution_rate |
| S050 | 歷年展覽投資報酬率 | RAGICSALES_2_default | time_series | group_by=year, roi |

### RAGICSALES_5: 客訴案件登記表

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| S051 | 本月客訴案件 | RAGICSALES_5_default | simple_filter | month=current |
| S052 | 尚未處理的客訴 | RAGICSALES_5_default | simple_filter | status=open |
| S053 | 客戶 C003 的客訴紀錄 | RAGICSALES_5_default | simple_filter | customer_code=C003 |
| S054 | 客訴案件 COMP001 詳情 | RAGICSALES_5_detail | simple_filter | case_no=COMP001 |
| S055 | 客訴原因分類統計 | RAGICSALES_5_default | aggregate | group_by=complaint_type, count |
| S056 | 本季客訴結案率 | RAGICSALES_5_default | aggregate | closure_rate, quarter=current |
| S057 | 嚴重等級客訴案件 | RAGICSALES_5_default | simple_filter | severity=high |
| S058 | 各產品客訴數量 | RAGICSALES_5_default | aggregate | group_by=product, count |
| S059 | 客訴處理時間超過 7 天的案件 | RAGICSALES_5_default | simple_filter | handling_days > 7 |
| S060 | 本年度各月客訴趨勢 | RAGICSALES_5_default | time_series | year=current, group_by=month, count |

### RAGICSALES_13: 銷售機會

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| S061 | 所有銷售機會清單 | RAGICSALES_13_default | simple_filter | table_key=RAGICSALES_13 |
| S062 | 本月新增銷售機會 | RAGICSALES_13_default | simple_filter | month=current |
| S063 | 業務員 SR001 的銷售機會 | RAGICSALES_13_default | simple_filter | sales_rep=SR001 |
| S064 | 成交機率 > 70% 的機會 | RAGICSALES_13_default | simple_filter | probability > 0.7 |
| S065 | 銷售機會 OPP001 詳情 | RAGICSALES_13_detail | simple_filter | opportunity_id=OPP001 |
| S066 | 各階段銷售機會數量 | RAGICSALES_13_default | aggregate | group_by=stage, count |
| S067 | 本季預計成交金額 | RAGICSALES_13_default | aggregate | sum(expected_revenue), quarter=current |
| S068 | 已贏得的銷售機會 | RAGICSALES_13_default | simple_filter | status=won |
| S069 | 產業別機會分析 | RAGICSALES_13_default | aggregate | group_by=industry, count, sum(amount) |
| S070 | 銷售漏斗轉換率 | RAGICSALES_13_default | aggregate | funnel_conversion_rate |

### FORMS4_1: CRM-聯絡人管理

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| S071 | 所有聯絡人清單 | FORMS4_1_default | simple_filter | table_key=FORMS4_1 |
| S072 | 公司 C004 的聯絡人 | FORMS4_1_default | simple_filter | company_code=C004 |
| S073 | 職稱為總經理的聯絡人 | FORMS4_1_default | simple_filter | title=總經理 |
| S074 | 聯絡人 CONT001 詳情 | FORMS4_1_detail | simple_filter | contact_id=CONT001 |
| S075 | 本月新增聯絡人 | FORMS4_1_default | simple_filter | month=current |
| S076 | 各產業聯絡人數量 | FORMS4_1_default | aggregate | group_by=industry, count |
| S077 | 負責業務員 SR002 的聯絡人 | FORMS4_1_default | simple_filter | sales_rep=SR002 |
| S078 | 電子郵件訂閱者 | FORMS4_1_default | simple_filter | email_subscription=true |
| S079 | 本年度聯絡人成長趨勢 | FORMS4_1_default | time_series | year=current, group_by=month, count |
| S080 | VIP 等級聯絡人 | FORMS4_1_default | simple_filter | vip_level=high |

### FORMS4_2: 潛在交易對象

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| S081 | 所有潛在客戶 | FORMS4_2_default | simple_filter | table_key=FORMS4_2 |
| S082 | 本週新增潛在客戶 | FORMS4_2_default | simple_filter | week=current |
| S083 | 高潛力潛在客戶 | FORMS4_2_default | simple_filter | potential=high |
| S084 | 潛在客戶 LEAD001 詳情 | FORMS4_2_detail | simple_filter | lead_id=LEAD001 |
| S085 | 尚未聯繫的潛在客戶 | FORMS4_2_default | simple_filter | contact_status=not_contacted |
| S086 | 各來源潛在客戶統計 | FORMS4_2_default | aggregate | group_by=source, count |
| S087 | 本月潛客轉換率 | FORMS4_2_default | aggregate | conversion_rate, month=current |
| S088 | 業務員 SR003 負責的潛客 | FORMS4_2_default | simple_filter | sales_rep=SR003 |
| S089 | 預算超過 10 萬的潛在客戶 | FORMS4_2_default | simple_filter | budget > 100000 |
| S090 | 本季潛客開發趨勢 | FORMS4_2_default | time_series | quarter=current, group_by=week, count |

---

## MANUFACTURING 領域測試情境 (110 scenarios)

### MES_1: 原料化學性快篩檢驗紀錄表

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| M001 | 今天的快篩檢驗紀錄 | MES_1_default | simple_filter | date=today |
| M002 | 本週不合格快篩案件 | MES_1_default | simple_filter | result=fail, week=current |
| M003 | 原料 RM001 的快篩歷史 | MES_1_default | simple_filter | material_code=RM001 |
| M004 | 快篩紀錄 QS001 詳情 | MES_1_detail | simple_filter | record_id=QS001 |
| M005 | 本月快篩合格率 | MES_1_default | aggregate | pass_rate, month=current |
| M006 | 各檢驗員快篩數量 | MES_1_default | aggregate | group_by=inspector, count |
| M007 | 化學性異常案件 | MES_1_default | simple_filter | chemical_abnormal=true |
| M008 | 供應商 S009 原料快篩結果 | MES_1_default | simple_filter | supplier_code=S009 |
| M009 | 本季快篩不合格原因分析 | MES_1_default | aggregate | group_by=fail_reason, count, quarter=current |
| M010 | 快篩時間趨勢 | MES_1_default | time_series | group_by=date, avg(test_duration) |

### MES_2~9: 原材料驗收紀錄表系列

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| M011 | 本月所有原材料驗收紀錄 | MES_2_default | simple_filter | month=current, 需跨表查詢 MES_2~9 |
| M012 | 肉類原料驗收紀錄 | MES_2_default | simple_filter | table_key=MES_2 (假設) |
| M013 | 蔬菜類驗收紀錄 | MES_3_default | simple_filter | table_key=MES_3 (假設) |
| M014 | 今日驗收不合格案件 | MES_2_default | simple_filter | result=fail, date=today, 跨表 |
| M015 | 原料 RM002 驗收歷史 | MES_2_default | simple_filter | material_code=RM002, 跨表 |
| M016 | 驗收紀錄 ACC001 詳情 | MES_2_detail | simple_filter | record_id=ACC001 |
| M017 | 本週驗收合格率 | MES_2_default | aggregate | pass_rate, week=current, 跨表 |
| M018 | 各供應商驗收統計 | MES_2_default | aggregate | group_by=supplier, count, 跨表 |
| M019 | 溫度異常的驗收紀錄 | MES_2_default | simple_filter | temperature_abnormal=true |
| M020 | 本月各類原料驗收數量 | MES_2_default | aggregate | group_by=material_category, count, 跨表 |

### MES_13: 成品留樣保存紀錄表

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| M021 | 本月成品留樣紀錄 | MES_13_default | simple_filter | month=current |
| M022 | 產品 FG001 的留樣紀錄 | MES_13_default | simple_filter | product_code=FG001 |
| M023 | 批號 B202604002 留樣資訊 | MES_13_detail | simple_filter | batch_no=B202604002 |
| M024 | 即將到期的留樣 | MES_13_default | simple_filter | expiry_date < (today + 7days) |
| M025 | 本季留樣數量統計 | MES_13_default | aggregate | sum(quantity), quarter=current |
| M026 | 各生產線留樣紀錄 | MES_13_default | aggregate | group_by=production_line, count |
| M027 | 尚未銷毀的過期留樣 | MES_13_default | simple_filter | expiry_date < today, disposal_status=pending |
| M028 | 留樣保存溫度異常 | MES_13_default | simple_filter | storage_temp_abnormal=true |
| M029 | 本年度留樣趨勢 | MES_13_default | time_series | year=current, group_by=month, count |
| M030 | 特定日期生產的留樣 | MES_13_default | simple_filter | production_date=2026-04-05 |

### MES_14: 報廢退貨及銷毀紀錄表

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| M031 | 本月報廢紀錄 | MES_14_default | simple_filter | month=current |
| M032 | 客戶退貨銷毀案件 | MES_14_default | simple_filter | type=customer_return |
| M033 | 產品 FG002 報廢歷史 | MES_14_default | simple_filter | product_code=FG002 |
| M034 | 報廢紀錄 DSP001 詳情 | MES_14_detail | simple_filter | record_id=DSP001 |
| M035 | 本季報廢金額統計 | MES_14_default | aggregate | sum(disposal_amount), quarter=current |
| M036 | 報廢原因分類 | MES_14_default | aggregate | group_by=disposal_reason, count |
| M037 | 尚未完成銷毀的案件 | MES_14_default | simple_filter | disposal_status=pending |
| M038 | 品質異常導致的報廢 | MES_14_default | simple_filter | reason=quality_issue |
| M039 | 各月報廢趨勢 | MES_14_default | time_series | group_by=month, sum(quantity) |
| M040 | 報廢金額最高的前 5 產品 | MES_14_default | aggregate | group_by=product, order_by=sum(amount) desc, limit=5 |

### MES2_1: 生產需求單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| M041 | 本週生產需求單 | MES2_1_default | simple_filter | week=current |
| M042 | 尚未排程的需求單 | MES2_1_default | simple_filter | schedule_status=pending |
| M043 | 產品 FG003 的生產需求 | MES2_1_default | simple_filter | product_code=FG003 |
| M044 | 需求單 PRD001 詳情 | MES2_1_detail | simple_filter | demand_id=PRD001 |
| M045 | 緊急生產需求 | MES2_1_default | simple_filter | priority=urgent |
| M046 | 本月需求數量統計 | MES2_1_default | aggregate | sum(quantity), month=current |
| M047 | 各產品線需求分析 | MES2_1_default | aggregate | group_by=product_line, sum(quantity) |
| M048 | 客戶訂單 O202604002 相關需求 | MES2_1_default | simple_filter | order_no=O202604002 |
| M049 | 本季需求趨勢 | MES2_1_default | time_series | quarter=current, group_by=week, sum(quantity) |
| M050 | 需求達交率分析 | MES2_1_default | aggregate | fulfillment_rate |

### MES2_2: 物料需求單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| M051 | 本週物料需求單 | MES2_2_default | simple_filter | week=current |
| M052 | 尚未備料的需求單 | MES2_2_default | simple_filter | preparation_status=pending |
| M053 | 原料 RM003 的需求清單 | MES2_2_default | simple_filter | material_code=RM003 |
| M054 | 物料需求單 MRQ001 詳情 | MES2_2_detail | simple_filter | requisition_id=MRQ001 |
| M055 | 緊急物料需求 | MES2_2_default | simple_filter | urgency=urgent |
| M056 | 本月各物料需求數量 | MES2_2_default | aggregate | group_by=material, sum(quantity), month=current |
| M057 | 庫存不足的物料需求 | MES2_2_default | simple_filter | stock_shortage=true |
| M058 | 生產製令 WO001 的物料需求 | MES2_2_default | simple_filter | work_order=WO001 |
| M059 | 本季物料需求趨勢 | MES2_2_default | time_series | quarter=current, group_by=week, count |
| M060 | 物料備料完成率 | MES2_2_default | aggregate | preparation_completion_rate |

### MES2_3: 托工單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| M061 | 本月托工單清單 | MES2_3_default | simple_filter | month=current |
| M062 | 外包商 OUT001 的托工單 | MES2_3_default | simple_filter | outsourcer_code=OUT001 |
| M063 | 尚未完工的托工單 | MES2_3_default | simple_filter | completion_status=in_progress |
| M064 | 托工單 SUB001 詳情 | MES2_3_detail | simple_filter | subcontract_id=SUB001 |
| M065 | 逾期未交的托工單 | MES2_3_default | simple_filter | due_date < today, status!=completed |
| M066 | 本季托工金額統計 | MES2_3_default | aggregate | sum(amount), quarter=current |
| M067 | 各外包商托工數量 | MES2_3_default | aggregate | group_by=outsourcer, count |
| M068 | 托工品質異常案件 | MES2_3_default | simple_filter | quality_issue=true |
| M069 | 本年度托工趨勢 | MES2_3_default | time_series | year=current, group_by=month, count |
| M070 | 產品 FG004 的托工紀錄 | MES2_3_default | simple_filter | product_code=FG004 |

### MES2_4: 領料單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| M071 | 今天的領料單 | MES2_4_default | simple_filter | date=today |
| M072 | 生產線 L001 的領料紀錄 | MES2_4_default | simple_filter | production_line=L001 |
| M073 | 原料 RM004 的領用歷史 | MES2_4_default | simple_filter | material_code=RM004 |
| M074 | 領料單 ISS001 詳情 | MES2_4_detail | simple_filter | issue_id=ISS001 |
| M075 | 尚未發料的領料單 | MES2_4_default | simple_filter | issue_status=pending |
| M076 | 本週領料數量統計 | MES2_4_default | aggregate | sum(quantity), week=current |
| M077 | 各生產線領料金額 | MES2_4_default | aggregate | group_by=production_line, sum(amount) |
| M078 | 生產製令 WO002 的領料明細 | MES2_4_default | simple_filter | work_order=WO002 |
| M079 | 本月領料趨勢 | MES2_4_default | time_series | month=current, group_by=date, sum(quantity) |
| M080 | 超領用的領料單 | MES2_4_default | simple_filter | over_issue=true |

### MES2_5: 派工單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| M081 | 今天的派工單 | MES2_5_default | simple_filter | date=today |
| M082 | 尚未開工的派工單 | MES2_5_default | simple_filter | status=not_started |
| M083 | 生產線 L002 的派工紀錄 | MES2_5_default | simple_filter | production_line=L002 |
| M084 | 派工單 DS001 詳情 | MES2_5_detail | simple_filter | dispatch_id=DS001 |
| M085 | 本週派工數量 | MES2_5_default | aggregate | count, week=current |
| M086 | 各班別派工統計 | MES2_5_default | aggregate | group_by=shift, count |
| M087 | 逾期未完成的派工單 | MES2_5_default | simple_filter | due_date < today, status!=completed |
| M088 | 產品 FG005 的派工紀錄 | MES2_5_default | simple_filter | product_code=FG005 |
| M089 | 本月派工效率分析 | MES2_5_default | aggregate | avg(efficiency), month=current |
| M090 | 派工達成率趨勢 | MES2_5_default | time_series | group_by=week, achievement_rate |

### MES2_6: 生產製令單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| M091 | 所有生產製令單 | MES2_6_default | simple_filter | table_key=MES2_6 |
| M092 | 本週新增製令 | MES2_6_default | simple_filter | week=current |
| M093 | 進行中的製令單 | MES2_6_default | simple_filter | status=in_progress |
| M094 | 製令單 WO003 詳情 | MES2_6_detail | simple_filter | work_order=WO003 |
| M095 | 產品 FG006 的製令紀錄 | MES2_6_default | simple_filter | product_code=FG006 |
| M096 | 本月生產數量統計 | MES2_6_default | aggregate | sum(quantity), month=current |
| M097 | 各生產線製令數量 | MES2_6_default | aggregate | group_by=production_line, count |
| M098 | 逾期未完成製令 | MES2_6_default | simple_filter | due_date < today, status!=completed |
| M099 | 本季生產達成率 | MES2_6_default | aggregate | achievement_rate, quarter=current |
| M100 | 製令完成時間趨勢 | MES2_6_default | time_series | group_by=month, avg(completion_time) |

### WORKREPORTINGAREA_1~13: 工序報工單系列

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| M101 | 今天工序1的報工紀錄 | WORKREPORTINGAREA_1_default | simple_filter | date=today, table_key=WORKREPORTINGAREA_1 |
| M102 | 本週工序2報工統計 | WORKREPORTINGAREA_2_default | aggregate | count, week=current |
| M103 | 工序3異常報工案件 | WORKREPORTINGAREA_3_default | simple_filter | abnormal=true |
| M104 | 報工單 WR001 詳情 | WORKREPORTINGAREA_1_detail | simple_filter | report_id=WR001 |
| M105 | 各工序今日完工數量 | WORKREPORTINGAREA_1_default | aggregate | group_by=process, sum(quantity), date=today, 跨表 |
| M106 | 工序5效率分析 | WORKREPORTINGAREA_5_default | aggregate | avg(efficiency) |
| M107 | 本月各工序良率 | WORKREPORTINGAREA_1_default | aggregate | group_by=process, yield_rate, month=current, 跨表 |
| M108 | 員工 EMP001 的報工紀錄 | WORKREPORTINGAREA_1_default | simple_filter | employee_id=EMP001, 跨表 |
| M109 | WIP 追蹤面板數據 | WORKREPORTINGAREA_13_default | simple_filter | table_key=WORKREPORTINGAREA_13 (假設為 WIP 面板) |
| M110 | 本週各工序產能利用率 | WORKREPORTINGAREA_1_default | aggregate | group_by=process, capacity_utilization, week=current, 跨表 |

---

## QUALITY 領域測試情境 (100 scenarios)

### G4102_1: 水塔清洗維修紀錄表

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| Q001 | 本年度水塔清洗紀錄 | G4102_1_default | simple_filter | year=current |
| Q002 | 上次清洗日期 | G4102_1_default | simple_filter | order_by=cleaning_date desc, limit=1 |
| Q003 | 水塔 WT001 維修歷史 | G4102_1_default | simple_filter | water_tank_id=WT001 |
| Q004 | 清洗紀錄 WTC001 詳情 | G4102_1_detail | simple_filter | record_id=WTC001 |
| Q005 | 本季清洗次數 | G4102_1_default | aggregate | count, quarter=current |
| Q006 | 各水塔清洗頻率 | G4102_1_default | aggregate | group_by=water_tank, count |
| Q007 | 尚未清洗的水塔 | G4102_1_default | simple_filter | last_cleaning < (today - 90days) |
| Q008 | 清洗異常紀錄 | G4102_1_default | simple_filter | abnormal=true |
| Q009 | 本年度清洗趨勢 | G4102_1_default | time_series | year=current, group_by=month, count |
| Q010 | 維修費用統計 | G4102_1_default | aggregate | sum(maintenance_cost) |

### G4102_11: 衛生自主管理檢查表

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| Q011 | 今天的衛生檢查紀錄 | G4102_11_default | simple_filter | date=today |
| Q012 | 本週不合格項目 | G4102_11_default | simple_filter | result=fail, week=current |
| Q013 | 區域 A1 的檢查歷史 | G4102_11_default | simple_filter | area_code=A1 |
| Q014 | 檢查紀錄 HYG001 詳情 | G4102_11_detail | simple_filter | record_id=HYG001 |
| Q015 | 本月檢查合格率 | G4102_11_default | aggregate | pass_rate, month=current |
| Q016 | 各區域檢查次數 | G4102_11_default | aggregate | group_by=area, count |
| Q017 | 檢查員 INS001 的檢查紀錄 | G4102_11_default | simple_filter | inspector_id=INS001 |
| Q018 | 重大缺失案件 | G4102_11_default | simple_filter | severity=major |
| Q019 | 本季衛生改善趨勢 | G4102_11_default | time_series | quarter=current, group_by=week, pass_rate |
| Q020 | 缺失類型統計 | G4102_11_default | aggregate | group_by=defect_type, count |

### G4102_12: 成品回收暨銷毀紀錄表

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| Q021 | 本月成品回收紀錄 | G4102_12_default | simple_filter | month=current |
| Q022 | 產品 FG007 回收歷史 | G4102_12_default | simple_filter | product_code=FG007 |
| Q023 | 尚未銷毀的回收品 | G4102_12_default | simple_filter | disposal_status=pending |
| Q024 | 回收紀錄 RCL001 詳情 | G4102_12_detail | simple_filter | record_id=RCL001 |
| Q025 | 本季回收金額統計 | G4102_12_default | aggregate | sum(recall_amount), quarter=current |
| Q026 | 回收原因分類 | G4102_12_default | aggregate | group_by=recall_reason, count |
| Q027 | 批號 B202604003 回收資訊 | G4102_12_default | simple_filter | batch_no=B202604003 |
| Q028 | 本年度回收趨勢 | G4102_12_default | time_series | year=current, group_by=month, count |
| Q029 | 客訴導致的回收案件 | G4102_12_default | simple_filter | recall_reason=customer_complaint |
| Q030 | 回收數量最多的前 5 產品 | G4102_12_default | aggregate | group_by=product, order_by=sum(quantity) desc, limit=5 |

### G4102_21: 客訴案件處理紀錄表

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| Q031 | 本月客訴案件 | G4102_21_default | simple_filter | month=current |
| Q032 | 尚未結案的客訴 | G4102_21_default | simple_filter | status=open |
| Q033 | 客戶 C005 的客訴紀錄 | G4102_21_default | simple_filter | customer_code=C005 |
| Q034 | 客訴案件 CC001 詳情 | G4102_21_detail | simple_filter | case_no=CC001 |
| Q035 | 嚴重客訴案件 | G4102_21_default | simple_filter | severity=critical |
| Q036 | 客訴原因統計 | G4102_21_default | aggregate | group_by=complaint_reason, count |
| Q037 | 本季客訴結案率 | G4102_21_default | aggregate | closure_rate, quarter=current |
| Q038 | 產品 FG008 客訴分析 | G4102_21_default | simple_filter | product_code=FG008 |
| Q039 | 客訴處理時間超過 7 天 | G4102_21_default | simple_filter | handling_days > 7 |
| Q040 | 本年度客訴趨勢 | G4102_21_default | time_series | year=current, group_by=month, count |

### ISO2_1: 研發紀錄表

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| Q041 | 所有研發專案 | ISO2_1_default | simple_filter | table_key=ISO2_1 |
| Q042 | 進行中的研發案 | ISO2_1_default | simple_filter | status=in_progress |
| Q043 | 研發人員 RD001 的專案 | ISO2_1_default | simple_filter | researcher_id=RD001 |
| Q044 | 研發紀錄 R&D001 詳情 | ISO2_1_detail | simple_filter | project_id=R&D001 |
| Q045 | 本年度完成的研發案 | ISO2_1_default | simple_filter | completion_year=current, status=completed |
| Q046 | 各研發類別統計 | ISO2_1_default | aggregate | group_by=research_type, count |
| Q047 | 研發預算執行率 | ISO2_1_default | aggregate | budget_execution_rate |
| Q048 | 逾期未完成的研發案 | ISO2_1_default | simple_filter | due_date < today, status!=completed |
| Q049 | 本年度研發投入趨勢 | ISO2_1_default | time_series | year=current, group_by=quarter, sum(budget) |
| Q050 | 已商品化的研發成果 | ISO2_1_default | simple_filter | commercialization_status=completed |

### ISO2_2: 異常處理單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| Q051 | 本週異常處理單 | ISO2_2_default | simple_filter | week=current |
| Q052 | 尚未結案的異常 | ISO2_2_default | simple_filter | status=open |
| Q053 | 生產線 L003 的異常紀錄 | ISO2_2_default | simple_filter | production_line=L003 |
| Q054 | 異常單 ABN001 詳情 | ISO2_2_detail | simple_filter | abnormal_id=ABN001 |
| Q055 | 嚴重異常案件 | ISO2_2_default | simple_filter | severity=major |
| Q056 | 異常類型統計 | ISO2_2_default | aggregate | group_by=abnormal_type, count |
| Q057 | 本月異常結案率 | ISO2_2_default | aggregate | closure_rate, month=current |
| Q058 | 責任部門 DEPT001 的異常 | ISO2_2_default | simple_filter | responsible_dept=DEPT001 |
| Q059 | 本季異常趨勢 | ISO2_2_default | time_series | quarter=current, group_by=week, count |
| Q060 | 重複發生的異常 | ISO2_2_default | simple_filter | recurrence=true |

### ISO2_10: 客訴處理單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| Q061 | 本月客訴處理單 | ISO2_10_default | simple_filter | month=current |
| Q062 | 尚未回覆的客訴 | ISO2_10_default | simple_filter | reply_status=pending |
| Q063 | 客戶 C006 的客訴處理 | ISO2_10_default | simple_filter | customer_code=C006 |
| Q064 | 客訴處理單 CP001 詳情 | ISO2_10_detail | simple_filter | complaint_id=CP001 |
| Q065 | 緊急客訴案件 | ISO2_10_default | simple_filter | urgency=urgent |
| Q066 | 客訴類型統計 | ISO2_10_default | aggregate | group_by=complaint_type, count |
| Q067 | 本季客訴滿意度 | ISO2_10_default | aggregate | avg(satisfaction_score), quarter=current |
| Q068 | 產品 FG009 相關客訴 | ISO2_10_default | simple_filter | product_code=FG009 |
| Q069 | 客訴回覆時間超過 48 小時 | ISO2_10_default | simple_filter | reply_hours > 48 |
| Q070 | 本年度客訴改善趨勢 | ISO2_10_default | time_series | year=current, group_by=month, count |

### ISO2_11: 供應商評鑑紀錄

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| Q071 | 本年度供應商評鑑 | ISO2_11_default | simple_filter | year=current |
| Q072 | 供應商 S010 評鑑歷史 | ISO2_11_default | simple_filter | supplier_code=S010 |
| Q073 | 評鑑不合格供應商 | ISO2_11_default | simple_filter | result=fail |
| Q074 | 評鑑紀錄 SEV001 詳情 | ISO2_11_detail | simple_filter | evaluation_id=SEV001 |
| Q075 | 各供應商平均分數 | ISO2_11_default | aggregate | group_by=supplier, avg(score) |
| Q076 | 本季評鑑完成率 | ISO2_11_default | aggregate | completion_rate, quarter=current |
| Q077 | 評分低於 60 分的供應商 | ISO2_11_default | simple_filter | score < 60 |
| Q078 | 品質項目平均分數 | ISO2_11_default | aggregate | group_by=quality_item, avg(score) |
| Q079 | 本年度評鑑趨勢 | ISO2_11_default | time_series | year=current, group_by=quarter, avg(score) |
| Q080 | 優良供應商清單 | ISO2_11_default | simple_filter | rating=excellent |

### NOTFOLLOWUPFORM_10: 收貨資料批號清單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| Q081 | 本週收貨批號清單 | NOTFOLLOWUPFORM_10_default | simple_filter | week=current |
| Q082 | 原料 RM005 的批號紀錄 | NOTFOLLOWUPFORM_10_default | simple_filter | material_code=RM005 |
| Q083 | 批號 LOT202604001 詳情 | NOTFOLLOWUPFORM_10_detail | simple_filter | lot_no=LOT202604001 |
| Q084 | 供應商 S011 的批號追蹤 | NOTFOLLOWUPFORM_10_default | simple_filter | supplier_code=S011 |
| Q085 | 本月收貨批號數量 | NOTFOLLOWUPFORM_10_default | aggregate | count, month=current |
| Q086 | 各原料批號統計 | NOTFOLLOWUPFORM_10_default | aggregate | group_by=material, count |
| Q087 | 批號效期即將到期 | NOTFOLLOWUPFORM_10_default | simple_filter | expiry_date < (today + 30days) |
| Q088 | 特定日期收貨批號 | NOTFOLLOWUPFORM_10_default | simple_filter | receiving_date=2026-04-08 |
| Q089 | 本季批號追溯性檢查 | NOTFOLLOWUPFORM_10_default | aggregate | traceability_check, quarter=current |
| Q090 | 批號異常紀錄 | NOTFOLLOWUPFORM_10_default | simple_filter | abnormal=true |

### NOTFOLLOWUPFORM_13: 交貨資料批號合一清單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| Q091 | 本週交貨批號清單 | NOTFOLLOWUPFORM_13_default | simple_filter | week=current |
| Q092 | 產品 FG010 的交貨批號 | NOTFOLLOWUPFORM_13_default | simple_filter | product_code=FG010 |
| Q093 | 批號 SHIP_LOT001 詳情 | NOTFOLLOWUPFORM_13_detail | simple_filter | shipment_lot=SHIP_LOT001 |
| Q094 | 客戶 C007 的交貨批號追蹤 | NOTFOLLOWUPFORM_13_default | simple_filter | customer_code=C007 |
| Q095 | 本月交貨批號數量 | NOTFOLLOWUPFORM_13_default | aggregate | count, month=current |
| Q096 | 各產品交貨批號統計 | NOTFOLLOWUPFORM_13_default | aggregate | group_by=product, count |
| Q097 | 批號合一性檢查異常 | NOTFOLLOWUPFORM_13_default | simple_filter | consistency_check=fail |
| Q098 | 特定訂單的交貨批號 | NOTFOLLOWUPFORM_13_default | simple_filter | order_no=O202604003 |
| Q099 | 本季交貨批號趨勢 | NOTFOLLOWUPFORM_13_default | time_series | quarter=current, group_by=week, count |
| Q100 | 批號追溯完整性驗證 | NOTFOLLOWUPFORM_13_default | aggregate | traceability_completeness |

---

## BASE 領域測試情境 (50 scenarios)

### CONFIGURATIONFILE_5: 員工管理

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| B001 | 所有在職員工清單 | CONFIGURATIONFILE_5_default | simple_filter | status=active |
| B002 | 部門 DEPT002 的員工 | CONFIGURATIONFILE_5_default | simple_filter | department_code=DEPT002 |
| B003 | 職稱為工程師的員工 | CONFIGURATIONFILE_5_default | simple_filter | title=工程師 |
| B004 | 員工 EMP002 詳細資料 | CONFIGURATIONFILE_5_detail | simple_filter | employee_id=EMP002 |
| B005 | 本月新進員工 | CONFIGURATIONFILE_5_default | simple_filter | hire_date >= (month_start), hire_date <= (month_end) |
| B006 | 各部門員工人數 | CONFIGURATIONFILE_5_default | aggregate | group_by=department, count |
| B007 | 試用期員工 | CONFIGURATIONFILE_5_default | simple_filter | employment_status=probation |
| B008 | 本年度離職員工 | CONFIGURATIONFILE_5_default | simple_filter | termination_year=current |
| B009 | 各職稱薪資統計 | CONFIGURATIONFILE_5_default | aggregate | group_by=title, avg(salary) |
| B010 | 年資超過 5 年的員工 | CONFIGURATIONFILE_5_default | simple_filter | tenure > 5 |

### CONFIGURATIONFILE_6: 品項管理

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| B011 | 所有品項清單 | CONFIGURATIONFILE_6_default | simple_filter | table_key=CONFIGURATIONFILE_6 |
| B012 | 產品類別 CAT001 的品項 | CONFIGURATIONFILE_6_default | simple_filter | category_code=CAT001 |
| B013 | 啟用中的品項 | CONFIGURATIONFILE_6_default | simple_filter | status=active |
| B014 | 品項 ITEM001 詳情 | CONFIGURATIONFILE_6_detail | simple_filter | item_code=ITEM001 |
| B015 | 本月新增品項 | CONFIGURATIONFILE_6_default | simple_filter | month=current |
| B016 | 各品項類別數量 | CONFIGURATIONFILE_6_default | aggregate | group_by=category, count |
| B017 | 庫存低於安全庫存的品項 | CONFIGURATIONFILE_6_default | simple_filter | stock < safety_stock |
| B018 | 停用品項清單 | CONFIGURATIONFILE_6_default | simple_filter | status=inactive |
| B019 | 各供應商供應品項數 | CONFIGURATIONFILE_6_default | aggregate | group_by=supplier, count |
| B020 | 單價最高的前 10 品項 | CONFIGURATIONFILE_6_default | aggregate | order_by=unit_price desc, limit=10 |

### CONFIGURATIONFILE_7: 交易對象(客戶/供應商)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| B021 | 所有客戶清單 | CONFIGURATIONFILE_7_default | simple_filter | partner_type=customer |
| B022 | 所有供應商清單 | CONFIGURATIONFILE_7_default | simple_filter | partner_type=supplier |
| B023 | 客戶 C008 詳細資料 | CONFIGURATIONFILE_7_detail | simple_filter | partner_code=C008 |
| B024 | 台北地區的客戶 | CONFIGURATIONFILE_7_default | simple_filter | city=台北, partner_type=customer |
| B025 | 信用等級 A 的客戶 | CONFIGURATIONFILE_7_default | simple_filter | credit_rating=A |
| B026 | 各地區客戶數量 | CONFIGURATIONFILE_7_default | aggregate | group_by=region, count, partner_type=customer |
| B027 | 本月新增交易對象 | CONFIGURATIONFILE_7_default | simple_filter | month=current |
| B028 | 停止交易的對象 | CONFIGURATIONFILE_7_default | simple_filter | status=inactive |
| B029 | 各產業客戶分佈 | CONFIGURATIONFILE_7_default | aggregate | group_by=industry, count, partner_type=customer |
| B030 | VIP 客戶清單 | CONFIGURATIONFILE_7_default | simple_filter | vip_status=true |

### CONFIGURATIONFILE_13: 供應商清冊

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| B031 | 合格供應商清冊 | CONFIGURATIONFILE_13_default | simple_filter | qualification_status=qualified |
| B032 | 供應商 S012 資訊 | CONFIGURATIONFILE_13_detail | simple_filter | supplier_code=S012 |
| B033 | 原料類供應商 | CONFIGURATIONFILE_13_default | simple_filter | supply_category=raw_material |
| B034 | 本年度新增供應商 | CONFIGURATIONFILE_13_default | simple_filter | registration_year=current |
| B035 | 各供應類別供應商數 | CONFIGURATIONFILE_13_default | aggregate | group_by=supply_category, count |
| B036 | ISO 認證供應商 | CONFIGURATIONFILE_13_default | simple_filter | iso_certified=true |
| B037 | 評鑑優良供應商 | CONFIGURATIONFILE_13_default | simple_filter | evaluation_rating=excellent |
| B038 | 黑名單供應商 | CONFIGURATIONFILE_13_default | simple_filter | blacklist_status=true |
| B039 | 各地區供應商分佈 | CONFIGURATIONFILE_13_default | aggregate | group_by=region, count |
| B040 | 合約即將到期的供應商 | CONFIGURATIONFILE_13_default | simple_filter | contract_expiry < (today + 30days) |

### CONFIGFILEDETAILS_3: 員工清單

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| B041 | 完整員工清單 | CONFIGFILEDETAILS_3_default | simple_filter | table_key=CONFIGFILEDETAILS_3 |
| B042 | 生產部門員工 | CONFIGFILEDETAILS_3_default | simple_filter | department=生產 |
| B043 | 員工 EMP003 基本資料 | CONFIGFILEDETAILS_3_detail | simple_filter | employee_id=EMP003 |
| B044 | 本月生日的員工 | CONFIGFILEDETAILS_3_default | simple_filter | birthday_month=current |
| B045 | 各部門性別分佈 | CONFIGFILEDETAILS_3_default | aggregate | group_by=department, gender, count |
| B046 | 主管級員工 | CONFIGFILEDETAILS_3_default | simple_filter | is_manager=true |
| B047 | 員工年齡分佈 | CONFIGFILEDETAILS_3_default | aggregate | group_by=age_range, count |
| B048 | 具備特定技能的員工 | CONFIGFILEDETAILS_3_default | simple_filter | skill=品質管理 |
| B049 | 員工流動率分析 | CONFIGFILEDETAILS_3_default | aggregate | turnover_rate |
| B050 | 本年度績效優良員工 | CONFIGFILEDETAILS_3_default | simple_filter | performance_rating=excellent, year=current |

---

## MANAGEMENT 領域測試情境 (50 scenarios)

### RAGICFORMS_1: 活動資訊

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| MG001 | 本月活動清單 | RAGICFORMS_1_default | simple_filter | month=current |
| MG002 | 即將舉辦的活動 | RAGICFORMS_1_default | simple_filter | event_date >= today |
| MG003 | 活動 ACT001 詳情 | RAGICFORMS_1_detail | simple_filter | activity_id=ACT001 |
| MG004 | 已結束的活動 | RAGICFORMS_1_default | simple_filter | status=completed |
| MG005 | 各活動類型統計 | RAGICFORMS_1_default | aggregate | group_by=activity_type, count |
| MG006 | 本季活動預算執行 | RAGICFORMS_1_default | aggregate | sum(budget), quarter=current |
| MG007 | 參與人數超過 50 的活動 | RAGICFORMS_1_default | simple_filter | participants > 50 |
| MG008 | 本年度活動趨勢 | RAGICFORMS_1_default | time_series | year=current, group_by=month, count |
| MG009 | 活動滿意度分析 | RAGICFORMS_1_default | aggregate | avg(satisfaction_score) |
| MG010 | 取消的活動 | RAGICFORMS_1_default | simple_filter | status=cancelled |

### RAGICFORMS_3: 場地資訊

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| MG011 | 所有場地清單 | RAGICFORMS_3_default | simple_filter | table_key=RAGICFORMS_3 |
| MG012 | 可容納 100 人以上的場地 | RAGICFORMS_3_default | simple_filter | capacity >= 100 |
| MG013 | 場地 VEN001 詳情 | RAGICFORMS_3_detail | simple_filter | venue_id=VEN001 |
| MG014 | 台北地區場地 | RAGICFORMS_3_default | simple_filter | city=台北 |
| MG015 | 本月場地預約紀錄 | RAGICFORMS_3_default | simple_filter | month=current |
| MG016 | 各場地類型數量 | RAGICFORMS_3_default | aggregate | group_by=venue_type, count |
| MG017 | 場地租金統計 | RAGICFORMS_3_default | aggregate | avg(rental_cost) |
| MG018 | 設備完善的場地 | RAGICFORMS_3_default | simple_filter | facilities_complete=true |
| MG019 | 場地使用率分析 | RAGICFORMS_3_default | aggregate | utilization_rate |
| MG020 | 熱門場地排名 | RAGICFORMS_3_default | aggregate | group_by=venue, order_by=booking_count desc, limit=10 |

### RAGICFORMS_4: 活動預算

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| MG021 | 本月活動預算清單 | RAGICFORMS_4_default | simple_filter | month=current |
| MG022 | 活動 ACT002 預算明細 | RAGICFORMS_4_detail | simple_filter | activity_id=ACT002 |
| MG023 | 預算超支的活動 | RAGICFORMS_4_default | simple_filter | budget_variance < 0 |
| MG024 | 本季總預算統計 | RAGICFORMS_4_default | aggregate | sum(budget), quarter=current |
| MG025 | 各活動預算執行率 | RAGICFORMS_4_default | aggregate | group_by=activity, execution_rate |
| MG026 | 尚未核准的預算 | RAGICFORMS_4_default | simple_filter | approval_status=pending |
| MG027 | 預算金額最高的前 5 活動 | RAGICFORMS_4_default | aggregate | order_by=budget desc, limit=5 |
| MG028 | 本年度預算使用趨勢 | RAGICFORMS_4_default | time_series | year=current, group_by=month, sum(actual_spend) |
| MG029 | 預算節餘的活動 | RAGICFORMS_4_default | simple_filter | budget_variance > 0 |
| MG030 | 預算調整紀錄 | RAGICFORMS_4_default | simple_filter | adjustment_history_exists=true |

### RAGICFORMS3_2: 收入表

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| MG031 | 本月收入明細 | RAGICFORMS3_2_default | simple_filter | month=current |
| MG032 | 今日收入金額 | RAGICFORMS3_2_default | aggregate | sum(amount), date=today |
| MG033 | 收入項目 INC001 詳情 | RAGICFORMS3_2_detail | simple_filter | income_id=INC001 |
| MG034 | 各收入類別統計 | RAGICFORMS3_2_default | aggregate | group_by=income_category, sum(amount) |
| MG035 | 本季總收入 | RAGICFORMS3_2_default | aggregate | sum(amount), quarter=current |
| MG036 | 尚未入帳的收入 | RAGICFORMS3_2_default | simple_filter | accounting_status=pending |
| MG037 | 本年度收入趨勢 | RAGICFORMS3_2_default | time_series | year=current, group_by=month, sum(amount) |
| MG038 | 客戶 C009 的付款紀錄 | RAGICFORMS3_2_default | simple_filter | customer_code=C009 |
| MG039 | 收入金額最高的前 10 筆 | RAGICFORMS3_2_default | aggregate | order_by=amount desc, limit=10 |
| MG040 | 比較本月與上月收入 | RAGICFORMS3_2_default | time_series | compare month-over-month, sum(amount) |

### RAGICFORMS3_3: 預算表

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| MG041 | 本年度預算表 | RAGICFORMS3_3_default | simple_filter | year=current |
| MG042 | 部門 DEPT003 預算明細 | RAGICFORMS3_3_default | simple_filter | department_code=DEPT003 |
| MG043 | 預算項目 BUD001 詳情 | RAGICFORMS3_3_detail | simple_filter | budget_id=BUD001 |
| MG044 | 各部門預算分配 | RAGICFORMS3_3_default | aggregate | group_by=department, sum(budget) |
| MG045 | 本季預算執行率 | RAGICFORMS3_3_default | aggregate | execution_rate, quarter=current |
| MG046 | 預算超支項目 | RAGICFORMS3_3_default | simple_filter | variance < 0 |
| MG047 | 尚未執行的預算 | RAGICFORMS3_3_default | simple_filter | execution_status=not_started |
| MG048 | 本年度預算調整紀錄 | RAGICFORMS3_3_default | simple_filter | adjustment_exists=true |
| MG049 | 各費用類別預算統計 | RAGICFORMS3_3_default | aggregate | group_by=expense_category, sum(budget) |
| MG050 | 預算使用率最高的前 5 部門 | RAGICFORMS3_3_default | aggregate | group_by=department, order_by=utilization_rate desc, limit=5 |

---

## 跨領域/複雜查詢情境 (50 scenarios)

### 跨表查詢 (Cross-Table)

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| X001 | 訂單 O202604004 的完整生產履歷 | ERP_2_default | cross_table | 跨 ERP_2, RAGICSALES_1, MES2_6 |
| X002 | 客戶 C010 的訂單、出貨、收款明細 | ERP_2_default | cross_table | 跨 ERP_2, ERP_9, RAGICFORMS3_2 |
| X003 | 供應商 S013 的採購、收貨、付款紀錄 | ERP_13_default | cross_table | 跨 ERP_13, ERP_5, RAGICFORMS3_3 |
| X004 | 產品 FG011 的 BOM、領料、生產紀錄 | CONFIGFILEDETAILS_5_default | cross_table | 跨 CONFIGFILEDETAILS_5, MES2_4, MES2_6 |
| X005 | 批號 B202604004 的原料追溯到成品出貨 | RAGICSALES_1_default | cross_table | 跨 NOTFOLLOWUPFORM_10, MES2_6, NOTFOLLOWUPFORM_13 |
| X006 | 客訴案件 COMP002 的相關訂單、生產、品檢紀錄 | RAGICSALES_5_default | cross_table | 跨 RAGICSALES_5, ERP_9, MES2_6, ERP_11 |
| X007 | 員工 EMP004 的請購、領料、報工紀錄 | CONFIGURATIONFILE_5_default | cross_table | 跨 RAGICPURCHASING_5, MES2_4, WORKREPORTINGAREA_1 |
| X008 | 原料 RM006 的詢價、採購、收貨、檢驗完整流程 | ERP_4_default | cross_table | 跨 ERP_4, ERP_13, ERP_5, ERP_11 |
| X009 | 製令 WO004 的派工、領料、報工、完工紀錄 | MES2_6_default | cross_table | 跨 MES2_6, MES2_5, MES2_4, WORKREPORTINGAREA_1 |
| X010 | 供應商 S014 的評鑑、採購、收貨合格率關聯分析 | RAGICPURCHASING_3_default | cross_table | 跨 RAGICPURCHASING_3, ERP_13, ERP_11 |

### 複雜條件查詢

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| X011 | 本月訂單金額 > 5 萬且尚未出貨的客戶 | ERP_2_default | simple_filter | 多條件: amount > 50000 AND status=pending AND month=current |
| X012 | 近三個月收貨合格率 < 90% 的供應商 | ERP_11_default | aggregate | 時間範圍 + 合格率計算 + 條件篩選 |
| X013 | 本季客訴次數 > 3 且嚴重度為高的產品 | RAGICSALES_5_default | aggregate | group_by + having count > 3 AND severity=high |
| X014 | 庫存低於安全庫存且本月領用量 > 平均值的物料 | CONFIGURATIONFILE_6_default | cross_table | 跨 CONFIGURATIONFILE_6, MES2_4, 複雜計算 |
| X015 | 逾期超過 7 天且金額 > 10 萬的應收帳款 | ERP_9_default | simple_filter | overdue_days > 7 AND amount > 100000 |
| X016 | 本年度退貨率 > 5% 的產品及相關客訴案件 | ERP_10_default | cross_table | 跨 ERP_10, RAGICSALES_5, 計算退貨率 |
| X017 | 評鑑分數 < 70 且本月有品質異常的供應商 | ISO2_11_default | cross_table | 跨 ISO2_11, ERP_11, 多條件 |
| X018 | 生產週期 > 標準工時 120% 的製令單 | MES2_6_default | simple_filter | cycle_time > (standard_time * 1.2) |
| X019 | 本季報工良率 < 95% 的工序及責任員工 | WORKREPORTINGAREA_1_default | aggregate | 跨多工序表, 良率計算, group_by |
| X020 | 近 6 個月未交易且有應收帳款的客戶 | CONFIGURATIONFILE_7_default | cross_table | 跨 CONFIGURATIONFILE_7, ERP_9, 時間條件 |

### 時間序列分析

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| X021 | 本年度各月銷售趨勢與去年同期比較 | ERP_9_default | time_series | year-over-year comparison |
| X022 | 近 12 個月客訴數量移動平均 | RAGICSALES_5_default | time_series | moving average calculation |
| X023 | 本季每週生產數量趨勢圖 | MES2_6_default | time_series | weekly trend, quarter=current |
| X024 | 各月採購金額季節性分析 | ERP_13_default | time_series | seasonal pattern detection |
| X025 | 本年度收貨合格率變化趨勢 | ERP_11_default | time_series | monthly pass_rate trend |
| X026 | 近 30 天報價轉單率趨勢 | ERP_1_default | time_series | daily conversion rate |
| X027 | 本季各週異常處理結案率 | ISO2_2_default | time_series | weekly closure rate |
| X028 | 近 6 個月庫存周轉率趨勢 | CONFIGURATIONFILE_6_default | time_series | inventory turnover trend |
| X029 | 本年度各月人力成本變化 | CONFIGURATIONFILE_5_default | time_series | monthly labor cost |
| X030 | 近 90 天每日進貨金額波動分析 | ERP_12_default | time_series | daily volatility |

### 聚合統計查詢

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| X031 | 各業務員本季業績排名及達成率 | ERP_9_default | aggregate | group_by, order_by, achievement_rate |
| X032 | 各產品線毛利率分析 | ERP_9_default | aggregate | cross_table with cost, profit margin calculation |
| X033 | 各部門本月費用預算執行率 | RAGICFORMS3_3_default | aggregate | group_by department, execution_rate |
| X034 | 各供應商平均交期準時率 | ERP_13_default | aggregate | group_by supplier, on_time_delivery_rate |
| X035 | 各工序平均良率及產能利用率 | WORKREPORTINGAREA_1_default | aggregate | 跨多工序表, yield_rate, capacity_utilization |
| X036 | 各客戶平均訂單金額及回購週期 | ERP_2_default | aggregate | group_by customer, avg(order_amount), repurchase_cycle |
| X037 | 各品項庫存周轉天數及呆滯分析 | CONFIGURATIONFILE_6_default | aggregate | inventory_turnover_days, aging analysis |
| X038 | 各生產線本月效率、良率、稼動率 | MES2_6_default | aggregate | group_by production_line, efficiency, yield, utilization |
| X039 | 各原料類別採購金額及佔比 | ERP_13_default | aggregate | group_by material_category, sum, percentage |
| X040 | 各地區客戶銷售貢獻度排名 | ERP_9_default | aggregate | group_by region, sum(sales), ranking |

### 異常/錯誤情境

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| X041 | 查詢不存在的表格資料 | UNKNOWN_TABLE | error | code != 0, error message 包含 table not found |
| X042 | 顯示所有訂購單和銷貨單 | CLARIFICATION_NEEDED | clarification | intent 應回傳 clarification request |
| X043 | 幫我查一下那個東西 | CLARIFICATION_NEEDED | clarification | 模糊查詢需要澄清 |
| X044 | 上次看的那筆資料 | CLARIFICATION_NEEDED | clarification | 缺少具體資訊 |
| X045 | 客戶資料 | CLARIFICATION_NEEDED | clarification | 需澄清是 CONFIGURATIONFILE_7 或 FORMS4_2 或 RAGICFORMS6_2 |
| X046 | 員工名單 | CLARIFICATION_NEEDED | clarification | 需澄清是 CONFIGURATIONFILE_5 或 CONFIGFILEDETAILS_3 |
| X047 | 供應商評鑑 | CLARIFICATION_NEEDED | clarification | 需澄清是 RAGICPURCHASING_3 或 ISO2_11 |
| X048 | 客訴處理 | CLARIFICATION_NEEDED | clarification | 需澄清是 RAGICSALES_5, G4102_21, 或 ISO2_10 |
| X049 | 查詢 2030 年的資料 | OUT_OF_RANGE | error | 未來日期應回傳錯誤或空結果 |
| X050 | 原材料驗收紀錄 | CLARIFICATION_NEEDED | clarification | 需澄清是 MES_2~9 的哪一個類別 |

---

## 格式轉換測試情境 (20 scenarios)

### 新舊格式相容性測試

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| F001 | 採購單列表 | ERP_13_default | simple_filter | table_key 應為 ERP_13 (新格式) |
| F002 | ERP-13 採購單 | ERP_13_default | simple_filter | 舊格式轉新格式: erp/tab/ERP-13 → ERP_13 |
| F003 | erp/tab/ERP-13 資料 | ERP_13_default | simple_filter | 完整路徑轉新格式 |
| F004 | 詢價單 RAGICPURCHASING-1 | RAGICPURCHASING_1_default | simple_filter | ragicpurchasing/RAGICPURCHASING-1 → RAGICPURCHASING_1 |
| F005 | forms4/FORMS4-1 聯絡人 | FORMS4_1_default | simple_filter | 舊路徑格式轉換 |
| F006 | 生產需求單 MES2-1 | MES2_1_default | simple_filter | mes2/MES2-1 → MES2_1 |
| F007 | 工序1報工 WORK-REPORTING-AREA-1 | WORKREPORTINGAREA_1_default | simple_filter | 帶連字號格式轉換 |
| F008 | G-4-1-02-/G-4-1-02-1 水塔清洗 | G4102_1_default | simple_filter | 複雜路徑格式轉換 |
| F009 | ISO2/ISO2-11 供應商評鑑 | ISO2_11_default | simple_filter | iso2/ISO2-11 → ISO2_11 |
| F010 | CONFIGURATION-FILE-5 員工 | CONFIGURATIONFILE_5_default | simple_filter | 帶連字號轉底線 |

### Intent ID 格式驗證

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| F011 | 報價單明細 | ERP_1_default | simple_filter | intent_id 格式: ERP_1_default |
| F012 | 訂單 O001 詳細資料 | ERP_2_detail | simple_filter | intent_id 格式: ERP_2_detail (detail action) |
| F013 | 新增採購單 | ERP_13_create | clarification | intent_id: ERP_13_create (action=create) |
| F014 | 更新銷貨單 SI001 | ERP_9_update | clarification | intent_id: ERP_9_update (action=update) |
| F015 | 刪除報價單 Q001 | ERP_1_delete | clarification | intent_id: ERP_1_delete (action=delete) |
| F016 | 匯出本月訂單 | ERP_2_export | clarification | intent_id: ERP_2_export (action=export) |
| F017 | 列印領料單 ISS001 | MES2_4_print | clarification | intent_id: MES2_4_print (action=print) |
| F018 | 複製製令單 WO001 | MES2_6_copy | clarification | intent_id: MES2_6_copy (action=copy) |
| F019 | 核准請購單 PR001 | RAGICPURCHASING_5_approve | clarification | intent_id: RAGICPURCHASING_5_approve (action=approve) |
| F020 | 結案客訴 COMP001 | RAGICSALES_5_close | clarification | intent_id: RAGICSALES_5_close (action=close) |

---

## 邊界條件測試情境 (30 scenarios)

### 空值/Null 處理

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| E001 | 沒有備註的訂單 | ERP_2_default | simple_filter | note IS NULL or note = '' |
| E002 | 尚未指派業務員的銷售機會 | RAGICSALES_13_default | simple_filter | sales_rep IS NULL |
| E003 | 沒有照片的品項 | CONFIGURATIONFILE_6_default | simple_filter | photo IS NULL |
| E004 | 未填寫聯絡電話的客戶 | CONFIGURATIONFILE_7_default | simple_filter | phone IS NULL |
| E005 | 沒有設定安全庫存的品項 | CONFIGURATIONFILE_6_default | simple_filter | safety_stock IS NULL |

### 極值查詢

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| E006 | 金額最高的訂單 | ERP_2_default | aggregate | order_by amount desc, limit=1 |
| E007 | 金額最低的採購單 | ERP_13_default | aggregate | order_by amount asc, limit=1 |
| E008 | 最早的報價單 | ERP_1_default | simple_filter | order_by date asc, limit=1 |
| E009 | 最新的客訴案件 | RAGICSALES_5_default | simple_filter | order_by created_at desc, limit=1 |
| E010 | 交期最近的製令單 | MES2_6_default | simple_filter | order_by due_date asc, limit=1 |

### 特殊字元處理

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| E011 | 客戶名稱包含 & 符號的資料 | CONFIGURATIONFILE_7_default | simple_filter | name LIKE '%&%' |
| E012 | 產品代碼含有 / 的品項 | CONFIGURATIONFILE_6_default | simple_filter | code LIKE '%/%' |
| E013 | 備註有特殊符號 #@! 的訂單 | ERP_2_default | simple_filter | note LIKE '%#%' OR note LIKE '%@%' |
| E014 | 地址包含括號()的供應商 | CONFIGURATIONFILE_13_default | simple_filter | address LIKE '%(%' |
| E015 | 批號含有連字號-的紀錄 | NOTFOLLOWUPFORM_10_default | simple_filter | batch_no LIKE '%-%' |

### 日期邊界

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| E016 | 今天 00:00 到 23:59 的訂單 | ERP_2_default | simple_filter | date >= today_start AND date <= today_end |
| E017 | 本月第一天的資料 | ERP_9_default | simple_filter | date = month_start |
| E018 | 本月最後一天的資料 | ERP_9_default | simple_filter | date = month_end |
| E019 | 跨年度的製令單 (去年開始今年完成) | MES2_6_default | simple_filter | start_date < year_start AND end_date >= year_start |
| E020 | 週末建立的報價單 | ERP_1_default | simple_filter | DAYOFWEEK(date) IN (6,7) |

### 大量資料查詢

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| E021 | 所有訂單 (無條件) | ERP_2_default | simple_filter | 應返回 total count, 測試分頁 |
| E022 | 前 1000 筆銷貨單 | ERP_9_default | simple_filter | limit=1000, 測試大量資料 |
| E023 | 近 5 年的採購紀錄 | ERP_13_default | simple_filter | date >= (today - 5years), 測試大時間範圍 |
| E024 | 所有員工的所有報工紀錄 | WORKREPORTINGAREA_1_default | simple_filter | 跨表大量資料 |
| E025 | 全部品項庫存統計 | CONFIGURATIONFILE_6_default | aggregate | 測試全表聚合運算 |

### 精度/小數點測試

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| E026 | 金額 = 10000.50 的訂單 | ERP_2_default | simple_filter | 精確小數點比對 |
| E027 | 數量 > 99.99 的領料單 | MES2_4_default | simple_filter | 小數點條件查詢 |
| E028 | 單價小於 0.01 的品項 | CONFIGURATIONFILE_6_default | simple_filter | 極小數值查詢 |
| E029 | 良率 = 99.95% 的報工紀錄 | WORKREPORTINGAREA_1_default | simple_filter | 百分比精度 |
| E030 | 匯率 3.1415926 的採購單 | ERP_13_default | simple_filter | 高精度小數 |

---

## 效能/壓力測試情境 (20 scenarios)

### 複雜 JOIN 查詢

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| P001 | 訂單->生產->領料->報工->出貨完整流程追蹤 | ERP_2_default | cross_table | 5 表 JOIN, 測試查詢效能 |
| P002 | 客戶->訂單->銷貨->收款->客訴完整關聯 | CONFIGURATIONFILE_7_default | cross_table | 多表關聯效能 |
| P003 | 原料->詢價->採購->收貨->檢驗->入庫完整流程 | CONFIGURATIONFILE_6_default | cross_table | 6 表 JOIN |
| P004 | 供應商->評鑑->採購->收貨->付款->品質異常關聯分析 | CONFIGURATIONFILE_13_default | cross_table | 複雜多表 JOIN |
| P005 | 員工->請購->領料->報工->績效完整追蹤 | CONFIGURATIONFILE_5_default | cross_table | 員工相關多表 JOIN |

### 大範圍聚合

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| P006 | 近 3 年每日銷售統計 | ERP_9_default | time_series | 1000+ 天聚合運算 |
| P007 | 所有客戶歷史訂單金額總計 | ERP_2_default | aggregate | 全客戶聚合 |
| P008 | 所有品項歷史進銷存統計 | CONFIGURATIONFILE_6_default | aggregate | 全品項複雜計算 |
| P009 | 近 2 年各月各產品線銷售分析 | ERP_9_default | aggregate | 多維度聚合 |
| P010 | 所有供應商歷史交易統計 | CONFIGURATIONFILE_13_default | aggregate | 大量供應商聚合 |

### 併發查詢模擬

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| P011 | 今日訂單 (模擬 50 人同時查詢) | ERP_2_default | simple_filter | 併發效能測試 |
| P012 | 本月業績 (模擬 20 業務同時查) | ERP_9_default | aggregate | 併發聚合效能 |
| P013 | 庫存查詢 (模擬 100 人同時查) | CONFIGURATIONFILE_6_default | simple_filter | 高併發讀取 |
| P014 | 生產進度 (模擬 30 人同時查) | MES2_6_default | simple_filter | 併發複雜查詢 |
| P015 | 客戶資料 (模擬 40 人同時查) | CONFIGURATIONFILE_7_default | simple_filter | 併發基礎查詢 |

### 長查詢語句

| ID | 自然語言查詢 | 預期意圖 | 預期 query_type | 驗證要點 |
|----|-------------|---------|----------------|---------|
| P016 | 請幫我查詢本月金額超過 5 萬且客戶信用等級為 A 且尚未出貨且業務員為張三且產品類別為電子零件的所有訂單明細包含客戶資訊和產品資訊 | ERP_2_default | cross_table | 長複雜條件解析 |
| P017 | 我需要看所有本年度已完成且良率大於 98% 且生產週期小於標準工時且沒有異常紀錄的製令單以及對應的報工明細和用料明細 | MES2_6_default | cross_table | 超長查詢解析 |
| P018 | 包含 500 個篩選條件的查詢，測試系統能正常解析而不崩潰 | ERP_9_default | simple_filter | 邊界條件：超多篩選 |
| P019 | 請列出生產資料表中所有包含特殊字元「'」「"」「;」「--」的備註欄位 | MES2_6_default | simple_filter | SQL 注入防護測試 |

---

## 執行方式

### 單筆查詢測試

```bash
# 直接呼叫 Data Agent
curl -s -X POST http://localhost:8003/ragic/query \
  -H "Content-Type: application/json" \
  -d '{"query": "查詢採購單"}' | python3 -m json.tool

# 預期成功回應（code=0）：
# {
#   "code": 0,
#   "status": "success",
#   "intent": { "intent_id": "ERP_13_default", "table_key": "ERP_13", "score": 0.785 },
#   "result": { "records": [...], "total": N }
# }

# 預期錯誤回應（table_key 格式無效）：
# {
#   "code": 4,
#   "status": "error",
#   "post_error": { "error_code": 4, "raw_error": "table_key format invalid: ERP_13", ... }
# }
```

### 批次執行

```bash
cd /Users/daniel/GitHub/AIBox/.tests/py
source ../../ai-services/.venv/bin/activate
python test_da_tables_scenarios.py
```

---

## 驗證標準

### 正常查詢（T001~T520 扣除 P 系列）

| 項目 | 通過條件 |
|------|---------|
| 意圖匹配 | `response.intent.intent_id == 預期意圖` |
| table_key 格式 | 新格式（如 `ERP_13`）正確解析為 `tab/sheet` |
| query_type | `response.intent.query_type == 預期類型` |
| 分數門檻 | `response.intent.score >= 0.30` |
| 執行成功 | `response.code == 0` |

### 錯誤情境驗證

| 項目 | 通過條件 |
|------|---------|
| 錯誤回應 | `response.code != 0` |
| post_error 存在 | `response.post_error != null` |
| error_code 正確 | `response.post_error.error_code` 為 4（格式錯誤）或 5（clarification） |

### 效能測試（P 系列）

| 項目 | 通過條件 |
|------|---------|
| 回應時間 | < 5000ms（simple_filter），< 15000ms（aggregate/cross_table） |
| 不崩潰 | HTTP 200 回應，body 存在 |