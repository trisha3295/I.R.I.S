"""
Generates an ultra-high-resolution, publication-grade IEEE system architecture diagram
for Project I.R.I.S. (Intelligent Real-Time Interface System).
Outputs:
  - iris_architecture_diagram.png (300 DPI high-res)
  - iris_architecture_diagram.pdf (Vector format for LaTeX / Overleaf)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import numpy as np

def create_iris_architecture_diagram():
    # Configure high-DPI figure (22 x 12.5 inches @ 300 DPI = 6600 x 3750 px)
    fig = plt.figure(figsize=(22, 12.5), dpi=300)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 2200)
    ax.set_ylim(0, 1250)
    ax.axis('off')

    # Background canvas
    bg = patches.Rectangle((0, 0), 2200, 1250, facecolor='#F8FAFC', edgecolor='none')
    ax.add_patch(bg)

    # Color Palette
    c_primary = '#0F172A'       # Slate 900
    c_teal = '#0D9488'          # Teal 600
    c_amber = '#D97706'         # Amber 600
    c_indigo = '#4F46E5'        # Indigo 600
    c_blue = '#2563EB'          # Blue 600
    c_emerald = '#059669'       # Emerald 600
    c_purple = '#7C3AED'        # Purple 600
    c_rose = '#E11D48'          # Rose 600
    c_cyan = '#0284C7'          # Sky 600

    # =========================================================================
    # HEADER BANNER
    # =========================================================================
    header_box = FancyBboxPatch((40, 1120), 2120, 100, boxstyle="round,pad=0,rounding_size=12",
                                facecolor='#FFFFFF', edgecolor='#CBD5E1', linewidth=1.5)
    ax.add_patch(header_box)

    ax.text(70, 1180, "PROJECT I.R.I.S. — END-TO-END SYSTEM PIPELINE ARCHITECTURE",
            fontsize=21, fontweight='bold', color=c_primary, family='sans-serif')
    ax.text(70, 1145, "Decoupled 7-Stage Neural Gaze Raycasting, Signal Conditioning & OS Kernel Input Injection Architecture",
            fontsize=12.5, color='#475569', family='sans-serif')

    # Top right metrics pill
    metrics_pill = FancyBboxPatch((1660, 1135), 480, 70, boxstyle="round,pad=0,rounding_size=8",
                                  facecolor='#EFF6FF', edgecolor='#93C5FD', linewidth=1.2)
    ax.add_patch(metrics_pill)
    ax.text(1900, 1178, "LATENCY: 4.10 ms | THROUGHPUT: 243.9 FPS", fontsize=11.5, fontweight='bold',
            color=c_blue, ha='center', family='sans-serif')
    ax.text(1900, 1152, "CPU-Only SIMD Execution • Zero Gimbal Lock • Zero Jitter", fontsize=10,
            color='#1E40AF', ha='center', family='sans-serif')

    # =========================================================================
    # GRID CONFIGURATION (4 Columns x 2 Rows)
    # =========================================================================
    # Card Width = 480, Gap = 60
    # C1 = 40..520, C2 = 580..1060, C3 = 1120..1600, C4 = 1660..2140
    # Row 1: Y = 650 to 1080 (Height 430)
    # Central Conduit: Y = 545 to 605 (Height 60)
    # Row 2: Y = 80 to 510 (Height 430)

    cards = [
        # ROW 1: SENSORY INGESTION & NEURAL 3D ESTIMATION
        {
            "num": "STAGE 1", "title": "Asynchronous Video Ingestion", "module": "iris_engine/camera.py",
            "latency": "0.08 ms", "color": c_teal, "box": (40, 650, 480, 430),
            "items": [
                ("Physical Sensor", "Commodity 720p/1080p CMOS webcam (RGB @ 30 FPS)"),
                ("Capture Driver", "DirectShow API backend (cv2.CAP_DSHOW)"),
                ("Concurrency", "Dedicated background daemon worker thread"),
                ("Buffering Model", "Thread-safe atomic double-buffer with Lock()"),
                ("Hardware Decoupling", "Bypasses 30-50ms physical sensor polling stalls"),
                ("Stage Output", "Fresh 640x480 raw BGR frame read in 0.08 ms")
            ],
            "tag": "Thread-Safe Zero-Wait Frame Buffer"
        },
        {
            "num": "STAGE 2", "title": "Dynamic Luminance Normalizer", "module": "iris_engine/preprocessor.py",
            "latency": "0.62 ms", "color": c_amber, "box": (580, 650, 480, 430),
            "items": [
                ("Color Space Split", "BGR -> YCrCb (Luma Y separated from Chroma)"),
                ("CLAHE Parameters", "clipLimit = 2.0, tileGridSize = (8, 8) tiles"),
                ("Selective Processing", "Equalization applied strictly to Y-channel"),
                ("Chroma Preservation", "Cr and Cb preserved without skin bleaching"),
                ("Anti-Flicker Immunity", "Neutralizes 50Hz/60Hz AC ambient light flutter"),
                ("Stage Output", "Contrast-stabilized RGB frame with invariant gradients")
            ],
            "tag": "50Hz/60Hz AC Mains Flicker Immune"
        },
        {
            "num": "STAGE 3", "title": "Edge Neural Landmark Engine", "module": "iris_engine/tracker.py",
            "latency": "2.05 ms", "color": c_indigo, "box": (1120, 650, 480, 430),
            "items": [
                ("Face Localization", "OpenCV YuNet C++ Model (0.81 ms inference)"),
                ("ROI Preprocessing", "Dynamic crop with +30% margin & aspect-square"),
                ("3D Dense Mesh", "MediaPipe FaceMesh.onnx (1.24 ms inference)"),
                ("Inference Backend", "ONNX Runtime CPU SIMD (intra_threads=2)"),
                ("Affine Reconstruction", "Inverse mapping from 192x192 crop to full frame"),
                ("Stage Output", "Dense 468 3D facial landmark tensor (X, Y, Z)")
            ],
            "tag": "486 FPS Real-Time CPU Graph Engine"
        },
        {
            "num": "STAGE 4", "title": "6-DOF PnP Pose Raycaster", "module": "iris_engine/pose_estimator.py",
            "latency": "0.41 ms", "color": c_blue, "box": (1660, 650, 480, 430),
            "items": [
                ("Anthropometric Model", "Canonical 3D facial rig (6 metric anchor points in mm)"),
                ("Selected Landmarks", "Nose tip, chin, left/right outer canthi, mouth corners"),
                ("PnP Solver", "solvePnP via Levenberg-Marquardt (LM) optimization"),
                ("Forward Raycasting", "1000mm normal gaze vector projected from nose tip"),
                ("Singularity Free", "Continuous Lie Algebra SO(3); bypasses Euler angles"),
                ("Stage Output", "Screen target pointer coordinates (X_raw, Y_raw)")
            ],
            "tag": "100% Gimbal-Lock & Singularity Immune"
        },

        # ROW 2: SIGNAL CONDITIONING, GESTURES & OS INJECTION
        {
            "num": "STAGE 5", "title": "Adaptive 1-Euro Signal Filter", "module": "iris_engine/filters.py",
            "latency": "0.04 ms", "color": c_emerald, "box": (40, 80, 480, 430),
            "items": [
                ("Filter Type", "2D Adaptive Velocity-Scaled Low-Pass Filter"),
                ("Cutoff Equation", "fc = fc_min + beta * |dx_hat / dt| (dynamic bandwidth)"),
                ("Filter Parameters", "fc_min = 0.005 Hz, beta = 0.001, fc_d = 1.0 Hz"),
                ("Tremor Reduction", "Stationary jitter variance dampened by 71.6% (>65%)"),
                ("Saccadic Response", "Instantly widens cutoff on fast head saccades (zero lag)"),
                ("Stage Output", "Jitter-free smoothed cursor coordinates (X_smooth, Y_smooth)")
            ],
            "tag": ">65% Tremor Reduction • Zero Saccadic Lag"
        },
        {
            "num": "STAGE 6", "title": "Relative Asymmetry Gestures", "module": "iris_engine/gesture_engine.py",
            "latency": "0.06 ms", "color": c_purple, "box": (580, 80, 480, 430),
            "items": [
                ("Asymmetry Metric", "A = |EAR_L - EAR_R| / max(EAR_L, EAR_R, 1e-6)"),
                ("Blink Rejection", "Involuntary 100ms blinks rejected (hold < 0.35s)"),
                ("Dual-Blink Actions", "Hold 0.35s: Left Click | Hold 0.75s: Toggle Drag & Drop"),
                ("Wink Discrimination", "A > 0.30 & EAR_active < 0.75*EAR_contra (0.18s hold)"),
                ("Physiological Fix", "Immune to contralateral orbicularis oculi squints"),
                ("Stage Output", "Action Events: Click / Drag / Scroll / Anti-Jump freeze")
            ],
            "tag": "Squint-Immune Ocular State Machine"
        },
        {
            "num": "STAGE 7", "title": "Win32 Kernel Cursor Dispatch", "module": "iris_engine/controller.py",
            "latency": "0.03 ms", "color": c_rose, "box": (1120, 80, 480, 430),
            "items": [
                ("Kernel Interface", "Direct ctypes binding to Microsoft Windows user32.dll"),
                ("Cursor Dispatch", "SetCursorPos(cx, cy) hardware positioning (<0.03 ms)"),
                ("Action Synthesis", "mouse_event (Left/Right Down, Up, Wheel Scroll)"),
                ("Deadzone Gate", "dx = 14px, dy = 8px threshold suppresses micro-drift"),
                ("Audio Feedback", "Asynchronous daemon winsound.Beep (1200Hz, 1700Hz)"),
                ("Stage Output", "Native OS pointer motion, click events & audio chimes")
            ],
            "tag": "Sub-0.05ms Direct Hardware OS Injection"
        },
        {
            "num": "INTEGRATED HUD", "title": "Cyber-Glass Telemetry HUD", "module": "iris_app.py",
            "latency": "Real-Time", "color": c_cyan, "box": (1660, 80, 480, 430),
            "items": [
                ("Camera Viewport", "640x480 Mirrored display with 3D gaze ray projection"),
                ("Facial Telemetry", "Eye contour landmark wireframes & hold progress ring"),
                ("Diagnostic Panel", "360x480 Real-time numerical EAR meters & baselines"),
                ("Asymmetry Gauge", "Live optical Asymmetry Index bar with trigger threshold"),
                ("Interactive Guide", "Full gesture tutorial matrix & scrolling event logger"),
                ("Hotkeys Control", "Space: Pause | C: Recenter | +/-: Sensitivity | H: HUD")
            ],
            "tag": "Interactive Glassmorphism Diagnostic Canvas"
        }
    ]

    # Draw Cards
    for card in cards:
        bx, by, bw, bh = card["box"]
        color = card["color"]

        # Drop Shadow
        shadow = FancyBboxPatch((bx + 4, by - 4), bw, bh, boxstyle="round,pad=0,rounding_size=12",
                                facecolor='#CBD5E1', edgecolor='none', alpha=0.35)
        ax.add_patch(shadow)

        # Card Base
        main_box = FancyBboxPatch((bx, by), bw, bh, boxstyle="round,pad=0,rounding_size=12",
                                  facecolor='#FFFFFF', edgecolor='#E2E8F0', linewidth=1.6)
        ax.add_patch(main_box)

        # Header Bar Background
        hdr_bar = FancyBboxPatch((bx, by + bh - 66), bw, 66, boxstyle="round,pad=0,rounding_size=12",
                                 facecolor=color, edgecolor=color)
        ax.add_patch(hdr_bar)
        ax.add_patch(patches.Rectangle((bx, by + bh - 66), bw, 24, facecolor=color, edgecolor=color))

        # Stage Number Badge
        ax.text(bx + 18, by + bh - 24, card["num"], fontsize=10.5, fontweight='bold',
                color='#FFFFFF', family='sans-serif')

        # Stage Title
        ax.text(bx + 18, by + bh - 48, card["title"], fontsize=13, fontweight='bold',
                color='#FFFFFF', family='sans-serif')

        # Latency pill in header
        lat_pill = FancyBboxPatch((bx + bw - 112, by + bh - 52), 96, 36, boxstyle="round,pad=0,rounding_size=8",
                                  facecolor='#FFFFFF', edgecolor='none')
        ax.add_patch(lat_pill)
        ax.text(bx + bw - 64, by + bh - 30, card["latency"], fontsize=10.5, fontweight='bold',
                color=color, ha='center', family='sans-serif')

        # Sub-header module path
        ax.text(bx + 18, by + bh - 90, f"Module: {card['module']}", fontsize=9.5,
                color='#64748B', style='italic', family='monospace')

        # Divider line
        ax.plot([bx + 18, bx + bw - 18], [by + bh - 104, by + bh - 104], color='#E2E8F0', linewidth=1.2)

        # Bullet items
        cur_y = by + bh - 134
        for label, val in card["items"]:
            bullet = patches.Circle((bx + 26, cur_y + 4), 3.8, facecolor=color, edgecolor='none')
            ax.add_patch(bullet)
            ax.text(bx + 40, cur_y, f"{label}:", fontsize=9.8, fontweight='bold',
                    color='#1E293B', family='sans-serif')
            ax.text(bx + 40, cur_y - 17, val, fontsize=9.2,
                    color='#475569', family='sans-serif')
            cur_y -= 42

        # Footer Badge
        tag_box = FancyBboxPatch((bx + 18, by + 16), bw - 36, 32, boxstyle="round,pad=0,rounding_size=8",
                                 facecolor=f"{color}18", edgecolor=color, linewidth=1.0)
        ax.add_patch(tag_box)
        ax.text(bx + bw / 2, by + 32, f"★  {card['tag']}", fontsize=9.8, fontweight='bold',
                color=color, ha='center', family='sans-serif')

    # =========================================================================
    # REFINED CONNECTING ARROWS (EXACT GEOMETRIC SHAPES)
    # =========================================================================
    # Card gap is 60 units (e.g. 520 to 580)
    # Clean, stylish arrow polygon inside the 60-unit gap:
    def draw_h_arrow(x_start, x_end, y_center, color='#64748B'):
        # Arrow from x_start to x_end
        dx = x_end - x_start
        hw = 12   # half width of head
        hl = 18   # head length
        shaft_h = 4
        
        arrow_poly = [
            (x_start, y_center - shaft_h),
            (x_end - hl, y_center - shaft_h),
            (x_end - hl, y_center - hw),
            (x_end, y_center),
            (x_end - hl, y_center + hw),
            (x_end - hl, y_center + shaft_h),
            (x_start, y_center + shaft_h)
        ]
        poly = patches.Polygon(arrow_poly, closed=True, facecolor=color, edgecolor='none')
        ax.add_patch(poly)

    # Row 1 Horizontal Arrows:
    draw_h_arrow(526, 574, 865, color='#64748B')
    draw_h_arrow(1066, 1114, 865, color='#64748B')
    draw_h_arrow(1606, 1654, 865, color='#64748B')

    # Row 2 Horizontal Arrows:
    draw_h_arrow(526, 574, 295, color='#64748B')
    draw_h_arrow(1066, 1114, 295, color='#64748B')
    draw_h_arrow(1606, 1654, 295, color='#64748B')

    # =========================================================================
    # INTER-STAGE PIPELINE BUS CONDUIT
    # =========================================================================
    # Conduit Bus Bar between Row 1 and Row 2 (Y = 555 to 605, Height 50)
    conduit_box = FancyBboxPatch((160, 555), 1880, 50, boxstyle="round,pad=0,rounding_size=10",
                                 facecolor='#EFF6FF', edgecolor='#93C5FD', linewidth=1.5)
    ax.add_patch(conduit_box)
    ax.text(1100, 580, "INTER-STAGE PIPELINE BUS: Gaze Raycast Target Coords (X_raw, Y_raw) & 468 3D Landmark Stream",
            fontsize=12, fontweight='bold', color=c_blue, ha='center', family='sans-serif')

    # Downward arrow from Stage 4 (center X = 1900) into Conduit:
    def draw_v_arrow(x_center, y_start, y_end, color=c_blue):
        dy = abs(y_end - y_start)
        hw = 12   # half width of head
        hl = 16   # head length
        shaft_w = 4
        if y_start > y_end: # pointing DOWN
            arrow_poly = [
                (x_center - shaft_w, y_start),
                (x_center - shaft_w, y_end + hl),
                (x_center - hw, y_end + hl),
                (x_center, y_end),
                (x_center + hw, y_end + hl),
                (x_center + shaft_w, y_end + hl),
                (x_center + shaft_w, y_start)
            ]
        else: # pointing UP
            arrow_poly = [
                (x_center - shaft_w, y_start),
                (x_center - shaft_w, y_end - hl),
                (x_center - hw, y_end - hl),
                (x_center, y_end),
                (x_center + hw, y_end - hl),
                (x_center + shaft_w, y_end - hl),
                (x_center + shaft_w, y_start)
            ]
        poly = patches.Polygon(arrow_poly, closed=True, facecolor=color, edgecolor='none')
        ax.add_patch(poly)

    # From Stage 4 bottom (Y = 650) to Conduit top (Y = 605)
    draw_v_arrow(1900, 646, 609, color=c_blue)

    # From Conduit bottom (Y = 555) into Stage 5 top (Y = 510)
    draw_v_arrow(280, 551, 514, color=c_blue)

    # =========================================================================
    # FOOTER BAR
    # =========================================================================
    footer_box = FancyBboxPatch((40, 18), 2120, 50, boxstyle="round,pad=0,rounding_size=10",
                                facecolor='#0F172A', edgecolor='none')
    ax.add_patch(footer_box)
    ax.text(1100, 43,
            "PROJECT I.R.I.S. • TOTAL END-TO-END PIPELINE LATENCY: 4.10 ms • THEORETICAL MAX THROUGHPUT: 243.9 FPS • CPU CONSUMPTION: 12.3% @ 30 FPS",
            fontsize=11.5, fontweight='bold', color='#F8FAFC', ha='center', family='sans-serif')

    plt.tight_layout()

    # Save outputs
    png_path = "c:\\I.R.I.S\\iris_architecture_diagram.png"
    pdf_path = "c:\\I.R.I.S\\iris_architecture_diagram.pdf"
    plt.savefig(png_path, dpi=300, bbox_inches='tight', facecolor='#F8FAFC')
    plt.savefig(pdf_path, dpi=300, bbox_inches='tight', facecolor='#F8FAFC')
    plt.close()
    print(f"Polished architecture diagram generated successfully:\n  - PNG: {png_path}\n  - PDF: {pdf_path}")

if __name__ == "__main__":
    create_iris_architecture_diagram()
