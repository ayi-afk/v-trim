
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import platform
import subprocess
import threading
import re
import time
import ctypes
import webbrowser
from PIL import Image, ImageTk

# --- DPI AWARENESS ---
if platform.system() == "Windows":
    try:
        # Set DPI Awareness before any Tkinter objects are created
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# --- COLOR UTILS ---
def lighten_color(hex_color, amount=0.15):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6: return "#ffffff"
    rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    new_rgb = [int(c + (255 - c) * amount) for c in rgb]
    return '#{:02x}{:02x}{:02x}'.format(*new_rgb)

# --- WINDOWS NATIVE AUDIO ---
class WindowsAudioPlayer:
    def __init__(self):
        self.alias = "vstudio_audio"
        self._is_open = False
        self.winmm = None
        if platform.system() == "Windows":
            self.winmm = ctypes.windll.winmm

    def _send_cmd(self, cmd):
        if not self.winmm: return
        self.winmm.mciSendStringW(cmd, None, 0, 0)

    def open(self, path):
        self.stop()
        path = os.path.abspath(path)
        self._send_cmd(f'open "{path}" type mpegvideo alias {self.alias}')
        self._is_open = True

    def play(self):
        if self._is_open:
            self._send_cmd(f'play {self.alias} from 0')

    def pause(self):
        if self._is_open:
            self._send_cmd(f'pause {self.alias}')

    def resume(self):
        if self._is_open:
            self._send_cmd(f'resume {self.alias}')

    def stop(self):
        if self._is_open:
            self._send_cmd(f'stop {self.alias}')
            self._send_cmd(f'close {self.alias}')
            self._is_open = False

# --- UI COMPONENTS ---

class ModernButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=80, height=30, bg="#1e293b", fg="#f8fafc", active_bg="#3b82f6", radius=10, font_size=8, **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, **kwargs)
        self.command = command
        self.text_str = text
        self.bg_color = bg
        self.fg_color = fg
        self.active_bg = active_bg
        self.radius = radius
        self.font_size = font_size
        self.is_active = False
        self.is_disabled = False
        
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.draw()

    def set_active(self, active):
        self.is_active = active
        self.draw()

    def set_text(self, text):
        self.text_str = text
        self.draw()

    def set_state(self, state):
        self.is_disabled = (state == "disabled")
        self.draw()

    def draw(self):
        self.delete("all")
        w = self.winfo_width() if self.winfo_width() > 1 else self.winfo_reqwidth()
        h = self.winfo_height() if self.winfo_height() > 1 else self.winfo_reqheight()
        base_color = "#0f172a" if self.is_disabled else (self.active_bg if self.is_active else self.bg_color)
        text_color = "#475569" if self.is_disabled else self.fg_color
        border_color = lighten_color(base_color, 0.15) if not self.is_disabled else "#1e293b"
        self._draw_rounded_rect(0, 0, w, h, self.radius, base_color, border_color)
        self.create_text(w//2, h//2, text=self.text_str, fill=text_color, font=("Segoe UI", self.font_size, "bold"))

    def _draw_rounded_rect(self, x, y, w, h, r, color, outline):
        self.create_oval(x, y, x+2*r, y+2*r, fill=color, outline=outline)
        self.create_oval(x+w-2*r, y, x+w, y+2*r, fill=color, outline=outline)
        self.create_oval(x, y+h-2*r, x+2*r, y+h, fill=color, outline=outline)
        self.create_oval(x+w-2*r, y+h-2*r, x+w, y+h, fill=color, outline=outline)
        self.create_rectangle(x+r, y, x+w-r, y+h, fill=color, outline=outline)
        self.create_rectangle(x, y+r, x+w, y+h-r, fill=color, outline=outline)
        self.create_rectangle(x+r, y+1, x+w-r, y+h-1, fill=color, outline=color)
        self.create_rectangle(x+1, y+r, x+w-1, y+h-r, fill=color, outline=color)

    def _on_click(self, event):
        if self.command and not self.is_disabled: self.command()

    def _on_enter(self, event):
        if not self.is_disabled and not self.is_active:
            w, h = self.winfo_width(), self.winfo_height()
            hover_bg = "#334155"
            hover_border = lighten_color(hover_bg, 0.15)
            self._draw_rounded_rect(0, 0, w, h, self.radius, hover_bg, hover_border)
            self.create_text(w//2, h//2, text=self.text_str, fill=self.fg_color, font=("Segoe UI", self.font_size, "bold"))

    def _on_leave(self, event):
        self.draw()

class RangeSlider(tk.Canvas):
    def __init__(self, parent, height=60, min_val=0, max_val=100, **kwargs):
        super().__init__(parent, height=height, bg="#030712", highlightthickness=0, **kwargs)
        self.min_val, self.max_val = min_val, max_val
        self.start_val, self.end_val = min_val, max_val
        self.padding = 30
        self.bar_y = height // 2
        self.on_change_callback = None
        self.active_handle = None
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<Button-1>", self.on_click)
        self.bind("<Configure>", lambda e: self.draw())

    def set_range(self, max_v):
        self.max_val = max_v
        self.start_val = 0.0
        self.end_val = max_v
        self.draw()

    def get_coords(self, val):
        w = self.winfo_width()
        ratio = (val - self.min_val) / (self.max_val - self.min_val) if self.max_val > self.min_val else 0
        return self.padding + ratio * (w - 2 * self.padding)

    def get_val(self, x):
        w = self.winfo_width()
        ratio = (x - self.padding) / (w - 2 * self.padding)
        val = self.min_val + ratio * (self.max_val - self.min_val)
        return max(self.min_val, min(self.max_val, val))

    def draw(self):
        self.delete("all")
        w = self.winfo_width()
        if w < 10: return
        x1, x2 = self.get_coords(self.start_val), self.get_coords(self.end_val)
        self.create_line(self.padding, self.bar_y, w - self.padding, self.bar_y, fill="#1e293b", width=8)
        self.create_line(x1, self.bar_y, x2, self.bar_y, fill="#3b82f6", width=8)
        self.create_oval(x1-12, self.bar_y-12, x1+12, self.bar_y+12, fill="#60a5fa", outline="white", width=2, tags="start")
        self.create_oval(x2-12, self.bar_y-12, x2+12, self.bar_y+12, fill="#60a5fa", outline="white", width=2, tags="end")

    def on_click(self, event):
        x1, x2 = self.get_coords(self.start_val), self.get_coords(self.end_val)
        self.active_handle = "start" if abs(event.x - x1) < abs(event.x - x2) else "end"

    def on_drag(self, event):
        val = self.get_val(event.x)
        if self.active_handle == "start": self.start_val = min(val, self.end_val - 0.1)
        else: self.end_val = max(val, self.start_val + 0.1)
        self.draw()
        if self.on_change_callback: self.on_change_callback(self.start_val, self.end_val, self.active_handle)

# --- APP CLASS ---

class VStudioPro:
    def __init__(self, root):
        self.root = root
        self.root.geometry("1200x900+100+100")
        self.root.configure(bg="#030712")
        self.root.overrideredirect(True)
        
        # Windows Taskbar Icon Logic: Standard Shadow Window Trick
        if platform.system() == "Windows":
            self.root.withdraw()
            self.taskbar_shadow = tk.Toplevel(self.root)
            self.taskbar_shadow.geometry("0x0+0+0")
            self.taskbar_shadow.overrideredirect(False) # Shows in taskbar
            self.taskbar_shadow.title("V-Studio Pro")
            self.taskbar_shadow.bind("<Map>", lambda e: self.root.deiconify())
            self.taskbar_shadow.bind("<Unmap>", lambda e: self.root.withdraw())
            # Close main when shadow is closed via taskbar (if it was a standard window)
            self.taskbar_shadow.protocol("WM_DELETE_WINDOW", self.on_close)

        self._drag_data = {"x": 0, "y": 0}
        self._resize_data = {"x": 0, "y": 0, "w": 0, "h": 0}
        self.previous_geometry = "1200x900+100+100"
        
        self.audio_player = WindowsAudioPlayer()
        self.is_paused = False

        self.video_path = tk.StringVar()
        self.audio_path = tk.StringVar()
        self.audio_mode = "ORIGINAL"
        self.codec = "copy"
        self.bitrate = tk.StringVar(value="15M")
        self.trim_start, self.trim_end = 0.0, 30.0
        self.duration = 30.0
        self.is_maximized = False
        self.is_processing = False
        self.ffmpeg_available = False
        
        self.setup_layout()
        self.update_command()
        
        # Async Check FFmpeg
        threading.Thread(target=self.async_check_ffmpeg, daemon=True).start()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def async_check_ffmpeg(self):
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            self.ffmpeg_available = True
        except:
            self.ffmpeg_available = False
        
        # Update UI on completion
        self.root.after(0, self.update_ffmpeg_ui)

    def update_ffmpeg_ui(self):
        if not self.ffmpeg_available:
            self.missing_btn = ModernButton(self.btn_area, "FFMPEG MISSING - CLICK TO DOWNLOAD", 
                                          lambda: webbrowser.open("https://ffmpeg.org/download.html"),
                                          width=300, height=35, bg="#ef4444", radius=10, font_size=7)
            self.missing_btn.pack(pady=5)

    def setup_layout(self):
        # Header
        self.header = tk.Frame(self.root, bg="#030712", height=100)
        self.header.pack(fill="x", padx=40, pady=(15, 5))
        self.header.bind("<Button-1>", self.start_drag)
        self.header.bind("<B1-Motion>", self.do_drag)
        self.header.bind("<Double-Button-1>", lambda e: self.toggle_maximize())
        
        tk.Label(self.header, text="V-STUDIO PRO", fg="#3b82f6", bg="#030712", font=("Segoe UI", 20, "bold")).pack(side="left")
        
        ctrls = tk.Frame(self.header, bg="#030712")
        ctrls.pack(side="right")
        ModernButton(ctrls, "✕", self.on_close, width=32, height=32, bg="#1e293b", fg="#ef4444", radius=8).pack(side="right", padx=2)
        self.max_btn = ModernButton(ctrls, "▢", self.toggle_maximize, width=32, height=32, bg="#1e293b", radius=8)
        self.max_btn.pack(side="right", padx=2)
        ModernButton(ctrls, "—", self.minimize_window, width=32, height=32, bg="#1e293b", radius=8).pack(side="right", padx=2)
        ModernButton(self.header, "LOAD MEDIA", self.smart_load, width=130, height=40, bg="#3b82f6").pack(side="right", padx=20)

        # Body
        body = tk.Frame(self.root, bg="#030712")
        body.pack(fill="both", expand=True, padx=40, pady=10)
        
        left = tk.Frame(body, bg="#030712")
        left.pack(side="left", fill="both", expand=True)
        self.prev_container = tk.Frame(left, bg="#0f172a")
        self.prev_container.pack(fill="both", expand=True)
        self.prev_container.pack_propagate(False)
        self.canvas = tk.Canvas(self.prev_container, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.msg = self.canvas.create_text(0,0, text="NO MEDIA LOADED", fill="#334155", font=("Segoe UI", 12))
        self.canvas.bind("<Configure>", lambda e: self.center_msg())

        timeline = tk.Frame(left, bg="#030712", pady=20)
        timeline.pack(fill="x")
        self.slider = RangeSlider(timeline)
        self.slider.pack(fill="x")
        self.slider.on_change_callback = self.on_slider
        self.time_lbl = tk.Label(timeline, text="START: 00:00:00 | END: 00:00:30", bg="#030712", fg="#94a3b8", font=("Consolas", 12))
        self.time_lbl.pack(pady=10)

        # Sidebar
        self.sidebar = tk.Frame(body, bg="#0f172a", width=420)
        self.sidebar.pack(side="right", fill="y", padx=(30, 0))
        self.sidebar.pack_propagate(False)
        
        sets = tk.Frame(self.sidebar, bg="#0f172a", padx=20, pady=20)
        sets.pack(fill="x")
        
        tk.Label(sets, text="AUDIO MODE", bg="#0f172a", fg="#3b82f6", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 5))
        audio_container = tk.Frame(sets, bg="#0f172a")
        audio_container.pack(fill="x", pady=(0, 15))
        self.audio_btns = {}
        for m in ["ORIGINAL", "NONE", "REPLACE", "MIX"]:
            btn = ModernButton(audio_container, m, lambda x=m: self.set_audio_mode(x), width=72, height=30)
            btn.pack(side="left", padx=2)
            self.audio_btns[m] = btn
        self.audio_btns["ORIGINAL"].set_active(True)

        tk.Label(sets, text="VIDEO CODEC", bg="#0f172a", fg="#3b82f6", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(5, 5))
        codec_container = tk.Frame(sets, bg="#0f172a")
        codec_container.pack(fill="x", pady=(0, 15))
        self.codec_btns = {}
        for l, v in [("COPY", "copy"), ("H.264", "libx264"), ("H.265", "libx265"), ("NV_264", "h264_nvenc"), ("NV_265", "hevc_nvenc")]:
            btn = ModernButton(codec_container, l, lambda x=v: self.set_codec(x), width=72, height=30)
            btn.pack(side="left", padx=2)
            self.codec_btns[v] = btn
        self.codec_btns["copy"].set_active(True)

        self.bit_frame = tk.Frame(self.sidebar, bg="#0f172a")
        tk.Label(self.bit_frame, text="BITRATE", bg="#0f172a", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=20, pady=(10, 5))
        box = tk.Frame(self.bit_frame, bg="#020617", padx=12, pady=8)
        box.pack(fill="x", padx=20)
        tk.Entry(box, textvariable=self.bitrate, bg="#020617", fg="#60a5fa", insertbackground="white", font=("Consolas", 13), borderwidth=0).pack(fill="x")

        tk.Label(self.sidebar, text="COMMAND", bg="#0f172a", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=20, pady=(15, 5))
        c_c = tk.Frame(self.sidebar, bg="#020617", padx=12, pady=12)
        c_c.pack(fill="x", padx=20)
        self.cmd_box = tk.Text(c_c, bg="#020617", fg="#3b82f6", font=("Consolas", 9), height=4, borderwidth=0, wrap="word")
        self.cmd_box.pack(fill="x")
        
        self.prog_area = tk.Frame(self.sidebar, bg="#0f172a", padx=20)
        self.prog_var = tk.DoubleVar()
        self.p_bar = ttk.Progressbar(self.prog_area, variable=self.prog_var, maximum=100)
        self.p_lbl = tk.Label(self.prog_area, text="", bg="#0f172a", fg="#60a5fa", font=("Consolas", 8))
        
        self.btn_area = tk.Frame(self.sidebar, bg="#0f172a")
        self.btn_area.pack(pady=20)
        self.run_btn = ModernButton(self.btn_area, "RUN FFMPEG PROCESS", self.run_ffmpeg, width=300, height=52, bg="#3b82f6", radius=15)
        self.run_btn.pack(pady=5)

        self.mani = tk.Frame(self.sidebar, bg="#0f172a", padx=20)
        self.mani.pack(fill="x", side="bottom", pady=20)
        self.mani_lbl = tk.Label(self.mani, text="NO MEDIA", bg="#0f172a", fg="#475569", font=("Segoe UI", 8))
        self.mani_lbl.pack(side="left")
        
        self.audio_ctrls = tk.Frame(self.mani, bg="#0f172a")
        self.p_btn = ModernButton(self.audio_ctrls, "▶", self.toggle_audio, width=32, height=25, radius=5)
        self.p_btn.pack(side="left", padx=2)
        self.s_btn = ModernButton(self.audio_ctrls, "■", self.stop_audio, width=32, height=25, radius=5, bg="#ef4444")
        self.s_btn.pack(side="left", padx=2)

        # Custom Resize Handle (Bottom Right)
        self.resizer = tk.Frame(self.root, bg="#030712", cursor="size_nw_se", width=12, height=12)
        self.resizer.place(relx=1.0, rely=1.0, anchor="se")
        self.resizer.bind("<Button-1>", self.start_resize)
        self.resizer.bind("<B1-Motion>", self.do_resize)

    def center_msg(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w > 0: self.canvas.coords(self.msg, w//2, h//2)

    def on_close(self):
        self.audio_player.stop()
        self.root.destroy()

    def minimize_window(self):
        if platform.system() == "Windows":
            self.taskbar_shadow.iconify()
        else:
            self.root.overrideredirect(False)
            self.root.iconify()

    def toggle_maximize(self):
        if self.is_maximized:
            self.root.state('normal')
            self.root.geometry(self.previous_geometry)
            self.is_maximized = False
            self.max_btn.set_text("▢")
        else:
            self.previous_geometry = self.root.geometry()
            # Windows 'zoomed' respects the taskbar automatically
            self.root.state('zoomed')
            self.is_maximized = True
            self.max_btn.set_text("❐")

    def start_drag(self, e):
        if self.is_maximized: return
        self._drag_data["x"], self._drag_data["y"] = e.x_root, e.y_root
        self._drag_data["win_x"] = self.root.winfo_x()
        self._drag_data["win_y"] = self.root.winfo_y()

    def do_drag(self, e):
        if self.is_maximized: return
        dx = e.x_root - self._drag_data["x"]
        dy = e.y_root - self._drag_data["y"]
        self.root.geometry(f"+{self._drag_data['win_x'] + dx}+{self._drag_data['win_y'] + dy}")

    def start_resize(self, e):
        if self.is_maximized: return
        self._resize_data["x"], self._resize_data["y"] = e.x_root, e.y_root
        self._resize_data["w"] = self.root.winfo_width()
        self._resize_data["h"] = self.root.winfo_height()

    def do_resize(self, e):
        if self.is_maximized: return
        dw = e.x_root - self._resize_data["x"]
        dh = e.y_root - self._resize_data["y"]
        new_w = max(800, self._resize_data["w"] + dw)
        new_h = max(600, self._resize_data["h"] + dh)
        self.root.geometry(f"{new_w}x{new_h}")

    def format_time(self, s):
        h, m = int(s // 3600), int((s % 3600) // 60)
        return f"{h:02d}:{m:02d}:{s%60:06.3f}"

    def parse_time(self, t):
        p = t.split(':')
        return float(p[0])*3600 + float(p[1])*60 + float(p[2])

    def smart_load(self):
        fs = filedialog.askopenfilenames()
        if not fs: return
        v_ext, a_ext = ('.mp4', '.mkv', '.mov', '.avi'), ('.mp3', '.wav', '.aac', '.m4a')
        fv, fa = None, None
        for f in fs:
            e = os.path.splitext(f)[1].lower()
            if not fv and e in v_ext: fv = f
            elif not fa and e in a_ext: fa = f
        if fv:
            self.video_path.set(fv)
            try:
                d = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', fv]).decode().strip())
                self.duration = d; self.trim_start = 0.0; self.trim_end = d
                self.slider.set_range(d)
                self.time_lbl.config(text=f"START: {self.format_time(0.0)} | END: {self.format_time(d)}")
                self.update_prev(0)
            except: pass
        if fa:
            self.audio_path.set(fa)
            self.audio_player.open(fa)
            self.audio_ctrls.pack(side="right")
        self.mani_lbl.config(text=f"V: {os.path.basename(fv or '')} | A: {os.path.basename(fa or '')}")
        self.update_command()

    def on_slider(self, s, e, h):
        self.trim_start, self.trim_end = s, e
        self.time_lbl.config(text=f"START: {self.format_time(s)} | END: {self.format_time(e)}")
        self.update_command()
        pt = s if h == "start" else e
        if not hasattr(self, '_timer'): self._timer = self.root.after(80, lambda: self.update_prev(pt))

    def update_prev(self, ts):
        if hasattr(self, '_timer'): self.root.after_cancel(self._timer); del self._timer
        v = self.video_path.get()
        if not v: return
        def gen():
            try:
                tmp = "vsp_prev.jpg"
                subprocess.run(['ffmpeg', '-y', '-ss', str(ts), '-i', v, '-vframes', '1', '-q:v', '5', tmp], capture_output=True)
                img = Image.open(tmp).convert("RGB")
                self.root.after(0, lambda: self.render_prev(img))
            except: pass
        threading.Thread(target=gen, daemon=True).start()

    def render_prev(self, img):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 1 or ch < 1: return
        w, h = img.size
        r = min(cw/w, ch/h)
        img = img.resize((int(w*r), int(h*r)), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(cw//2, ch//2, image=self.photo, anchor="center")

    def toggle_audio(self):
        if not self.audio_path.get(): return
        if self.is_paused: self.audio_player.resume(); self.is_paused = False; self.p_btn.set_text("II")
        elif self.p_btn.text_str == "▶": self.audio_player.play(); self.p_btn.set_text("II")
        else: self.audio_player.pause(); self.is_paused = True; self.p_btn.set_text("▶")

    def stop_audio(self):
        self.audio_player.stop()
        self.is_paused = False; self.p_btn.set_text("▶")
        if self.audio_path.get(): self.audio_player.open(self.audio_path.get())

    def set_audio_mode(self, m):
        self.audio_mode = m
        for k, b in self.audio_btns.items(): b.set_active(k == m)
        self.update_command()

    def set_codec(self, c):
        self.codec = c
        for k, b in self.codec_btns.items(): b.set_active(k == c)
        if c == "copy": self.bit_frame.pack_forget()
        else: self.bit_frame.pack(after=self.sidebar.children.get('!frame'), fill="x")
        self.update_command()

    def update_command(self, out="output.mp4"):
        v, a = self.video_path.get() or "input.mp4", self.audio_path.get() or "audio.mp3"
        start, dur = self.format_time(self.trim_start), self.format_time(self.trim_end - self.trim_start)
        cmd = f'ffmpeg -y -ss {start} -t {dur} -i "{v}"'
        if self.audio_mode in ["REPLACE", "MIX"]: cmd += f' -i "{a}"'
        if self.audio_mode == "NONE": cmd += " -map 0:v:0 -an"
        elif self.audio_mode == "ORIGINAL": cmd += " -map 0:v:0 -map 0:a:0"
        elif self.audio_mode == "REPLACE": cmd += " -map 0:v:0 -map 1:a:0"
        elif self.audio_mode == "MIX": 
            cmd += ' -filter_complex "[0:a]volume=1.0[a0];[1:a]volume=1.0[a1];[a0][a1]amix=inputs=2:duration=first" -map 0:v:0'
        cmd += f' -c:v {self.codec}'
        if self.codec != "copy": cmd += f' -b:v {self.bitrate.get()}'
        if self.audio_mode != "NONE": cmd += ' -c:a aac'
        cmd += f' -t {dur} "{out}"'
        self.cmd_box.delete(1.0, tk.END); self.cmd_box.insert(tk.END, cmd)

    def run_ffmpeg(self):
        if not self.ffmpeg_available:
            messagebox.showwarning("Warning", "FFmpeg not ready."); return
        if not self.video_path.get() or self.is_processing: return
        out = filedialog.asksaveasfilename(defaultextension=".mp4", initialfile=f"out_{os.path.basename(self.video_path.get())}")
        if not out: return
        self.update_command(out); cmd = self.cmd_box.get(1.0, tk.END).strip()
        self.is_processing = True; self.run_btn.set_text("PROCESSING..."); self.run_btn.set_state("disabled")
        self.prog_area.pack(fill="x", pady=10); self.p_bar.pack(fill="x"); self.p_lbl.pack(pady=5)
        total_d = self.trim_end - self.trim_start
        def task():
            try:
                p = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
                t_re = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d+)")
                while True:
                    l = p.stderr.readline()
                    if not l and p.poll() is not None: break
                    if l:
                        tm = t_re.search(l)
                        if tm: self.root.after(0, lambda v=(self.parse_time(tm.group(1))/total_d)*100: self.prog_var.set(v))
                p.communicate()
                self.root.after(0, self.cleanup, p.returncode)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e))); self.root.after(0, self.cleanup, -1)
        threading.Thread(target=task, daemon=True).start()

    def cleanup(self, code):
        self.is_processing = False; self.run_btn.set_text("RUN FFMPEG PROCESS"); self.run_btn.set_state("normal"); self.prog_area.pack_forget()
        if code == 0: messagebox.showinfo("Success", "Process Finished!")
        elif code != -1: messagebox.showerror("Error", "FFmpeg failed.")

if __name__ == "__main__":
    root = tk.Tk(); app = VStudioPro(root); root.mainloop()
