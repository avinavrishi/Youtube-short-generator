import pandas as pd
import os

def clean_quizzes(file_path="quizzes.xlsx"):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    print(f"Reading {file_path}...")
    df = pd.read_excel(file_path)
    
    initial_count = len(df)
    
    # Clean whitespace and standardize for comparison
    df['Question_Clean'] = df['Question'].astype(str).str.strip().str.lower()
    
    # Drop duplicates while keeping the first occurrence
    df = df.drop_duplicates(subset=['Question_Clean'], keep='first')
    
    # Remove the temporary column
    df = df.drop(columns=['Question_Clean'])
    
    final_count = len(df)
    removed = initial_count - final_count
    
    if removed > 0:
        df.to_excel(file_path, index=False)
        print(f"Success! Removed {removed} duplicate questions.")
        print(f"New total: {final_count} questions.")
    else:
        print("No duplicates found. Your database is already clean!")

if __name__ == "__main__":
    clean_quizzes()
