import os
import random
import glob
import asyncio
import datetime
import subprocess
from core.utils import get_hash, get_duration, sanitize_path, get_font_path, wrap_text
from core.voice import generate_voiceover
from core.renderer import BaseRenderer, VIDEO_WIDTH, VIDEO_HEIGHT
import imageio_ffmpeg

class TextQuizRenderer(BaseRenderer):
    def create_gradient_bg(self, w, h, output_path):
        from PIL import Image, ImageDraw
        sw, sh = w // 10, h // 10
        img = Image.new('RGB', (sw, sh))
        draw = ImageDraw.Draw(img)
        c1 = (255, 126, 95)
        c2 = (254, 180, 123)
        for y in range(sh):
            for x in range(sw):
                ratio = (x + y) / (sw + sh)
                r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
                g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
                b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
                draw.point((x, y), fill=(r, g, b))
        img = img.resize((w, h), Image.Resampling.BILINEAR)
        img.save(output_path)
        return output_path

    def create_hazard_bg(self, w, h, output_path):
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (w, h), (255, 204, 0)) # Caution Yellow
        draw = ImageDraw.Draw(img)
        stripe_w = 60
        # Draw diagonal stripes at top and bottom
        for i in range(-stripe_w, w + h, stripe_w * 2):
            # Top stripes (first 150px)
            draw.polygon([(i, 0), (i + stripe_w, 0), (i + stripe_w - 150, 150), (i - 150, 150)], fill="black")
            # Bottom stripes (last 150px)
            draw.polygon([(i, h - 150), (i + stripe_w, h - 150), (i + stripe_w + 150, h), (i + 150, h)], fill="black")
        img.save(output_path)
        return output_path

    def create_blueprint_bg(self, w, h, output_path):
        from PIL import Image, ImageDraw
        # Blueprint Blue
        img = Image.new('RGB', (w, h), (0, 40, 85))
        draw = ImageDraw.Draw(img)
        # White grid lines
        grid_size = 60
        for x in range(0, w, grid_size):
            draw.line([(x, 0), (x, h)], fill=(255, 255, 255, 50), width=1)
        for y in range(0, h, grid_size):
            draw.line([(0, y), (w, y)], fill=(255, 255, 255, 50), width=1)
        img.save(output_path)
        return output_path

    def create_omr_bg(self, w, h, output_path):
        from PIL import Image, ImageDraw
        # Off-white paper color
        img = Image.new('RGB', (w, h), (250, 250, 245))
        draw = ImageDraw.Draw(img)
        # Subtle blue lines (ruled paper)
        for y in range(100, h, 60):
            draw.line([(0, y), (w, y)], fill=(200, 220, 255), width=2)
        # Red margin line
        draw.line([(120, 0), (120, h)], fill=(255, 200, 200), width=3)
        img.save(output_path)
        return output_path

    def create_wildlife_bg(self, w, h, output_path):
        from PIL import Image, ImageDraw
        # Deep Forest Green
        img = Image.new('RGB', (w, h), (10, 30, 10))
        draw = ImageDraw.Draw(img)
        # Subtle gradient
        for y in range(h):
            r = int(10 + (20 * y / h))
            g = int(30 + (40 * y / h))
            b = int(10 + (20 * y / h))
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        img.save(output_path)
        return output_path

    def create_gameboy_bg(self, w, h, output_path):
        from PIL import Image, ImageDraw
        # Classic Gameboy Grey Plastic
        img = Image.new('RGB', (w, h), (150, 150, 150))
        draw = ImageDraw.Draw(img)
        
        # Screen Bezel (Darker Grey)
        draw.rectangle([50, 100, w-50, h-400], fill=(80, 80, 80))
        
        # LCD Screen (Greenish tint)
        draw.rectangle([80, 130, w-80, h-430], fill=(155, 188, 15))
        
        # Decorative dots/lines
        draw.text((100, 50), "DOT MATRIX WITH STEREO SOUND", fill=(50, 50, 50))
        
        img.save(output_path)
        return output_path

    def create_chat_bubble(self, w, h, color, output_path, align="left"):
        from PIL import Image, ImageDraw
        img = Image.new('RGBA', (w + 40, h + 20), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Main bubble
        radius = 30
        if align == "left":
            draw.rounded_rectangle([20, 0, w + 20, h], radius=radius, fill=color)
            # Tail
            draw.polygon([(20, h - 20), (0, h), (30, h - 20)], fill=color)
        else:
            draw.rounded_rectangle([0, 0, w, h], radius=radius, fill=color)
            # Tail
            draw.polygon([(w - 20, h - 20), (w + 20, h), (w - 40, h - 20)], fill=color)
        img.save(output_path)
        return output_path

    def create_chat_bg(self, w, h, output_path):
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (w, h), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        # Add subtle chat wallpaper pattern (dots or similar)
        for y in range(0, h, 60):
            for x in range(0, w, 60):
                draw.ellipse([x, y, x+4, y+4], fill=(220, 220, 220))
        img.save(output_path)
        return output_path

    def build_video(self, video_id, topic, questions, bg_type, music_dir, images_dir, videos_dir, fonts_dir, voiceovers_dir, output_dir, tts_voice, is_preview=False, template="classic"):
        try:
            print(f"\n[Engine][V{video_id}] Building Text Quiz: {topic}")
            qty = len(questions)
            heading_font = get_font_path("BebasNeue-Regular.ttf", fonts_dir)
            question_font = get_font_path("Poppins-Bold.ttf", fonts_dir)
            if template == "hazard":
                question_font = get_font_path("Poppins-Regular.ttf", fonts_dir)
            answer_font = get_font_path("Poppins-Bold.ttf", fonts_dir)
            if template == "hazard":
                answer_font = get_font_path("Poppins-Bold.ttf", fonts_dir) # Options stay bold for aggression
            
            if template in ["hacker", "gameboy", "blueprint"]:
                sys_font = "C:/Windows/Fonts/consola.ttf"
                if not os.path.exists(sys_font): sys_font = "C:/Windows/Fonts/cour.ttf"
                if os.path.exists(sys_font):
                    question_font = sanitize_path(sys_font)
                    answer_font = sanitize_path(sys_font)
                    heading_font = sanitize_path(sys_font)
            elif template == "wildlife":
                serif_font = "C:/Windows/Fonts/times.ttf"
                if not os.path.exists(serif_font): serif_font = "C:/Windows/Fonts/georgia.ttf"
                if os.path.exists(serif_font):
                    question_font = sanitize_path(serif_font)
                    answer_font = sanitize_path(serif_font)
                    heading_font = sanitize_path(serif_font)
            elif template in ["omr", "omr_hand"]:
                hw_font = os.path.join(fonts_dir, "segoepr.ttf") # Local copy
                if not os.path.exists(hw_font): hw_font = "C:/Windows/Fonts/segoepr.ttf"
                if not os.path.exists(hw_font): hw_font = "C:/Windows/Fonts/comic.ttf"
                if os.path.exists(hw_font):
                    question_font = sanitize_path(hw_font)
                    answer_font = sanitize_path(hw_font)
                    heading_font = sanitize_path(hw_font)
            topic_clean = topic.strip()
            high_ctr_titles = {
                "ipl 2026": "The Ultimate IPL 2026 Quiz! Can You Score 100%?",
                "icc champion trophy 2025": "ICC Champions Trophy 2025 Quiz! Are You Ready?",
                "india vs pakistan": "India vs Pakistan! The Ultimate Rivalry Quiz!",
                "virat kohli": "Only 1% of Fans Know These Virat Kohli Facts!",
                "rohit sharma": "Are You The Biggest Hitman Rohit Sharma Fan?",
                "90s kids": "Only True 90s Kids Will Pass This Nostalgia Quiz!",
                "2000s kids": "Nostalgia Alert! Are You a True 2000s Kid?",
                "indian quiz": "Can You Pass The Hardest Indian Trivia Quiz?",
                "ncert students": "Are You Smarter Than an NCERT Student?",
                "animal quiz": "Can You Guess The Animal? 99% Will Fail!",
                "space": "Mind-Blowing Space Quiz: Are You A Genius?",
                "science": "Only True Geniuses Can Pass This Science Quiz!"
            }

            topic_display = None
            for key, title in high_ctr_titles.items():
                if key in topic_clean.lower():
                    topic_display = title
                    break
            
            if not topic_display:
                hook_text = random.choice(self.hooks).format(Topic=topic_clean, Qty=qty)
                if topic_clean.lower() not in hook_text.lower():
                    topic_display = f"{topic_clean} Quiz\n{hook_text}"
                else:
                    topic_display = hook_text

            intro_text = topic_display
            print(f"[V{video_id}] Hook/Intro: {intro_text}")
            cta_text = "If you are still here\nhit like, subscribe and comment\nhow many answer were correct."
            
            # 1. Background Logic
            self.input_cmds = []
            bg_music_file = "jungle.mp3" if template == "wildlife" else "background_music.mp3"
            bg_music_path = os.path.join(music_dir, bg_music_file)
            if not os.path.exists(bg_music_path): bg_music_path = os.path.join(music_dir, "background_music.mp3")
            has_bgm = os.path.exists(bg_music_path)
            if has_bgm:
                bgm_idx = 0
                self.input_cmds.extend(["-stream_loop", "-1", "-i", bg_music_path.replace('\\', '/')])
            else:
                bgm_idx = -1
            
            bg_input_idx = -1
            if template == "pastel":
                pastel_bg_path = os.path.join(output_dir, f"pastel_bg_v{video_id}.png")
                self.create_gradient_bg(VIDEO_WIDTH, VIDEO_HEIGHT, pastel_bg_path)
                bg_input_idx = sum(1 for cmd in self.input_cmds if cmd == "-i")
                self.input_cmds.extend(["-loop", "1", "-i", pastel_bg_path])
            elif template == "chat":
                chat_bg_path = os.path.join(output_dir, f"chat_bg_v{video_id}.png")
                self.create_chat_bg(VIDEO_WIDTH, VIDEO_HEIGHT, chat_bg_path)
                bg_input_idx = sum(1 for cmd in self.input_cmds if cmd == "-i")
                self.input_cmds.extend(["-loop", "1", "-i", chat_bg_path])
            elif template == "gameboy":
                gb_bg_path = os.path.join(output_dir, f"gb_bg_v{video_id}.png")
                self.create_gameboy_bg(VIDEO_WIDTH, VIDEO_HEIGHT, gb_bg_path)
                bg_input_idx = sum(1 for cmd in self.input_cmds if cmd == "-i")
                self.input_cmds.extend(["-loop", "1", "-i", gb_bg_path])
            elif template == "blueprint":
                bp_bg_path = os.path.join(output_dir, f"bp_bg_v{video_id}.png")
                self.create_blueprint_bg(VIDEO_WIDTH, VIDEO_HEIGHT, bp_bg_path)
                bg_input_idx = sum(1 for cmd in self.input_cmds if cmd == "-i")
                self.input_cmds.extend(["-loop", "1", "-i", bp_bg_path])
            elif template == "wildlife":
                wl_bg_path = os.path.join(output_dir, f"wl_bg_v{video_id}.png")
                self.create_wildlife_bg(VIDEO_WIDTH, VIDEO_HEIGHT, wl_bg_path)
                bg_input_idx = sum(1 for cmd in self.input_cmds if cmd == "-i")
                self.input_cmds.extend(["-loop", "1", "-i", wl_bg_path])
            elif template in ["omr", "omr_hand"]:
                omr_bg_path = os.path.join(output_dir, f"omr_bg_v{video_id}.png")
                self.create_omr_bg(VIDEO_WIDTH, VIDEO_HEIGHT, omr_bg_path)
                bg_input_idx = sum(1 for cmd in self.input_cmds if cmd == "-i")
                self.input_cmds.extend(["-loop", "1", "-i", omr_bg_path])
            elif template == "hazard":
                hazard_bg_path = os.path.join(output_dir, f"hazard_bg_v{video_id}.png")
                self.create_hazard_bg(VIDEO_WIDTH, VIDEO_HEIGHT, hazard_bg_path)
                bg_input_idx = sum(1 for cmd in self.input_cmds if cmd == "-i")
                self.input_cmds.extend(["-loop", "1", "-i", hazard_bg_path])
            elif bg_type == "image":
                bg_files = glob.glob(os.path.join(images_dir, "backgrounds", "*.*"))
                if bg_files:
                    bg_file = random.choice(bg_files)
                    bg_input_idx = sum(1 for cmd in self.input_cmds if cmd == "-i")
                    self.input_cmds.extend(["-loop", "1", "-i", bg_file.replace('\\', '/')])
            elif bg_type == "video":
                vid_files = glob.glob(os.path.join(videos_dir, "*.*"))
                if vid_files:
                    bg_file = random.choice(vid_files)
                    bg_input_idx = sum(1 for cmd in self.input_cmds if cmd == "-i")
                    self.input_cmds.extend(["-stream_loop", "-1", "-i", bg_file.replace('\\', '/')])

            offset_before_common = sum(1 for cmd in self.input_cmds if cmd == "-i")
            indices = self.build_common_assets(video_id, offset_before_common)
            if template == "omr_hand":
                hand_path = os.path.join(self.assets_dir, "hand_holding_red_pen.png")
                if os.path.exists(hand_path):
                    indices['hand'] = sum(1 for cmd in self.input_cmds if cmd == "-i")
                    self.input_cmds.extend(["-i", hand_path])
            base_input_count = sum(1 for cmd in self.input_cmds if cmd == "-i")
            
            # DRAWING LOGIC WITH EQUAL SPACING
            # Layout
            if template == "grid":
                header_h = 350
                q_h = 240
                opt_h = 180
                opt_w = 420
                opt_gap_x = 40
                opt_gap_y = 40
                l_h = 160
                
                q_y = header_h + 60
                opt_start_y = q_y + q_h + 60
                l_y = opt_start_y + 2 * opt_h + 1 * opt_gap_y + 120
            elif template == "millionaire":
                header_h = 350
                q_h = 240
                opt_h = 160
                opt_w = 460
                opt_gap_x = 20
                opt_gap_y = 40
                l_h = 160
                
                q_y = header_h + 60
                opt_start_y = q_y + q_h + 60
                l_y = opt_start_y + 2 * opt_h + 1 * opt_gap_y + 120
            elif template == "quadrants":
                header_h = 320
                q_h = 240
                opt_h = 450
                opt_w = 480
                opt_gap_x = 20
                opt_gap_y = 20
                l_h = 160
                
                q_y = header_h + 60
                opt_start_y = q_y + q_h + 80
                l_y = opt_start_y + 2 * opt_h + opt_gap_y + 100
            elif template == "retro":
                header_h = 320
                q_h = 240
                opt_h = 140
                opt_w = 920
                opt_gap_x = 0
                opt_gap_y = 35
                l_h = 160
                
                q_y = header_h + 80
                opt_start_y = q_y + q_h + 40
                l_y = opt_start_y + 4 * opt_h + 3 * opt_gap_y + 40
            elif template == "stadium":
                header_h = 320
                q_h = 240
                opt_h = 140
                opt_w = 940
                opt_gap_x = 0
                opt_gap_y = 30
                l_h = 160
                
                q_y = header_h + 80
                opt_start_y = q_y + q_h + 50
                l_y = opt_start_y + 4 * opt_h + 3 * opt_gap_y + 50
            elif template == "hazard":
                header_h = 300
                q_h = 240
                opt_h = 130
                opt_w = 900
                opt_gap_x = 0
                opt_gap_y = 35
                l_h = 160
                
                q_y = header_h + 80
                opt_start_y = q_y + q_h + 40
                l_y = opt_start_y + 4 * opt_h + 3 * opt_gap_y + 40
            elif template == "gameboy":
                # Must fit within the green screen: [80, 130, w-80, h-430]
                header_h = 320 # Reduced to prevent overlap
                q_h = 240
                opt_h = 130
                opt_w = 880
                opt_gap_x = 0
                opt_gap_y = 30
                l_h = 160
                
                q_y = header_h + 180 # Shifted down for proper spacing
                opt_start_y = q_y + q_h + 80 
                l_y = opt_start_y + 4 * opt_h + 3 * opt_gap_y + 40
            elif template == "blueprint":
                header_h = 350
                q_h = 240
                opt_h = 140
                opt_w = 920
                opt_gap_x = 0
                opt_gap_y = 35
                l_h = 160
                
                q_y = header_h + 80
                opt_start_y = q_y + q_h + 40
                l_y = opt_start_y + 4 * opt_h + 3 * opt_gap_y + 40
            elif template == "wildlife":
                header_h = 350
                q_h = 240
                opt_h = 140
                opt_w = 900
                opt_gap_x = 0
                opt_gap_y = 35
                l_h = 160
                
                q_y = header_h + 80
                opt_start_y = q_y + q_h + 40
                l_y = opt_start_y + 4 * opt_h + 3 * opt_gap_y + 40
            elif template in ["omr", "omr_hand"]:
                header_h = 300
                q_h = 240
                opt_h = 130
                opt_w = 900
                opt_gap_x = 0
                opt_gap_y = 35
                l_h = 160
                
                q_y = header_h + 80
                opt_start_y = q_y + q_h + 50
                l_y = opt_start_y + 4 * opt_h + 3 * opt_gap_y + 50
            elif template == "chat":
                header_h = 200
                q_h = 200
                opt_h = 120
                opt_w = 700
                opt_gap_x = 0
                opt_gap_y = 20
                l_h = 120
                
                q_y = header_h + 100
                opt_start_y = q_y + q_h + 50
                l_y = opt_start_y + 4 * opt_h + 3 * opt_gap_y + 40
            else: # classic, chalkboard, hacker, pastel
                header_h = 320
                q_h = 240
                opt_h = 130
                opt_w = 900
                opt_gap_x = 0
                opt_gap_y = 30
                l_h = 160
                
                q_y = header_h + 60
                opt_start_y = q_y + q_h + 40
                l_y = opt_start_y + 4 * opt_h + 3 * opt_gap_y + 60
            
            # Voiceovers
            intro_audio_path = os.path.join(voiceovers_dir, f"intro_{get_hash(intro_text)}.mp3")
            asyncio.run(generate_voiceover(intro_text, intro_audio_path, tts_voice))
            intro_dur = get_duration(intro_audio_path)
            
            ticktock_path = os.path.join(music_dir, "ticktock.mp3")
            # Hazard uses siren, others use bing
            clap_path = os.path.join(music_dir, "siren.mp3") if template == "hazard" else os.path.join(music_dir, "bing.mp3")
            if template == "hazard" and not os.path.exists(clap_path):
                clap_path = os.path.join(music_dir, "bing.mp3")
                
            has_ticktock = os.path.exists(ticktock_path)
            has_clap = os.path.exists(clap_path)
            
            # Input Paths for Q&A audio
            input_paths = []
            def get_input_idx(path):
                idx = base_input_count + len(input_paths)
                input_paths.append(path)
                return idx

            audio_mixes = []
            intro_idx = get_input_idx(intro_audio_path)
            audio_mixes.append(f"[{intro_idx}:a]volume=1.5,adelay=0|0[a_intro]")
            
            if template == "chat":
                q_bubble_path = os.path.join(output_dir, f"q_bubble_v{video_id}.png")
                self.create_chat_bubble(900, q_h, (233, 233, 235), q_bubble_path, align="left")
                q_bubble_idx = sum(1 for cmd in self.input_cmds if cmd == "-i")
                self.input_cmds.extend(["-i", q_bubble_path])
                
                opt_bubble_path = os.path.join(output_dir, f"opt_bubble_v{video_id}.png")
                self.create_chat_bubble(opt_w, opt_h, (0, 122, 255), opt_bubble_path, align="right")
                opt_bubble_idx = sum(1 for cmd in self.input_cmds if cmd == "-i")
                self.input_cmds.extend(["-i", opt_bubble_path])
                
                hl_bubble_path = os.path.join(output_dir, f"hl_bubble_v{video_id}.png")
                self.create_chat_bubble(opt_w, opt_h, (52, 199, 89), hl_bubble_path, align="right")
                hl_bubble_idx = sum(1 for cmd in self.input_cmds if cmd == "-i")
                self.input_cmds.extend(["-i", hl_bubble_path])

            q_assets = []
            temp_time = intro_dur
            for idx, q_data in enumerate(questions):
                q_text, a_text, timer = q_data['Question'], str(q_data['Answer']), float(q_data['Time_to_Guess'])
                opt_a, opt_b = str(q_data.get('Option_A', '')), str(q_data.get('Option_B', ''))
                opt_c, opt_d = str(q_data.get('Option_C', '')), str(q_data.get('Option_D', ''))
                options = [opt_a, opt_b, opt_c, opt_d]

                # Determine correct index
                ans_lower = a_text.strip().lower()
                correct_idx = 0
                for i, opt in enumerate(options):
                    if ans_lower == opt.strip().lower():
                        correct_idx = i
                        break
                else:
                    if ans_lower in ['a', 'option_a']: correct_idx = 0
                    elif ans_lower in ['b', 'option_b']: correct_idx = 1
                    elif ans_lower in ['c', 'option_c']: correct_idx = 2
                    elif ans_lower in ['d', 'option_d']: correct_idx = 3

                q_audio_path = os.path.join(voiceovers_dir, f"q_{get_hash(q_text)}.mp3")
                a_audio_path = os.path.join(voiceovers_dir, f"a_{get_hash(a_text)}.mp3")
                asyncio.run(generate_voiceover(q_text, q_audio_path, tts_voice))
                asyncio.run(generate_voiceover(a_text, a_audio_path, tts_voice))
                
                q_dur, a_dur = get_duration(q_audio_path), get_duration(a_audio_path)
                start_t, reveal_t = temp_time, temp_time + q_dur + timer
                end_t = reveal_t + a_dur + 1.5
                
                q_assets.append({
                    'q_path': q_audio_path, 'a_path': a_audio_path,
                    'q_dur': q_dur, 'a_dur': a_dur,
                    'start_t': start_t, 'reveal_t': reveal_t, 'end_t': end_t,
                    'q_text': q_text, 'a_text': a_text, 'timer': timer,
                    'options': options, 'correct_idx': correct_idx
                })
                temp_time = end_t
            
            # Outro Voiceover
            outro_hook = random.choice(self.outro_variations).format(Qty=qty)
            outro_text = f"{outro_hook} {self.channel_cta}"
            outro_audio_path = os.path.join(voiceovers_dir, f"outro_{get_hash(outro_text)}.mp3")
            asyncio.run(generate_voiceover(outro_text, outro_audio_path, tts_voice))
            outro_dur = get_duration(outro_audio_path)
            print(f"[V{video_id}] Outro: {outro_text[:50]}...")
            
            score_start = temp_time
            score_end = score_start + max(5.0, outro_dur + 1.0)
            total_duration = score_end
            
            # Start Graph
            if template == "chalkboard":
                self.filter_graph.append(f"color=c=0x283e2e:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r=24[bg{video_id}];")
            elif template == "hacker":
                self.filter_graph.append(f"color=c=black:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r=24[bg_base{video_id}];")
                self.filter_graph.append(f"[bg_base{video_id}]drawgrid=w=120:h=120:t=2:c=0x00FF00@0.15,vignette=PI/3[bg{video_id}];")
            elif template == "retro":
                # Synthwave Background: Purple sky + Neon Grid
                self.filter_graph.append(f"color=c=0x1A0033:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}[bg_sky{video_id}];")
                self.filter_graph.append(f"color=c=black:s={VIDEO_WIDTH}x{VIDEO_HEIGHT//2}[bg_bot{video_id}];")
                self.filter_graph.append(f"[bg_bot{video_id}]drawgrid=w=120:h=120:t=2:c=0xFF00FF@0.4[bg_grid{video_id}];")
                self.filter_graph.append(f"[bg_sky{video_id}][bg_grid{video_id}]overlay=x=0:y={VIDEO_HEIGHT//2}[bg_base{video_id}];")
                self.filter_graph.append(f"[bg_base{video_id}]vignette=PI/4[bg{video_id}];")
            elif template == "stadium":
                # Broadcaster Blue Background with subtle vignette
                self.filter_graph.append(f"color=c=0x000032:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}[bg_base{video_id}];")
                self.filter_graph.append(f"[bg_base{video_id}]vignette=PI/4[bg{video_id}];")
            elif template in ["pastel", "chat", "hazard", "gameboy", "blueprint", "wildlife"]:
                # Background already added in the logic above
                self.filter_graph.append(f"[{bg_input_idx}:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}[bg_raw{video_id}];")
                if template == "wildlife":
                    # Signature Yellow Border
                    self.filter_graph.append(f"[bg_raw{video_id}]drawbox=x=0:y=0:w={VIDEO_WIDTH}:h={VIDEO_HEIGHT}:color=0xFFCC00:t=40[bg{video_id}];")
                else:
                    self.filter_graph.append(f"[bg_raw{video_id}]copy[bg{video_id}];")
            elif bg_input_idx != -1:
                self.filter_graph.append(f"[{bg_input_idx}:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}[bg{video_id}];")
            else:
                self.filter_graph.append(f"color=c=black:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r=24[bg{video_id}];")
            
            last_node = f"[bg{video_id}]"
            
            # Header Box
            if template not in ["chalkboard", "hacker", "pastel", "gameboy", "omr", "omr_hand"]:
                self.filter_graph.append(f"{last_node}drawbox=x=0:y=0:w={VIDEO_WIDTH}:h={header_h}:color=white:t=fill[v_hbg{video_id}];")
                last_node = f"[v_hbg{video_id}]"
            
            # Logo (Bottom right corner)
            self.filter_graph.append(f"[{indices['logo']}:v]scale=120:-1[vlogo{video_id}];")
            self.filter_graph.append(f"{last_node}[vlogo{video_id}]overlay=x=W-w-40:y=H-h-60[vl{video_id}];")
            last_node = f"[vl{video_id}]"
            
            # Heading Text (Fully Centered since logo moved)
            if template == "retro":
                h_wrap_w = 24
                h_size = 110 if len(topic_display) < 22 else 85
                lines = wrap_text(topic_display, width=h_wrap_w).split('\n') 
                total_text_h = len(lines) * (h_size * 1.15)
                start_y = (header_h - total_text_h) // 2
                
                # Special Synthwave Header: Dark bar with glow
                self.filter_graph.append(f"color=c=black@0.6:s={VIDEO_WIDTH}x{header_h}[hbar{video_id}];")
                self.filter_graph.append(f"{last_node}[hbar{video_id}]overlay=x=0:y=0[v_h1_{video_id}];")
                last_node = self.add_line_to_graph(f"[v_h1_{video_id}]", topic_display, heading_font, "#00FFFF", h_size, 0, start_y, wrap_w=h_wrap_w, align="center", video_id=video_id)
            elif template == "stadium":
                # Broadcaster Style Header: Clean Blue Bar
                self.filter_graph.append(f"color=c=0x000044@0.8:s={VIDEO_WIDTH}x{header_h}[hbar{video_id}];")
                self.filter_graph.append(f"{last_node}[hbar{video_id}]overlay=x=0:y=0[vh1{video_id}];")
                # Topic Title (Re-positioned to fill space)
                h_size = 95 if len(topic_display) < 25 else 80
                h_wrap = 38
                lines = wrap_text(topic_display.upper(), width=h_wrap).split('\n')
                total_text_h = len(lines) * (h_size * 1.15)
                start_y = (header_h - total_text_h) // 2
                last_node = self.add_line_to_graph(f"[vh1{video_id}]", topic_display.upper(), heading_font, "white", h_size, 0, start_y, h_wrap, align="center", video_id=video_id)
            elif template == "gameboy":
                h_size = 75 if len(topic_display) < 25 else 60
                h_wrap = 18 # Added margin by reducing wrap width
                lines = wrap_text(topic_display.upper(), width=h_wrap).split('\n')
                total_text_h = len(lines) * (h_size * 1.15)
                start_y = 180 # Moved down slightly for padding from bezel
                last_node = self.add_line_to_graph(last_node, topic_display.upper(), heading_font, "0x0f380f", 75, 0, start_y, h_wrap, align="center", video_id=video_id)
            elif template == "blueprint":
                h_size = 85 if len(topic_display) < 25 else 70
                h_wrap = 22 # Reduced to prevent screen overflow
                lines = wrap_text(topic_display.upper(), width=h_wrap).split('\n')
                total_text_h = len(lines) * (h_size * 1.15)
                start_y = (header_h - total_text_h) // 2
                last_node = self.add_line_to_graph(last_node, topic_display.upper(), heading_font, "red", h_size, 0, start_y, h_wrap, align="center", video_id=video_id)
            elif template in ["omr", "omr_hand"]:
                h_size = 80 if len(topic_display) < 25 else 65
                h_wrap = 24
                lines = wrap_text(topic_display.upper(), width=h_wrap).split('\n')
                total_text_h = len(lines) * (h_size * 1.15)
                start_y = (header_h - total_text_h) // 2
                # Use Blue Ink for heading since no white box
                last_node = self.add_line_to_graph(last_node, topic_display.upper(), heading_font, "0x323296", h_size, 0, start_y, h_wrap, align="center", video_id=video_id)
            elif template == "chat":
                self.filter_graph.append(f"color=c=0x007AFF:s={VIDEO_WIDTH}x{header_h}[hbar{video_id}];")
                self.filter_graph.append(f"{last_node}[hbar{video_id}]overlay=x=0:y=0[v_h1_{video_id}];")
                last_node = self.add_line_to_graph(f"[v_h1_{video_id}]", f"💬 {topic_clean}", heading_font, "white", 60, 0, (header_h - 60) // 2, 30, align="center", video_id=video_id)
            else:
                if template == "hacker":
                    h_wrap_w = 15
                    h_size = 90 if len(topic_display) < 15 else 75
                else:
                    h_wrap_w = 24
                    h_size = 130 if len(topic_display) < 22 else 90
                
                lines = wrap_text(topic_display, width=h_wrap_w).split('\n') 
                total_text_h = len(lines) * (h_size * 1.15)
                start_y = (header_h - total_text_h) // 2
                h_color = "white" if template == "chalkboard" else ("0x00FF00" if template == "hacker" else ("#333333" if template == "pastel" else "red"))
                last_node = self.add_line_to_graph(last_node, topic_display, heading_font, h_color, h_size, 0, start_y, wrap_w=h_wrap_w, align="center", video_id=video_id)
            
            # Option Box Gen
            opt_box_w = opt_w
            opt_box_h = opt_h
            opt_box_path = os.path.join(self.assets_dir, f"opt_box_{opt_box_w}_{opt_box_h}_{template}.png")
            hl_box_path = os.path.join(self.assets_dir, f"hl_box_{opt_box_w}_{opt_box_h}_{template}.png")
            
            if not os.path.exists(opt_box_path) or not os.path.exists(hl_box_path):
                from PIL import Image, ImageDraw, ImageFilter
                radius = 60 if template in ["grid", "millionaire"] else 40
                
                if template == "millionaire":
                    # Deep Navy fill, Gold outline
                    fill_col = (0, 0, 50, 230)
                    out_col = (255, 215, 0, 255)
                    hl_fill = (0, 180, 0, 230)
                    hl_out = (255, 255, 255, 255)
                    out_w = 5
                    blur_radius = 15
                elif template == "quadrants":
                    # Colored boxes based on index will be handled in the loop
                    # We create 4 different colored boxes
                    quad_colors = [
                        (255, 75, 43, 230),  # Red
                        (51, 153, 255, 230), # Blue
                        (0, 200, 81, 230),   # Green
                        (255, 187, 51, 230)  # Yellow
                    ]
                    for i, col in enumerate(quad_colors):
                        q_box_path = os.path.join(self.assets_dir, f"quad_box_{i}_{opt_box_w}_{opt_box_h}.png")
                        if not os.path.exists(q_box_path):
                            q_img = Image.new('RGBA', (opt_box_w + 100, opt_box_h + 100), (0, 0, 0, 0))
                            q_draw = ImageDraw.Draw(q_img)
                            q_draw.rounded_rectangle((50, 50, opt_box_w + 50, opt_box_h + 50), radius=30, fill=col)
                            q_img.save(q_box_path)
                    
                    # Highlight box for quadrants (White glow)
                    fill_col = (0, 0, 0, 0)
                    out_col = (255, 255, 255, 255)
                    hl_fill = (0, 0, 0, 0)
                    hl_out = (255, 255, 255, 255)
                    out_w = 8
                    radius = 30
                    blur_radius = 20
                elif template == "stadium":
                    # Slick Blue Glass-morphism boxes, Orange highlight
                    fill_col = (0, 0, 80, 180) # Semi-transparent blue
                    out_col = (255, 255, 255, 150)
                    hl_fill = (255, 140, 0, 230) # Orange
                    hl_out = (255, 255, 255, 255)
                    out_w = 4
                    radius = 20
                    blur_radius = 15
                elif template == "hazard":
                    # Sharp square boxes, Black fill, Red highlight
                    fill_col = (0, 0, 0, 255)
                    out_col = (0, 0, 0, 255)
                    hl_fill = (220, 0, 0, 255)
                    hl_out = (255, 255, 255, 255)
                    out_w = 0
                    radius = 0 
                    blur_radius = 0
                elif template == "retro":
                    # Sharp square boxes, black fill, Neon Pink border
                    fill_col = (0, 0, 0, 230)
                    out_col = (255, 0, 255, 255)
                    hl_fill = (0, 0, 0, 230)
                    hl_out = (0, 255, 255, 255)
                    out_w = 4
                    radius = 0 # Sharp corners
                    blur_radius = 10
                elif template == "gameboy":
                    # 8-bit Pixel boxes: Dark green border, Lighter green fill
                    fill_col = (130, 160, 10, 255)
                    out_col = (15, 56, 15, 255)
                    hl_fill = (15, 56, 15, 255)
                    hl_out = (255, 255, 255, 255)
                    out_w = 6
                    radius = 0 # Sharp pixel corners
                    blur_radius = 0
                elif template in ["omr", "omr_hand"]:
                    # Exam Sheet: White fill, Thin blue/black border
                    fill_col = (255, 255, 255, 255)
                    out_col = (50, 50, 150, 200) # Blue ink color
                    hl_fill = (255, 250, 250, 255) # Slightly red tint
                    hl_out = (255, 0, 0, 255) # Teacher's Red
                    out_w = 3
                    radius = 15
                    blur_radius = 5
                elif template == "wildlife":
                    # Nat Geo Style: Deep green fill, elegant thin gold/yellow border
                    fill_col = (10, 40, 10, 230)
                    out_col = (255, 204, 0, 255)
                    hl_fill = (255, 204, 0, 255)
                    hl_out = (255, 255, 255, 255)
                    out_w = 4
                    radius = 0 # Sharp elegant corners
                    blur_radius = 5
                elif template == "blueprint":
                    # Technical Blueprint: Dotted/Solid white border, blue tint
                    fill_col = (0, 60, 120, 150)
                    out_col = (255, 255, 255, 255)
                    hl_fill = (255, 255, 255, 200) # Solid white-ish
                    hl_out = (255, 255, 255, 255)
                    out_w = 4
                    radius = 0 # Architectural sharp corners
                    blur_radius = 5
                elif template == "chalkboard":
                    fill_col = (0, 0, 0, 0)
                    out_col = (0, 0, 0, 0)
                    hl_fill = (0, 0, 0, 0)
                    hl_out = (255, 255, 255, 255)
                    out_w = 5
                    blur_radius = 0
                elif template == "hacker":
                    fill_col = (0, 20, 0, 180)
                    out_col = (0, 255, 0, 255)
                    hl_fill = (0, 255, 0, 220)
                    hl_out = (0, 255, 0, 255)
                    out_w = 2
                    blur_radius = 0
                    radius = 0
                elif template == "pastel":
                    fill_col = (255, 255, 255, 140)
                    out_col = (255, 255, 255, 255)
                    hl_fill = (255, 107, 107, 255)
                    hl_out = (255, 255, 255, 255)
                    out_w = 4
                    blur_radius = 20
                    radius = 50
                else:
                    fill_col = (0, 0, 0, 150)
                    out_col = (255, 255, 255, 100)
                    hl_fill = (0, 180, 0, 220)
                    hl_out = (0, 255, 0, 255)
                    out_w = 3
                    blur_radius = 15

                # Normal box
                b_img = Image.new('RGBA', (opt_box_w + 100, opt_box_h + 100), (0,0,0,0))
                if template not in ["chalkboard", "hacker"]:
                    s_draw = ImageDraw.Draw(b_img)
                    shadow_col = (0,0,0,60) if template == "pastel" else (0,0,0,200)
                    s_draw.rounded_rectangle((50, 50, opt_box_w + 50, opt_box_h + 50), radius=radius, fill=shadow_col)
                    b_img = b_img.filter(ImageFilter.GaussianBlur(blur_radius))
                b_draw = ImageDraw.Draw(b_img)
                b_draw.rounded_rectangle((50, 50, opt_box_w + 50, opt_box_h + 50), radius=radius, fill=fill_col)
                if template != "chalkboard":
                    b_draw.rounded_rectangle((50, 50, opt_box_w + 50, opt_box_h + 50), radius=radius, outline=out_col, width=out_w)
                b_img.save(opt_box_path)
                
                # Highlight box
                h_img = Image.new('RGBA', (opt_box_w + 100, opt_box_h + 100), (0,0,0,0))
                if template not in ["chalkboard", "hacker"]:
                    hs_draw = ImageDraw.Draw(h_img)
                    h_shadow_col = (255, 107, 107, 100) if template == "pastel" else (0,200,0,200)
                    hs_draw.rounded_rectangle((50, 50, opt_box_w + 50, opt_box_h + 50), radius=radius, fill=h_shadow_col)
                    h_img = h_img.filter(ImageFilter.GaussianBlur(blur_radius))
                hb_draw = ImageDraw.Draw(h_img)
                hb_draw.rounded_rectangle((50, 50, opt_box_w + 50, opt_box_h + 50), radius=radius, fill=hl_fill)
                hb_draw.rounded_rectangle((50, 50, opt_box_w + 50, opt_box_h + 50), radius=radius, outline=hl_out, width=5)
                h_img.save(hl_box_path)

            opt_box_idx = get_input_idx(opt_box_path)
            hl_box_idx = get_input_idx(hl_box_path)

            # Animated Questions & Loader
            for idx, asset in enumerate(q_assets):
                start_t, reveal_t, end_t = asset['start_t'], asset['reveal_t'], asset['end_t']
                q_dur, a_dur, timer = asset['q_dur'], asset['a_dur'], asset['timer']
                
                # Audio
                q_at, a_at = int(start_t*1000), int(reveal_t*1000)
                audio_mixes.append(f"[{get_input_idx(asset['q_path'])}:a]volume=1.5,adelay={q_at}|{q_at}[a_q{idx}]")
                audio_mixes.append(f"[{get_input_idx(asset['a_path'])}:a]volume=1.5,adelay={a_at}|{a_at}[a_a{idx}]")
                if has_ticktock:
                    tt_at = int((start_t+q_dur)*1000)
                    if template == "omr":
                        tt_sound = os.path.join(music_dir, "ticktock.mp3")
                        audio_mixes.append(f"[{get_input_idx(tt_sound)}:a]atrim=0:{timer},adelay={tt_at}|{tt_at}[a_tt{idx}]")
                    elif template == "omr_hand":
                        tt_sound = os.path.join(music_dir, "pencil.mp3")
                        if not os.path.exists(tt_sound): tt_sound = os.path.join(music_dir, "ticktock.mp3")
                        audio_mixes.append(f"[{get_input_idx(tt_sound)}:a]atrim=0:{timer},adelay={tt_at}|{tt_at}[a_tt{idx}]")
                    else:
                        tt_sound = os.path.join(music_dir, "chalk.mp3" if template == "blueprint" else "ticktock.mp3")
                        if not os.path.exists(tt_sound): tt_sound = ticktock_path
                        audio_mixes.append(f"[{get_input_idx(tt_sound)}:a]atrim=0:{timer},adelay={tt_at}|{tt_at}[a_tt{idx}]")
                
                # Correct Answer Sound (8-bit Level Up for Gameboy / Shutter for Wildlife)
                reveal_sound_file = "shutter.mp3" if template == "wildlife" else ("levelup.mp3" if template == "gameboy" else "bing.mp3")
                bing_path = os.path.join(music_dir, reveal_sound_file)
                if not os.path.exists(bing_path): bing_path = os.path.join(music_dir, "bing.mp3")
                if os.path.exists(bing_path):
                    audio_mixes.append(f"[{get_input_idx(bing_path)}:a]volume=1.2,adelay={a_at}|{a_at}[a_bing{idx}]")

                # Question Text
                if template == "chat":
                    self.filter_graph.append(f"[{q_bubble_idx}:v]setpts=PTS-STARTPTS[q_bub_{idx}];")
                    self.filter_graph.append(f"{last_node}[q_bub_{idx}]overlay=enable=between(t\\,{start_t:.2f}\\,{end_t:.2f}):x=40:y={q_y}[v_q_bub_{idx}];")
                    last_node = f"[v_q_bub_{idx}]"
                    q_text_color = "black"
                    q_x = 80
                    q_y_text = q_y + 40
                else:
                    if template == "retro":
                        q_text_color = "#FF00FF"
                    elif template == "stadium":
                        q_text_color = "white"
                    elif template == "hazard":
                        q_text_color = "black"
                    elif template == "omr_hand":
                        q_text_color = "black"
                    elif template == "omr":
                        q_text_color = "black"
                    elif template in ["gameboy", "blueprint"]:
                        q_text_color = "white" if template == "blueprint" else "0x0f380f"
                    else:
                        q_text_color = "white" if template in ["millionaire", "chalkboard"] else ("0x00FF00" if template == "hacker" else ("#333333" if template == "pastel" else "yellow"))
                    q_x = 80
                    q_y_text = q_y
                    
                q_wrap_w = 22 if template == "blueprint" else (26 if template == "gameboy" else (22 if template == "hacker" else 28))
                q_size = 60 if template in ["hazard", "gameboy"] else 70
                last_node = self.add_line_to_graph(last_node, f"Q{idx+1}: {asset['q_text']}", question_font, q_text_color, q_size, q_x, q_y_text, q_wrap_w, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", align="left" if template == "chat" else "center", fade=True, video_id=video_id)
                
                # Question Count Tag
                tag_text = f"{idx+1} OF {qty}"
                if template == "retro":
                    tag_color = "#00FFFF"
                elif template == "stadium":
                    tag_color = "#FFD700" # Gold
                elif template == "hazard":
                    tag_color = "black"
                elif template in ["omr", "omr_hand"]:
                    tag_color = "0x323296" # Dark Blue Ink
                else:
                    tag_color = "white" if template == "chalkboard" else ("0x00FF00" if template == "hacker" else ("#555555" if template == "pastel" else ("#888888" if template == "chat" else "gray")))
                tag_y = q_y - 50 if template != "chat" else q_y + q_h + 10
                tag_align = "center" if template != "chat" else "left"
                tag_x = 0 if template != "chat" else 60
                last_node = self.add_line_to_graph(last_node, tag_text, answer_font, tag_color, 45, tag_x, tag_y, 30, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", align=tag_align, fade=True, video_id=video_id)
                
                # Draw Options
                for i, opt_text in enumerate(asset['options']):
                    o_y = opt_start_y + i * (opt_h + opt_gap_y)
                    
                    if template == "chat":
                        self.filter_graph.append(f"[{opt_bubble_idx}:v]setpts=PTS-STARTPTS[obub_{idx}_{i}];")
                        self.filter_graph.append(f"{last_node}[obub_{idx}_{i}]overlay=enable=between(t\\,{start_t:.2f}\\,{end_t:.2f}):x={VIDEO_WIDTH - opt_w - 60}:y={o_y}[v_o_bub_{idx}_{i}];")
                        last_node = f"[v_o_bub_{idx}_{i}]"
                        
                        # Correct Highlight
                        if i == asset['correct_idx']:
                            self.filter_graph.append(f"[{hl_bubble_idx}:v]setpts=PTS-STARTPTS[hlbub_{idx}];")
                            self.filter_graph.append(f"{last_node}[hlbub_{idx}]overlay=reveal=between(t\\,{reveal_t:.2f}\\,{end_t:.2f}):x={VIDEO_WIDTH - opt_w - 60}:y={o_y}[v_h_bub_{idx}];")
                            # Wait, 'reveal' is not a valid param for overlay, just enable.
                            self.filter_graph[-1] = self.filter_graph[-1].replace("reveal=", "enable=")
                            last_node = f"[v_h_bub_{idx}]"
                        
                        prefix = ["A.", "B.", "C.", "D."][i]
                        opt_display = f"{prefix} {opt_text}"
                        opt_x = VIDEO_WIDTH - opt_w - 30
                        opt_y_text = o_y + 65 # Centered for Chat bubble
                        
                        last_node = self.add_line_to_graph(last_node, opt_display, answer_font, "white", 60, opt_x, opt_y_text, 25, align="left", enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", video_id=video_id)
                        
                        if i == asset['correct_idx']:
                            last_node = self.add_line_to_graph(last_node, opt_display, question_font, "white", 65, opt_x, opt_y_text, 25, align="left", enable=f"between(t\\,{reveal_t:.2f}\\,{end_t:.2f})", video_id=video_id)
                        
                        continue
                    else:
                        if template in ["grid", "millionaire", "quadrants"]:
                            row = i // 2
                            col = i % 2
                            total_grid_w = 2 * opt_w + opt_gap_x
                            start_x = (VIDEO_WIDTH - total_grid_w) // 2
                            ox = start_x + col * (opt_w + opt_gap_x)
                            oy = opt_start_y + row * (opt_h + opt_gap_y)
                        else:
                            ox = (VIDEO_WIDTH - opt_w) // 2
                            oy = opt_start_y + i * (opt_h + opt_gap_y)
                    
                    # Normal Box
                    if template == "quadrants":
                        padding = 50
                        q_box_path = os.path.join(self.assets_dir, f"quad_box_{i}_{opt_w}_{opt_h}.png")
                        q_box_idx = get_input_idx(q_box_path)
                        self.filter_graph.append(f"[{q_box_idx}:v]setpts=PTS-STARTPTS[qbox_{idx}_{i}];")
                        self.filter_graph.append(f"{last_node}[qbox_{idx}_{i}]overlay=enable=between(t\\,{start_t:.2f}\\,{end_t:.2f}):x={ox - padding}:y={oy - padding}[v_o_{idx}_{i}];")
                        last_node = f"[v_o_{idx}_{i}]"
                    elif template == "omr_hand":
                        # No box for OMR Hand, just text on ruled paper
                        pass
                    else:
                        self.filter_graph.append(f"[{opt_box_idx}:v]setpts=PTS-STARTPTS[obox_{idx}_{i}];")
                        padding = 50 if template == "pastel" else 30
                        self.filter_graph.append(f"{last_node}[obox_{idx}_{i}]overlay=enable=between(t\\,{start_t:.2f}\\,{end_t:.2f}):x={ox - padding}:y={oy - padding}[v_o_{idx}_{i}];")
                        last_node = f"[v_o_{idx}_{i}]"
                    
                    # Normal Text
                    prefix = ["A:", "B:", "C:", "D:"][i] if template == "millionaire" else ["A.", "B.", "C.", "D."][i]
                    opt_display = f"{prefix} {opt_text}"
                    
                    if template == "millionaire":
                        # Dual color logic: prefix orange, text white
                        wrapped_opt = wrap_text(opt_text, width=15)
                        lines = wrapped_opt.split('\n')
                        text_h = len(lines) * (50 * 1.15)
                        ty = oy + (opt_h - text_h) // 2 + 30 # Centered for Millionaire
                        
                        # Prefix
                        last_node = self.add_line_to_graph(last_node, prefix, question_font, "orange", 55, ox + 30, ty, 5, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", align="left", video_id=video_id)
                        # Text
                        last_node = self.add_line_to_graph(last_node, wrapped_opt, answer_font, "white", 50, ox + 90, ty, 15, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", align="left", video_id=video_id)
                        
                        text_x_hl, text_y_hl = ox + 90, ty
                        hl_size, hl_align, hl_wrap = 55, "left", 15
                        hl_text = wrapped_opt
                        prefix_hl_size = 60
                    elif template == "grid":
                        wrapped_opt = wrap_text(opt_display, width=16)
                        lines = wrapped_opt.split('\n')
                        text_h = len(lines) * (50 * 1.15)
                        ty = oy + (opt_h - text_h) // 2 + 30 # Centered for Grid
                        text_x_expr = f"{ox}+({opt_w}-text_w)/2"
                        last_node = self.add_line_to_graph(last_node, wrapped_opt, answer_font, "white", 50, text_x_expr, ty, 16, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", align="custom", video_id=video_id)
                        text_x_hl, text_y_hl = text_x_expr, ty
                        hl_size, hl_align, hl_wrap = 55, "custom", 16
                        hl_text = wrapped_opt
                    else:
                        if template == "retro":
                            opt_wrap_w = 32
                            lines = wrap_text(opt_display, width=opt_wrap_w).split('\n')
                            text_h = len(lines) * (60 * 1.15)
                            text_y = oy + (opt_h - text_h) // 2 + 35 # Centered for Retro
                            last_node = self.add_line_to_graph(last_node, opt_display, answer_font, "white", 60, 0, text_y, opt_wrap_w, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", align="center", video_id=video_id)
                            text_x_hl, text_y_hl = 0, text_y
                            hl_size, hl_align, hl_wrap = 65, "center", opt_wrap_w
                            hl_text = opt_display
                        elif template == "quadrants":
                            opt_wrap_w = 16
                            lines = wrap_text(opt_display, width=opt_wrap_w).split('\n')
                            text_h = len(lines) * (65 * 1.15)
                            text_y = oy + (opt_h - text_h) // 2 + 35 # Centered for Quadrants
                            text_x_expr = f"{ox}+({opt_w}-text_w)/2"
                            last_node = self.add_line_to_graph(last_node, opt_display, question_font, "white", 65, text_x_expr, text_y, opt_wrap_w, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", align="custom", video_id=video_id)
                            text_x_hl, text_y_hl = text_x_expr, text_y
                            hl_size, hl_align, hl_wrap = 75, "custom", opt_wrap_w
                            hl_text = opt_display
                        elif template == "gameboy":
                            opt_wrap_w = 26
                            lines = wrap_text(opt_display, width=opt_wrap_w).split('\n')
                            text_h = len(lines) * (60 * 1.15)
                            text_y = oy + (opt_h - text_h) // 2 + 25 # Refined vertical centering for Gameboy font
                            last_node = self.add_line_to_graph(last_node, opt_display, question_font, "0x0f380f", 60, 0, text_y, opt_wrap_w, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", align="center", video_id=video_id)
                            text_x_hl, text_y_hl = 0, text_y
                            hl_size, hl_align, hl_wrap = 65, "center", opt_wrap_w
                            hl_text = opt_display
                        else:
                            if template == "hazard":
                                opt_font_col = "#FFCC00" # Aggressive Yellow
                                opt_wrap_w = 28
                                lines = wrap_text(opt_display, width=opt_wrap_w).split('\n')
                                text_h = len(lines) * (60 * 1.15)
                                text_y = oy + (opt_h - text_h) // 2 + 5 # Small offset for visual balance
                                last_node = self.add_line_to_graph(last_node, opt_display, answer_font, opt_font_col, 60, 0, text_y, opt_wrap_w, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", align="center", video_id=video_id)
                                text_x_hl, text_y_hl = 0, text_y
                                hl_size, hl_align, hl_wrap = 65, "center", opt_wrap_w
                                hl_text = opt_display
                            else:
                                if template == "stadium":
                                    opt_wrap_w = 28
                                    lines = wrap_text(opt_display, width=opt_wrap_w).split('\n')
                                    text_h = len(lines) * (60 * 1.15)
                                    text_y = oy + (opt_h - text_h) // 2 + 10 # Centered with margin
                                    # Increased x from 80 to 110 to keep A,B,C,D safely inside the box
                                    last_node = self.add_line_to_graph(last_node, opt_display, answer_font, "white", 60, 110, text_y, opt_wrap_w, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", align="left", video_id=video_id)
                                    text_x_hl, text_y_hl = 110, text_y
                                    hl_size, hl_align, hl_wrap = 65, "left", opt_wrap_w
                                    hl_text = opt_display
                                else:
                                    opt_font_col = "0x00FF00" if template == "hacker" else ("#333333" if template == "pastel" else "white")
                                    opt_wrap_w = 24 if template == "hacker" else 30
                                    lines = wrap_text(opt_display, width=opt_wrap_w).split('\n')
                                    text_h = len(lines) * (60 * 1.15)
                                    text_y = oy + (opt_h - text_h) // 2 + 35 # Global vertical centering fix
                                    text_x = ox + 45 # Increased padding to keep A,B,C,D inside
                                    last_node = self.add_line_to_graph(last_node, opt_display, answer_font, opt_font_col, 60, text_x, text_y, opt_wrap_w, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", align="left", video_id=video_id)
                                    text_x_hl, text_y_hl = text_x, text_y
                                    hl_size, hl_align, hl_wrap = 65, "left", opt_wrap_w
                                    hl_text = opt_display

                    # Highlight Box (if correct)
                    if i == asset['correct_idx'] and template != "omr_hand":
                        self.filter_graph.append(f"[{hl_box_idx}:v]setpts=PTS-STARTPTS[hlbox_{idx}];")
                        padding = 50 if template == "pastel" else 30
                        self.filter_graph.append(f"{last_node}[hlbox_{idx}]overlay=enable=between(t\\,{reveal_t:.2f}\\,{end_t:.2f}):x={ox - padding}:y={oy - padding}[v_h_{idx}];")
                        last_node = f"[v_h_{idx}]"
                        
                        # Highlight Text
                        hl_font_col = "white" if template == "hazard" else ("black" if template == "hacker" else "white")
                        if template == "millionaire":
                            # Draw prefix highlight
                            last_node = self.add_line_to_graph(last_node, prefix, question_font, "orange", prefix_hl_size, ox + 30, ty, 5, enable=f"between(t\\,{reveal_t:.2f}\\,{end_t:.2f})", align="left", video_id=video_id)
                            # Draw text highlight
                            last_node = self.add_line_to_graph(last_node, hl_text, question_font, hl_font_col, hl_size, text_x_hl, text_y_hl, hl_wrap, enable=f"between(t\\,{reveal_t:.2f}\\,{end_t:.2f})", align=hl_align, video_id=video_id)
                        else:
                            last_node = self.add_line_to_graph(last_node, hl_text, question_font, hl_font_col, hl_size, text_x_hl, text_y_hl, hl_wrap, enable=f"between(t\\,{reveal_t:.2f}\\,{end_t:.2f})", align=hl_align, video_id=video_id)

                        if template == "omr":
                             # Simple Red Tick without hand
                             tick_font = get_font_path("segoepr.ttf", fonts_dir)
                             last_node = self.add_line_to_graph(last_node, "✔", tick_font, "red", 140, ox - 30, oy - 40, align="left", enable=f"between(t\\,{reveal_t:.2f}\\,{end_t:.2f})", video_id=video_id)

                # HAND ANIMATION (OMR_HAND ONLY) - Must be at end of question loop to be on top
                if template == "omr_hand" and 'hand' in indices:
                    hand_idx = indices['hand']
                    h_w = 1000 # Doubled size
                    hand_node = f"vhand{idx}"
                    self.filter_graph.append(f"[{hand_idx}:v]colorkey=white:0.1,scale={h_w}:-1,setpts=PTS-STARTPTS[{hand_node}];")
                    
                    # 1. Pointing at Question (start_t -> start_t + q_dur)
                    q_text = asset['q_text']
                    words = q_text.split()
                    q_lines = wrap_text(q_text, width=22).split('\n')
                    
                    # Hand Tip Offset (Calibrated for the scale 1000)
                    tip_off_x = -250
                    tip_off_y = -450
                    
                    pointing_parts_x = []
                    pointing_parts_y = []
                    t_curr = start_t
                    line_y = q_y
                    
                    for l_idx, line in enumerate(q_lines):
                        l_words = line.split()
                        l_w_dur = q_dur * (len(l_words) / len(words)) if len(words)>0 else 0
                        l_start_t = t_curr
                        l_end_t = t_curr + l_w_dur
                        t_curr = l_end_t
                        
                        l_width_est = len(line) * 35
                        l_x_start = (VIDEO_WIDTH - l_width_est) // 2
                        l_x_end = l_x_start + l_width_est
                        
                        # Point slightly above/at the words
                        l_y_pos = line_y + 80
                        
                        px = f"if(between(t\\,{l_start_t:.2f}\\,{l_end_t:.2f})\\,{l_x_start}+({l_x_end}-{l_x_start})*(t-{l_start_t:.2f})/{l_w_dur:.2f}+{tip_off_x:.2f}\\,0)"
                        py = f"if(between(t\\,{l_start_t:.2f}\\,{l_end_t:.2f})\\,{l_y_pos}+{tip_off_y:.2f}\\,0)"
                        pointing_parts_x.append(px)
                        pointing_parts_y.append(py)
                        line_y += int(70 * 1.15)

                    # 2. Waiting Position (During Timer: t_start_timer -> reveal_t)
                    # Move hand to the right side of the screen, out of the way
                    wait_x = VIDEO_WIDTH - 150 + tip_off_x
                    wait_y = opt_start_y + (opt_h * 2) + tip_off_y # Roughly middle of options area
                    t_start_timer = start_t + q_dur
                    
                    w_px = f"if(between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f})\\,{wait_x:.2f}\\,0)"
                    w_py = f"if(between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f})\\,{wait_y:.2f}\\,0)"

                    # 3. Ticking Correct Answer (reveal_t -> reveal_t + 1.0)
                    correct_opt = asset['options'][asset['correct_idx']]
                    c_ox = (VIDEO_WIDTH - opt_w) // 2
                    c_oy = opt_start_y + asset['correct_idx'] * (opt_h + opt_gap_y)
                    c_width_est = len(correct_opt) * 45
                    tick_target_x = c_ox + c_width_est + 50
                    tick_target_y = c_oy + 50
                    
                    # Slide from wait position to tick target
                    t_px = f"if(between(t\\,{reveal_t:.2f}\\,{reveal_t+1.0:.2f})\\,if(lte(t\\,{reveal_t+0.4:.2f})\\,{wait_x}+({tick_target_x}+{tip_off_x}-{wait_x})*(t-{reveal_t:.2f})/0.4\\,{tick_target_x}+{tip_off_x})\\,0)"
                    t_py = f"if(between(t\\,{reveal_t:.2f}\\,{reveal_t+1.0:.2f})\\,if(lte(t\\,{reveal_t+0.4:.2f})\\,{wait_y}+({tick_target_y}+{tip_off_y}-{wait_y})*(t-{reveal_t:.2f})/0.4\\,{tick_target_y}+{tip_off_y})\\,0)"
                    
                    final_hand_x = f"({' + '.join(pointing_parts_x)} + {w_px} + {t_px})"
                    final_hand_y = f"({' + '.join(pointing_parts_y)} + {w_py} + {t_py})"
                    
                    self.filter_graph.append(f"{last_node}[{hand_node}]overlay=enable=between(t\\,{start_t:.2f}\\,{reveal_t+1.0:.2f}):x={final_hand_x}:y={final_hand_y}[v_hnd_{idx}];")
                    last_node = f"[v_hnd_{idx}]"
                    
                    tick_font = get_font_path("segoepr.ttf", fonts_dir)
                    last_node = self.add_line_to_graph(last_node, "v", tick_font, "orange", 140, tick_target_x, tick_target_y - 40, align="left", enable=f"between(t\\,{reveal_t+0.4:.2f}\\,{end_t:.2f})", video_id=video_id)
                
                t_start_timer = start_t + q_dur
                
                # Loader Bar
                prog_expr = f"(({timer}-(t-{t_start_timer:.2f}))/{timer})"
                l_w = VIDEO_WIDTH - (2 * self.side_margin)
                
                if template in ["classic", "grid"]:
                    # Premium Star Timer
                    self.filter_graph.append(f"[{indices['loader_frame']}:v]scale={l_w}:{l_h}[vframe{idx}];")
                    self.filter_graph.append(f"{last_node}[vframe{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x={self.side_margin}:y={l_y}[vfr{idx}];")
                    
                    self.filter_graph.append(f"[{indices['loader_fill']}:v]scale={l_w}:{l_h}[vfill{idx}];")
                    self.filter_graph.append(f"color=c=black:s={l_w}x{l_h}[vmask_b{idx}];")
                    self.filter_graph.append(f"[{indices['loader_fill']}:v]alphaextract,scale={l_w}:{l_h}[vfill_alpha{idx}];")
                    self.filter_graph.append(f"[vfill_alpha{idx}][vmask_b{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x=-{l_w}*{prog_expr}:y=0[vmask_an{idx}];")
                    self.filter_graph.append(f"[vfill{idx}][vmask_an{idx}]alphamerge[vfill_m{idx}];")
                    self.filter_graph.append(f"[vfr{idx}][vfill_m{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x={self.side_margin}:y={l_y}[vfb{idx}];")
                    
                    star_size = 180
                    self.filter_graph.append(f"[{indices['loader_star']}:v]scale={star_size}:-1[vstar{idx}];")
                    self.filter_graph.append(f"[vfb{idx}][vstar{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x={self.side_margin}+{l_w}*(1-{prog_expr})-{star_size}/2:y={l_y}+{l_h}/2-{star_size}/2[vls{idx}];")
                    last_node = f"[vls{idx}]"
                else:
                    # Dynamic Shrinking Progress Bars
                    if template == "millionaire":
                        tw, th = l_w, 40
                        bg_c = "0x000032"
                        fill_c = "0xFFD700"
                    elif template == "chalkboard":
                        tw, th = l_w, 15
                        bg_c = "0x283e2e"
                        fill_c = "white"
                    elif template == "pastel":
                        tw, th = l_w, 15
                        bg_c = "0xFFFFFF@0.3"
                        fill_c = "white"
                    elif template == "hazard":
                        tw, th = l_w, 20
                        bg_c = "black"
                        fill_c = "red"
                    elif template == "stadium":
                        tw, th = l_w, 20
                        bg_c = "0x000044"
                        fill_c = "0x00FF00" # Neon Green (Grass vibe)
                    elif template == "blueprint":
                        tw, th = l_w, 10
                        bg_c = "white@0.2"
                        fill_c = "white"
                    else: # hacker
                        tw, th = l_w, 20
                        bg_c = "0x003300"
                        fill_c = "0x00FF00"
                        
                    tx = self.side_margin
                    ty = l_y + (l_h - th) // 2
                    
                    self.filter_graph.append(f"color=c={bg_c}:s={tw}x{th}[tbg{idx}];")
                    self.filter_graph.append(f"color=c={fill_c}:s={tw}x{th}[tfill{idx}];")
                    
                    # Slide the fill bar left
                    self.filter_graph.append(f"[tbg{idx}][tfill{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x=-{tw}*(1-{prog_expr}):y=0[tbar{idx}];")
                    
                    if template == "millionaire":
                        self.filter_graph.append(f"[tbar{idx}]drawbox=x=0:y=0:w={tw}:h={th}:color=0xFFD700:thickness=3[tbar_f{idx}];")
                        final_tbar = f"[tbar_f{idx}]"
                    else:
                        final_tbar = f"[tbar{idx}]"
                        
                    self.filter_graph.append(f"{last_node}{final_tbar}overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x={tx}:y={ty}[vls{idx}];")
                    last_node = f"[vls{idx}]"
                    
                    if template == "blueprint":
                        # Vertical Scan Line (Sweeping Laser)
                        scan_x = f"{self.side_margin} + {l_w} * (1-{prog_expr})"
                        self.filter_graph.append(f"color=c=white@0.6:s=10x{VIDEO_HEIGHT}[scan{idx}];")
                        self.filter_graph.append(f"{last_node}[scan{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x={scan_x}:y=0[vscan{idx}];")
                        last_node = f"[vscan{idx}]"
                    
                    if template in ["millionaire", "hacker"]:
                        cd_font = question_font
                        cd_color = "0x00FF00" if template == "hacker" else "white"
                        last_node = self.add_line_to_graph(last_node, "TIME REMAINING", cd_font, cd_color, 45, 0, ty - 70, wrap_w=30, align="center", enable=f"between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f})", video_id=video_id)

            # END SCREEN SETTINGS
            # score_start and score_end handled above for audio sync
            total_duration = score_end
            
            # End Screen Background
            self.filter_graph.append(f"{last_node}drawbox=enable=between(t\\,{score_start}\\,{score_end}):x=0:y=0:w={VIDEO_WIDTH}:h={VIDEO_HEIGHT}:color=black:t=fill[v_endbg{video_id}];")
            
            # End Logo & Text
            self.filter_graph.append(f"[{indices['logo']}:v]scale=250:-1,setpts=PTS-STARTPTS[end_logo];")
            self.filter_graph.append(f"[v_endbg{video_id}][end_logo]overlay=enable=between(t\\,{score_start}\\,{score_end}):x=(W-250)/2:y=200[v_endl{video_id}];")
            
            tyfw_text = "Thank you for watching!"
            last_node = self.add_line_to_graph(f"[v_endl{video_id}]", tyfw_text, heading_font, "red", 80, 0, 480, 30, f"between(t\\,{score_start}\\,{score_end})", fade=True, video_id=video_id)
            
            score_text = f"How many did you get right?\n{qty}/{qty} = Genius!"
            last_node = self.add_line_to_graph(last_node, score_text, question_font, "yellow", 65, 0, 600, 30, f"between(t\\,{score_start}\\,{score_end})", fade=True, video_id=video_id)

            # Subscribe Button Animation
            sub_y = VIDEO_HEIGHT - 550
            btn_w = 420
            btn_x = (VIDEO_WIDTH - btn_w) / 2
            
            like_text = "👍 LIKE THIS VIDEO!"
            last_node = self.add_line_to_graph(last_node, like_text, question_font, "white", 60, 0, sub_y - 120, 30, f"between(t\\,{score_start}\\,{score_end})", fade=True, video_id=video_id)

            self.filter_graph.append(f"[{indices['btn_sub']}:v]scale={btn_w}:-1,setpts=PTS-STARTPTS[btn_sub_s];")
            self.filter_graph.append(f"{last_node}[btn_sub_s]overlay=enable=between(t\\,{score_start}\\,{score_start+2.5}):x={btn_x}:y={sub_y}[v_btn1];")
            
            self.filter_graph.append(f"[{indices['btn_subbed']}:v]scale={btn_w}:-1,setpts=PTS-STARTPTS[btn_subbed_s];")
            self.filter_graph.append(f"[v_btn1][btn_subbed_s]overlay=enable=between(t\\,{score_start+2.5}\\,{score_end}):x={btn_x}:y={sub_y}[v_btn2];")

            # Cursor Logic
            c_start_x, c_start_y = 1000, 1800
            c_end_x, c_end_y = btn_x + 280, sub_y + 40
            anim_time = f"(t-{score_start}-1.0)"
            clamp_time = f"min(max(0\\, {anim_time})\\, 1.5)"
            move_x = f"{c_start_x} + ({c_end_x} - {c_start_x})/1.5 * {clamp_time}"
            move_y = f"{c_start_y} + ({c_end_y} - {c_start_y})/1.5 * {clamp_time}"
            
            self.filter_graph.append(f"[{indices['cursor']}:v]split[cur_in1][cur_in2];")
            self.filter_graph.append(f"[cur_in1]scale=120:-1,setpts=PTS-STARTPTS,split=2[cur1a][cur1b];")
            self.filter_graph.append(f"[cur_in2]scale=90:-1,setpts=PTS-STARTPTS[cur2];")
            
            self.filter_graph.append(f"[v_btn2][cur1a]overlay=enable=between(t\\,{score_start}\\,{score_start+2.4}):x={move_x}:y={move_y}[vc1];")
            self.filter_graph.append(f"[vc1][cur2]overlay=enable=between(t\\,{score_start+2.4}\\,{score_start+2.6}):x={c_end_x+10}:y={c_end_y+10}[vc2];")
            
            out_anim_time = f"(t-{score_start}-2.6)"
            clamp_out = f"min(max(0\\, {out_anim_time})\\, 2.4)"
            move_curr_x = f"{c_end_x} + (1200 - {c_end_x})/2.4 * {clamp_out}"
            move_curr_y = f"{c_end_y} + (1800 - {c_end_y})/2.4 * {clamp_out}"
            self.filter_graph.append(f"[vc2][cur1b]overlay=enable=between(t\\,{score_start+2.6}\\,{score_end}):x={move_curr_x}:y={move_curr_y}[vc3];")
            
            # Progress Bar (Bottom)
            self.filter_graph.append(f"[vc3]drawbox=x=0:y={VIDEO_HEIGHT-15}:w={VIDEO_WIDTH}:h=15:color=black@0.4:t=fill[v_hbg2_{video_id}];")
            self.filter_graph.append(f"color=c=red:s={VIDEO_WIDTH}x15[pgfg{video_id}];")
            self.filter_graph.append(f"[v_hbg2_{video_id}][pgfg{video_id}]overlay=x='-w+w*(t/{total_duration})':y={VIDEO_HEIGHT-15}[vpb{video_id}];")
            last_node = f"[vpb{video_id}]"

            # End Screen Bell
            if template in ["omr", "omr_hand"]:
                bell_path = os.path.join(music_dir, "bell.mp3")
                if os.path.exists(bell_path):
                    at = int(score_start * 1000)
                    audio_mixes.append(f"[{get_input_idx(bell_path)}:a]volume=1.5,adelay={at}|{at}[a_bell]")

            # Final mixing
            outro_at = int(score_start * 1000)
            audio_mixes.append(f"[{get_input_idx(outro_audio_path)}:a]volume=1.5,adelay={outro_at}|{outro_at}[a_outro]")

            amix_tags = ""
            for m in audio_mixes:
                bracket_start = m.rfind('[')
                if bracket_start != -1: amix_tags += m[bracket_start:]
            
            if is_preview:
                # In preview mode, we only need video filters
                full_filter = ";".join([f.strip().rstrip(';') for f in self.filter_graph]).rstrip(';')
            else:
                num_audio_inputs = len(audio_mixes) + 1
                anchor_filter = f"aevalsrc=0:d={total_duration}[anchor{video_id}];"
                
                if has_bgm:
                    # Dynamic volume: 0.05 during quiz, 0.25 during end screen
                    bgm_vol = f"if(between(t\\,{score_start}\\,{score_end})\\,0.25\\,0.05)"
                    # We add audio filters to a local list for final combination to keep filter_graph clean
                    audio_filters = [f"[0:a]volume={bgm_vol}:eval=frame[bgm_v{video_id}]"]
                    num_audio_inputs += 1
                    final_mixer = f"{anchor_filter} [anchor{video_id}][bgm_v{video_id}]{amix_tags}amix=inputs={num_audio_inputs}:duration=first:normalize=0[aout{video_id}]"
                else:
                    audio_filters = []
                    final_mixer = f"{anchor_filter} [anchor{video_id}]{amix_tags}amix=inputs={num_audio_inputs}:duration=first:normalize=0[aout{video_id}]"
                
                full_filter = ";".join([f.strip().rstrip(';') for f in self.filter_graph]).rstrip(';') + ";" + \
                             ";".join(audio_filters + audio_mixes).rstrip(';') + ";" + final_mixer
                
            filter_script_path = os.path.abspath(os.path.join(output_dir, f"v{video_id}_filter.txt")).replace('\\', '/')
            with open(filter_script_path, "w", encoding="utf-8") as f: f.write(full_filter)
            
            if is_preview:
                preview_target_time = q_assets[0]['reveal_t'] + 0.5 if q_assets else 2.0
                out_path = os.path.join(output_dir, f"Preview_{topic}_{video_id}_{datetime.datetime.now().strftime('%M%S')}.png")
                cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-an"] + self.input_cmds
                for p in input_paths: cmd.extend(["-i", p.replace('\\', '/')])
                return self.render_preview(cmd, filter_script_path, out_path, preview_target_time, last_node, video_id)
            
            out_path = os.path.join(output_dir, f"Quiz_{topic}_{video_id}_{datetime.datetime.now().strftime('%M%S')}.mp4")
            cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y"] + self.input_cmds
            for p in input_paths: cmd.extend(["-i", p.replace('\\', '/')])
            
            return self.render_final(cmd, filter_script_path, out_path, total_duration, last_node, video_id)

        except Exception as e:
            print(f"Error building video: {e}")
            import traceback
            traceback.print_exc()
            return False
