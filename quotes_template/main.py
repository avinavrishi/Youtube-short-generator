"""
YouTube Short Generator – First version.
Reads quotes from Excel, generates TTS voiceover, creates 9:16 shorts
using a single background image (images/bg-image.jpg) and quote text.
"""

import os
import asyncio
import pandas as pd
import numpy as np
import edge_tts
import random
import glob
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.audio.fx.AudioLoop import AudioLoop
from moviepy.audio.fx.MultiplyVolume import MultiplyVolume
from moviepy.audio.fx.AudioFadeOut import AudioFadeOut
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.fx.Loop import Loop
from moviepy.video.VideoClip import ImageClip, TextClip, ColorClip, VideoClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from PIL import Image, ImageDraw

# ===================== CONFIG =====================

EXCEL_FILE = "quotes.xlsx"
IMAGES_DIR = "images"
FONTS_DIR = "fonts"
MUSIC_DIR = "music"
VIDEOS_DIR = "videos"
SATISFYING_DIR = "satisfying_videos"
VOICEOVERS_DIR = "voiceovers"
OUTPUT_DIR = "output"

MUSIC_VOLUME = 0.1  # 10% volume for background music
WATERMARK_TEXT = "@bhagvatGeetaQuotes"  # Change to your brand name

# Progress bar
PROGRESS_BAR_COLOR = (255, 0, 0)  # Red
PROGRESS_BAR_HEIGHT = 15

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

# Text layout
QUOTE_WIDTH = 900
MAX_QUOTE_FONT = 58
MIN_QUOTE_FONT = 32
QUOTE_COLOR = "white"
TITLE_FONT_SIZE = 90       # Drastically increased title size
TITLE_COLOR = "yellow"     # Make the heading pop with yellow
EXTRA_SECONDS_AFTER_VOICE = 2.0

# TTS Dynamic VOICES list (Indian / Hinglish optimized)
TTS_VOICES = [
    "en-IN-PrabhatNeural",      # Indian English Male
    "en-IN-NeerjaNeural",       # Indian English Female
    "hi-IN-MadhurNeural",       # Hindi Male
    "hi-IN-SwaraNeural"         # Hindi Female
]

# ==================================================

