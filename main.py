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
import requests

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

app = FastAPI()

# Static and template settings
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/pdf_reports", StaticFiles(directory="pdf_reports"), name="pdf_reports")
templates = Jinja2Templates(directory="templates")

# Database initialization
DB_PATH = "./reports.db"
def init_db():
    conn = sqlite3.connect(DB_PATH)
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
    try:
        pdf_dir = "pdf_reports/"
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_filename = f"{timestamp}.pdf"
        pdf_path = os.path.join(pdf_dir, pdf_filename)

        # 폰트 설정
        font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf"
        font_path = "NotoSansCJKsc-Regular.otf"
        if not os.path.exists(font_path):
            response = requests.get(font_url)
            with open(font_path, "wb") as f:
                f.write(response.content)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # 폰트 등록
        pdf.add_font("NotoSansCJK", "", font_path, uni=True)
        pdf.set_font("NotoSansCJK", size=12)

        # 제목
        pdf.set_font_size(24)
        pdf.cell(0, 15, "아차사고 경험사례", ln=True, align="C")
        pdf.ln(10)

        # 보고서 내용
        pdf.set_font_size(12)
        if description:
            pdf.multi_cell(0, 10, f"사례명: {description}")
        else:
            pdf.multi_cell(0, 10, "사례명: (내용 없음)")
        pdf.multi_cell(0, 10, f"발생일시: {timestamp}")
        pdf.ln(5)

        # 이미지 추가
        if image_path and image_path != "None":
            try:
                image_full_path = image_path.strip("/")
                pdf.set_fill_color(240, 240, 240)
                pdf.cell(0, 10, "관련 사진", ln=True, fill=True)
                pdf.image("." + image_full_path, x=15, w=180)
                pdf.ln(10)
            except Exception as e:
                print(f"이미지 추가 중 오류 발생: {e}")

        # PDF 저장
        pdf.output(pdf_path)

        # 파일이 정상적으로 생성된 경우에만 경로 반환
        if os.path.exists(pdf_path):
            return f"/pdf_reports/{pdf_filename}"
        else:
            print("❌ PDF 파일 생성 실패")
            return None

    except Exception as e:
        print(f"PDF 생성 중 오류 발생: {e}")
        return None

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/list", response_class=HTMLResponse)
async def list_cases(request: Request):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, description, image_path, timestamp, pdf_path FROM cases ORDER BY timestamp DESC")
    cases = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("list.html", {"request": request, "cases": cases})

@app.post("/submit", response_class=RedirectResponse)
async def submit_case(description: str = Form(...), image: UploadFile = File(None)):
    try:
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
            image_path = f"/uploads/{file_name}"

        # PDF 생성
        pdf_path = generate_pdf(description, image_path, timestamp)

        # PDF 파일이 생성된 경우에만 DB에 저장
        if pdf_path is not None:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO cases (description, image_path, timestamp, pdf_path) VALUES (?, ?, ?, ?)", 
                           (description, image_path, timestamp, pdf_path))
            conn.commit()
            conn.close()
            print("✅ 데이터베이스 저장 완료")
        else:
            print("❌ PDF 생성 실패로 데이터베이스 저장 생략")

        return RedirectResponse(url="/list", status_code=303)

    except Exception as e:
        print(f"사례 등록 중 오류 발생: {e}")
        return RedirectResponse(url="/", status_code=303)
