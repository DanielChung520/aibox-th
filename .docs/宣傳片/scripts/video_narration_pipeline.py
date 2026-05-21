#!/usr/bin/env python3
"""
EEA 影片旁白生產管線

將螢幕錄影影片轉為含旁白的成品影片：
  Step 1: analyze  — 抽幀 → Qwen3-VL 分析畫面 → 產出畫面描述 JSON
  Step 2: draft    — 畫面描述 → LLM 生成逐字稿 → 產出 .md 腳本
  Step 3: tts     — 確認後的 .md 腳本 → Qwen3-TTS 生成 .wav 音軌（分開，供後製）
  Step 4: merge   — 影片 + 音軌 → ffmpeg 合併最終影片

用法:
  python video_narration_pipeline.py analyze  <video.mov> [--fps 1]
  python video_narration_pipeline.py draft    <analysis.json> [--lang zh]
  python video_narration_pipeline.py tts      <script.md> [--voice zh_tw_ting] [--speed 1.0] [--output audio.wav]
  python video_narration_pipeline.py merge    <video.mov> <audio.wav> [--output final.mp4]
  python video_narration_pipeline.py all      <video.mov> [--fps 1] [--voice zh_tw_ting] [--speed 1.0]

相依:
  - ffmpeg
  - Ollama with qwen3-vl:latest
  - Ollama with LLM model (default: gemma4:31b)
  - Qwen3-TTS service (port 5001), VoiceTTS project
"""

import argparse
import json
import os
import subprocess
import sys
import time
import re
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
TTS_API_URL = os.environ.get("TTS_API_URL", "http://localhost:5001")
VL_MODEL = os.environ.get("VL_MODEL", "qwen3-vl:latest")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma4:31b")
TEMP_BASE = Path(".tmp/video_pipeline")
CHARS_PER_SEC = 3.5


def info(msg):
    print(f"[INFO] {msg}")


def warn(msg):
    print(f"[WARN] {msg}")


def err(msg):
    print(f"[ERROR] {msg}", file=sys.stderr)


