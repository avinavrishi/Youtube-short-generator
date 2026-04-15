import os
import edge_tts
import asyncio
from .utils import get_hash

async def generate_voiceover(text: str, path: str, voice: str, retries: int = 3) -> None:
    # If file exists and is valid (not 0 bytes), skip
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return

    for attempt in range(retries):
        try:
            # Delete if exists but empty (previous failed attempt)
            if os.path.exists(path):
                os.remove(path)
                
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(path)
            
            # Final validation: check if file is non-empty
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return # Success
                
        except Exception as e:
            if attempt == retries - 1:
                raise RuntimeError(f"Failed to generate voiceover after {retries} attempts: {e}")
            await asyncio.sleep(1) # Wait before retry

    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise RuntimeError(f"Failed to generate valid voiceover file: {path}")

def get_voiceover_path(text, voiceovers_dir, voice_name):
    h = get_hash(text)
    return os.path.join(voiceovers_dir, f"v_{h}.mp3")
