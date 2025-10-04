import os
import json
from typing import List, Dict, Any

import pandas as pd
import numpy as np
from PIL import Image
from dotenv import load_dotenv, find_dotenv

# OCR / PDF
import cv2
import fitz  # PyMuPDF
import easyocr

# Gemini
import google.generativeai as genai

# ---------- Env ----------
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(dotenv_path):
    dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)


def _configure_gemini_or_error():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return {"error": "Missing GOOGLE_API_KEY. Add it to .env or Render env."}
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        return {"error": f"Failed to configure Gemini API: {e}"}
    return None


# ---------- Gemini helpers ----------

def create_gemini_prompt() -> str:
    return (
        """
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
    )


def _parse_gemini_json(text: str) -> Dict[str, Any]:
    cleaned = (text or "").strip()
    cleaned = cleaned.replace('```json', '').replace('```', '').strip()
    return json.loads(cleaned)


def _normalize_records_to_df(dates: List[str], students: List[Dict[str, Any]]) -> pd.DataFrame:
    processed: List[Dict[str, Any]] = []
    for record in students:
        row = {
            'Roll No': record.get('roll_no', ''),
            'Student ID': record.get('student_id', ''),
            'Name': record.get('name', '')
        }
        att = record.get('attendance', []) or []
        for i, date in enumerate(dates):
            raw = ''
            if i < len(att):
                raw = str(att[i]).strip().lower()
            if raw in ('present', 'p', '✓', '✔', 'tick', 'yes', '1', 'true'):
                row[date] = 'Present'
            else:
                row[date] = 'Absent'
        processed.append(row)
    df = pd.DataFrame(processed)
    return df


def _build_reports_from_dataframe(df: pd.DataFrame, dates: List[str] | None = None) -> Dict[str, Any]:
    if dates is None:
        dates = [c for c in df.columns if c not in ('Roll No', 'Student ID', 'Name', 'Total Lectures', 'Lectures Attended', 'Percentage', 'Status', 'Anomaly')]

    lecture_cols = dates
    df['Total Lectures'] = len(lecture_cols)
    if lecture_cols:
        df['Lectures Attended'] = df[lecture_cols].apply(lambda row: (row == 'Present').sum(), axis=1)
        df['Percentage'] = round((df['Lectures Attended'] / df['Total Lectures']) * 100, 2)
    else:
        df['Lectures Attended'] = 0
        df['Percentage'] = 0.0

    df['Status'] = df['Percentage'].apply(lambda p: 'Defaulter' if p < 75.0 else 'Compliant')

    df['Roll No'] = df['Roll No'].astype(str).str.strip()
    is_dup = df.duplicated(subset=['Roll No'], keep=False) & (df['Roll No'] != '')
    df['Anomaly'] = np.where(is_dup, 'Duplicate Roll No', '')

    return {
        'dates': dates,
        'full_report': df.to_dict(orient='records'),
        'defaulters': df[df['Status'] == 'Defaulter'].to_dict(orient='records'),
        'anomalies': df[df['Anomaly'] != ''].to_dict(orient='records')
    }


# ---------- PDF OCR (EasyOCR + OpenCV + PyMuPDF) ----------

def convert_pdf_page_to_image(pdf_path: str, page_number: int = 0, dpi: int = 300):
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=dpi)
        out_path = os.path.splitext(pdf_path)[0] + f"_page{page_number+1}.png"
        pix.save(out_path)
        doc.close()
        return out_path
    except Exception as e:
        return {"error": f"Failed to convert PDF to image: {e}"}


def process_pdf_with_easyocr(pdf_path: str) -> pd.DataFrame | Dict[str, Any]:
    img_path = convert_pdf_page_to_image(pdf_path)
    if isinstance(img_path, dict):
        return img_path

    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return {"error": "Could not read the converted image file."}

    # Binarize and invert
    _, img_bin = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    img_bin = 255 - img_bin

    contours, _ = cv2.findContours(img_bin, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    H, W = img.shape[:2]
    cells = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if (w > 20 and h > 20) and w < int(W * 0.9) and h < int(H * 0.25):
            cells.append((x, y, w, h))

    reader = easyocr.Reader(['en'])

    if not cells:
        lines = reader.readtext(img, detail=0, paragraph=True)
        if not lines:
            return {"error": "OCR could not detect any text in the PDF image."}
        df = pd.DataFrame({'Raw': lines})
        try:
            os.remove(img_path)
        except Exception:
            pass
        return df

    cells.sort(key=lambda r: (r[1], r[0]))
    first_row_y = cells[0][1]
    num_cols = sum(1 for c in cells if abs(c[1] - first_row_y) < 10)

    rows: List[List[str]] = []
    row_acc: List[str] = []
    for (x, y, w, h) in cells:
        crop = img[y:y+h, x:x+w]
        text = " ".join(reader.readtext(crop, detail=0, paragraph=True)).strip()
        row_acc.append(text)
        if len(row_acc) == num_cols:
            rows.append(row_acc)
            row_acc = []

    if not rows or not rows[0]:
        return {"error": "Failed to reconstruct table from OCR results."}

    header = [str(h or '').strip() for h in rows[0]]
    data_rows = rows[1:] if len(rows) > 1 else []

    df = pd.DataFrame(data_rows, columns=header)

    # Map key columns best-effort
    cols = list(df.columns)
    if len(cols) >= 1:
        df.rename(columns={cols[0]: 'Roll No'}, inplace=True)
    if len(cols) >= 2:
        df.rename(columns={cols[1]: 'Name'}, inplace=True)
    if 'Student ID' not in df.columns:
        df['Student ID'] = ''

    date_cols = [c for c in df.columns if c not in ('Roll No', 'Student ID', 'Name')]

    def norm_att(v: str) -> str:
        m = str(v or '').strip().lower()
        if m in ('p', 'present', '✓', '✔', 'tick', 'yes', '1', 'true') or len(m) > 4:
            return 'Present'
        return 'Absent'

    for c in date_cols:
        df[c] = df[c].astype(str).apply(norm_att)

    try:
        os.remove(img_path)
    except Exception:
        pass

    # Ensure column order
    df = df[['Roll No', 'Student ID', 'Name'] + date_cols]
    return df


# ---------- Public entry used by Flask ----------

def process_image(path: str) -> Dict[str, Any]:
    ext = os.path.splitext(path)[1].lower()

    # PDF -> OCR pipeline
    if ext == '.pdf':
        df_or_err = process_pdf_with_easyocr(path)
        if isinstance(df_or_err, dict) and df_or_err.get('error'):
            return df_or_err
        if isinstance(df_or_err, pd.DataFrame):
            return _build_reports_from_dataframe(df_or_err)
        return {"error": "Unexpected OCR output."}

    # Images -> Gemini pipeline
    err = _configure_gemini_or_error()
    if err:
        return err

    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    image = Image.open(path)
    prompt = create_gemini_prompt()

    response = model.generate_content([prompt, image])
    data = _parse_gemini_json(response.text)

    dates = [str(d).strip() for d in data.get('dates', [])]
    students = data.get('students', [])
    if not dates or not students:
        return {"error": "Gemini could not extract valid date or student records from the image."}

    df = _normalize_records_to_df(dates, students)
    return _build_reports_from_dataframe(df, dates)
