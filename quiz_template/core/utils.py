import hashlib
import textwrap
import os
import glob
from moviepy.audio.io.AudioFileClip import AudioFileClip

def get_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()

def wrap_text(text: str, width: int = 28) -> str:
    lines = textwrap.wrap(text, width=width)
    return "\n".join(lines)

def sanitize_path(p: str) -> str:
    # Use relative path if possible to avoid Windows drive letter colon issues in FFmpeg filters
    try:
        rel = os.path.relpath(p)
        if not rel.startswith('..'):
            return rel.replace('\\', '/')
    except:
        pass
    # Fallback to absolute with escaped colon
    return os.path.abspath(p).replace('\\', '/').replace(':', '\\:')

def safe_text(text: str) -> str:
    # FFmpeg drawtext escaping is nightmare-ish. 
    # For text inside single quotes, we escape ' as '\''
    return (
        text.replace('\\', '\\\\')
            .replace("'", "'\\''") 
            .replace(':', '\\:')
            .replace(',', '\\,')
            .replace('%', '\\%')
    )

def escape_expr(expr: str) -> str:
    """Escapes commas inside expressions used in filter graphs (e.g., enable, alpha)."""
    return expr.replace(',', '\\,')
def get_duration(f_path):
    try:
        if not os.path.exists(f_path) or os.path.getsize(f_path) == 0:
            print(f"[Warning] Audio file missing or empty: {f_path}")
            return 3.0
            
        clip = AudioFileClip(f_path)
        dur = clip.duration
        clip.close()
        return dur
    except Exception as e:
        print(f"[Warning] Could not get duration for {f_path}: {e}")
        return 3.0

def get_font_path(target, fonts_dir):
    path = os.path.join(fonts_dir, target)
    if os.path.exists(path):
        return sanitize_path(path)
    
    # Fallback
    fonts = glob.glob(os.path.join(fonts_dir, "*.ttf"))
    return sanitize_path(fonts[0]) if fonts else sanitize_path("C:/Windows/Fonts/arial.ttf")
