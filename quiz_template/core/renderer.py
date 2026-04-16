import os
import random
import glob
import subprocess
import imageio_ffmpeg
from .utils import sanitize_path, safe_text, escape_expr, wrap_text

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

class BaseRenderer:
    def __init__(self, topic, questions, assets_dir):
        self.topic = topic
        self.questions = questions
        self.assets_dir = assets_dir
        self.v_idx = 1
        self.filter_graph = []
        self.input_cmds = []
        self.input_paths = []
        
        # UI Config
        self.header_h = 380
        self.footer_h = 100
        self.side_margin = 120
        
        # Viral Hooks
        self.hooks = [
            "Only 1% get all {Qty} right",
            "Don’t skip, last one is insane",
            "Score {Qty} out of {Qty} equals genius",
            "Prove you are smart",
            "Last question will trick you",
            "Think fast or lose",
            "How many can you get right",
            "This one fooled everyone",
            "Genius test, pass or fail"
        ]

        self.outro_variations = [
            "Comment your score now."
            "Drop your score below.",
            "Did you get 3 out of 3.",
            "Be honest, what’s your score.",
            "Only geniuses got all 3 right."
        ]
        
        self.channel_cta = "Subscribe to Quiz Raptor for more fun and tricky quizzes!"

    def add_line_to_graph(self, last_node, text, font, color, size, x_start, y_start, wrap_w=32, enable="", align="center", fade=False, border_color="black", border_w=4, use_box=False, video_id=1):
        lines = wrap_text(text, width=wrap_w).split('\n')
        y_pos = y_start
        current_node = last_node
        line_height = int(size * 1.15) 
        
        for line in lines:
            escaped_text = safe_text(line.strip())
            en_str = f"enable={enable}:" if enable else ""
            x_str = f"x={x_start}" if align != "center" else "x=(w-text_w)/2"
            
            alpha_str = ""
            if fade and enable:
                clean_en = enable.replace('\\,', ',')
                if "between" in clean_en:
                    try:
                        start_t_val = clean_en.split('(')[1].split(',')[1].strip()
                        alpha_str = f":alpha=min(1\\,max(0\\,(t-{start_t_val})/0.5))"
                    except: pass
                elif "gte" in clean_en:
                    try:
                        start_t_val = clean_en.split('(')[1].split(',')[1].split(')')[0].strip()
                        alpha_str = f":alpha=min(1\\,max(0\\,(t-{start_t_val})/0.5))"
                    except: pass

            border_str = f":bordercolor={border_color}:borderw={border_w}" if border_w > 0 else ""
            box_str = ":box=1:boxcolor=black@0.4:boxborderw=10" if use_box else ""
            self.filter_graph.append(f"{current_node}drawtext={en_str}text='{escaped_text}':expansion=none:fontfile='{font}':fontcolor={color}:fontsize={size}:{x_str}:y={y_pos}{alpha_str}{border_str}{box_str}[v{video_id}_{self.v_idx}];")
            current_node = f"[v{video_id}_{self.v_idx}]"
            self.v_idx += 1
            y_pos += line_height
            
        return current_node

    def build_common_assets(self, video_id, audio_offset):
        # Premium Loader Assets
        assets = ["loader_frame.png", "loader_fill.png", "loader_star.png", "logo.png", "btn_sub.png", "btn_subbed.png", "cursor.png"]
        indices = {}
        for i, asset in enumerate(assets):
            path = os.path.abspath(os.path.join(self.assets_dir, asset))
            # Use raw path for -i, but sanitize_path for filters if needed.
            # Here we just need it for the input command.
            self.input_cmds.extend(["-loop", "1", "-i", path.replace('\\', '/')])
            indices[asset.split('.')[0]] = audio_offset + i
        return indices

    def render_final(self, cmd, filter_script_path, out_path, total_duration, last_video_node, video_id):
        cmd.extend([
            "-filter_complex_script", filter_script_path, "-map", last_video_node, "-map", f"[aout{video_id}]",
            "-t", str(total_duration), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-c:a", "aac", out_path
        ])
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding="utf-8", errors="replace")
        log_buffer = []
        for line in process.stdout:
            clean_line = line.strip()
            log_buffer.append(clean_line)
            if len(log_buffer) > 100:
                log_buffer.pop(0)
                
            if clean_line.startswith("frame=") or clean_line.startswith("size="):
                pass # Optionally suppress frame spam to make logs readable
            else:
                print(f"[V{video_id}][FFmpeg] {clean_line}")
                
        process.wait()
        if process.returncode != 0:
            print(f"\n[V{video_id}] Render FAILED with exit code {process.returncode}")
            print(f"--- EXTENDED FFMPEG CRASH LOG FOR V{video_id} ---")
            for l in log_buffer[-50:]:
                print(l)
            print("---------------------------------------")
            
            # Also read the filter generated script to help debugging
            if os.path.exists(filter_script_path):
                print("\n[DEBUG] Contents of the generated filter graph:")
                with open(filter_script_path, "r", encoding="utf-8") as f:
                    print(f.read())
                print("[DEBUG] ---------------------------------------\n")
                
        return process.returncode == 0
