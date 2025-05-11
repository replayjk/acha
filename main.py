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
def init_db():
    conn = sqlite3.connect("reports.db")
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

    # 폰트 설정 (Noto Sans CJK)
    font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf"
    font_path = "NotoSansCJKsc-Regular.otf"

    # 폰트 다운로드 (없으면 다운로드)
    if not os.path.exists(font_path):
        print("📝 Noto Sans CJK 폰트 다운로드 중...")
        response = requests.get(font_url)
        if response.status_code == 200:
            with open(font_path, "wb") as f:
                f.write(response.content)
            print("✅ 폰트 다운로드 완료")
        else:
            print("❌ 폰트 다운로드 실패")
            return None

    try:
        # GPT-4를 사용하여 필드 자동 채우기
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
        sections = {"사례명": "", "발생일시": "", "발생장소": "", "발생개요": "", "설비": "", "발생원인": "", "예상피해": "", "재발방지대책": ""}

        for line in generated_text.splitlines():
            for key in sections.keys():
                if line.startswith(key):
                    sections[key] = line.replace(key + ":", "").strip()

        # PDF 생성
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # 폰트 등록
        pdf.add_font("NotoSansCJK", "", font_path, uni=True)
        pdf.set_font("NotoSansCJK", size=12)

        # 문서 상단 제목
        pdf.set_font_size(24)
        pdf.cell(0, 15, "아차사고 경험사례", ln=True, align="C")
        pdf.ln(10)

        # 보고서 표 양식 (1페이지 구성)
        table_headers = ["사례명", "발생일시", "발생장소", "발생개요", "설비", "발생원인", "예상피해", "재발방지대책"]
        pdf.set_font_size(12)
        pdf.set_fill_color(240, 240, 240)
        for header in table_headers:
            pdf.cell(0, 10, f"{header}: {sections[header]}", ln=True, fill=True)
            pdf.ln(2)

        # 이미지 추가 (개선 전/후 사진)
        if image_path and image_path != "None":
            try:
                image_full_path = image_path.lstrip("/")
                pdf.set_fill_color(240, 240, 240)
                pdf.cell(0, 10, "관련 사진", ln=True, fill=True)
                pdf.image(image_full_path, x=15, w=180)
                pdf.ln(10)
            except Exception as e:
                print(f"이미지 추가 중 오류 발생: {e}")

        # PDF 저장
        pdf.output(pdf_path)

        print(f"✅ PDF 생성 완료: {pdf_path}")
        return f"/pdf_reports/{pdf_filename}"

    except Exception as e:
        print(f"🚨 PDF 생성 실패: {e}")
        return None

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/list", response_class=HTMLResponse)
async def list_cases(request: Request):
    conn = sqlite3.connect("reports.db")
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
        image_path = f"/uploads/{file_name}"

    # PDF 생성
    pdf_path = generate_pdf(description, image_path, timestamp)

    # 데이터베이스 저장
    conn = sqlite3.connect("reports.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO cases (description, image_path, timestamp, pdf_path) VALUES (?, ?, ?, ?)", (description, image_path, timestamp, pdf_path))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/list", status_code=303)
