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
    def build_video(self, video_id, topic, questions, bg_type, music_dir, images_dir, videos_dir, fonts_dir, voiceovers_dir, output_dir, tts_voice, is_preview=False):
        try:
            print(f"\n[Engine][V{video_id}] Building Text Quiz: {topic}")
            qty = len(questions)
            heading_font = get_font_path("BebasNeue-Regular.ttf", fonts_dir)
            question_font = get_font_path("Poppins-Bold.ttf", fonts_dir)
            answer_font = get_font_path("Poppins-Regular.ttf", fonts_dir)
            topic_display = random.choice(self.hooks).format(Topic=topic.strip(), Qty=qty)
            intro_text = topic_display
            print(f"[V{video_id}] Hook/Intro: {intro_text}")
            cta_text = "If you are still here\nhit like, subscribe and comment\nhow many answer were correct."
            
            # 1. Background Logic
            has_bgm = os.path.exists(os.path.join(music_dir, "background_music.mp3"))
            if has_bgm:
                bgm_path = os.path.join(music_dir, "background_music.mp3")
                self.input_cmds.extend(["-stream_loop", "-1", "-i", bgm_path.replace('\\', '/')])
            
            bg_input_idx = -1
            if bg_type == "image":
                bg_files = glob.glob(os.path.join(images_dir, "backgrounds", "*.*"))
                if bg_files:
                    bg_file = random.choice(bg_files)
                    self.input_cmds.extend(["-loop", "1", "-i", bg_file.replace('\\', '/')])
                    bg_input_idx = 1 if has_bgm else 0
            elif bg_type == "video":
                vid_files = glob.glob(os.path.join(videos_dir, "*.*"))
                if vid_files:
                    bg_file = random.choice(vid_files)
                    self.input_cmds.extend(["-stream_loop", "-1", "-i", bg_file.replace('\\', '/')])
                    bg_input_idx = 1 if has_bgm else 0

            audio_offset = (1 if has_bgm else 0) + (1 if bg_input_idx != -1 else 0)
            indices = self.build_common_assets(video_id, audio_offset)
            
            # Voiceovers
            intro_audio_path = os.path.join(voiceovers_dir, f"intro_{get_hash(intro_text)}.mp3")
            asyncio.run(generate_voiceover(intro_text, intro_audio_path, tts_voice))
            intro_dur = get_duration(intro_audio_path)
            
            ticktock_path = os.path.join(music_dir, "ticktock.mp3")
            clap_path = os.path.join(music_dir, "bing.mp3")
            has_ticktock = os.path.exists(ticktock_path)
            has_clap = os.path.exists(clap_path)
            
            # Input Paths for Q&A audio
            input_paths = []
            def get_input_idx(path):
                idx = audio_offset + 7 + len(input_paths)
                input_paths.append(path)
                return idx

            audio_mixes = []
            intro_idx = get_input_idx(intro_audio_path)
            audio_mixes.append(f"[{intro_idx}:a]volume=1.5,adelay=0|0[a_intro]")
            
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
            outro_hook = random.choice(self.outro_variations)
            outro_text = f"{outro_hook} {self.channel_cta}"
            outro_audio_path = os.path.join(voiceovers_dir, f"outro_{get_hash(outro_text)}.mp3")
            asyncio.run(generate_voiceover(outro_text, outro_audio_path, tts_voice))
            outro_dur = get_duration(outro_audio_path)
            print(f"[V{video_id}] Outro: {outro_text[:50]}...")
            
            score_start = temp_time
            score_end = score_start + max(5.0, outro_dur + 1.0)
            total_duration = score_end
            
            # DRAWING LOGIC WITH EQUAL SPACING
            # Layout
            header_h = 320
            q_h = 240
            opt_h = 130
            opt_gap = 30
            l_h = 160
            
            q_y = header_h + 60
            opt_start_y = q_y + q_h + 40
            l_y = opt_start_y + 4 * opt_h + 3 * opt_gap + 60
            
            # Start Graph
            if bg_input_idx != -1:
                self.filter_graph.append(f"[{bg_input_idx}:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}[bg{video_id}];")
            else:
                self.filter_graph.append(f"color=c=black:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r=24[bg{video_id}];")
            
            last_node = f"[bg{video_id}]"
            
            # Header Box
            self.filter_graph.append(f"{last_node}drawbox=x=0:y=0:w={VIDEO_WIDTH}:h={header_h}:color=white:t=fill[v_hbg{video_id}];")
            last_node = f"[v_hbg{video_id}]"
            
            # Logo (Bottom right corner)
            self.filter_graph.append(f"[{indices['logo']}:v]scale=120:-1[vlogo{video_id}];")
            self.filter_graph.append(f"{last_node}[vlogo{video_id}]overlay=x=W-w-40:y=H-h-60[vl{video_id}];")
            last_node = f"[vl{video_id}]"
            
            # Heading Text (Fully Centered since logo moved)
            h_size = 130 if len(topic_display) < 22 else 90
            lines = wrap_text(topic_display, width=24).split('\n') 
            total_text_h = len(lines) * (h_size * 1.15)
            start_y = (header_h - total_text_h) // 2
            last_node = self.add_line_to_graph(last_node, topic_display, heading_font, "red", h_size, 0, start_y, wrap_w=24, align="center", video_id=video_id)
            
            # Option Box Gen
            opt_box_w = 900
            opt_box_h = 130
            opt_box_path = os.path.join(self.assets_dir, f"opt_box_{opt_box_w}_{opt_box_h}.png")
            hl_box_path = os.path.join(self.assets_dir, f"hl_box_{opt_box_w}_{opt_box_h}.png")
            
            if not os.path.exists(opt_box_path) or not os.path.exists(hl_box_path):
                from PIL import Image, ImageDraw, ImageFilter
                # Normal box
                b_img = Image.new('RGBA', (opt_box_w + 60, opt_box_h + 60), (0,0,0,0))
                s_draw = ImageDraw.Draw(b_img)
                s_draw.rounded_rectangle((30, 30, opt_box_w + 30, opt_box_h + 30), radius=40, fill=(0,0,0,200))
                b_img = b_img.filter(ImageFilter.GaussianBlur(15))
                b_draw = ImageDraw.Draw(b_img)
                b_draw.rounded_rectangle((30, 30, opt_box_w + 30, opt_box_h + 30), radius=40, fill=(0,0,0, 150))
                b_draw.rounded_rectangle((30, 30, opt_box_w + 30, opt_box_h + 30), radius=40, outline=(255,255,255,100), width=3)
                b_img.save(opt_box_path)
                
                # Highlight box
                h_img = Image.new('RGBA', (opt_box_w + 60, opt_box_h + 60), (0,0,0,0))
                hs_draw = ImageDraw.Draw(h_img)
                hs_draw.rounded_rectangle((30, 30, opt_box_w + 30, opt_box_h + 30), radius=40, fill=(0,200,0,200))
                h_img = h_img.filter(ImageFilter.GaussianBlur(15))
                hb_draw = ImageDraw.Draw(h_img)
                hb_draw.rounded_rectangle((30, 30, opt_box_w + 30, opt_box_h + 30), radius=40, fill=(0,180,0, 220))
                hb_draw.rounded_rectangle((30, 30, opt_box_w + 30, opt_box_h + 30), radius=40, outline=(0,255,0,255), width=5)
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
                    audio_mixes.append(f"[{get_input_idx(ticktock_path)}:a]atrim=0:{timer},adelay={tt_at}|{tt_at}[a_tt{idx}]")

                # Question Text
                last_node = self.add_line_to_graph(last_node, f"Q{idx+1}: {asset['q_text']}", question_font, "yellow", 70, 80, q_y, 28, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", fade=True, video_id=video_id)
                
                # Draw Options
                for i, opt_text in enumerate(asset['options']):
                    oy = opt_start_y + i * (opt_h + opt_gap)
                    
                    # Normal Box
                    self.filter_graph.append(f"[{opt_box_idx}:v]setpts=PTS-STARTPTS[obox_{idx}_{i}];")
                    self.filter_graph.append(f"{last_node}[obox_{idx}_{i}]overlay=enable=between(t\\,{start_t:.2f}\\,{end_t:.2f}):x={(VIDEO_WIDTH - 900) // 2 - 30}:y={oy - 30}[v_o_{idx}_{i}];")
                    last_node = f"[v_o_{idx}_{i}]"
                    
                    # Normal Text
                    prefix = ["A.", "B.", "C.", "D."][i]
                    opt_display = f"{prefix} {opt_text}"
                    last_node = self.add_line_to_graph(last_node, opt_display, answer_font, "white", 60, (VIDEO_WIDTH - 840) // 2, oy + 25, 30, enable=f"between(t\\,{start_t:.2f}\\,{end_t:.2f})", align="left", video_id=video_id)
                    
                    # Highlight Box (if correct)
                    if i == asset['correct_idx']:
                        self.filter_graph.append(f"[{hl_box_idx}:v]setpts=PTS-STARTPTS[hlbox_{idx}];")
                        self.filter_graph.append(f"{last_node}[hlbox_{idx}]overlay=enable=between(t\\,{reveal_t:.2f}\\,{end_t:.2f}):x={(VIDEO_WIDTH - 900) // 2 - 30}:y={oy - 30}[v_h_{idx}];")
                        last_node = f"[v_h_{idx}]"
                        
                        # Highlight Text
                        last_node = self.add_line_to_graph(last_node, opt_display, question_font, "white", 65, (VIDEO_WIDTH - 840) // 2, oy + 25, 30, enable=f"between(t\\,{reveal_t:.2f}\\,{end_t:.2f})", align="left", video_id=video_id)
                
                t_start_timer = start_t + q_dur
                
                # Loader Bar
                prog_expr = f"(({timer}-(t-{t_start_timer:.2f}))/{timer})"
                l_w = VIDEO_WIDTH - (2 * self.side_margin)
                
                # 1. Frame
                self.filter_graph.append(f"[{indices['loader_frame']}:v]scale={l_w}:{l_h}[vframe{idx}];")
                self.filter_graph.append(f"{last_node}[vframe{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x={self.side_margin}:y={l_y}[vfr{idx}];")
                
                # 2. Fill (Dynamic mask)
                self.filter_graph.append(f"[{indices['loader_fill']}:v]scale={l_w}:{l_h}[vfill{idx}];")
                self.filter_graph.append(f"color=c=black:s={l_w}x{l_h}[vmask_b{idx}];")
                self.filter_graph.append(f"[{indices['loader_fill']}:v]alphaextract,scale={l_w}:{l_h}[vfill_alpha{idx}];")
                self.filter_graph.append(f"[vfill_alpha{idx}][vmask_b{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x=-{l_w}*{prog_expr}:y=0[vmask_an{idx}];")
                self.filter_graph.append(f"[vfill{idx}][vmask_an{idx}]alphamerge[vfill_m{idx}];")
                self.filter_graph.append(f"[vfr{idx}][vfill_m{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x={self.side_margin}:y={l_y}[vfb{idx}];")
                
                # 3. Star
                star_size = 180
                self.filter_graph.append(f"[{indices['loader_star']}:v]scale={star_size}:-1[vstar{idx}];")
                self.filter_graph.append(f"[vfb{idx}][vstar{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x={self.side_margin}+{l_w}*(1-{prog_expr})-{star_size}/2:y={l_y}+{l_h}/2-{star_size}/2[vls{idx}];")
                last_node = f"[vls{idx}]"

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

            # Final mixing
            outro_at = int(score_start * 1000)
            audio_mixes.append(f"[{get_input_idx(outro_audio_path)}:a]volume=1.5,adelay={outro_at}|{outro_at}[a_outro]")

            amix_tags = ""
            for m in audio_mixes:
                bracket_start = m.rfind('[')
                if bracket_start != -1: amix_tags += m[bracket_start:]
            
            num_audio_inputs = len(audio_mixes) + 1
            anchor_filter = f"aevalsrc=0:d={total_duration}[anchor{video_id}];"
            
            if has_bgm:
                # Dynamic volume: 0.05 during quiz, 0.25 during end screen
                bgm_vol = f"if(between(t\\,{score_start}\\,{score_end})\\,0.25\\,0.05)"
                self.filter_graph.append(f"[0:a]volume={bgm_vol}:eval=frame[bgm_v{video_id}];")
                num_audio_inputs += 1
                final_mixer = f"{anchor_filter} [anchor{video_id}][bgm_v{video_id}]{amix_tags}amix=inputs={num_audio_inputs}:duration=first:normalize=0[aout{video_id}]"
            else:
                final_mixer = f"{anchor_filter} [anchor{video_id}]{amix_tags}amix=inputs={num_audio_inputs}:duration=first:normalize=0[aout{video_id}]"
            
            full_filter = ";".join([f.strip().rstrip(';') for f in self.filter_graph]).rstrip(';') + ";" + ";".join(audio_mixes).rstrip(';') + ";" + final_mixer
            if is_preview:
                full_filter += f";[aout{video_id}]anullsink"
                
            filter_script_path = os.path.join(output_dir, f"v{video_id}_filter.txt")
            with open(filter_script_path, "w", encoding="utf-8") as f: f.write(full_filter)
            
            if is_preview:
                preview_target_time = q_assets[0]['reveal_t'] + 0.5 if q_assets else 2.0
                out_path = os.path.join(output_dir, f"Preview_{topic}_{video_id}_{datetime.datetime.now().strftime('%M%S')}.png")
                cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y"] + self.input_cmds
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
