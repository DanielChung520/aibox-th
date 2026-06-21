"""
@file        bpa/welfare_secretary/main.py
@description 福祉業務小秘 Router 聚合入口
@lastUpdate  2026-06-20
@author      Sisyphus
"""

from fastapi import APIRouter
from bpa.welfare_secretary.router import router as welfare_router

router = APIRouter()
router.include_router(welfare_router)
