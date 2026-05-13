import os
import pandas as pd
import concurrent.futures
from templates.text_quiz import TextQuizRenderer
from templates.image_quiz import ImageQuizRenderer

# ===================== CONFIG =====================
MAX_PARALLEL_RENDERS = 1
TTS_VOICE = "en-US-ChristopherNeural"

# Dirs
ASSETS_DIR = "assets"
IMAGES_DIR = "images"
VIDEOS_DIR = "videos"
FONTS_DIR = "fonts"
MUSIC_DIR = "music"
VOICEOVERS_DIR = "voiceovers"
OUTPUT_DIR = "output"
DATA_DIR = "data"

for d in [VOICEOVERS_DIR, OUTPUT_DIR, MUSIC_DIR, IMAGES_DIR, VIDEOS_DIR, FONTS_DIR, DATA_DIR, os.path.join(IMAGES_DIR, "thumbnails")]:
    os.makedirs(d, exist_ok=True)

def main():
    print("\n🚀 Welcome to Viral Quiz Generator!")
    print("-" * 35)
    print("Select Quiz Type:")
    print("1. 📝 Text Quiz (Standard Q&A)")
    print("2. 🖼️ Image Quiz (Identify Flag, Animal, etc.)")
    
    quiz_type_choice = input("\nChoice (1/2): ").strip()
    
    if quiz_type_choice == "1":
        excel_path = os.path.join(DATA_DIR, "quizzes_text.xlsx")
        if not os.path.exists(excel_path):
            # Fallback to root quizzes.xlsx if data folder is newly created
            if os.path.exists("quizzes.xlsx"):
                os.rename("quizzes.xlsx", excel_path)
            else:
                print(f"Error: {excel_path} not found!")
                return
        renderer_class = TextQuizRenderer
    elif quiz_type_choice == "2":
        excel_path = os.path.join(DATA_DIR, "quizzes_image.xlsx")
        if not os.path.exists(excel_path):
            print(f"Creating template at {excel_path}...")
            df_template = pd.DataFrame(columns=['Topic', 'Question', 'Answer', 'Time_to_Guess', 'Used'])
            df_template.to_excel(excel_path, index=False)
            print("Please add some questions to the Excel file first!")
            return
        renderer_class = ImageQuizRenderer
    else:
        print("Invalid choice.")
        return

    df = pd.read_excel(excel_path)
    df.dropna(subset=['Topic', 'Question', 'Answer'], inplace=True)
    if 'Used' not in df.columns: df['Used'] = False
    else: df['Used'] = df['Used'].map(lambda x: True if str(x).lower() in ['true', 'yes', '1', 'y'] else False)

    topics = df['Topic'].unique().tolist()
    print("\n--- Available Topics ---")
    for t in topics:
        avail = len(df[(df['Topic'] == t) & (df['Used'] != True)])
        print(f" - {t} ({avail} q)")
        
    topic_choice = input("\nTopic? ").strip()
    q_per_vid = int(input("Questions per video? "))
    num_vids = int(input("How many videos? "))
    bg_type_choice = input("\nBG Type (1:Img, 2:Vid, 3:None): ")
    bg_type = {"1": "image", "2": "video", "3": "blue"}.get(bg_type_choice, "blue")

    # Thumbnail Selection
    thumb_path = None
    thumb_dir = os.path.join(IMAGES_DIR, "thumbnails")
    if os.path.exists(thumb_dir):
        thumb_files = [f for f in os.listdir(thumb_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if thumb_files:
            print("\n--- Available Thumbnails (End-of-video 0.5s) ---")
            print("0. No Thumbnail")
            for i, f in enumerate(thumb_files, 1):
                print(f"{i}. {f}")
            
            thumb_choice = input("Select Thumbnail (0-N): ").strip()
            if thumb_choice.isdigit() and int(thumb_choice) > 0 and int(thumb_choice) <= len(thumb_files):
                thumb_path = os.path.join(thumb_dir, thumb_files[int(thumb_choice)-1])
        else:
            print("\n[Note] No thumbnails found in images/thumbnails/ directory.")

    print("\nSelect Visual Template:")
    print("1. Classic List (1 Column)")
    print("2. Modern Grid (2x2 Columns)")
    print("3. Millionaire (TV Show Style)")
    print("4. Chalkboard (Educational / Student Vibe)")
    print("5. Hacker / Matrix (Tech & Science Vibe)")
    print("6. Soft Pastel / Aesthetic (Modern TikTok Vibe)")
    print("7. Chat Message (iMessage / WhatsApp Style)")
    print("8. Retro Synthwave / Outrun (80s Neon Aesthetic)")
    print("9. Color Quadrants (High Contrast / Fun Style)")
    print("10. Hazard / Impossible Test (High Urgency)")
    print("11. Stadium Live (Sports Broadcaster Style)")
    print("12. 90s Handheld / Gameboy (Retro Nostalgia)")
    print("13. Blueprint / Lab Notes (Technical & Science)")
    print("14. National Geographic / Wildlife (Nature Documentary)")
    print("15. OMR / Exam Sheet (Simple)")
    print("16. OMR / Exam Sheet (With Hand Animation)")
    print("17. OMR / Exam Sheet (With Cursor Animation)")
    template_choice = input("Choice (1-17): ").strip()
    template_map = {
        "1": "classic", "2": "grid", "3": "millionaire", "4": "chalkboard", "5": "hacker",
        "6": "pastel", "7": "chat", "8": "retro", "9": "quadrants", "10": "hazard",
        "11": "stadium", "12": "gameboy", "13": "blueprint", "14": "wildlife",
        "15": "omr", "16": "omr_hand", "17": "omr_cursor"
    }
    template_name = template_map.get(template_choice, "grid")

    # Intro Animation Selection
    selected_char = None
    
    char_files = [f for f in os.listdir(ASSETS_DIR) if f.lower().startswith("intro_char")]
    
    if char_files:
        print("\n--- Select Intro Character ---")
        print("0. Random / Each video different")
        print("N. None (Plain Intro)")
        for i, f in enumerate(char_files, 1):
            print(f"{i}. {f}")
        c_choice = input("Choice (0/N/Num): ").strip().lower()
        if c_choice == 'n':
            selected_char = "NONE"
        elif c_choice.isdigit() and 0 < int(c_choice) <= len(char_files):
            selected_char = char_files[int(c_choice)-1]
    gen_script_choice = input("\nGenerate Voiceover Script & Folders? (Y/N, default Y): ").strip().lower()
    generate_script = False if gen_script_choice == 'n' else True

    render_mode = input("\nRender Mode (1: Full Video, 2: Preview Frame): ").strip()
    is_preview = (render_mode == "2")
    if is_preview:
        num_vids = 1

    topic_df = df[(df['Topic'] == topic_choice) & (df['Used'] != True)]
    
    msg = "videos" if not is_preview else "preview frame"
    print(f"\n[Batch] Starting parallel rendering of {num_vids} {msg}...\n")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_RENDERS) as executor:
        futures_to_indices = {}
        for v_i in range(num_vids):
            if len(topic_df) < q_per_vid: break
            sampled_indices = topic_df.sample(n=q_per_vid).index
            sampled_df = df.loc[sampled_indices].to_dict('records')
            
            renderer = renderer_class(topic_choice, sampled_df, ASSETS_DIR)
            future = executor.submit(
                renderer.build_video, 
                v_i+1, topic_choice, sampled_df, bg_type, 
                MUSIC_DIR, IMAGES_DIR, VIDEOS_DIR, FONTS_DIR, VOICEOVERS_DIR, OUTPUT_DIR, TTS_VOICE, 
                is_preview=is_preview, template=template_name, thumbnail_path=thumb_path,
                selected_char=selected_char, generate_script=generate_script
            )
            futures_to_indices[future] = sampled_indices
            topic_df = topic_df.drop(sampled_indices)

        for future in concurrent.futures.as_completed(futures_to_indices):
            sampled_indices = futures_to_indices[future]
            try:
                success = future.result()
                # Only mark as used if full render succeeded and NOT a preview
                if success and not is_preview:
                    df.loc[sampled_indices, 'Used'] = True
                    print(f"[Batch] Successfully marked {len(sampled_indices)} questions as used.")
            except Exception as e:
                print(f"[Batch] Video generation failed: {e}")
        
        df.to_excel(excel_path, index=False)
    
    print(f"\n[Batch Completed] Done!")

if __name__ == "__main__":
    main()


#Hello this is update