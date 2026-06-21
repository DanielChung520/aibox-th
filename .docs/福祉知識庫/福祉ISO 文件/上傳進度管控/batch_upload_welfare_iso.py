#!/usr/bin/env python3
"""
福祉ISO 文件 — 批次上傳腳本（離線執行）

完整流程：
  Phase 1 [Ontology 匯入] → Phase 2 [Knowledge Root 建立] → Phase 3 [結構錨點上傳] → Phase 4 [分批文件上傳]

用法：
  # 完整執行所有 Phase
  python batch_upload_welfare_iso.py --all

  # 只執行特定 Phase
  python batch_upload_welfare_iso.py --phase 1   # Ontology 匯入
  python batch_upload_welfare_iso.py --phase 2   # Knowledge Root 建立
  python batch_upload_welfare_iso.py --phase 3   # 結構錨點上傳
  python batch_upload_welfare_iso.py --phase 4   # 批次文件上傳

  # 從特定批次開始
  python batch_upload_welfare_iso.py --phase 4 --batch 4.8

  # 指定並行數與重試次數
  python batch_upload_welfare_iso.py --phase 4 --parallel 5 --retry 3

  # 僅上傳特定批次檔案清單（用於重試失敗的批次）
  python batch_upload_welfare_iso.py --phase 4 --batch 4.3 --retry-failed

相依性：
  pip install httpx

設定：
  - API_GATEWAY: 預設 http://localhost:6500
  - ARANGO_URL: 預設 http://localhost:8529
  - 需有 ArangoDB root 密碼（寫在下方變數中）
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# ═══════════════════════════════════════════════════════
# 設定區（依環境調整）
# ═══════════════════════════════════════════════════════

API_GATEWAY = os.getenv("API_GATEWAY", "http://localhost:6500")
UNIFIED_AGENTS = os.getenv("UNIFIED_AGENTS", "http://localhost:8011")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DB", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")

# ISO 文件根目錄
ISO_ROOT = Path(__file__).parent.parent  # .docs/福祉ISO 文件/
TRACKING_FILE = Path(__file__).parent / "福祉ISO_上傳盤點總表.md"

# 知識庫設定
ROOT_ID = "kb_welfare_iso"
ROOT_NAME = "福祉 ISO 品質管理系統"
DOMAIN_ONTOLOGY_FILE = ISO_ROOT / "domain_iso_quality_management.json"
MAJOR_ONTOLOGY_FILE = ISO_ROOT / "major_manufacturing_management_process.json"
STRUCTURE_ANCHOR_FILE = ISO_ROOT / "福祉ISO文件體系總覽.md"

# Domain 與 Major ontology 的名稱（用於查詢 ArangoDB 確認是否已匯入）
DOMAIN_ONTOLOGY_NAME = "ISO_Quality_Management"
MAJOR_ONTOLOGY_NAME = "Manufacturing_Management_Process"

# ═══════════════════════════════════════════════════════
# 批次定義（對應盤點總表 Phase 4.x）
# ═══════════════════════════════════════════════════════

TB_BASE = ISO_ROOT / "R18_01 四階文(表單) TB-"
INSTR_BASE = TB_BASE / "儀器"


def _scan_files(base_dir: Path, pattern: str = "*", exclude_dirs: list[str] | None = None) -> list[dict]:
    """掃描目錄中的檔案，返回 {file, doc_code} 清單"""
    exclude_dirs = exclude_dirs or []
    files = []
    for f in sorted(base_dir.glob(pattern)):
        if f.suffix not in (".docx", ".xlsx", ".pdf", ".jpg", ".jpeg", ".png", ".md"):
            continue
        # 跳過排除目錄
        rel = f.relative_to(base_dir)
        if any(excl in str(rel) for excl in exclude_dirs):
            continue
        # 跳過 .pdf 當同名 .xlsx 已存在時
        if f.suffix == ".pdf":
            xlsx = f.with_suffix(".xlsx")
            if xlsx.exists():
                continue
        doc_code = f.stem.split(" ")[0].split("_")[0].split("V0")[0]
        files.append({"file": str(rel), "doc_code": doc_code})
    return files


def _scan_subdir(base_dir: Path, exclude_dirs: list[str] | None = None) -> list[dict]:
    """掃描子目錄中所有檔案，回傳相對 TB_BASE 的路徑"""
    exclude_dirs = exclude_dirs or []
    files = []
    for f in sorted(base_dir.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix not in (".docx", ".xlsx", ".pdf", ".jpg", ".jpeg", ".png", ".md"):
            continue
        rel = str(f.relative_to(TB_BASE))
        if any(excl in rel for excl in exclude_dirs):
            continue
        if f.suffix == ".pdf":
            xlsx = f.with_suffix(".xlsx")
            if xlsx.exists():
                continue
        doc_code = f.stem.split(" ")[0].split("_")[0]
        files.append({"file": rel, "doc_code": doc_code})
    return files


def _get_instr_files(subdir: str, exclude_dirs: list[str] | None = None) -> list[dict]:
    """掃描儀器子目錄中的檔案"""
    d = INSTR_BASE / subdir
    if not d.exists():
        return []
    return _scan_subdir(d, exclude_dirs)


EXCLUDE_OLD = ["1090408之前", "舊TB-T16", "舊TB-T17", "刪除舊資料", "已下市", "Thumbs.db", ".DS_Store"]


BATCHES = {
    "4.1": {
        "name": "QM 品質手冊 (Level 1)",
        "entity_class": "Level1_QualityManual",
        "hierarchy_level": "1",
        "base_dir": ISO_ROOT / "R18 一階文(品質手冊) QM",
        "files": [
            {"file": "QM-P01品質手冊 V11. 20240925.docx", "doc_code": "QM-P01"},
            {"file": "ISO9001文件及表單對照表20250318更新.docx", "doc_code": "QM-REF"},
        ],
    },
    "4.2": {
        "name": "QP 管理辦法 (Level 2)",
        "entity_class": "Level2_ManagementProcedure",
        "hierarchy_level": "2",
        "base_dir": ISO_ROOT / "R18 二階文(管理辦法) QP",
        "files": [
            {"file": "QP-P01訂單處理管理辦法 V07. 20230615.docx", "doc_code": "QP-P01"},
            {"file": "QP-P02標案處理管理辦法 V01_.docx", "doc_code": "QP-P02"},
            {"file": "QP-P03顧客滿意度管理辦法 V02_.docx", "doc_code": "QP-P03"},
            {"file": "QP-P04顧客抱怨處理辦法 V01_.docx", "doc_code": "QP-P04"},
            {"file": "QP-P05售後服務管理辦法 V02. ok.docx", "doc_code": "QP-P05"},
            {"file": "QP-S01文件與資料管理辦法 V04. 20240925.docx", "doc_code": "QP-S01"},
            {"file": "QP-S02品質記錄管理辦法 V01_.docx", "doc_code": "QP-S02"},
            {"file": "QP-S03教育訓練管理辦法V03 20240925.docx", "doc_code": "QP-S03"},
            {"file": "QP-S04產品及物料防護管理辦法 V03. 20231025.docx", "doc_code": "QP-S04"},
            {"file": "QP-S05採購作業管理辦法 V03 20231025.docx", "doc_code": "QP-S05"},
            {"file": "QP-S06供應商管理辦法 V03. 20240325.docx", "doc_code": "QP-S06"},
            {"file": "QP-S07顧客財產管理辦法 V04 20240925.docx", "doc_code": "QP-S07"},
            {"file": "QP-S08產品識別及追溯管理辦法 V02. ok.docx", "doc_code": "QP-S08"},
            {"file": "QP-S09委外加工作業管理辦法 V04. ok.docx", "doc_code": "QP-S09"},
            {"file": "QP-S10內部品質稽核管理辦法 V03 20240925_.docx", "doc_code": "QP-S10"},
            {"file": "QP-S11管理審查辦法 V02 20240925_.docx", "doc_code": "QP-S11"},
            {"file": "QP-S12資料分析管理辦法 V01_.docx", "doc_code": "QP-S12"},
            {"file": "QP-S13員工提案管理辦法 V01_.docx", "doc_code": "QP-S13"},
            {"file": "QP-S14機會與風險管理辦法 V03. 20240325.docx", "doc_code": "QP-S14"},
            {"file": "QP-S15 特採管理辦法(福祉)  V01_.docx", "doc_code": "QP-S15"},
            {"file": "QP-S17個人資料檔案安全維護作業規定 V02(未發行).docx", "doc_code": "QP-S17"},
            {"file": "QP-T01圖面管理辦法 V04 ok.docx", "doc_code": "QP-T01"},
            {"file": "QP-T02矯正及預防措施管理辦法 V02. 20240925.docx", "doc_code": "QP-T02"},
            {"file": "QP-T03製程管制管理辦法 V13 20250325.docx", "doc_code": "QP-T03"},
            {"file": "QP-T04不合格品管理辦法 V02_.docx", "doc_code": "QP-T04"},
            {"file": "QP-T05檢驗與測試管理辦法 V09 20231025.docx", "doc_code": "QP-T05"},
            {"file": "QP-T06設備管理辦法 V01_.docx", "doc_code": "QP-T06"},
            {"file": "QP-T07儀器管理辦法 V01_.docx", "doc_code": "QP-T07"},
            {"file": "QP-T08新產品開發管理辦法 V01 調整新產品定義.docx", "doc_code": "QP-T08"},
            {"file": "QP-T09設計變更管理辦法 V01 20230615.docx", "doc_code": "QP-T09"},
        ],
    },
    "4.3": {
        "name": "W 作業規範 (Level 3)",
        "entity_class": "Level3_WorkInstruction",
        "hierarchy_level": "3",
        "base_dir": ISO_ROOT / "R18 三階文(作業規範) W",
        "files": [
            {"file": "WC-T01檢驗作業規範-載運輪椅車輛 V19 20250325.docx", "doc_code": "WC-T01"},
            {"file": "WI-T19 載運輪椅車輛工作要領書(昇降設備用)(LoNO)-福斯Transporter V01 (待下期發行).docx", "doc_code": "WI-T19"},
            {"file": "WI-TX 工作要領書-○○○產品 (公版) (待下期發行).docx", "doc_code": "WI-TX"},
            {"file": "WO-S01風險管理表-載運輪椅車輛(輪椅升降台用) V02. 20240325.docx", "doc_code": "WO-S01"},
            {"file": "WO-S05風險管理表-載運輪椅車輛(活動式坡道用) V02. 20240325.docx", "doc_code": "WO-S05"},
            {"file": "WO-S07風險管理表-到宅沐浴車 V02. 20240325.docx", "doc_code": "WO-S07"},
            {"file": "WO-S09風險管理表-小型廂式醫療車輛 V02. 20240325.docx", "doc_code": "WO-S09"},
            {"file": "WO-S11風險管理表-小型廂式露營車 V01. 20240325.docx", "doc_code": "WO-S11"},
            {"file": "WO-Sxx風險管理表-空白 V02. 20240325.docx", "doc_code": "WO-Sxx"},
            {"file": "WO-T01載運輪椅使用者車輛銲接規範 V02_.docx", "doc_code": "WO-T01"},
            {"file": "WP-T01載運輪椅車輛製程作業規範(輪椅升降台用)(多量認證車款) V05_.docx", "doc_code": "WP-T01"},
            {"file": "WP-T02載運輪椅車輛製程作業規範(輪椅升降台用)(多量認證車款)-NEW DELICA V06. 20240325.docx", "doc_code": "WP-T02"},
            {"file": "WP-T05載運輪椅車輛製程作業規範(活動式坡道用)(現代STAREX多量認證車款) V03_.docx", "doc_code": "WP-T05"},
            {"file": "WP-T06沐浴車車輛製程作業規範(中華ZINGER多量認證) V01 ok.docx", "doc_code": "WP-T06"},
            {"file": "WP-T07沐浴車車輛製程作業規範(中華新得利卡多量認證) V05. 20240325. 更正.docx", "doc_code": "WP-T07"},
            {"file": "WP-T11載運輪椅車輛製程作業規範(VERYCA WAV(油車)活動式坡道) V03-抽換SOP圖 更正.docx", "doc_code": "WP-T11"},
            {"file": "WP-T12載運輪椅車輛製程作業規範(VERYCA WAV(電動車)活動式坡道) V01-抽換SOP圖.docx", "doc_code": "WP-T12"},
            {"file": "WP-T13福特旅行家輪椅區輪椅升降台  V02 20240925.docx", "doc_code": "WP-T13"},
            {"file": "WP-T14福特旅行家輪椅區斜坡板 V01. 20240925.docx", "doc_code": "WP-T14"},
            {"file": "WP-T15載運輪椅車輛製程作業規範(活動式坡道用)(TOYOTA SIENTA WAV多量認證車款) V04_.docx", "doc_code": "WP-T15"},
            {"file": "WP-T19載運輪椅車輛製程作業規範(輪椅升降台用)(多量LoNO)-福斯含第三點安全帶 外稽用 V03.docx", "doc_code": "WP-T19"},
            {"file": "WP-T23載運輪椅車輛製程作業規範(現代STARIA(ABC崁入式固定座)輪椅升降台用 V04 20240325.docx", "doc_code": "WP-T23"},
            {"file": "WP-T24載運輪椅車輛製程作業規範(現代STARIA(ABC崁入式固定座)活動式坡道 V03 20240325.docx", "doc_code": "WP-T24"},
            {"file": "WP-T25載運輪椅車輛製程作業規範(輪椅升降台用)(多量非營業認證車款)-NEW DELICA崁入式固定點 V02. 20240325.docx", "doc_code": "WP-T25"},
            {"file": "WP-T27 載運輪椅車輛製程作業規範(活動式坡道用)(多量認證車款)-福特旅玩家 V02 20240325.docx", "doc_code": "WP-T27"},
            {"file": "WP-T29 M1特種車製程作業規範(小型廂式醫療車)(使用中車輛變更)-福斯Kombi高頂 V01.docx", "doc_code": "WP-T29"},
            {"file": "WP-T33露營車輛製程作業規範(掀頂帳用)-中華Delica_V01.20240325.docx", "doc_code": "WP-T33"},
            {"file": "WP-T35 活動式坡道用(多量認證車款)-CADDY IPC V01.20240925.docx", "doc_code": "WP-T35"},
            {"file": "WP-T37 8.使用的工具、治具、儀器、設備清單(舊項更新有顏色版).docx", "doc_code": "WP-T37-LIST"},
            {"file": "WP-T37載運輪椅車輛製程作業規範(CMC-J SPACE WAV活動式坡道) V01.docx", "doc_code": "WP-T37"},
        ],
    },
    "4.4": {
        "name": "TB 根層級表單模板 (P/S/T)",
        "entity_class": "Form_Template",
        "hierarchy_level": "4",
        "base_dir": TB_BASE,
        "files": _scan_files(TB_BASE, "TB-*"),
    },
    "4.5": {
        "name": "TB-T04/T05/T20 檢驗紀錄子目錄",
        "entity_class": "Form_Template",
        "hierarchy_level": "4",
        "base_dir": TB_BASE,
        "files": _scan_subdir(TB_BASE / "TB-T04 品質檢驗紀錄表 V02. 20240325", EXCLUDE_OLD)
               + _scan_subdir(TB_BASE / "TB-T05 自主檢查表 V03. 20240325", EXCLUDE_OLD)
               + _scan_subdir(TB_BASE / "TB-T20 關鍵組(套)件檢查表 V02. 20240325"),
    },
    "4.6": {
        "name": "法規檢驗 T21~34 + T58 工時",
        "entity_class": "Form_Template",
        "hierarchy_level": "4",
        "base_dir": TB_BASE,
        "files": _scan_subdir(TB_BASE / "TB-T21~25,30,32~34 車輛安全法規檢驗項目")
               + _scan_subdir(TB_BASE / "TB-T58 工時工段(序)表"),
    },
    "4.7": {
        "name": "TB-T50~T67 新品開發",
        "entity_class": "Form_Template",
        "hierarchy_level": "4",
        "base_dir": TB_BASE,
        "files": _scan_subdir(TB_BASE / "TB-T50-TB67新品開發 19份"),
    },
    "4.8": {
        "name": "樹八廠儀器總表/履歷/內校",
        "entity_class": "Form_Instance",
        "hierarchy_level": "4",
        "base_dir": TB_BASE,
        "files": _scan_subdir(INSTR_BASE / "樹八廠使用文件夾/儀器總表-樹八廠", EXCLUDE_OLD),
    },
    "4.9": {
        "name": "樹八廠設備履歷+點檢+工具治具",
        "entity_class": "Form_Instance",
        "hierarchy_level": "4",
        "base_dir": TB_BASE,
        "files": _scan_subdir(INSTR_BASE / "樹八廠使用文件夾/設備總表-樹八廠", EXCLUDE_OLD)
               + _scan_subdir(INSTR_BASE / "樹八廠使用文件夾/工具總表-樹八廠")
               + _scan_subdir(INSTR_BASE / "樹八廠使用文件夾/治具總表-樹八廠"),
    },
    "4.10": {
        "name": "土城廠儀器總表/履歷",
        "entity_class": "Form_Instance",
        "hierarchy_level": "4",
        "base_dir": TB_BASE,
        "files": _scan_subdir(INSTR_BASE / "土城儀器", EXCLUDE_OLD)
               + _scan_subdir(INSTR_BASE / "新TB-T17儀器履歷表-土城廠"),
    },
    "4.11": {
        "name": "樹林廠儀器履歷 + 儀器資產",
        "entity_class": "Form_Instance",
        "hierarchy_level": "4",
        "base_dir": TB_BASE,
        "files": _scan_subdir(INSTR_BASE / "新TB-T17儀器履歷表-樹林廠")
               + _scan_subdir(INSTR_BASE / "儀器列為資產"),
    },
    "4.12": {
        "name": "樹八廠儀器履歷 PDF 掃描檔",
        "entity_class": "Form_Instance",
        "hierarchy_level": "4",
        "base_dir": TB_BASE,
        "files": _scan_subdir(INSTR_BASE / "樹八廠使用文件夾/儀器總表-樹八廠/樹八儀器履歷PDF"),
    },
    "4.13": {
        "name": "土城廠儀器履歷 PDF 掃描檔",
        "entity_class": "Form_Instance",
        "hierarchy_level": "4",
        "base_dir": TB_BASE,
        "files": _scan_subdir(INSTR_BASE / "土城儀器/土城儀器履歷PDF"),
    },
    "4.14": {
        "name": "未入ISO表單",
        "entity_class": "Form_Template",
        "hierarchy_level": "4",
        "base_dir": TB_BASE,
        "files": _scan_subdir(TB_BASE / "未入ISO表單"),
    },
}


# ═══════════════════════════════════════════════════════
# 通用工具函數
# ═══════════════════════════════════════════════════════


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def log(msg: str):
    print(f"[{timestamp()}] {msg}")


def log_error(msg: str):
    print(f"[{timestamp()}] ❌ {msg}", file=sys.stderr)


def log_ok(msg: str):
    print(f"[{timestamp()}] ✅ {msg}")


def log_warn(msg: str):
    print(f"[{timestamp()}] ⚠️  {msg}")


def arango_post(endpoint: str, payload: dict) -> dict | None:
    """直接對 ArangoDB REST API 發送 POST 請求"""
    url = f"{ARANGO_URL}/_db/{ARANGO_DB}/{endpoint}"
    try:
        r = httpx.post(url, json=payload, auth=(ARANGO_USER, ARANGO_PASSWORD), timeout=30)
        if r.status_code in (200, 201, 202):
            return r.json()
        log_warn(f"ArangoDB POST {endpoint}: HTTP {r.status_code} - {r.text[:200]}")
        return None
    except Exception as e:
        log_error(f"ArangoDB POST {endpoint} failed: {e}")
        return None


def arango_get(endpoint: str) -> dict | None:
    """直接對 ArangoDB REST API 發送 GET 請求"""
    url = f"{ARANGO_URL}/_db/{ARANGO_DB}/{endpoint}"
    try:
        r = httpx.get(url, auth=(ARANGO_USER, ARANGO_PASSWORD), timeout=30)
        if r.status_code in (200, 201, 202):
            return r.json()
        return None
    except Exception:
        return None


def arango_patch(endpoint: str, payload: dict) -> dict | None:
    """直接對 ArangoDB REST API 發送 PATCH 請求（用於更新文件）"""
    # endpoint 格式: _api/document/{collection}/{document_key}
    url = f"{ARANGO_URL}/_db/{ARANGO_DB}/{endpoint}"
    try:
        r = httpx.request("PATCH", url, json=payload, auth=(ARANGO_USER, ARANGO_PASSWORD), timeout=30)
        if r.status_code in (200, 201, 202):
            return r.json()
        log_warn(f"ArangoDB PATCH {endpoint}: HTTP {r.status_code} - {r.text[:200]}")
        return None
    except Exception as e:
        log_error(f"ArangoDB PATCH {endpoint} failed: {e}")
        return None


def arango_aql(query: str, bind_vars: dict | None = None) -> list[dict]:
    """執行 AQL 查詢"""
    payload: dict[str, Any] = {"query": query}
    if bind_vars:
        payload["bindVars"] = bind_vars
    result = arango_post("_api/cursor", payload)
    if result:
        return result.get("result", [])
    return []


def update_tracking_file(batch_id: str, batch_name: str, status: str):
    """更新盤點總表的進度狀態"""
    if not TRACKING_FILE.exists():
        log_warn(f"追蹤檔案不存在: {TRACKING_FILE}")
        return
    content = TRACKING_FILE.read_text(encoding="utf-8")
    # 更新總表進度
    pattern = f"| {batch_id} | {batch_name}"
    new_status = "✅" if status == "completed" else "⬜"
    old_status = "⬜" if status == "completed" else "❌"
    content = content.replace(
        f"| {batch_id} | {batch_name}",
        f"| {batch_id} | {batch_name}"
    )
    # 更新該批次區域的 ⬜ 為 ✅
    in_section = False
    lines = content.split("\n")
    new_lines = []
    for line in lines:
        if line.startswith(f"## Phase {batch_id}"):
            in_section = True
            line = line.replace("⬜", "✅")
        elif line.startswith("## Phase ") and line != f"## Phase {batch_id}":
            in_section = False
        if in_section and "| ⬜ |" in line:
            line = line.replace("| ⬜ |", "| ✅ |")
        elif in_section and "⬜" in line and "上傳狀態" not in line and "---" not in line:
            line = line.replace("⬜", "✅")
        new_lines.append(line)
    TRACKING_FILE.write_text("\n".join(new_lines), encoding="utf-8")
    log(f"📝 追蹤檔案已更新: Phase {batch_id} → {status}")


# ═══════════════════════════════════════════════════════
# Phase 1: Ontology 匯入
# ═══════════════════════════════════════════════════════


def phase1_import_ontologies():
    """匯入 Domain + Major Ontology 到 ArangoDB ontologies collection"""
    log("=" * 60)
    log("Phase 1: Ontology 匯入")
    log("=" * 60)

    # 檢查是否已存在
    existing = arango_aql(
        "FOR o IN ontologies FILTER o.name == @name RETURN o.name",
        {"name": DOMAIN_ONTOLOGY_NAME},
    )
    if existing:
        log_ok(f"Domain Ontology '{DOMAIN_ONTOLOGY_NAME}' 已存在，跳過")
    else:
        if not DOMAIN_ONTOLOGY_FILE.exists():
            log_error(f"Domain Ontology 檔案不存在: {DOMAIN_ONTOLOGY_FILE}")
            return False
        log(f"  讀取: {DOMAIN_ONTOLOGY_FILE}")
        domain_data = json.loads(DOMAIN_ONTOLOGY_FILE.read_text(encoding="utf-8"))
        log(f"  匯入 Domain Ontology: {DOMAIN_ONTOLOGY_NAME}")
        result = arango_post("_api/document/ontologies", domain_data)
        if result:
            log_ok(f"  Domain Ontology 匯入成功: _key={result.get('_key')}")
        else:
            log_error("  Domain Ontology 匯入失敗")
            return False

    existing = arango_aql(
        "FOR o IN ontologies FILTER o.name == @name RETURN o.name",
        {"name": MAJOR_ONTOLOGY_NAME},
    )
    if existing:
        log_ok(f"Major Ontology '{MAJOR_ONTOLOGY_NAME}' 已存在，跳過")
    else:
        if not MAJOR_ONTOLOGY_FILE.exists():
            log_error(f"Major Ontology 檔案不存在: {MAJOR_ONTOLOGY_FILE}")
            return False
        log(f"  讀取: {MAJOR_ONTOLOGY_FILE}")
        major_data = json.loads(MAJOR_ONTOLOGY_FILE.read_text(encoding="utf-8"))
        log(f"  匯入 Major Ontology: {MAJOR_ONTOLOGY_NAME}")
        result = arango_post("_api/document/ontologies", major_data)
        if result:
            log_ok(f"  Major Ontology 匯入成功: _key={result.get('_key')}")
        else:
            log_error("  Major Ontology 匯入失敗")
            return False

    # 驗證
    count = arango_aql(
        "FOR o IN ontologies FILTER o.name == @n1 OR o.name == @n2 RETURN o",
        {"n1": DOMAIN_ONTOLOGY_NAME, "n2": MAJOR_ONTOLOGY_NAME},
    )
    if len(count) == 2:
        log_ok(f"Phase 1 完成: {len(count)} 個 Ontology 已就緒")
        return True
    else:
        log_warn(f"Phase 1 部分完成: 只找到 {len(count)}/2 個")
        return False


# ═══════════════════════════════════════════════════════
# Phase 2: Knowledge Root 建立
# ═══════════════════════════════════════════════════════


def phase2_create_knowledge_root():
    """建立 Knowledge Root"""
    log("=" * 60)
    log("Phase 2: Knowledge Root 建立")
    log("=" * 60)

    # 檢查是否已存在
    existing = arango_aql(
        "FOR r IN knowledge_roots FILTER r._key == @key RETURN r.name",
        {"key": ROOT_ID},
    )
    if existing:
        log_ok(f"Knowledge Root '{ROOT_ID}' 已存在: {existing[0]}")
        return True

    root_doc = {
        "_key": ROOT_ID,
        "name": ROOT_NAME,
        "description": "福祉車輛改裝製造業 ISO 9001 品質管理系統文件集，涵蓋文件四階層、儀器設備管理、製程檢驗與法規符合性。",
        "ontology_domain": DOMAIN_ONTOLOGY_NAME,
        "ontology_majors": [MAJOR_ONTOLOGY_NAME],
        "source_count": 0,
        "vector_status": "pending",
        "graph_status": "pending",
        "is_favorite": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = arango_post("_api/document/knowledge_roots", root_doc)
    if result:
        log_ok(f"Knowledge Root 建立成功: _key={result.get('_key')}")
        # 不需要再透過 API Gateway 建立（會產生不同 key 的重複 root）
        return True
    else:
        log_error("Knowledge Root 建立失敗，嘗試透過 API Gateway...")
        # 如果直接 ArangoDB 失敗，改用 API Gateway
        try:
            api_result = httpx.post(
                f"{API_GATEWAY}/api/v1/knowledge/roots",
                json={k: v for k, v in root_doc.items() if k != "_key"},
                timeout=10,
            )
            if api_result.status_code in (200, 201):
                log_ok("  API Gateway 建立成功")
                return True
        except Exception as e:
            log_error(f"  API Gateway 也失敗: {e}")
        return False


# ═══════════════════════════════════════════════════════
# Phase 3: 結構錨點文件上傳
# ═══════════════════════════════════════════════════════


def phase3_upload_structure_anchor():
    """上傳文件體系總覽（結構錨點）"""
    log("=" * 60)
    log("Phase 3: 結構錨點上傳")
    log("=" * 60)

    if not STRUCTURE_ANCHOR_FILE.exists():
        log_warn(f"結構錨點檔案不存在: {STRUCTURE_ANCHOR_FILE}")
        log("  請先建立 福祉ISO文件體系總覽.md")
        return False

    file_path = str(STRUCTURE_ANCHOR_FILE)
    file_name = STRUCTURE_ANCHOR_FILE.name

    log(f"  上傳: {file_name}")
    try:
        with open(file_path, "rb") as f:
            r = httpx.post(
                f"{API_GATEWAY}/api/v1/knowledge/roots/{ROOT_ID}/files/upload",
                files={"file": (file_name, f, "text/markdown")},
                timeout=300,
            )
        if r.status_code in (200, 201):
            data = r.json()
            file_id = data.get("data", {}).get("fileId", "?")
            log_ok(f"  結構錨點上傳成功: file_id={file_id}")
            log("  ⏳ Pipeline 已觸發（向量化 + 圖譜萃取非同步執行）")
            return True
        else:
            log_error(f"  上傳失敗: HTTP {r.status_code} - {r.text[:200]}")
            return False
    except Exception as e:
        log_error(f"  上傳例外: {e}")
        return False


# ═══════════════════════════════════════════════════════
# Phase 4: 批次文件上傳核心
# ═══════════════════════════════════════════════════════


def upload_single_file(
    client: httpx.Client,
    file_path: str,
    doc_code: str,
    hierarchy_level: str,
    entity_class: str,
    factory: str | None = None,
    form_type: str | None = None,
    parent_form: str | None = None,
) -> dict:
    """上傳單一檔案並觸發 Pipeline"""
    file_name = os.path.basename(file_path)
    if not os.path.exists(file_path):
        return {"success": False, "file": file_name, "error": "FILE_NOT_FOUND"}

    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".md": "text/markdown",
    }
    mime = mime_map.get(ext, "application/octet-stream")

    try:
        with open(file_path, "rb") as f:
            r = client.post(
                f"{API_GATEWAY}/api/v1/knowledge/roots/{ROOT_ID}/files/upload",
                files={"file": (file_name, f, mime)},
                timeout=600,
            )
        if r.status_code in (200, 201):
            data = r.json()
            file_id = data.get("data", {}).get("fileId", "")
            if file_id:
                # 更新 metadata（透過 ArangoDB PATCH 直接操作）
                arango_patch(f"_api/document/knowledge_files/{file_id}", {
                    "document_code": doc_code,
                    "hierarchy_level": hierarchy_level,
                    "entity_class": entity_class,
                    "factory": factory or "",
                    "form_type": form_type or "",
                    "parent_form": parent_form or "",
                })
                return {"success": True, "file_id": file_id, "file": file_name}
        return {"success": False, "file": file_name, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"success": False, "file": file_name, "error": str(e)}


def process_batch(
    batch_id: str,
    batch_config: dict,
    parallel: int = 3,
    max_retries: int = 2,
    dry_run: bool = False,
):
    """處理一個批次的所有檔案"""
    batch_name = batch_config["name"]
    entity_class = batch_config["entity_class"]
    hierarchy_level = batch_config["hierarchy_level"]
    base_dir = batch_config["base_dir"]
    files_list = batch_config["files"]

    log(f"\n{'=' * 60}")
    log(f"Phase 4.{batch_id}: {batch_name} ({len(files_list)} files)")
    log(f"{'=' * 60}")

    results: list[dict] = []
    failed: list[dict] = []

    if dry_run:
        log("🔍 Dry-run 模式 — 僅列出將上傳的檔案：")
        for f_info in files_list:
            fpath = base_dir / f_info["file"]
            exists = "✅" if fpath.exists() else "❌"
            log(f"  [{exists}] {f_info['doc_code']:12s} → {f_info['file']}")
        return True

    with httpx.Client(timeout=300) as client:
        for i in range(0, len(files_list), parallel):
            batch = files_list[i:i + parallel]
            for f_info in batch:
                fpath = base_dir / f_info["file"]
                if not fpath.exists():
                    log_warn(f"  檔案不存在，跳過: {fpath}")
                    results.append({"success": False, "file": f_info["file"], "error": "NOT_FOUND"})
                    failed.append(f_info)
                    continue

                log(f"  ⬆️  上傳: {f_info['doc_code']:12s} → {fpath.name[:60]}...")
                result = upload_single_file(
                    client,
                    str(fpath),
                    doc_code=f_info["doc_code"],
                    hierarchy_level=hierarchy_level,
                    entity_class=entity_class,
                )
                results.append(result)
                if result["success"]:
                    log_ok(f"    OK: file_id={result.get('file_id', '?')[:12]}...")
                else:
                    log_error(f"    失敗: {result.get('error', '?')}")
                    failed.append(f_info)

            # 批次間暫停，避免壓垮服務
            if i + parallel < len(files_list):
                time.sleep(0.5)

    # 重試失敗的
    retry_count = 0
    while failed and retry_count < max_retries:
        retry_count += 1
        log(f"\n🔄 第 {retry_count} 次重試 ({len(failed)} 個檔案)...")
        time.sleep(2)
        still_failed = []
        with httpx.Client(timeout=300) as client:
            for f_info in failed:
                fpath = base_dir / f_info["file"]
                if fpath.exists():
                    log(f"  🔄 重試: {f_info['doc_code']}")
                    result = upload_single_file(
                        client,
                        str(fpath),
                        doc_code=f_info["doc_code"],
                        hierarchy_level=hierarchy_level,
                        entity_class=entity_class,
                    )
                    if result["success"]:
                        log_ok(f"    重試成功: {result.get('file_id', '?')[:12]}...")
                    else:
                        log_error(f"    重試失敗: {result.get('error', '?')}")
                        still_failed.append(f_info)
        failed = still_failed

    success_count = sum(1 for r in results if r["success"])
    fail_count = len(failed)
    log(f"\n📊 批次 {batch_id} 結果: {success_count} 成功, {fail_count} 失敗 / {len(files_list)} 總計")

    if fail_count == 0:
        update_tracking_file(batch_id, batch_name, "completed")
        return True
    else:
        log_warn(f"批次 {batch_id} 有 {fail_count} 個檔案未成功，請檢視後重試")
        # 輸出失敗清單供後續重試
        fail_log = Path(__file__).parent / f"failed_batch_{batch_id}.json"
        fail_log.write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"  失敗清單已寫入: {fail_log}")
        update_tracking_file(batch_id, batch_name, "failed")
        return False


def phase4_upload_files(
    start_batch: str = "4.1",
    parallel: int = 3,
    max_retries: int = 2,
    dry_run: bool = False,
    retry_failed: bool = False,
):
    """執行 Phase 4 批次文件上傳"""
    log("=" * 60)
    log("Phase 4: 批次文件上傳")
    if dry_run:
        log("  模式: Dry-run（僅列出不上傳）")
    log("=" * 60)

    batch_ids = sorted(BATCHES.keys(), key=lambda x: tuple(int(n) for n in x.split('.')))
    started = False

    for bid in batch_ids:
        if bid == start_batch or started:
            started = True
        if not started:
            continue
        if retry_failed:
            fail_log = Path(__file__).parent / f"failed_batch_{bid}.json"
            if fail_log.exists():
                log(f"  發現批次 {bid} 的失敗清單，將重試 {len(json.loads(fail_log.read_text()))} 個檔案")
        process_batch(bid, BATCHES[bid], parallel=parallel, max_retries=max_retries, dry_run=dry_run)


# ═══════════════════════════════════════════════════════
# 驗證（Phase 5）
# ═══════════════════════════════════════════════════════


def verify_all():
    """執行驗證檢查"""
    log("=" * 60)
    log("Phase 5: 驗證檢查")
    log("=" * 60)

    # 5.1 驗證 Ontology
    log("\n5.1 驗證 Ontology:")
    result = arango_aql(
        "FOR o IN ontologies FILTER o.name == @n1 OR o.name == @n2 RETURN {name: o.name, classes: LENGTH(o.entity_classes), props: LENGTH(o.object_properties)}",
        {"n1": DOMAIN_ONTOLOGY_NAME, "n2": MAJOR_ONTOLOGY_NAME},
    )
    for item in result:
        log_ok(f"  {item.get('name')}: {item.get('classes')} classes, {item.get('props')} properties")

    # 5.2 驗證 Knowledge Root
    log("\n5.2 驗證 Knowledge Root:")
    result = arango_aql(
        "FOR kr IN knowledge_roots FILTER kr._key == @key RETURN {name: kr.name, sources: kr.source_count}",
        {"key": ROOT_ID},
    )
    if result:
        log_ok(f"  {result[0].get('name')}: {result[0].get('sources')} files")

    # 5.3 統計各批次上傳情況
    log("\n5.3 上傳統計:")
    result = arango_aql(
        "FOR f IN knowledge_files FILTER f.knowledge_root_id == @key COLLECT status = f.vector_status WITH COUNT INTO cnt RETURN {status: status, count: cnt}",
        {"key": ROOT_ID},
    )
    total = 0
    for item in result:
        log(f"  vector_status={item.get('status')}: {item.get('count')}")
        total += item.get("count", 0)
    log(f"  總計: {total} files")

    # 5.4 列出未完成的檔案
    log("\n5.4 未完成的檔案:")
    failed = arango_aql(
        "FOR f IN knowledge_files FILTER f.knowledge_root_id == @key AND (f.vector_status != 'completed' OR f.`graph_status` != 'completed') RETURN {file: f.filename, vector: f.vector_status, `graph`: f.`graph_status`}",
        {"key": ROOT_ID},
    )
    for item in failed[:20]:  # 最多顯示 20 個
        log(f"  ⚠️  {item.get('file', '?')}: vector={item.get('vector','?')}, graph={item.get('graph','?')}")
    if len(failed) > 20:
        log(f"  ... 還有 {len(failed) - 20} 個未列出")


# ═══════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════


def run_all(parallel: int = 3, max_retries: int = 2, dry_run: bool = False):
    """執行完整流程 Phase 1 → 5"""
    log("🚀 福祉ISO 批次上傳腳本啟動")
    log(f"    API Gateway: {API_GATEWAY}")
    log(f"    ArangoDB:    {ARANGO_URL}")
    log(f"    Root ID:     {ROOT_ID}")
    log(f"    ISO Root:    {ISO_ROOT}")
    log("")

    if not phase1_import_ontologies():
        log_error("Phase 1 失敗，中止")
        return

    if not phase2_create_knowledge_root():
        log_error("Phase 2 失敗，中止")
        return

    phase3_upload_structure_anchor()
    phase4_upload_files(parallel=parallel, max_retries=max_retries, dry_run=dry_run)
    verify_all()

    log("\n" + "=" * 60)
    log("🎉 全部流程完成！")
    log("=" * 60)


def phase6_merge_graph(aql_path: str | None = None):
    """執行 Phase 6 跨檔案圖譜融合"""
    log("=" * 60)
    log("Phase 6: 跨檔案圖譜融合 (Metadata Linker)")
    log("=" * 60)

    root = "kb_welfare_iso"
    bind = {"root": root}

    # 每個 STEP 是獨立的 AQL 查詢
    steps = [
        ("STEP_A1 清理 merged_graphs",
         "FOR m IN merged_graphs FILTER m.root_id == @root REMOVE m IN merged_graphs OPTIONS { ignoreErrors: true }"),
        ("STEP_A2 清理 merged_edges",
         "FOR e IN merged_edges FILTER e.root_id == @root REMOVE e IN merged_edges OPTIONS { ignoreErrors: true }"),
        ("STEP_B 合併實體",
         f"""FOR g IN knowledge_graphs
  FILTER g.root_id == @root
  COLLECT entity_name = g.entity INTO groups = {{ fid: g.file_id, typ: g.entity_type, dsc: g.description }}
  LET type_counts = (
    FOR gr IN groups COLLECT t = gr.typ WITH COUNT INTO cnt SORT cnt DESC LIMIT 1 RETURN t
  )
  LET best_type = FIRST(type_counts) || FIRST(groups).typ || "concept"
  INSERT {{
    entity: entity_name,
    entity_type: best_type,
    root_id: @root,
    source_files: UNIQUE(groups[*].fid),
    merge_count: LENGTH(groups),
    description: SUBSTRING(CONCAT_SEPARATOR("; ", UNIQUE(groups[*].dsc)), 0, 2000),
    is_merged: LENGTH(groups) > 1
  }} INTO merged_graphs OPTIONS {{ ignoreErrors: true }}
  RETURN NEW"""),
    ]

    # STEP_C: 文件階層關係（每個子步驟獨立查詢）
    edge_steps = [
        ("STEP_C1 QM→QP",
         "FOR qm IN merged_graphs FILTER qm.root_id == @root AND STARTS_WITH(qm.entity, @pre1) "
         "FOR qp IN merged_graphs FILTER qp.root_id == @root AND STARTS_WITH(qp.entity, @pre2) "
         "INSERT { _from: CONCAT('merged_graphs/', qm._key), _to: CONCAT('merged_graphs/', qp._key), "
         "relation: 'governs', root_id: @root, description: CONCAT(qm.entity, ' 管轄 ', qp.entity) } "
         "INTO merged_edges OPTIONS { ignoreErrors: true } RETURN 1",
         {"pre1": "QM-", "pre2": "QP-"}),
        ("STEP_C2 QP→TB",
         "FOR qp IN merged_graphs FILTER qp.root_id == @root AND STARTS_WITH(qp.entity, @pre1) "
         "FOR tb IN merged_graphs FILTER tb.root_id == @root AND STARTS_WITH(tb.entity, @pre2) "
         "INSERT { _from: CONCAT('merged_graphs/', qp._key), _to: CONCAT('merged_graphs/', tb._key), "
         "relation: 'defines_form', root_id: @root, description: CONCAT(qp.entity, ' 定義表單 ', tb.entity) } "
         "INTO merged_edges OPTIONS { ignoreErrors: true } RETURN 1",
         {"pre1": "QP-", "pre2": "TB-"}),
        ("STEP_C3 QP-T03~T08→W",
         "FOR qp IN merged_graphs FILTER qp.root_id == @root AND qp.entity IN @qps "
         "FOR w IN merged_graphs FILTER w.root_id == @root AND (STARTS_WITH(w.entity, @p1) OR STARTS_WITH(w.entity, @p2) OR STARTS_WITH(w.entity, @p3) OR STARTS_WITH(w.entity, @p4)) "
         "INSERT { _from: CONCAT('merged_graphs/', qp._key), _to: CONCAT('merged_graphs/', w._key), "
         "relation: 'governs', root_id: @root, description: CONCAT(qp.entity, ' 管轄 ', w.entity) } "
         "INTO merged_edges OPTIONS { ignoreErrors: true } RETURN 1",
         {"qps": ["QP-T03", "QP-T05", "QP-T06", "QP-T07", "QP-T08"],
          "p1": "WP-", "p2": "WO-", "p3": "WC-", "p4": "WI-"}),
    ]

    # STEP_D: 模板→實例 + 廠區（每個子步驟獨立查詢）
    link_steps = [
        ("STEP_D1 TB-T17→儀器",
         "FOR t17 IN merged_graphs FILTER t17.root_id == @root AND t17.entity == @t17 "
         "FOR inst IN merged_graphs FILTER inst.root_id == @root AND (STARTS_WITH(inst.entity, @s1) OR STARTS_WITH(inst.entity, @s2) OR inst.entity_type == @itype) "
         "INSERT { _from: CONCAT('merged_graphs/', t17._key), _to: CONCAT('merged_graphs/', inst._key), "
         "relation: 'filled_by', root_id: @root, description: CONCAT(t17.entity, ' 被 ', inst.entity, ' 填寫') } "
         "INTO merged_edges OPTIONS { ignoreErrors: true } RETURN 1",
         {"t17": "TB-T17", "s1": "SM", "s2": "TM", "itype": "Instrument"}),
        ("STEP_D2 TB-T13→設備",
         "FOR t13 IN merged_graphs FILTER t13.root_id == @root AND t13.entity == @t13 "
         "FOR eq IN merged_graphs FILTER eq.root_id == @root AND STARTS_WITH(eq.entity, @pre) AND LENGTH(eq.entity) == 4 "
         "INSERT { _from: CONCAT('merged_graphs/', t13._key), _to: CONCAT('merged_graphs/', eq._key), "
         "relation: 'filled_by', root_id: @root, description: CONCAT(t13.entity, ' 被 ', eq.entity, ' 填寫') } "
         "INTO merged_edges OPTIONS { ignoreErrors: true } RETURN 1",
         {"t13": "TB-T13", "pre": "E"}),
        ("STEP_D3 樹八廠→儀器",
         "FOR f IN merged_graphs FILTER f.root_id == @root AND f.entity == @fac AND f.entity_type == @ftype "
         "FOR inst2 IN merged_graphs FILTER inst2.root_id == @root AND ((STARTS_WITH(inst2.entity, @s1) AND LENGTH(inst2.entity) >= 3) OR (STARTS_WITH(inst2.entity, @s2) AND LENGTH(inst2.entity) >= 3)) "
         "INSERT { _from: CONCAT('merged_graphs/', f._key), _to: CONCAT('merged_graphs/', inst2._key), "
         "relation: 'has_instrument', root_id: @root, description: CONCAT(f.entity, ' 擁有儀器 ', inst2.entity) } "
         "INTO merged_edges OPTIONS { ignoreErrors: true } RETURN 1",
         {"fac": "SM", "ftype": "Factory_Unit", "s1": "SM", "s2": "M0"}),
        ("STEP_D4 土城廠→儀器",
         "FOR f2 IN merged_graphs FILTER f2.root_id == @root AND f2.entity == @fac AND f2.entity_type == @ftype "
         "FOR inst3 IN merged_graphs FILTER inst3.root_id == @root AND STARTS_WITH(inst3.entity, @s1) AND LENGTH(inst3.entity) >= 3 "
         "INSERT { _from: CONCAT('merged_graphs/', f2._key), _to: CONCAT('merged_graphs/', inst3._key), "
         "relation: 'has_instrument', root_id: @root, description: CONCAT(f2.entity, ' 擁有儀器 ', inst3.entity) } "
         "INTO merged_edges OPTIONS { ignoreErrors: true } RETURN 1",
         {"fac": "TM", "ftype": "Factory_Unit", "s1": "TM"}),
    ]

    total_merged = 0
    total_edges = 0

    for step_name, aql, *extra in steps + edge_steps + link_steps:
        extra_binds = extra[0] if extra else {}
        all_binds = dict(bind)
        all_binds.update(extra_binds)
        log(f"  ⏳ {step_name}...")
        try:
            result = arango_post("_api/cursor", {"query": aql, "bindVars": all_binds})
            if result:
                results = result.get("result", [])
                cnt = len(results)
                if step_name.startswith("STEP_B"):
                    total_merged = cnt
                    log_ok(f"    {cnt} 實體已合併")
                else:
                    total_edges += cnt
                    log_ok(f"    {cnt} 關係邊已建立")
            else:
                log_error(f"    {step_name} 失敗")
                return False
        except Exception as e:
            log_error(f"    {step_name} 錯誤: {e}")
            return False

    log_ok(f"\n  ✅ 融合完成! merged_graphs={total_merged} nodes, merged_edges={total_edges} edges")
    return True


def main():
    parser = argparse.ArgumentParser(description="福祉ISO 批次上傳腳本")
    parser.add_argument("--all", action="store_true", help="執行完整流程 Phase 1 → 5")
    parser.add_argument("--phase", type=str, choices=["1", "2", "3", "4", "5"], help="執行特定 Phase")
    parser.add_argument("--batch", type=str, help="Phase 4 從指定批次開始 (e.g., 4.3)")
    parser.add_argument("--parallel", type=int, default=3, help="並行上傳數 (default: 3)")
    parser.add_argument("--retry", type=int, default=2, help="最大重試次數 (default: 2)")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run 模式，僅列出不上傳")
    parser.add_argument("--retry-failed", action="store_true", help="重試之前失敗的檔案（讀取 failed_batch_*.json）")
    parser.add_argument("--merge", action="store_true", help="執行 Phase 6 跨檔案圖譜融合")
    parser.add_argument("--merge-aql", type=str, help="指定 Phase 6 的自訂 AQL 腳本路徑")

    args = parser.parse_args()

    if args.merge:
        phase6_merge_graph(aql_path=args.merge_aql)
    elif args.all:
        run_all(parallel=args.parallel, max_retries=args.retry, dry_run=args.dry_run)
    elif args.phase == "1":
        phase1_import_ontologies()
    elif args.phase == "2":
        phase2_create_knowledge_root()
    elif args.phase == "3":
        phase3_upload_structure_anchor()
    elif args.phase == "4":
        start = args.batch or "4.1"
        phase4_upload_files(
            start_batch=start,
            parallel=args.parallel,
            max_retries=args.retry,
            dry_run=args.dry_run,
            retry_failed=args.retry_failed,
        )
    elif args.phase == "5":
        verify_all()
    else:
        # 無參數時顯示摘要
        print("福祉ISO 批次上傳腳本")
        print("=" * 40)
        print("用法:")
        print("  python batch_upload_welfare_iso.py --all              # 完整執行")
        print("  python batch_upload_welfare_iso.py --phase 1          # 只匯入 Ontology")
        print("  python batch_upload_welfare_iso.py --phase 4 --dry-run # 預覽上傳清單")
        print("  python batch_upload_welfare_iso.py --phase 4 --batch 4.3  # 從批次4.3開始")
        print("  python batch_upload_welfare_iso.py --phase 5          # 驗證檢查")
        print(f"\n已定義批次: {', '.join(sorted(BATCHES.keys(), key=lambda x: tuple(int(n) for n in x.split('.'))))}")
        print(f"  完整批次清單請參考盤點總表: {TRACKING_FILE}")


if __name__ == "__main__":
    main()
