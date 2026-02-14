
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import platform
import subprocess
import threading
from PIL import Image, ImageTk

class RangeSlider(tk.Canvas):
    def __init__(self, parent, width=400, height=40, min_val=0, max_val=100, **kwargs):
        super().__init__(parent, width=width, height=height, bg="#0f172a", highlightthickness=0, **kwargs)
        self.width = width
        self.height = height
        self.min_val = min_val
        self.max_val = max_val
        self.start_val = min_val
        self.end_val = max_val
        
        self.padding = 10
        self.bar_y = height // 2
        
        self.on_change_callback = None
        
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<Button-1>", self.on_click)
        self.draw()

    def set_range(self, max_v):
        self.max_val = max_v
        self.end_val = max_v
        self.draw()

    def get_coords(self, val):
        ratio = (val - self.min_val) / (self.max_val - self.min_val) if self.max_val > self.min_val else 0
        return self.padding + ratio * (self.width - 2 * self.padding)

    def get_val(self, x):
        ratio = (x - self.padding) / (self.width - 2 * self.padding)
        val = self.min_val + ratio * (self.max_val - self.min_val)
        return max(self.min_val, min(self.max_val, val))

    def draw(self):
        self.delete("all")
        # Bar
        x1 = self.get_coords(self.start_val)
        x2 = self.get_coords(self.end_val)
        
        self.create_line(self.padding, self.bar_y, self.width - self.padding, self.bar_y, fill="#1e293b", width=4)
        self.create_line(x1, self.bar_y, x2, self.bar_y, fill="#3b82f6", width=4)
        
        # Handles
        self.create_oval(x1-8, self.bar_y-8, x1+8, self.bar_y+8, fill="#60a5fa", outline="white", tags="start")
        self.create_oval(x2-8, self.bar_y-8, x2+8, self.bar_y+8, fill="#60a5fa", outline="white", tags="end")

    def on_click(self, event):
        x1 = self.get_coords(self.start_val)
        x2 = self.get_coords(self.end_val)
        if abs(event.x - x1) < abs(event.x - x2):
            self.active_handle = "start"
        else:
            self.active_handle = "end"

    def on_drag(self, event):
        val = self.get_val(event.x)
        if self.active_handle == "start":
            self.start_val = min(val, self.end_val - 0.1)
        else:
            self.end_val = max(val, self.start_val + 0.1)
        self.draw()
        if self.on_change_callback:
            self.on_change_callback(self.start_val, self.end_val)

