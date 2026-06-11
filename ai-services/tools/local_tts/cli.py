"""
@file        Local TTS CLI
@description 提供本地逐字稿轉語音的命令列介面，支援單一輸出與多聲線樣本輸出。
@lastUpdate  2026-04-25 16:25:01
@author      Hephaestus
@version     1.0.0
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from tools.local_tts.local_tts_tool import LocalTTSInput, LocalTTSTool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Traditional Chinese TTS CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    synthesize_parser = subparsers.add_parser("synthesize", help="Synthesize a script into a single wav file")
    _add_common_source_arguments(synthesize_parser)
    synthesize_parser.add_argument("--output", required=True, help="Output wav path")
    synthesize_parser.add_argument("--voice-seed", type=int, default=None, help="Speaker seed for reproducible voice")
    synthesize_parser.add_argument("--pause-ms", type=int, default=900, help="Default pause between segments")
    synthesize_parser.add_argument(
        "--max-chars", type=int, default=180, help="Maximum characters per chunk before splitting"
    )

    sample_parser = subparsers.add_parser("sample-voices", help="Generate multiple voice samples for selection")
    _add_common_source_arguments(sample_parser)
    sample_parser.add_argument("--output-dir", required=True, help="Directory to save sampled wav files")
    sample_parser.add_argument(
        "--seeds",
        default="11,23,47,89",
        help="Comma-separated voice seeds used to generate samples",
    )
    sample_parser.add_argument("--pause-ms", type=int, default=900, help="Default pause between segments")
    sample_parser.add_argument(
        "--max-chars", type=int, default=180, help="Maximum characters per chunk before splitting"
    )

    return parser


def _add_common_source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", help="Input markdown/text file path")
    parser.add_argument("--text", help="Inline text content")


async def run_cli() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.input and not args.text:
        parser.error("Either --input or --text must be provided")

    tool = LocalTTSTool()

    if args.command == "synthesize":
        result = await tool.execute(
            LocalTTSInput(
                text=args.text,
                file_path=args.input,
                output_path=args.output,
                voice_seed=args.voice_seed,
                paragraph_pause_ms=args.pause_ms,
                max_chars_per_chunk=args.max_chars,
            )
        )
        print(f"Generated: {result.files[0].path}")
        print(f"Segments: {result.segment_count}")
        print(f"Voice seed: {result.files[0].voice_seed}")
        return 0

    seeds = [int(seed.strip()) for seed in args.seeds.split(",") if seed.strip()]
    result = await tool.execute(
        LocalTTSInput(
            text=args.text,
            file_path=args.input,
            output_path=args.output_dir,
            sample_voices=True,
            voice_seeds=seeds,
            paragraph_pause_ms=args.pause_ms,
            max_chars_per_chunk=args.max_chars,
        )
    )
    print(f"Generated {len(result.files)} sample voices in: {Path(args.output_dir).resolve()}")
    for generated_file in result.files:
        print(f"  - seed={generated_file.voice_seed}: {generated_file.path}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
