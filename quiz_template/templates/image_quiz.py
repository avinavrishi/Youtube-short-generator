import os
import random
import glob
import asyncio
import datetime
from core.utils import get_hash, get_duration, sanitize_path, get_font_path, wrap_text
from core.voice import generate_voiceover
from core.renderer import BaseRenderer, VIDEO_WIDTH, VIDEO_HEIGHT
import imageio_ffmpeg

class ImageQuizRenderer(BaseRenderer):
    def build_video(self, video_id, topic, questions, bg_type, music_dir, images_dir, videos_dir, fonts_dir, voiceovers_dir, output_dir, tts_voice, is_preview=False):
        try:
            print(f"\n[Engine][V{video_id}] Building Image Quiz: {topic}")
            qty = len(questions)
            heading_font = get_font_path("BebasNeue-Regular.ttf", fonts_dir)
            question_font = get_font_path("Poppins-Bold.ttf", fonts_dir)
            answer_font = get_font_path("Poppins-Regular.ttf", fonts_dir)
            
            topic_display = random.choice(self.hooks).format(Topic=topic.strip(), Qty=qty)
            intro_text = topic_display
            print(f"[V{video_id}] Hook/Intro: {intro_text}")
            
            # Background & Basic Assets
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
            
            audio_offset = (1 if has_bgm else 0) + (1 if bg_input_idx != -1 else 0)
            indices = self.build_common_assets(video_id, audio_offset)
            
            intro_audio_path = os.path.join(voiceovers_dir, f"intro_{get_hash(intro_text)}.mp3")
            asyncio.run(generate_voiceover(intro_text, intro_audio_path, tts_voice))
            intro_dur = get_duration(intro_audio_path)
            
            ticktock_path = os.path.join(music_dir, "ticktock.mp3")
            has_ticktock = os.path.exists(ticktock_path)
            
            # PRE-QUESTION DELAY (seconds where only the image is shown)
            PRE_QUESTION_DELAY = 1.5
            
            # Input Paths for Q&A audio AND Quiz Images
            input_paths = []
            def get_input_idx(path):
                idx = audio_offset + 7 + len(input_paths)
                input_paths.append(path)
                return idx

            audio_mixes = []
            intro_idx = get_input_idx(intro_audio_path)
            audio_mixes.append(f"[{intro_idx}:a]volume=1.5,adelay=0|0[a_intro]")
            
            bing_path = os.path.join(music_dir, "bing.mp3")
            has_bing = os.path.exists(bing_path)
            
            q_assets = []
            temp_time = intro_dur
            for idx, q_data in enumerate(questions):
                q_text, a_text, timer = q_data['Question'], str(q_data['Answer']), float(q_data['Time_to_Guess'])
                
                # Look for image
                topic_img_dir = os.path.join(images_dir, "quiz_data", topic)
                img_path = None
                for ext in ["png", "jpg", "jpeg", "webp"]:
                    p = os.path.join(topic_img_dir, f"{a_text}.{ext}")
                    if os.path.exists(p):
                        img_path = p
                        break
                
                if not img_path:
                    print(f"Warning: Image not found for {a_text} in {topic_img_dir}")
                    # Fallback or Skip? Let's use a placeholder if possible or just skip the image overlay
                
                q_audio_path = os.path.join(voiceovers_dir, f"q_{get_hash(q_text)}.mp3")
                a_audio_path = os.path.join(voiceovers_dir, f"a_{get_hash(a_text)}.mp3")
                asyncio.run(generate_voiceover(q_text, q_audio_path, tts_voice))
                asyncio.run(generate_voiceover(a_text, a_audio_path, tts_voice))
                
                q_dur, a_dur = get_duration(q_audio_path), get_duration(a_audio_path)
                start_t = temp_time
                q_start_t = start_t + PRE_QUESTION_DELAY
                reveal_t = q_start_t + q_dur + timer
                end_t = reveal_t + a_dur + 1.5
                
                q_assets.append({
                    'q_path': q_audio_path, 'a_path': a_audio_path, 'img_path': img_path,
                    'q_dur': q_dur, 'a_dur': a_dur,
                    'start_t': start_t, 'q_start_t': q_start_t, 'reveal_t': reveal_t, 'end_t': end_t,
                    'q_text': q_text, 'a_text': a_text, 'timer': timer
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
            
            # LAYOUT (QUESTION -> IMAGE -> LOADER -> ANSWERS)
            header_h = 350
            footer_h = 350 # Higher safety margin for social media UI
            content_h = VIDEO_HEIGHT - header_h - footer_h
            
            num_cols = 1 if qty <= 5 else 2
            rows = (qty + num_cols - 1) // num_cols
            
            q_h = 0
            img_h = 550 # Increased image size slightly since question is gone
            l_h = 130
            a_h = rows * 90
            
            total_elements_h = q_h + img_h + l_h + a_h
            gap = (content_h - total_elements_h) // 4
            
            img_y = header_h + gap # Image position (Moved up)
            l_y = img_y + img_h + gap # Loader position (Moved up)
            a_y_start = l_y + l_h + gap # Answers top position (Moved up)
            
            # Start Graph
            if bg_input_idx != -1:
                self.filter_graph.append(f"[{bg_input_idx}:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}[bg{video_id}];")
            else:
                self.filter_graph.append(f"color=c=black:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r=24[bg{video_id}];")
            last_node = f"[bg{video_id}]"
            
            # Header
            self.filter_graph.append(f"{last_node}drawbox=x=0:y=0:w={VIDEO_WIDTH}:h={header_h}:color=white:t=fill[v_hbg{video_id}];")
            last_node = f"[v_hbg{video_id}]"
            
            # Logo (Bottom right corner)
            self.filter_graph.append(f"[{indices['logo']}:v]scale=120:-1[vlogo{video_id}];")
            self.filter_graph.append(f"{last_node}[vlogo{video_id}]overlay=x=W-w-40:y=H-h-60[vl{video_id}];")
            last_node = f"[vl{video_id}]"
            
            h_size = 100
            lines = wrap_text(topic_display, width=28).split('\n')
            total_text_h = len(lines) * (h_size * 1.15)
            start_y = (header_h - total_text_h) // 2
            last_node = self.add_line_to_graph(last_node, topic_display, heading_font, "red", h_size, 0, start_y, wrap_w=28, align="center", video_id=video_id)
            
            # Answer Box Gen
            box_w = 1000
            box_h = (rows * 90) + 40
            box_path = os.path.join(self.assets_dir, f"ans_box_{box_w}_{box_h}.png")
            if not os.path.exists(box_path):
                from PIL import Image, ImageDraw, ImageFilter
                b_img = Image.new('RGBA', (box_w + 60, box_h + 60), (0,0,0,0))
                s_draw = ImageDraw.Draw(b_img)
                s_draw.rounded_rectangle((30, 30, box_w + 30, box_h + 30), radius=40, fill=(0,0,0,200))
                b_img = b_img.filter(ImageFilter.GaussianBlur(15))
                b_draw = ImageDraw.Draw(b_img)
                b_draw.rounded_rectangle((30, 30, box_w + 30, box_h + 30), radius=40, fill=(0,0,0, 150))
                b_img.save(box_path)

            box_idx = get_input_idx(box_path)
            self.filter_graph.append(f"[{box_idx}:v]setpts=PTS-STARTPTS[abox{video_id}];")
            self.filter_graph.append(f"{last_node}[abox{video_id}]overlay=x=10:y={a_y_start-60}[v_abg{video_id}];")
            last_node = f"[v_abg{video_id}]"

            # Answer Markers (Multi-column)
            for idx in range(qty):
                col = idx // rows
                row = idx % rows
                ans_x = 80 + col * (VIDEO_WIDTH // 2)
                ans_y = a_y_start + (row * 90)
                last_node = self.add_line_to_graph(last_node, f"{idx+1}.", answer_font, "white", 65, ans_x, ans_y, align="left", video_id=video_id)

            # Loop Questions
            for idx, asset in enumerate(q_assets):
                start_t, reveal_t, end_t = asset['start_t'], asset['reveal_t'], asset['end_t']
                q_dur, a_dur, timer = asset['q_dur'], asset['a_dur'], asset['timer']
                
                # Audio
                q_at, a_at = int(asset['q_start_t']*1000), int(reveal_t*1000)
                audio_mixes.append(f"[{get_input_idx(asset['q_path'])}:a]volume=1.5,adelay={q_at}|{q_at}[a_q{idx}]")
                audio_mixes.append(f"[{get_input_idx(asset['a_path'])}:a]volume=1.5,adelay={a_at}|{a_at}[a_a{idx}]")
                if has_bing:
                    audio_mixes.append(f"[{get_input_idx(bing_path)}:a]volume=0.3,adelay={a_at}|{a_at}[a_bing{idx}]")
                if has_ticktock:
                    tt_at = int((asset['q_start_t']+q_dur)*1000)
                    audio_mixes.append(f"[{get_input_idx(ticktock_path)}:a]atrim=0:{timer},adelay={tt_at}|{tt_at}[a_tt{idx}]")

                # Question Text (HIDDEN as per user request - only VO plays)
                # last_node = self.add_line_to_graph(last_node, f"Q{idx+1}: {asset['q_text']}", question_font, "yellow", 80, 80, q_y, 30, enable=f"between(t\\,{asset['q_start_t']:.2f}\\,{end_t:.2f})", fade=True, video_id=video_id)
                
                # IMAGE OVERLAY
                if asset['img_path']:
                    img_idx = get_input_idx(asset['img_path'])
                    # Scale image to fit within img_h and VIDEO_WIDTH/2
                    self.filter_graph.append(f"[{img_idx}:v]scale=-1:{img_h-40},drawbox=w=iw+20:h=ih+20:x=-10:y=-10:color=white:t=10[vimg{idx}];")
                    self.filter_graph.append(f"{last_node}[vimg{idx}]overlay=enable=between(t\\,{asset['start_t']:.2f}\\,{asset['end_t']:.2f}):x=(W-w)/2:y={img_y}+20[vifo{idx}];")
                    last_node = f"[vifo{idx}]"
                
                # Loader Bar
                t_start_timer = asset['q_start_t'] + q_dur
                l_w = VIDEO_WIDTH - (2 * self.side_margin)
                prog_expr = f"(({timer}-(t-{t_start_timer:.2f}))/{timer})"
                
                self.filter_graph.append(f"[{indices['loader_frame']}:v]scale={l_w}:{l_h}[vframe{idx}];")
                self.filter_graph.append(f"{last_node}[vframe{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x={self.side_margin}:y={l_y}[vfr{idx}];")
                self.filter_graph.append(f"[{indices['loader_fill']}:v]scale={l_w}:{l_h}[vfill{idx}];")
                self.filter_graph.append(f"color=c=black:s={l_w}x{l_h}[vmask_b{idx}];")
                self.filter_graph.append(f"[{indices['loader_fill']}:v]alphaextract,scale={l_w}:{l_h}[vfill_alpha{idx}];")
                self.filter_graph.append(f"[vfill_alpha{idx}][vmask_b{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x=-{l_w}*{prog_expr}:y=0[vmask_an{idx}];")
                self.filter_graph.append(f"[vfill{idx}][vmask_an{idx}]alphamerge[vfill_m{idx}];")
                self.filter_graph.append(f"[vfr{idx}][vfill_m{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x={self.side_margin}:y={l_y}[vfb{idx}];")
                
                star_size = 150
                self.filter_graph.append(f"[{indices['loader_star']}:v]scale={star_size}:-1[vstar{idx}];")
                self.filter_graph.append(f"[vfb{idx}][vstar{idx}]overlay=enable=between(t\\,{t_start_timer:.2f}\\,{reveal_t:.2f}):x={self.side_margin}+{l_w}*(1-{prog_expr})-{star_size}/2:y={l_y}+{l_h}/2-{star_size}/2[vls{idx}];")
                last_node = f"[vls{idx}]"
                
                # Reveal Answer (Multi-column)
                col = idx // rows
                row = idx % rows
                ans_x_reveal = 160 + col * (VIDEO_WIDTH // 2)
                ans_y_reveal = a_y_start + (row * 90)
                last_node = self.add_line_to_graph(last_node, asset['a_text'], answer_font, "white", 65, ans_x_reveal, ans_y_reveal, 26, enable=f"gte(t\\,{reveal_t:.2f})", align="left", fade=True, video_id=video_id)

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
            
            out_path = os.path.join(output_dir, f"ImageQuiz_{topic}_{video_id}_{datetime.datetime.now().strftime('%M%S')}.mp4")
            cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y"] + self.input_cmds
            for p in input_paths: cmd.extend(["-i", p.replace('\\', '/')])
            
            return self.render_final(cmd, filter_script_path, out_path, total_duration, last_node, video_id)

        except Exception as e:
            print(f"Error in ImageQuiz building: {e}")
            import traceback
            traceback.print_exc()
            return False
