"""Live demo (Hugging Face Space, CPU): upload a road-camera clip, get the events back.

Runs the same pipeline as the submission with the light "demo" profile (YOLO11n, ~6 processed
frames per second), then renders an annotated video, the event timeline and the Part B risk curve.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# In the repository the app lives in demo/; prepare_space.sh copies it next to src/.
ROOT = HERE if (HERE / "src").is_dir() else HERE.parent
sys.path.insert(0, str(ROOT / "src"))

import gradio as gr  # noqa: E402
import plotly.graph_objects as go  # noqa: E402

from trafficwatch import CLASSES  # noqa: E402
from trafficwatch.config import load_config  # noqa: E402
from trafficwatch.pipeline import analyze  # noqa: E402
from trafficwatch.risk import risk_curve_from_perception  # noqa: E402
from trafficwatch.video import probe  # noqa: E402
from trafficwatch.viz import render_video  # noqa: E402

BLUE, INK_MUTED, GRID = "#2a78d6", "#898781", "#e1e0d9"
MAX_DURATION_S = 120.0
MAX_UPLOAD_BYTES = 500 * 1024 * 1024
# Gradio 5.50's age check uses timedelta.seconds (modulo 24 hours), so an age
# of 86400 never expires while the server runs. Check hourly with a six-hour TTL.
CACHE_MAX_AGE_S = 6 * 60 * 60


def timeline_figure(events: list[list], times, scores, duration: float) -> go.Figure:
    fig = go.Figure()
    labels = [c for c in CLASSES if any(e[2] == c for e in events)]
    for s, e, label in events:
        fig.add_trace(go.Bar(x=[e - s], base=[s], y=[label], orientation="h", marker_color=BLUE, width=0.6,
                             hovertemplate=f"{label}<br>{s:.1f}–{e:.1f} s<extra></extra>", showlegend=False))
    fig.add_trace(go.Scatter(x=list(times), y=list(scores), yaxis="y2", mode="lines", name="risk",
                             line=dict(color=BLUE, width=2), hovertemplate="%{x:.1f}s risk %{y:.2f}<extra></extra>"))
    fig.update_layout(
        height=260 + 22 * len(labels), margin=dict(l=10, r=10, t=10, b=30), barmode="overlay",
        xaxis=dict(title="seconds", range=[0, duration], gridcolor=GRID, linecolor=INK_MUTED),
        yaxis=dict(domain=[0.38, 1.0], categoryorder="array", categoryarray=labels[::-1] or ["no events"],
                   gridcolor=GRID),
        yaxis2=dict(domain=[0.0, 0.28], range=[0, 1], title="accident risk", gridcolor=GRID, tickvals=[0, 0.5, 1]),
        shapes=[dict(type="line", xref="x", yref="y2", x0=0, x1=duration, y0=0.5, y1=0.5,
                     line=dict(color=INK_MUTED, dash="dot", width=1))],  # alarm threshold 0.5
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def run(video_path: str, progress=gr.Progress()):
    if not video_path:
        raise gr.Error("Upload an .mp4 first.")
    path = Path(video_path)
    if path.suffix.lower() != ".mp4":
        raise gr.Error("Only .mp4 files are accepted.")
    t0 = time.perf_counter()
    try:
        if path.stat().st_size > MAX_UPLOAD_BYTES:
            raise gr.Error("The public demo accepts files up to 500 MB.")
        info = probe(video_path)
    except OSError as exc:
        raise gr.Error("The uploaded file is not a readable MP4 video.") from exc
    if info.n_frames <= 0 or info.width <= 0 or info.height <= 0:
        raise gr.Error("The uploaded video has no readable frames.")
    if info.duration > MAX_DURATION_S + 0.1:
        raise gr.Error(f"The public demo accepts clips up to {MAX_DURATION_S / 60:.0f} minutes.")
    cfg = load_config()
    progress(0.02, desc="Detecting and tracking road users")
    result = analyze(video_path, cfg, profile="demo", progress=lambda f: progress(0.02 + 0.55 * f, desc="Detecting and tracking"))
    progress(0.6, desc="Part B: accident risk")
    times, scores = risk_curve_from_perception(result.perception, cfg)
    progress(0.65, desc="Rendering annotated video")
    # Gradio copies returned files into its cache; unmanaged temporary originals
    # would otherwise accumulate forever. Clean the workspace even if rendering
    # fails, and register successful outputs before removing their originals.
    with tempfile.TemporaryDirectory(prefix="trafficwatch-render-") as work_dir:
        out_mp4 = Path(work_dir) / "annotated.mp4"
        render_video(video_path, result.perception, result.scene, result.events, result.raw_events, str(out_mp4),
                     risk=(times, scores), max_width=854, progress=lambda f: progress(0.65 + 0.33 * f, desc="Rendering"))
        out_json = Path(work_dir) / "events.json"
        with out_json.open("w") as f:
            json.dump({"events": result.events, "risk": [[round(float(t), 2), round(float(s), 3)] for t, s in zip(times, scores)]}, f)
        cached_mp4 = out_video.move_resource_to_block_cache(out_mp4)
        cached_json = download.move_resource_to_block_cache(out_json)
    duration = result.perception.info.duration
    table = [[s, e, label, round(e - s, 2)] for s, e, label in result.events]
    elapsed = time.perf_counter() - t0
    summary = (f"**{len(result.events)} events** in {duration:.1f} s of video "
               f"({info.width}×{info.height} @ {info.fps:.0f} fps), processed in {elapsed:.0f} s on CPU.")
    progress(1.0, desc="Ready")
    return summary, cached_mp4, timeline_figure(result.events, times, scores, duration), table, cached_json


with gr.Blocks(title="TrafficWatch live demo", theme=gr.themes.Soft(), analytics_enabled=False,
               delete_cache=(3600, CACHE_MAX_AGE_S)) as demo:
    gr.Markdown("## TrafficWatch · live demo\nUpload an MP4 clip from the road camera (up to **2 minutes / 500 MB**). "
                "The whole clip is analysed on CPU and progress is shown while it runs.")
    with gr.Row():
        with gr.Column(scale=1):
            # format=None: the file is analysed as uploaded (format="mp4" made Gradio re-encode every
            # .MP4 upload, which takes longer than the analysis itself for a large 4K file)
            inp = gr.Video(label="Input clip", sources=["upload"], format=None)
            btn = gr.Button("Detect events", variant="primary")
        with gr.Column(scale=2):
            summary = gr.Markdown()
            out_video = gr.Video(label="Annotated result", autoplay=False)
    plot = gr.Plot(label="Timeline and accident risk")
    table = gr.Dataframe(headers=["start_sec", "end_sec", "label", "length_s"], label="Events", wrap=True)
    download = gr.File(label="events.json")
    btn.click(run, inputs=inp, outputs=[summary, out_video, plot, table, download], concurrency_limit=1)

if __name__ == "__main__":
    demo.queue(max_size=8).launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)),
                                max_file_size=MAX_UPLOAD_BYTES)
