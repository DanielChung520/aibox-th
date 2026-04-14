---
lastUpdate: 2026-04-13 07:17:19
author: Daniel Chung
version: 1.0.0
---

# Data Agent da_tables 測試報告

## 測試摘要

| 項目 | 值 |
|------|-----|
| 測試日期 | 2026-04-13 07:17:19 |
| 總場景數 | 649 |
| 通過 | 3 (0.5%)
| 失敗 | 646 |
| 平均延遲 | 31257.5ms |
| 最大延遲 | 33047.8ms |

## 按領域統計

| 領域 | 總數 | 通過 | 失敗 | 通過率 |
|------|------|------|------|--------|
| BASE 領域測試情境 (50 scenarios) | 50 | 0 | 50 | 0.0% |
| MANAGEMENT 領域測試情境 (50 scenarios) | 50 | 0 | 50 | 0.0% |
| MANUFACTURING 領域測試情境 (110 scenarios) | 110 | 0 | 110 | 0.0% |
| QUALITY 領域測試情境 (100 scenarios) | 100 | 0 | 100 | 0.0% |
| SALES 領域測試情境 (90 scenarios) | 90 | 0 | 90 | 0.0% |
| TRADE 領域測試情境 (120 scenarios) | 130 | 3 | 127 | 2.3% |
| 效能/壓力測試情境 (20 scenarios) | 19 | 0 | 19 | 0.0% |
| 格式轉換測試情境 (20 scenarios) | 20 | 0 | 20 | 0.0% |
| 跨領域/複雜查詢情境 (50 scenarios) | 50 | 0 | 50 | 0.0% |
| 邊界條件測試情境 (30 scenarios) | 30 | 0 | 30 | 0.0% |

## 按 query_type 統計

| query_type | 總數 | 通過 | 失敗 | 通過率 |
|------------|------|------|------|--------|
| aggregate | 173 | 0 | 173 | 0.0% |
| clarification | 16 | 0 | 16 | 0.0% |
| cross_table | 21 | 0 | 21 | 0.0% |
| error | 2 | 0 | 2 | 0.0% |
| simple_filter | 388 | 2 | 386 | 0.5% |
| time_series | 49 | 1 | 48 | 2.0% |

## 回應代碼分佈

| code | 數量 | 說明 |
|------|------|------|
| -1 | 630 | 未知 |
| 0 | 12 | 成功 |
| 6 | 7 | 未知 |

## 失敗場景（前 30 項）