class VStudioPro:
    def __init__(self, root):
        self.root = root
        self.root.title("V-Studio Pro | High Performance FFmpeg Studio")
        self.root.geometry("1100x850")
        self.root.configure(bg="#030712")
        
        # Defaults
        self.video_path = tk.StringVar(value="")
        self.audio_path = tk.StringVar(value="")
        self.audio_mode = tk.StringVar(value="ORIGINAL")
        self.codec = tk.StringVar(value="copy") # Default set to copy
        self.bitrate = tk.StringVar(value="15M")
        
        self.trim_start = 0.0
        self.trim_end = 30.0
        self.duration = 30.0
        self.preview_img = None
        
        self.setup_styles()
        self.create_layout()
        self.update_command()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#030712")
        style.configure("Sidebar.TFrame", background="#0f172a")
        style.configure("TLabel", background="#030712", foreground="#f8fafc", font=("Segoe UI", 10))
        style.configure("Header.TLabel", background="#030712", foreground="#3b82f6", font=("Segoe UI", 16, "bold"))
        style.configure("Small.TLabel", background="#0f172a", foreground="#94a3b8", font=("Segoe UI", 8))
        style.configure("TRadiobutton", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 9, "bold"))
        style.configure("Primary.TButton", background="#3b82f6", foreground="white")
        style.map("Primary.TButton", background=[('active', '#2563eb')])

    def create_layout(self):
        # Header
        header = ttk.Frame(self.root, padding=20)
        header.pack(fill="x")
        ttk.Label(header, text="V-STUDIO PRO", style="Header.TLabel").pack(side="left")
        
        # Main content
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Left Panel (Preview & Timeline)
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        
        self.preview_label = tk.Label(left, bg="black", text="LOAD VIDEO FOR PREVIEW", fg="#1e293b", font=("Segoe UI", 12))
        self.preview_label.pack(fill="both", expand=True, pady=(0, 20))
        
        # Timeline
        timeline_box = ttk.Frame(left, padding=10)
        timeline_box.pack(fill="x")
        
        self.slider = RangeSlider(timeline_box, width=600, height=50)
        self.slider.pack(fill="x")
        self.slider.on_change_callback = self.on_slider_change
        
        # Manual Inputs
        inputs = ttk.Frame(timeline_box)
        inputs.pack(fill="x", pady=10)
        
        self.ss_label = ttk.Label(inputs, text="START: 0.00s")
        self.ss_label.pack(side="left", padx=10)
        self.end_label = ttk.Label(inputs, text="END: 30.00s")
        self.end_label.pack(side="left", padx=10)
        
        # Right Sidebar
        right = ttk.Frame(body, style="Sidebar.TFrame", width=420)
        right.pack(side="right", fill="y", padx=(20, 0))
        right.pack_propagate(False)
        
        # Grouped Settings (Side by Side)
        settings_grid = ttk.Frame(right, style="Sidebar.TFrame", padding=15)
        settings_grid.pack(fill="x")
        
        # Col 1: Audio
        aud_col = ttk.Frame(settings_grid, style="Sidebar.TFrame")
        aud_col.grid(row=0, column=0, sticky="nw", padx=10)
        ttk.Label(aud_col, text="AUDIO MODE", font=("Segoe UI", 9, "bold"), background="#0f172a", foreground="#3b82f6").pack(anchor="w", pady=5)
        for m in ["ORIGINAL", "NONE", "REPLACE", "MIX"]:
            ttk.Radiobutton(aud_col, text=m, variable=self.audio_mode, value=m, command=self.update_command).pack(anchor="w")
            
        # Col 2: Codec
        cod_col = ttk.Frame(settings_grid, style="Sidebar.TFrame")
        cod_col.grid(row=0, column=1, sticky="nw", padx=10)
        ttk.Label(cod_col, text="VIDEO CODEC", font=("Segoe UI", 9, "bold"), background="#0f172a", foreground="#3b82f6").pack(anchor="w", pady=5)
        for label, val in [("COPY", "copy"), ("H.264", "libx264"), ("H.265", "libx265"), ("NV_264", "h264_nvenc"), ("NV_265", "hevc_nvenc")]:
            ttk.Radiobutton(cod_col, text=label, variable=self.codec, value=val, command=self.update_command).pack(anchor="w")

        # Bitrate
        bit_frame = ttk.Frame(right, style="Sidebar.TFrame", padding=15)
        bit_frame.pack(fill="x")
        ttk.Label(bit_frame, text="TARGET BITRATE", background="#0f172a", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Entry(bit_frame, textvariable=self.bitrate).pack(fill="x", pady=5)
        self.bitrate.trace_add("write", lambda *a: self.update_command())

        # Command & Copy
        cmd_frame = ttk.Frame(right, style="Sidebar.TFrame", padding=15)
        cmd_frame.pack(fill="both", expand=True)
        
        title_row = ttk.Frame(cmd_frame, style="Sidebar.TFrame")
        title_row.pack(fill="x")
        ttk.Label(title_row, text="FFMPEG COMMAND", background="#0f172a", font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Button(title_row, text="COPY", width=6, command=self.copy_command).pack(side="right")
        
        self.cmd_box = tk.Text(cmd_frame, bg="#020617", fg="#60a5fa", font=("Consolas", 9), height=10, borderwidth=0, padx=10, pady=10)
        self.cmd_box.pack(fill="both", expand=True, pady=10)
        
        # Run Button
        ttk.Button(right, text="RUN FFMPEG PROCESS", style="Primary.TButton", command=self.run_ffmpeg).pack(fill="x", padx=15, pady=20)
        
        # Manifest
        self.mani_frame = ttk.Frame(right, style="Sidebar.TFrame", padding=15)
        self.mani_frame.pack(fill="x")
        ttk.Label(self.mani_frame, text="ASSET MANIFEST", background="#0f172a", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.mani_list = ttk.Frame(self.mani_frame, style="Sidebar.TFrame")
        self.mani_list.pack(fill="x", pady=5)

        # File Loaders
        loader_bar = ttk.Frame(header)
        loader_bar.pack(side="right")
        ttk.Button(loader_bar, text="ADD VIDEO", command=lambda: self.load_file('video')).pack(side="left", padx=5)
        ttk.Button(loader_bar, text="ADD AUDIO", command=lambda: self.load_file('audio')).pack(side="left", padx=5)

    def load_file(self, ftype):
        path = filedialog.askopenfilename()
        if not path: return
        if ftype == 'video':
            self.video_path.set(path)
            self.get_video_info(path)
        else:
            self.audio_path.set(path)
        self.refresh_manifest()
        self.update_command()

    def get_video_info(self, path):
        # Extract duration using ffprobe
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', path]
            dur = float(subprocess.check_output(cmd).decode().strip())
            self.duration = dur
            self.trim_end = dur
            self.slider.set_range(dur)
            self.update_preview()
        except:
            pass

    def on_slider_change(self, start, end):
        self.trim_start = start
        self.trim_end = end
        self.ss_label.config(text=f"START: {start:.2f}s")
        self.end_label.config(text=f"END: {end:.2f}s")
        self.update_command()
        # Update preview frame (throttled)
        if not hasattr(self, '_preview_timer'):
            self._preview_timer = self.root.after(200, self.update_preview)

    def update_preview(self):
        if hasattr(self, '_preview_timer'):
            self.root.after_cancel(self._preview_timer)
            del self._preview_timer
            
        v = self.video_path.get()
        if not v: return
        
        # Extract a single frame at trim_start
        try:
            tmp = "preview_tmp.jpg"
            cmd = ['ffmpeg', '-y', '-ss', str(self.trim_start), '-i', v, '-vframes', '1', '-q:v', '2', tmp]
            subprocess.run(cmd, capture_output=True)
            img = Image.open(tmp)
            img.thumbnail((600, 400))
            self.preview_img = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_img, text="")
        except:
            pass

    def refresh_manifest(self):
        for w in self.mani_list.winfo_children(): w.destroy()
        if self.video_path.get():
            f = ttk.Frame(self.mani_list, style="Sidebar.TFrame")
            f.pack(fill="x")
            ttk.Label(f, text="V: "+os.path.basename(self.video_path.get()), style="Small.TLabel").pack(side="left")
        if self.audio_path.get():
            f = ttk.Frame(self.mani_list, style="Sidebar.TFrame")
            f.pack(fill="x")
            ttk.Label(f, text="A: "+os.path.basename(self.audio_path.get()), style="Small.TLabel").pack(side="left")
            tk.Button(f, text="▶", bg="#020617", fg="#10b981", relief="flat", command=self.preview_audio).pack(side="right")

    def preview_audio(self):
        messagebox.showinfo("Preview", "Audio preview playing (Simulated)")

    def update_command(self):
        v = self.video_path.get() or "input.mp4"
        a = self.audio_path.get() or "audio.mp3"
        mode = self.audio_mode.get()
        codec = self.codec.get()
        bitrate = self.bitrate.get()
        
        ffmpeg = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
        cmd = f'{ffmpeg} -y -i "{v}"'
        
        if mode in ["REPLACE", "MIX"]:
            cmd += f' -i "{a}"'
            
        dur = self.trim_end - self.trim_start
        cmd += f' -ss {self.trim_start:.2f} -t {dur:.2f}'
        
        if mode == "NONE": cmd += " -map 0:v:0 -an"
        elif mode == "ORIGINAL": cmd += " -map 0:v:0 -map 0:a:0"
        elif mode == "REPLACE": cmd += " -map 0:v:0 -map 1:a:0"
        elif mode == "MIX": cmd += ' -filter_complex "[0:a][1:a]amix=inputs=2:duration=first[a]" -map 0:v:0 -map "[a]"'
            
        cmd += f' -c:v {codec}'
        if codec != "copy": cmd += f' -b:v {bitrate}'
        if mode != "NONE": cmd += ' -c:a copy'
            
        cmd += f' "output_{os.path.basename(v)}"'
        
        self.cmd_box.delete(1.0, tk.END)
        self.cmd_box.insert(tk.END, cmd)

    def copy_command(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.cmd_box.get(1.0, tk.END).strip())

    def run_ffmpeg(self):
        cmd = self.cmd_box.get(1.0, tk.END).strip()
        if not cmd: return
        
        def run():
            try:
                # Use shell=True for simple command string execution
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()
                if process.returncode == 0:
                    messagebox.showinfo("Success", "FFmpeg process completed successfully!")
                else:
                    messagebox.showerror("Error", f"FFmpeg Error:\n{stderr.decode()}")
            except Exception as e:
                messagebox.showerror("Error", str(e))
                
        threading.Thread(target=run, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = VStudioPro(root)
    root.mainloop()
