import os
import json
import pandas as pd
import numpy as np
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv, find_dotenv

# --- 1. LOAD ENVIRONMENT VARIABLES ---
# Try to load the .env file that lives next to this module (app/.env).
# This makes loading robust when the app is started from the project root
# or when the uvicorn reloader spawns subprocesses with a different cwd.
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(dotenv_path):
    # Fallback: search upward for a .env file if it's not colocated.
    dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

# --- 2. CONFIGURE THE GEMINI API ---
try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found. Make sure it's set in your .env file.")
    genai.configure(api_key=api_key)
except Exception as e:
    raise ValueError(f"Failed to configure Gemini API: {e}")

def create_gemini_prompt():
    """Creates the detailed prompt for the Gemini API."""
    return """
    You are an expert OCR system specializing in extracting structured data from handwritten attendance sheets.
    Your task is to analyze the provided image and return a single, clean JSON object. Do not include any explanatory text before or after the JSON.

    The JSON object must have two main keys: "dates" and "students".

    1.  "dates": This should be a list of strings, representing the lecture dates found in the column headers. Extract them in order from left to right.

    2.  "students": This should be a list of student objects. Each object must contain the following keys:
        - "roll_no": The student's roll number (string).
        - "student_id": The student's ID (string).
        - "name": The student's full name (string).
        - "attendance": A list of strings, either "Present" or "Absent", corresponding to the dates list.

    INTERPRETATION RULES:
    - A signature, a 'P', a tick mark, or any significant marking in an attendance cell means "Present".
    - An 'A', 'AB', or a blank/empty cell means "Absent".
    - Ignore any rows that do not contain a student's name.
    - Clean the extracted text to remove noise or formatting characters.
    """

def process_image(image_path: str):
    """
    Processes the attendance sheet image using the Gemini API for data extraction.
    """
    try:
        # --- 3. PREPARE THE MODEL AND PROMPT ---
        # --- MODEL CHANGED TO GEMINI FLASH ---
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        image = Image.open(image_path)
        prompt = create_gemini_prompt()

        # --- 4. CALL THE GEMINI API ---
        response = model.generate_content([prompt, image])
        
        # --- 5. PARSE THE RESPONSE ---
        cleaned_response_text = response.text.strip()
        # Remove common Markdown code fences the model might include
        cleaned_response_text = cleaned_response_text.replace('```json', '').replace('```', '').strip()
        data = json.loads(cleaned_response_text)
        
        # Normalize dates: strip whitespace and stringify
        dates = [str(d).strip() for d in data.get('dates', [])]
        student_records = data.get('students', [])

        if not dates or not student_records:
            return {"error": "Gemini could not extract valid date or student records from the image."}

        # --- 6. CONSTRUCT THE PANDAS DATAFRAME ---
        processed_data = []
        for record in student_records:
            row = {
                'Roll No': record.get('roll_no', ''),
                'Student ID': record.get('student_id', ''),
                'Name': record.get('name', '')
            }
            # Normalize attendance markers to canonical 'Present'/'Absent'
            att = record.get('attendance', []) or []
            for i, date in enumerate(dates):
                raw = ''
                if i < len(att):
                    raw = str(att[i]).strip().lower()
                if raw in ('present', 'p', '✓', '✔', 'tick', 'yes', '1', 'true'):
                    row[date] = 'Present'
                else:
                    # Treat missing/blank/A/AB as Absent
                    row[date] = 'Absent'
            processed_data.append(row)
            
        df = pd.DataFrame(processed_data)

        # --- 7. AGGREGATION AND ANALYSIS ---
        lecture_cols = dates
        df['Total Lectures'] = len(lecture_cols)
        df['Lectures Attended'] = df[lecture_cols].apply(lambda row: (row == 'Present').sum(), axis=1)
        
        if lecture_cols:
            df['Percentage'] = round((df['Lectures Attended'] / df['Total Lectures']) * 100, 2)
        else:
            df['Percentage'] = 0
        
        df['Status'] = df['Percentage'].apply(lambda p: 'Defaulter' if p < 75.0 else 'Compliant')
        
        df['Roll No'] = df['Roll No'].astype(str).str.strip()
        is_duplicate = df.duplicated(subset=['Roll No'], keep=False) & (df['Roll No'] != '')
        df['Anomaly'] = np.where(is_duplicate, 'Duplicate Roll No', '')
        
        # --- 8. GENERATE REPORTS ---
        full_report = df.to_dict(orient='records')
        defaulters = df[df['Status'] == 'Defaulter'].to_dict(orient='records')
        anomalies = df[df['Anomaly'] != ''].to_dict(orient='records')

        return {
            "dates": dates,
            "full_report": full_report,
            "defaulters": defaulters,
            "anomalies": anomalies
        }

    except Exception as e:
        if "API key not valid" in str(e):
            return {"error": "Your Gemini API key is not valid. Please check your GOOGLE_API_KEY in the .env file."}
        return {"error": f"An unexpected error occurred: {str(e)}"}