| ID | 查詢 | 預期意圖 | 實際意圖 | code | score | 原因 |
|----|------|---------|---------|------|-------|------|
| Q061 | 本月客訴處理單 | ISO2_10_default | ISO2_10_default | 6 | 0.677 | intent mismatch (expected=ISO2_10_default) |
| MG021 | 本月活動預算清單 | RAGICFORMS_4_default | RAGICFORMS_4_default | 6 | 0.651 | intent mismatch (expected=RAGICFORMS_4_default) |
| M071 | 今天的領料單 | MES2_4_default | MES2_4_default | 6 | 0.650 | intent mismatch (expected=MES2_4_default) |
| M061 | 本月托工單清單 | MES2_3_default | MES2_3_default | 6 | 0.654 | intent mismatch (expected=MES2_3_default) |
| T104 | IQC 紀錄 IQC202604001 詳情 | ERP_11_detail | ERP_11_default | 0 | 0.655 | intent mismatch (expected=ERP_11_detail) |
| B022 | 所有供應商清單 | CONFIGURATIONFILE_7_default | CONFIGURATIONFILE_13_default | 0 | 0.651 | intent mismatch (expected=CONFIGURATIONFILE_7_default) |
| T011 | 列出所有訂購單 | ERP_2_default | RAGICPURCHASING_5_default | 0 | 0.671 | intent mismatch (expected=ERP_2_default) |
| X048 | 客訴處理 | CLARIFICATION_NEEDED | ISO2_10_default | 0 | 0.662 | intent mismatch (expected=CLARIFICATION_NEEDED) |
| F013 | 新增採購單 | ERP_13_create | ERP_13_default | 0 | 0.664 | intent mismatch (expected=ERP_13_create) |
| X050 | 原材料驗收紀錄 | CLARIFICATION_NEEDED | MES_8_default | 0 | 0.661 | intent mismatch (expected=CLARIFICATION_NEEDED) |
| X047 | 供應商評鑑 | CLARIFICATION_NEEDED | RAGICPURCHASING_3_default | 0 | 0.728 | intent mismatch (expected=CLARIFICATION_NEEDED) |
| Q071 | 本年度供應商評鑑 | ISO2_11_default | RAGICPURCHASING_3_default | 6 | 0.670 | intent mismatch (expected=ISO2_11_default) |
| Q001 | 本年度水塔清洗紀錄 | G4102_1_default | G4102_1_default | 6 | 0.651 | intent mismatch (expected=G4102_1_default) |
| T061 | 本月進貨退出單 | ERP_7_default | ERP_7_default | 6 | 0.664 | intent mismatch (expected=ERP_7_default) |
| F007 | 工序1報工 WORK-REPORTING-AREA-1 | WORKREPORTINGAREA_1_default | WORKREPORTINGAREA_2_default | 0 | 0.672 | intent mismatch (expected=WORKREPORTINGAREA_1_default) |
| P004 | 供應商->評鑑->採購->收貨->付款->品質異常關聯分析 | CONFIGURATIONFILE_13_default | RAGICPURCHASING_3_default | 0 | 0.666 | intent mismatch (expected=CONFIGURATIONFILE_13_default) |
| Q076 | 本季評鑑完成率 | ISO2_11_default | N/A | -1 | 0.000 | intent mismatch (expected=ISO2_11_default) |
| S023 | 部門 D001 的請購紀錄 | RAGICPURCHASING_5_default | N/A | -1 | 0.000 | intent mismatch (expected=RAGICPURCHASING_5_default) |
| M059 | 本季物料需求趨勢 | MES2_2_default | N/A | -1 | 0.000 | intent mismatch (expected=MES2_2_default) |
| S025 | 緊急請購單 | RAGICPURCHASING_5_default | N/A | -1 | 0.000 | intent mismatch (expected=RAGICPURCHASING_5_default) |
| M060 | 物料備料完成率 | MES2_2_default | N/A | -1 | 0.000 | intent mismatch (expected=MES2_2_default) |
| Q075 | 各供應商平均分數 | ISO2_11_default | N/A | -1 | 0.000 | intent mismatch (expected=ISO2_11_default) |
| Q079 | 本年度評鑑趨勢 | ISO2_11_default | N/A | -1 | 0.000 | intent mismatch (expected=ISO2_11_default) |
| M063 | 尚未完工的托工單 | MES2_3_default | N/A | -1 | 0.000 | intent mismatch (expected=MES2_3_default) |
| Q078 | 品質項目平均分數 | ISO2_11_default | N/A | -1 | 0.000 | intent mismatch (expected=ISO2_11_default) |
| X002 | 客戶 C010 的訂單、出貨、收款明細 | ERP_2_default | N/A | -1 | 0.000 | intent mismatch (expected=ERP_2_default) |
| X003 | 供應商 S013 的採購、收貨、付款紀錄 | ERP_13_default | N/A | -1 | 0.000 | intent mismatch (expected=ERP_13_default) |
| S024 | 請購單 PR001 詳情 | RAGICPURCHASING_5_detail | N/A | -1 | 0.000 | intent mismatch (expected=RAGICPURCHASING_5_detail) |
| Q077 | 評分低於 60 分的供應商 | ISO2_11_default | N/A | -1 | 0.000 | intent mismatch (expected=ISO2_11_default) |
| X004 | 產品 FG011 的 BOM、領料、生產紀錄 | CONFIGFILEDETAILS_5_default | N/A | -1 | 0.000 | intent mismatch (expected=CONFIGFILEDETAILS_5_default) |

## 分數分佈

| 分數區間 | 數量 |
|----------|------|
| 0.9+ | 0 |
| 0.7-0.9 | 3 |
| 0.5-0.7 | 16 |
| 0.3-0.5 | 0 |
| <0.3 | 0 |


*報告生成時間: 2026-04-13 07:17:19*
