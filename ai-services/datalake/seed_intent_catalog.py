#!/usr/bin/env python3
"""
@file        seed_intent_catalog.py
@description Main assembler script: seeds both SAP and Ragic intents into ArangoDB
             intent_catalog collection. Orchestrates imports from SAP and Ragic
             modules to create a dual-source intent architecture.
             Note: During migration, SAP intents are preserved for dual-source support.
@lastUpdate  2026-03-29 02:42:47
@author      Daniel Chung
@version     2.0.0
"""

from .seed_intent_catalog_sap import (
    GROUP_A as SAP_GROUP_A,
    GROUP_B as SAP_GROUP_B,
    GROUP_C as SAP_GROUP_C,
    GROUP_D as SAP_GROUP_D,
    GROUP_E as SAP_GROUP_E,
    GROUP_F as SAP_GROUP_F,
    ORCHESTRATOR_INTENTS as SAP_ORCHESTRATOR,
)
from .seed_intent_catalog_ragic import (
    GROUP_A as RAGIC_GROUP_A,
    GROUP_B as RAGIC_GROUP_B,
    GROUP_C as RAGIC_GROUP_C,
    GROUP_D as RAGIC_GROUP_D,
    GROUP_E as RAGIC_GROUP_E,
    GROUP_F as RAGIC_GROUP_F,
)
from .seed_intent_catalog_shared import insert_batch

if __name__ == "__main__":
    all_sap = (
        SAP_GROUP_A
        + SAP_GROUP_B
        + SAP_GROUP_C
        + SAP_GROUP_D
        + SAP_GROUP_E
        + SAP_GROUP_F
    )
    all_ragic = (
        RAGIC_GROUP_A
        + RAGIC_GROUP_B
        + RAGIC_GROUP_C
        + RAGIC_GROUP_D
        + RAGIC_GROUP_E
        + RAGIC_GROUP_F
    )
    all_da = all_sap + all_ragic

    print(f"\n{'=' * 60}")
    print("Seeding intent_catalog (SAP + Ragic)")
    print(f"{'=' * 60}")

    print(f"\n[SAP Data Agent intents — {len(all_sap)} docs]")
    insert_batch(all_sap, "sap data_agent intents")

    print(f"\n[Ragic Data Agent intents — {len(all_ragic)} docs]")
    insert_batch(all_ragic, "ragic data_agent intents")

    print(f"\n[SAP Orchestrator intents — {len(SAP_ORCHESTRATOR)} docs]")
    insert_batch(SAP_ORCHESTRATOR, "sap orchestrator intents")

    total = len(all_da) + len(SAP_ORCHESTRATOR)
    print(f"\n{'=' * 60}")
    print(f"✅ Seeding complete: {total} intents total")
    print(f"   Data Agent (SAP):     {len(all_sap)} (Groups A-F)")
    print(f"   Data Agent (Ragic):   {len(all_ragic)} (Groups A-F)")
    print(f"   Orchestrator:         {len(SAP_ORCHESTRATOR)}")
    print(f"{'=' * 60}")
