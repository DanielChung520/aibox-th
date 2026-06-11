"""
@file        Local TTS tool exports
@description 導出本地 TTS 工具與 CLI 可共用的核心類型。
@lastUpdate  2026-04-25 16:25:01
@author      Hephaestus
@version     1.0.0
"""

from tools.local_tts.local_tts_tool import GeneratedAudioFile, LocalTTSInput, LocalTTSOutput, LocalTTSTool

__all__ = ["GeneratedAudioFile", "LocalTTSInput", "LocalTTSOutput", "LocalTTSTool"]
