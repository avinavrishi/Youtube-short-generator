import os
import pandas as pd
import glob

def sync_quizzes(data_dir="data", images_dir="images/quiz_data"):
    excel_path = os.path.join(data_dir, "quizzes_image.xlsx")
    os.makedirs(data_dir, exist_ok=True)
    
    if os.path.exists(excel_path):
        df_old = pd.read_excel(excel_path)
    else:
        df_old = pd.DataFrame(columns=['Topic', 'Question', 'Answer', 'Time_to_Guess', 'Used'])

    new_rows = []
    
    # Scan topic directories
    if not os.path.exists(images_dir):
        print(f"Error: {images_dir} not found!")
        return

    topics = [d for d in os.listdir(images_dir) if os.path.isdir(os.path.join(images_dir, d))]
    
    for topic in topics:
        topic_path = os.path.join(images_dir, topic)
        image_files = []
        for ext in ["png", "jpg", "jpeg", "webp"]:
            image_files.extend(glob.glob(os.path.join(topic_path, f"*.{ext}")))
            
        for img_path in image_files:
            filename = os.path.basename(img_path)
            answer = os.path.splitext(filename)[0]
            
            # Check if already exists
            exists = df_old[(df_old['Topic'] == topic) & (df_old['Answer'] == answer)]
            
            if exists.empty:
                new_rows.append({
                    'Topic': topic,
                    'Question': f"Guess the name of this {topic}?",
                    'Answer': answer,
                    'Time_to_Guess': 5.0,
                    'Used': False
                })

    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df_final = pd.concat([df_old, df_new], ignore_index=True)
        df_final.to_excel(excel_path, index=False)
        print(f"Success! Added {len(new_rows)} new questions to {excel_path}.")
    else:
        print("Everything is up to date. No new images found.")

if __name__ == "__main__":
    sync_quizzes()