os.makedirs(VOICEOVERS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MUSIC_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(SATISFYING_DIR, exist_ok=True)


async def generate_voiceover(text: str, path: str, voice: str) -> None:
    """Generate TTS and save to path."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)


def get_background_path() -> str:
    """Pick a random background image from IMAGES_DIR."""
    valid_exts = ('*.jpg', '*.jpeg', '*.png')
    images = []
    for ext in valid_exts:
        images.extend(glob.glob(os.path.join(IMAGES_DIR, ext)))
    if not images:
        raise FileNotFoundError(f"No background images found in {IMAGES_DIR}")
    return random.choice(images)

def get_random_font() -> str:
    """Pick a random .ttf or .otf font from FONTS_DIR, or use a default."""
    if not os.path.exists(FONTS_DIR):
        return "Arial"
    valid_exts = ('*.ttf', '*.otf')
    fonts = []
    for ext in valid_exts:
        fonts.extend(glob.glob(os.path.join(FONTS_DIR, ext)))
    if not fonts:
        return "Arial"
    return random.choice(fonts)

def get_random_music():
    """Pick a random background music track from MUSIC_DIR, or None if empty."""
    if not os.path.exists(MUSIC_DIR):
        return None
    valid_exts = ('*.mp3', '*.wav')
    music_files = []
    for ext in valid_exts:
        music_files.extend(glob.glob(os.path.join(MUSIC_DIR, ext)))
    if not music_files:
        return None
    return random.choice(music_files)

def get_random_video():
    """Pick a random background video from VIDEOS_DIR, or None if empty."""
    if not os.path.exists(VIDEOS_DIR):
        return None
    valid_exts = ('*.mp4', '*.mov')
    video_files = []
    for ext in valid_exts:
        video_files.extend(glob.glob(os.path.join(VIDEOS_DIR, ext)))
    if not video_files:
        return None
    return random.choice(video_files)

def get_random_satisfying_video():
    """Pick a random gameplay video from SATISFYING_DIR, or None if empty."""
    if not os.path.exists(SATISFYING_DIR):
        return None
    valid_exts = ('*.mp4', '*.mov')
    video_files = []
    for ext in valid_exts:
        video_files.extend(glob.glob(os.path.join(SATISFYING_DIR, ext)))
    if not video_files:
        return None
    return random.choice(video_files)

def create_zoomed_image_clip(img_path: str, duration: float, target_w: int, target_h: int, zoom_factor: float = 0.05):
    """Creates a 'Ken Burns' slow zoom effect from a static image."""
    img = Image.open(img_path).convert("RGB")
    # Base resize to cover target dimensions exactly
    img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    def make_frame(t):
        progress = min(max(t / duration, 0.0), 1.0)
        scale = 1.0 + zoom_factor * progress
        w, h = int(target_w * scale), int(target_h * scale)
        # Fast bilinear resize for video frame rendering
        frame_img = img.resize((w, h), Image.Resampling.BILINEAR)
        # Crop exactly to center to rigidly maintain canvas boundaries
        left = (w - target_w) // 2
        top = (h - target_h) // 2
        return np.array(frame_img.crop((left, top, left + target_w, top + target_h)))
        
    return VideoClip(make_frame, duration=duration)

def create_quote_text_clip(quote: str, duration: float, font_path: str):
    """Build a centered quote text clip; scale font to fit."""
    font_size = MAX_QUOTE_FONT
    clip = None
    while font_size >= MIN_QUOTE_FONT:
        try:
            clip = TextClip(
                text=quote,
                font=font_path,
                font_size=font_size,
                color=QUOTE_COLOR,
                method="caption",
                size=(QUOTE_WIDTH, None),
                text_align="center",
                margin=(20, 20),
            )
        except Exception:
            font_size -= 2
            continue
        if clip.h <= VIDEO_HEIGHT - 200:
            break
        clip.close()
        font_size -= 2
    if clip is None:
        raise RuntimeError("Could not create quote text clip (font too small).")
    y = (VIDEO_HEIGHT - clip.h) // 2
    return clip.with_position(("center", y)).with_duration(duration)

def create_glass_box_clip(w: int, h: int, duration: float, radius: int = 40):
    """Builds a premium frosted glass bounding box."""
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    if radius > 0:
        # Rounded rectangle for free-floating boxes
        draw.rounded_rectangle((0, 0, w-1, h-1), radius, fill=(0, 0, 0, 160), outline=(255, 255, 255, 90), width=4)
    else:
        # Flush rectangle for top headers, with only a bottom white trim
        draw.rectangle((0, 0, w, h), fill=(0, 0, 0, 180))
        draw.line([(0, h-2), (w, h-2)], fill=(255, 255, 255, 90), width=4)
    
    # Save a temporary PNG to guarantee moviepy natively preserves the exact alpha mask
    temp_path = os.path.join(OUTPUT_DIR, "temp_glass_box.png")
    img.save(temp_path, "PNG")
    
    return ImageClip(temp_path).with_duration(duration)

def create_title_clip(title: str, duration: float, font_path: str):
    """Build a title clip at the top."""
    try:
        clip = TextClip(
            text=title,
            font=font_path,
            font_size=TITLE_FONT_SIZE,
            color=TITLE_COLOR,
            stroke_color="black",
            stroke_width=3,  # Reduced stroke slightly to prevent ImageMagick bleed
            method="caption",
            size=(VIDEO_WIDTH - 120, None),
            text_align="center",
            margin=(20, 30),  # Added generous internal margin so the bottom of the letters never get chopped
        )
    except Exception:
        return None
    return clip.with_duration(duration)

def create_watermark_clip(duration: float, font_path: str):
    """Build a semi-transparent watermark clip at the bottom."""
    try:
        clip = TextClip(
            text=WATERMARK_TEXT,
            font=font_path,
            font_size=40,
            color="white",
            method="caption",
            size=(VIDEO_WIDTH, None),
            text_align="center",
        )
        return clip.with_position(("center", VIDEO_HEIGHT - 120)).with_duration(duration).with_opacity(0.6)
    except Exception:
        return None

def create_cta_clip(duration: float, font_path: str):
    """Pops up a massive Subscribe/Like CTA at the end of the video."""
    try:
        clip = TextClip(
            text="Please like if you agree!\nSubscribe for daily wisdom!",
            font=font_path,
            font_size=60,
            color="yellow",
            stroke_color="black",
            stroke_width=4,
            method="caption",
            size=(VIDEO_WIDTH - 100, None),
            text_align="center"
        )
        # Appear exactly when the voiceover stops (last 2 seconds)
        start_time = max(0.0, duration - 2.0)
        return clip.with_position(("center", "center")).with_start(start_time).with_duration(2.0)
    except Exception:
        return None

def create_short(index: int, title: str, quote: str, bg_type: str, show_text: bool = True) -> str:
    """
    Generate TTS for the quote, then create a 9:16 video with a background.
    If show_text is False, the quote, title, and overlays are skipped.
    """
    voice = random.choice(TTS_VOICES)
    print(f"[{index + 1}] Generating voiceover using {voice}...")
    voice_path = os.path.join(VOICEOVERS_DIR, f"{index}.mp3")
    asyncio.run(generate_voiceover(quote, voice_path, voice))

    voice_audio = AudioFileClip(voice_path)
    duration = voice_audio.duration + EXTRA_SECONDS_AFTER_VOICE
    voice_audio.close()

    print(f"[{index + 1}] Building video (duration={duration:.1f}s)...")
    
    if bg_type == "split":
        half_h = VIDEO_HEIGHT // 2
        
        # --- Top Half (Quote Background) ---
        top_img_path = get_background_path()
        top_clip = create_zoomed_image_clip(
            top_img_path, duration, VIDEO_WIDTH, half_h, zoom_factor=0.06
        ).with_position(("center", "top"))
        
        # --- Bottom Half (Satisfying Gameplay) ---
        bottom_vid_path = get_random_satisfying_video()
        if bottom_vid_path:
            bottom_clip = (
                VideoFileClip(bottom_vid_path)
                .without_audio()
                .resized((VIDEO_WIDTH, half_h))
                .with_effects([Loop(duration=duration)])
                .with_position(("center", half_h))
            )
        else:
            # Fallback if no satisfying videos exist yet
            print(f"[{index + 1}] No gameplay found in {SATISFYING_DIR}. Repeating top image fallback.")
            bottom_clip = top_clip.with_position(("center", half_h))
            
        bg_clip = CompositeVideoClip([top_clip, bottom_clip], size=(VIDEO_WIDTH, VIDEO_HEIGHT))

    elif bg_type == "video":
        bg_path = get_random_video()
        if bg_path:
            bg_clip = (
                VideoFileClip(bg_path)
                .without_audio()
                .resized((VIDEO_WIDTH, VIDEO_HEIGHT))
                .with_effects([Loop(duration=duration)])
                .with_position(("center", "center"))
            )
        else:
            print(f"[{index + 1}] No videos found in {VIDEOS_DIR}. Falling back to image.")
            bg_type = "image"
            
    if bg_type == "image":
        bg_path = get_background_path()
        bg_clip = create_zoomed_image_clip(
            bg_path, duration, VIDEO_WIDTH, VIDEO_HEIGHT, zoom_factor=0.06
        ).with_position(("center", "center"))

    layers = [bg_clip]

    if show_text:
        font_path = get_random_font()

        # 50% opacity dark overlay to guarantee text readability
        overlay = (
            ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(0, 0, 0))
            .with_opacity(0.5)
            .with_position(("center", "center"))
            .with_duration(duration)
        )
        layers.append(overlay)

        quote_clip = create_quote_text_clip(quote, duration, font_path)
        layers.append(quote_clip)

        title_clip = create_title_clip(str(title).strip(), duration, font_path)
        if title_clip is not None:
            title_w, title_h = title_clip.size
            pad_y = 50  # Reduced since the text clip now has healthy internal margin
            
            # Stretch incredibly wide so it touches the absolute edges of the video
            box_w = VIDEO_WIDTH
            box_h = title_h + pad_y
            
            box_clip = create_glass_box_clip(box_w, box_h, duration, radius=0)
            # Pin it flush to the absolute top corner edge
            box_clip = box_clip.with_position(("center", "top"))
            
            # Center the text precisely inside the new top header box, shifted slightly up for visual gravity
            title_y = (box_h - title_h) // 2 - 5
            title_clip = title_clip.with_position(("center", title_y))
            
            layers.append(box_clip)
            layers.append(title_clip)
            
        watermark_clip = create_watermark_clip(duration, font_path)
        if watermark_clip is not None:
            layers.append(watermark_clip)
            
        cta_clip = create_cta_clip(duration, font_path)
        if cta_clip is not None:
            start_time = max(0.0, duration - 2.0)
            black_screen = (
                ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(0, 0, 0))
                .with_position(("center", "center"))
                .with_start(start_time)
                .with_duration(2.0)
            )
            layers.append(black_screen)
            layers.append(cta_clip)

        # Progress bar logic
        def make_frame_progressbar(t):
            progress = min(max(t / duration, 0.0), 1.0) # Clamp between 0-1
            bar_width = int(VIDEO_WIDTH * progress)
            frame = np.zeros((PROGRESS_BAR_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8)
            if bar_width > 0:
                frame[:, :bar_width] = PROGRESS_BAR_COLOR
            return frame

        progress_clip = VideoClip(make_frame_progressbar, duration=duration).with_position(("left", "bottom"))
        layers.append(progress_clip)

    padded_voice = CompositeAudioClip([AudioFileClip(voice_path)]).with_duration(duration)
    
    music_path = get_random_music()
    if music_path:
        music_clip = (
            AudioFileClip(music_path)
            .with_effects([
                AudioLoop(duration=duration),
                MultiplyVolume(MUSIC_VOLUME),
                AudioFadeOut(2.0)
            ])
        )
        final_audio = CompositeAudioClip([music_clip, padded_voice]).with_duration(duration)
    else:
        final_audio = padded_voice

    final = (
        CompositeVideoClip(layers, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
        .with_audio(final_audio)
        .with_duration(duration)
    )

    output_path = os.path.join(OUTPUT_DIR, f"short_{index + 1}.mp4")
    final.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    for c in layers:
        c.close()
    final.close()
    print(f"[{index + 1}] Saved: {output_path}")
    return output_path


def main():
    if not os.path.isfile(EXCEL_FILE):
        print(f"Error: {EXCEL_FILE} not found.")
        return

    df = pd.read_excel(EXCEL_FILE)
    if "quote" not in df.columns:
        print("Error: Excel must have a 'quote' column.")
        return

    title_col = "title" if "title" in df.columns else None
    
    # Pre-calculate the exact number of valid quotes
    valid_rows = []
    for i, row in df.iterrows():
        quote = str(row["quote"]).strip()
        if quote and quote.lower() != "nan":
            valid_rows.append((i, row))
            
    total = len(valid_rows)
    if total == 0:
        print("No valid quotes found in the Excel file.")
        return
        
    print(f"Found {total} valid quote(s) in {EXCEL_FILE}.")
    
    while True:
        try:
            choice = input(f"How many videos do you want to make out of {total} quotes? (1-{total}, or 'all'): ").strip().lower()
            if choice == "all":
                num_to_generate = total
                break
            num_to_generate = int(choice)
            if 1 <= num_to_generate <= total:
                break
            else:
                print(f"Please enter a number between 1 and {total}.")
        except ValueError:
            print("Invalid input. Please enter a valid number or 'all'.")

    # Ask for background type
    while True:
        bg_type = input("What type of background do you want? (image/video/split): ").strip().lower()
        if bg_type in ["image", "video", "split"]:
            break
        print("Please enter 'image', 'video', or 'split'.")

    # Ask if text should be shown
    while True:
        text_choice = input("Do you want text on the screen? (yes/no): ").strip().lower()
        if text_choice in ["yes", "no", "y", "n"]:
            show_text = text_choice in ["yes", "y"]
            break
        print("Please enter 'yes' or 'no'.")

    print(f"\nStarting generation of {num_to_generate} video(s) using '{bg_type}' background (Text Mode: {show_text})...\n")

    count = 0
    for i, row in valid_rows:
        if count >= num_to_generate:
            break
        title = str(row[title_col]) if title_col else ""
        quote = str(row["quote"]).strip()
        create_short(i, title, quote, bg_type, show_text)
        count += 1

    print("\nDone. Shorts are in the 'output' folder.")


if __name__ == "__main__":
    main()
