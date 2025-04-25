from flask import Flask, render_template, request
import os
import re
# import spacy
import string
import matplotlib.pyplot as plt
from PyPDF2 import PdfReader
import docx
from fuzzywuzzy import process
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

app = Flask(__name__)

# Synonym Dictionary for Skill Matching
synonym_dict = {
    "machine learning": ["ml", "deep learning", "artificial intelligence"],
    "data analysis": ["data analytics", "business intelligence"],
    "nlp": ["natural language processing"],
    "sql": ["structured query language"]
}

# Set your Poppler path (for Windows, adjust as needed)
poppler_path = r"C:\path\to\poppler\bin"

# Extract Text from PDF
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        if text.strip():
            return text.lower().translate(str.maketrans('', '', string.punctuation.replace('+','')))
    except:
        pass  # fallback to OCR if PyPDF2 fails

    # Fallback to OCR (uncomment if OCR needed)
    # pages = convert_from_path(pdf_path, 300, poppler_path=poppler_path)
    # for page in pages:
    #     text += pytesseract.image_to_string(page) + "\n"
    # return text.lower().translate(str.maketrans('', '', string.punctuation.replace('+','')))

# Extract Text from DOCX
def extract_text_from_docx(docx_path):
    doc = docx.Document(docx_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text.lower()

# Extract Resume Information

# Load English NLP model (you can also use multilingual model if needed)
# nlp = spacy.load("en_core_web_sm")

def extract_resume_info(text, job_keywords):
    name = extract_name(text)  # Assume this is defined

    # Email extraction
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    email = email_match.group(0) if email_match else "Not Found"

    # Phone extraction (Pakistani and international)
    phone_match = re.search(r"(\+92|0092)?[-\s]?\d{3}[-\s]?\d{7}", text)
    phone = phone_match.group(0) if phone_match else "Not Found"

    # Address extraction (Pakistani format)
    address_match = re.search(
        r"(House|Flat|Apartment|Plot)\s*(No\.?|#)?\s*\d+[-\w]*,?\s*(Street|Block|Sector|Phase)?\s*\d*[-\w]*,?.*?(Karachi|Lahore|Islamabad|Rawalpindi|Peshawar|Multan|Quetta|Hyderabad|Faisalabad)",
        text,
        re.IGNORECASE
    )
    address = address_match.group(0) if address_match else "Not Found"

    # Skills extraction
    skills = []
    for s in job_keywords:
        pattern = r"\b" + re.escape(s.lower()) + r"\b"
        if re.search(pattern, text.lower()):
            skills.append(s)

    return name, email, phone, address, skills



# Placeholder Name Extraction
def extract_name(text):
    lines = text.split("\n")
    return lines[0].strip() if lines else "Unknown"

# Normalize Skills using Synonyms
def normalize_skills(resume_skills):
    normalized_resume_skills = set()
    for skill in resume_skills:
        matched = False
        for key, synonyms in synonym_dict.items():
            if skill in synonyms or skill == key:
                normalized_resume_skills.add(key)
                matched = True
                break
        if not matched:
            normalized_resume_skills.add(skill)
    return normalized_resume_skills

# Generate Matched vs Missing Visualization
def generate_visualization(matched_skills, missing_skills, match_percentage, filename_prefix):
    skills = list(matched_skills) + list(missing_skills)
    presence = [1] * len(skills)
    colors = ["green"] * len(matched_skills) + ["red"] * len(missing_skills)

    plt.figure(figsize=(8, 5))
    plt.bar(skills, presence, color=colors)
    plt.xlabel("Skills")
    plt.ylabel("Presence")
    plt.title("Matched & Missing Skills")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f"static/{filename_prefix}_bar_chart.png")
    plt.close()

    plt.figure(figsize=(5, 5))
    plt.pie([match_percentage, 100 - match_percentage],
            labels=["Matched", "Not Matched"],
            colors=["green", "red"],
            autopct="%1.1f%%")
    plt.title("Resume Match Percentage")
    plt.savefig(f"static/{filename_prefix}_pie_chart.png")
    plt.close()

# Generate Top Candidate Ranking Chart
def generate_ranking_chart(candidate_results, filename="static/top_candidates.png"):
    names = [c['name'] for c in candidate_results]
    scores = [c['percentage'] for c in candidate_results]

    plt.figure(figsize=(10, 6))
    bars = plt.barh(names, scores, color="skyblue")
    plt.xlabel("Match Percentage")
    plt.title("Top Candidates Ranked by Resume Match")

    for bar in bars:
        width = bar.get_width()
        plt.text(width + 1, bar.get_y() + bar.get_height() / 2, f'{width:.1f}%', va='center')

    plt.xlim(0, 100)
    plt.gca().invert_yaxis()  # Highest on top
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

# Process a Single Resume
def process_single_resume(resume_path, job_keywords):
    print("job keywords ",job_keywords)
    if resume_path.endswith(".pdf"):
        resume_text = extract_text_from_pdf(resume_path)
        print("resume text  ",resume_text)
    elif resume_path.endswith(".docx"):
        resume_text = extract_text_from_docx(resume_path)
    else:
        return None, None, None, None, None, None, None

    name, email, phone, address, resume_skills = extract_resume_info(resume_text, job_keywords)
    normalized_resume_skills = normalize_skills(resume_skills)
    print("normalized resume skills",normalized_resume_skills)

    final_matched_skills = set()
    for job_skill in job_keywords:
        result = process.extractOne(job_skill, normalized_resume_skills)
        if result:
            match, score = result
            if score >= 85:
                final_matched_skills.add(job_skill)

    match_percentage = (len(final_matched_skills) / len(job_keywords)) * 100
    missing_skills = set(job_keywords) - final_matched_skills

    filename_prefix = os.path.splitext(os.path.basename(resume_path))[0]
    generate_visualization(final_matched_skills, missing_skills, match_percentage, filename_prefix)

    return name, email, phone, address, final_matched_skills, match_percentage, missing_skills

# Flask Route
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        job_keywords = request.form["job_description"].lower().split(",")
        files = request.files.getlist("resumes")
        results = []

        for file in files:
            filepath = os.path.join("uploads", file.filename)
            file.save(filepath)

            name, email, phone, address, matched_skills, match_percentage, missing_skills = process_single_resume(filepath, job_keywords)
            os.remove(filepath)

            results.append({
                "name": name,
                "email": email,
                "phone": phone,
                "address": address,
                "skills": matched_skills,
                "percentage": match_percentage
            })

        sorted_results = sorted(results, key=lambda x: x["percentage"], reverse=True)
        top_candidates = sorted_results[:10]

        generate_ranking_chart(top_candidates)

        return render_template("result.html", candidates=top_candidates)

    return render_template("index.html")

# Run the App
if __name__ == "__main__":
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    app.run(debug=True)