def run_cmd(cmd, desc="", timeout=300):
    info(f"  -> {desc or cmd[0]}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            err(f"CMD_FAIL (exit={r.returncode}): {' '.join(cmd)}")
            err(r.stderr[:500])
            return None
        return r.stdout
    except subprocess.TimeoutExpired:
        err(f"TIMEOUT ({timeout}s): {' '.join(cmd)}")
        return None
    except FileNotFoundError:
        err(f"NOT_FOUND: {cmd[0]}")
        return None


def ollama_generate(model, prompt, images=None, timeout=120):
    import urllib.request
    payload = {
        "model": model, "prompt": prompt,
        "stream": False, "options": {"temperature": 0.3},
    }
    if images:
        payload["images"] = images
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return result.get("response", "")
    except Exception as e:
        err(f"OLLAMA_GEN_FAIL: {e}")
        return None


def ollama_chat(model, messages, timeout=120):
    import urllib.request
    payload = {
        "model": model, "messages": messages,
        "stream": False, "options": {"temperature": 0.5},
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return result.get("message", {}).get("content", "")
    except Exception as e:
        err(f"OLLAMA_CHAT_FAIL: {e}")
        return None


def get_video_info(video_path):
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(video_path),
    ]
    out = run_cmd(cmd, "READ_VIDEO_INFO")
    if not out:
        return None
    try:
        return float(json.loads(out)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        err(f"PARSE_VIDEO_INFO_FAIL: {e}")
        return None


def extract_frames(video_path, output_dir, fps=1):
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(output_dir / "frame_%03d.jpg")
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", f"fps={fps},scale=1080:-1",
        "-frame_pts", "1",
        "-y", pattern,
    ]
    if run_cmd(cmd, "EXTRACT_FRAMES") is None:
        return False
    frames = sorted(output_dir.glob("frame_*.jpg"))
    info(f"  extracted {len(frames)} frames")
    return len(frames)


def frame_to_base64(frame_path):
    import base64
    with open(frame_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def analyze_frames(frame_dir, duration):
    frames = sorted(frame_dir.glob("frame_*.jpg"))
    if not frames:
        err("no frames to analyze")
        return None
    if len(frames) > 8:
        step = len(frames) / 8
        frames = [frames[int(i * step)] for i in range(8)]

    timeline = []
    total = len(frames)
    for i, fp in enumerate(frames):
        ts = i * (duration / total)
        info(f"  analyzing frame {i+1}/{total} (t={ts:.1f}s)")
        b64 = frame_to_base64(fp)
        prompt = (
            "Describe this screen recording frame in one short sentence "
            "(Chinese, <20 chars). Identify the UI and function shown."
        )
        desc = ollama_generate(VL_MODEL, prompt, images=[b64], timeout=120)
        timeline.append({
            "time": round(ts, 1),
            "description": (desc or "(failed)").strip(),
        })
    return timeline


def cmd_analyze(args):
    video_path = Path(args.video)
    if not video_path.exists():
        err(f"video not found: {video_path}")
        return 1

    basename = video_path.stem
    work_dir = TEMP_BASE / basename
    work_dir.mkdir(parents=True, exist_ok=True)
    analysis_file = work_dir / "analysis.json"

    duration = get_video_info(video_path)
    if duration is None:
        return 1
    info(f"duration: {duration:.1f}s")

    frames_dir = work_dir / "frames"
    if not extract_frames(video_path, frames_dir, fps=args.fps):
        return 1

    timeline = analyze_frames(frames_dir, duration)
    if not timeline:
        return 1

    result = {
        "video": str(video_path),
        "basename": basename,
        "duration": duration,
        "fps": args.fps,
        "timeline": timeline,
    }
    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    info(f"\nOK analysis -> {analysis_file}")
    info("timeline:")
    for t in timeline:
        print(f"  t={t['time']:5.1f}s  {t['description']}")
    return 0


def cmd_draft(args):
    analysis_path = Path(args.analysis)
    if not analysis_path.exists():
        err(f"analysis not found: {analysis_path}")
        return 1

    with open(analysis_path, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    duration = analysis["duration"]
    timeline = analysis["timeline"]
    basename = analysis["basename"]
    target_chars = int(duration * CHARS_PER_SEC)

    timeline_text = "\n".join(
        f"  [{t['time']:.1f}s] {t['description']}" for t in timeline
    )

    lang = getattr(args, "lang", "zh")
    lang_instruction = (
        f"Write in Traditional Chinese, ~{target_chars} characters "
        f"(={duration:.0f}s narration)."
        if lang == "zh" else
        f"Use English, ~{int(duration * 2.5)} words."
    )

    system_prompt = (
        "Professional narration script writer. "
        "Write a smooth voiceover script matching the video timeline.\n"
        "Rules:\n"
        "1. Match visual pacing\n"
        "2. Professional yet direct tone\n"
        "3. Stay within target length\n"
        "4. Output ONLY the script text, no labels or notes"
    )
    user_prompt = (
        f"Video timeline analysis:\n\n{timeline_text}\n\n"
        f"Duration: {duration:.0f}s\n{lang_instruction}\n\n"
        "Write a complete continuous narration script (no timestamps)."
    )

    info(f"generating script (~{target_chars} chars, model={LLM_MODEL})")
    script = ollama_chat(LLM_MODEL, [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ], timeout=180)

    if not script:
        err("script generation failed")
        return 1

    script = script.strip()
    actual_chars = len(script.replace(" ", "").replace("\n", ""))
    est_dur = actual_chars / CHARS_PER_SEC
    info(f"  {actual_chars} chars, est {est_dur:.1f}s narration")

    out_dir = Path(args.output) if args.output else Path(analysis_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{basename}_narration.md"

    md_content = (
        f"---\n"
        f"lastUpdate: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"author: AI Generated\n"
        f"version: 1.0.0\n"
        f"source_video: {analysis['video']}\n"
        f"duration: {duration:.1f}s\n"
        f"chars: {actual_chars}\n"
        f"estimated_narration_sec: {est_dur:.1f}\n"
        f"---\n\n"
        f"# {basename} - Narration Script\n\n"
        f"## Script ({actual_chars} chars / ~{est_dur:.0f}s)\n\n"
        f"{script}\n\n"
        f"## Timeline\n\n"
        f"{timeline_text}\n\n"
        f"---\n\n"
        f"## Changelog\n"
        f"| Date | Version | Author | Changes |\n"
        f"|------|---------|--------|---------|\n"
        f"| {time.strftime('%Y-%m-%d')} | 1.0.0 | AI Generated | Initial |\n"
    )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    info(f"\nOK script -> {md_path}")
    print(f"\n=== SCRIPT ===\n{script}\n==============")
    return 0


def call_tts(text, voice_id, speed, output_path):
    import urllib.request
    payload = {
        "text": text,
        "engine": "qwen3",
        "voice_id": voice_id,
        "speed": speed,
        "qwen_speaker": None,
        "qwen_instruct": "Professional and serious tone.",
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{TTS_API_URL}/v1/tts/generate", data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode())
    except Exception as e:
        err(f"TTS_API_FAIL: {e}")
        return None

    audio_url = result.get("audio_url")
    tts_dur = result.get("duration", 0)
    if not audio_url:
        err("TTS returned no audio_url")
        return None

    try:
        with urllib.request.urlopen(f"{TTS_API_URL}{audio_url}", timeout=120) as resp:
            with open(output_path, "wb") as f:
                f.write(resp.read())
    except Exception as e:
        err(f"AUDIO_DL_FAIL: {e}")
        return None
    return tts_dur


def merge_video_audio(video_path, audio_path, output_path):
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "libx264", "-c:a", "aac",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", "-y", str(output_path),
    ]
    return run_cmd(cmd, "MERGE") is not None


def start_tts_service():
    dir_ = Path("/Users/daniel/GitHub/VoiceTTS/ai-services")
    python = dir_ / ".venv" / "bin" / "python3"
    cmd = [
        str(python), "-m", "uvicorn",
        "tts.main:app", "--port", "5001", "--host", "0.0.0.0",
    ]
    info("starting TTS service (background)...")
    try:
        subprocess.Popen(
            cmd, cwd=str(dir_),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        err(f"TTS_START_FAIL: {e}")
        return False


def extract_narration(script_path):
    """Parse .md script and extract the narration text from the ## Script section."""
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
    body = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)
    m = re.search(r'## Script.*?\n\n(.*?)(?:\n\n##|\Z)', body, re.DOTALL)
    if m:
        narration = m.group(1).strip()
    else:
        lines = body.strip().split("\n")
        narration = "\n".join(
            l for l in lines
            if l.strip() and not l.startswith("#") and not l.startswith("|")
        ).strip()
    return narration


def cmd_tts(args):
    """Step 3: script.md -> Qwen3-TTS -> .wav audio (separate track)."""
    script_path = Path(args.script)
    if not script_path.exists():
        err(f"script not found: {script_path}")
        return 1

    narration = extract_narration(script_path)
    if not narration:
        err("could not extract script text")
        return 1
    info(f"narration: {narration[:100]}... ({len(narration)} chars)")

    output_path = Path(args.output) if args.output else script_path.with_suffix(".wav")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    info(f"TTS (voice={args.voice}, speed={args.speed})")
    tts_dur = call_tts(narration, args.voice, args.speed, output_path)
    if tts_dur is None:
        warn("TTS unreachable, attempting to start...")
        start_tts_service()
        time.sleep(5)
        tts_dur = call_tts(narration, args.voice, args.speed, output_path)
        if tts_dur is None:
            err("TTS failed")
            info("manual: cd ../VoiceTTS/ai-services && source .venv/bin/activate && uvicorn tts.main:app --port 5001")
            return 1

    info(f"\nOK audio: {output_path} ({tts_dur:.1f}s)")
    return 0


def cmd_merge(args):
    """Step 4: video + audio -> ffmpeg merge."""
    video_path = Path(args.video)
    audio_path = Path(args.audio)
    if not video_path.exists() or not audio_path.exists():
        err("video or audio not found")
        return 1

    output_path = Path(args.output) if args.output else video_path.with_suffix(".mp4").name
    info(f"merging: {video_path.name} + {audio_path.name} -> {output_path}")
    if merge_video_audio(video_path, audio_path, output_path):
        info(f"\nOK output: {output_path}")
    else:
        err("merge failed")
        return 1
    return 0


def cmd_all(args):
    video_path = Path(args.video)
    if not video_path.exists():
        err(f"video not found: {video_path}")
        return 1

    basename = video_path.stem
    work_dir = TEMP_BASE / basename
    work_dir.mkdir(parents=True, exist_ok=True)
    analysis_file = work_dir / "analysis.json"
    script_file = work_dir / f"{basename}_narration.md"
    audio_file = work_dir / f"{basename}_narration.wav"
    output_file = Path(args.output) if args.output else Path(f"{basename}_final.mp4")

    if not analysis_file.exists():
        info("=" * 50)
        info("Step 1/4: analyze")
        info("=" * 50)
        sa = argparse.Namespace(video=args.video, fps=args.fps)
        if cmd_analyze(sa) != 0:
            return 1
    else:
        info(f"skip analysis: {analysis_file}")

    if not script_file.exists():
        info("=" * 50)
        info("Step 2/4: draft")
        info("=" * 50)
        sd = argparse.Namespace(
            analysis=str(analysis_file), output=str(work_dir), lang=args.lang
        )
        if cmd_draft(sd) != 0:
            return 1
    else:
        info(f"skip draft: {script_file}")

    info("=" * 50)
    info("Step 3/4: tts")
    info("=" * 50)
    st = argparse.Namespace(
        script=str(script_file), voice=args.voice,
        speed=args.speed, output=str(audio_file),
    )
    if cmd_tts(st) != 0:
        return 1

    info("=" * 50)
    info("Step 4/4: merge")
    info("=" * 50)
    sm = argparse.Namespace(
        video=args.video, audio=str(audio_file), output=str(output_file),
    )
    if cmd_merge(sm) != 0:
        return 1

    info(f"\nDONE: {output_file}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="EEA Video Narration Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python video_narration_pipeline.py all "EEA va LINE 整合.mov"
  python video_narration_pipeline.py analyze "video.mov" --fps 0.5
  python video_narration_pipeline.py draft analysis.json --lang zh
  python video_narration_pipeline.py produce "video.mov" script.md --voice zh_tw_ting
        """,
    )
    parser.add_argument("--fps", type=float, default=1)
    parser.add_argument("--voice", default="zh_tw_ting")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--lang", default="zh", choices=["zh", "en"])
    parser.add_argument("--output", "-o")

    sub = parser.add_subparsers(dest="command")
    p_a = sub.add_parser("analyze", help="Step 1: extract frames + Qwen3-VL analysis")
    p_a.add_argument("video")
    p_d = sub.add_parser("draft", help="Step 2: generate narration script from analysis")
    p_d.add_argument("analysis")
    p_t = sub.add_parser("tts", help="Step 3: script -> TTS audio .wav (separate)")
    p_t.add_argument("script")
    p_m = sub.add_parser("merge", help="Step 4: video + audio -> final video")
    p_m.add_argument("video")
    p_m.add_argument("audio")
    p_all = sub.add_parser("all", help="full pipeline: analyze + draft + tts + merge")
    p_all.add_argument("video")

    args = parser.parse_args()
    TEMP_BASE.mkdir(parents=True, exist_ok=True)

    return {
        "analyze": cmd_analyze,
        "draft": cmd_draft,
        "tts": cmd_tts,
        "merge": cmd_merge,
        "all": cmd_all,
    }.get(args.command, lambda _: parser.print_help() or 1)(args)


if __name__ == "__main__":
    sys.exit(main())
