import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from dotenv import load_dotenv
import openai
from fpdf import FPDF

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

app = FastAPI()

# Static and template settings
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Database initialization
DB_FILE = "reports.db"
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            image_path TEXT,
            timestamp TEXT,
            pdf_path TEXT
        )
    ''')
    conn.commit()
    conn.close()
init_db()

# PDF generation function
def generate_pdf(description, image_path, timestamp):
    pdf_dir = "pdf_reports/"
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_filename = f"{timestamp}.pdf"
    pdf_path = os.path.join(pdf_dir, pdf_filename)

    # GPT-4를 사용하여 필드 자동 채우기
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "너는 아차사고 사례를 작성하는 전문가입니다. 입력된 사고 내용을 바탕으로 사례명, 발생일시, 발생장소, 발생개요, 설비, 발생원인, 예상피해, 재발방지대책을 자동으로 작성하세요."},
                {"role": "user", "content": f"사고 내용: {description}\n필드를 다음 형식으로 채우세요:\n\n사례명:\n발생일시:\n발생장소:\n발생개요:\n설비:\n발생원인:\n예상피해:\n재발방지대책:"}
            ],
            max_tokens=500,
            temperature=0.7
        )
        generated_text = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"GPT 처리 중 오류 발생: {e}")
        return None

    # PDF 생성
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 15, "아차사고 사례 보고서", ln=True, align="C")
    pdf.ln(10)
    for line in generated_text.splitlines():
        pdf.multi_cell(0, 10, line)
    pdf.output(pdf_path)
    return f"/{pdf_path}"

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/list", response_class=HTMLResponse)
async def list_cases(request: Request):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, description, image_path, timestamp, pdf_path FROM cases ORDER BY timestamp DESC")
    cases = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("list.html", {"request": request, "cases": cases})

@app.post("/submit", response_class=RedirectResponse)
async def submit_case(description: str = Form(...), image: UploadFile = File(None)):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    image_path = ""

    # 이미지 저장
    if image is not None and image.filename != "":
        upload_dir = "uploads/"
        os.makedirs(upload_dir, exist_ok=True)
        file_extension = image.filename.split(".")[-1]
        file_name = f"{timestamp}.{file_extension}"
        file_path = os.path.join(upload_dir, file_name)

        with open(file_path, "wb") as f:
            f.write(await image.read())
        image_path = f"/{file_path}"

    # PDF 생성
    pdf_path = generate_pdf(description, image_path, timestamp)

    # 데이터베이스 저장
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO cases (description, image_path, timestamp, pdf_path) VALUES (?, ?, ?, ?)", (description, image_path, timestamp, pdf_path))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/list", status_code=303)
