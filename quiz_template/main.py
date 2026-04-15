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

for d in [VOICEOVERS_DIR, OUTPUT_DIR, MUSIC_DIR, IMAGES_DIR, VIDEOS_DIR, FONTS_DIR, DATA_DIR]:
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

    topic_df = df[(df['Topic'] == topic_choice) & (df['Used'] != True)]
    
    print(f"\n[Batch] Starting parallel rendering of {num_vids} videos...\n")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_RENDERS) as executor:
        futures = []
        for v_i in range(num_vids):
            if len(topic_df) < q_per_vid: break
            sampled_indices = topic_df.sample(n=q_per_vid).index
            sampled_df = df.loc[sampled_indices].to_dict('records')
            
            renderer = renderer_class(topic_choice, sampled_df, ASSETS_DIR)
            futures.append(executor.submit(
                renderer.build_video, 
                v_i+1, topic_choice, sampled_df, bg_type, 
                MUSIC_DIR, IMAGES_DIR, VIDEOS_DIR, FONTS_DIR, VOICEOVERS_DIR, OUTPUT_DIR, TTS_VOICE
            ))
            
            df.loc[sampled_indices, 'Used'] = True
            topic_df = topic_df.drop(sampled_indices)
            df.to_excel(excel_path, index=False)

        concurrent.futures.wait(futures)
    
    print(f"\n[Batch Completed] Done!")

if __name__ == "__main__":
    main()
