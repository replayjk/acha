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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from PIL import Image
import io

load_dotenv()

# 환경변수 확인 및 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("🚨 경고: OPENAI_API_KEY가 설정되지 않았습니다!")
    print("현재 환경변수 목록:")
    for key in os.environ:
        print(f"- {key}")
else:
    print(f"✅ OPENAI_API_KEY가 설정되었습니다. (길이: {len(OPENAI_API_KEY)})")
    print(f"API Key 시작: {OPENAI_API_KEY[:8]}...")

openai.api_key = OPENAI_API_KEY

# API Key 검증 함수 (openai 1.x 방식)
def validate_api_key():
    try:
        if not OPENAI_API_KEY:
            return False, "API Key가 설정되지 않았습니다."
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        return True, "API Key가 유효합니다."
    except openai.AuthenticationError:
        return False, "API Key가 유효하지 않습니다."
    except Exception as e:
        return False, f"API Key 검증 중 오류 발생: {str(e)}"

# 서버 시작 시 API Key 검증
is_valid, message = validate_api_key()
if not is_valid:
    print(f"🚨 API Key 검증 실패: {message}")
else:
    print(f"✅ API Key 검증 성공: {message}")

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
            pdf_path TEXT,
            report_image_path TEXT
        )
    ''')
    conn.commit()
    conn.close()
init_db()

# PDF generation function
def generate_pdf(data, timestamp):
    try:
        if not OPENAI_API_KEY:
            print("🚨 OpenAI API Key가 설정되지 않았습니다.")
            return None

        print(f"🔑 PDF 생성 시작 - API Key 상태: {'설정됨' if OPENAI_API_KEY else '설정되지 않음'}")
        pdf_dir = "pdf_reports"
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_filename = f"{timestamp}.pdf"
        pdf_path = os.path.join(pdf_dir, pdf_filename)

        font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf"
        font_path = "NotoSansCJKsc-Regular.otf"
        if not os.path.exists(font_path):
            response = requests.get(font_url)
            if response.status_code == 200:
                with open(font_path, "wb") as f:
                    f.write(response.content)
            else:
                print(f"❌ 폰트 다운로드 실패: {response.status_code}")
                return None

        pdf = FPDF()
        pdf.add_page()
        pdf.add_font("NotoSansCJK", "", font_path, uni=True)
        pdf.set_font("NotoSansCJK", size=12)

        # 제목
        pdf.set_font_size(20)
        pdf.cell(0, 15, "아차사고 경험사례", ln=True, align="C")
        pdf.ln(5)

        # 작성자 정보 표
        pdf.set_font_size(12)
        pdf.cell(40, 10, "작성일자", 1, 0, "C")
        pdf.cell(50, 10, data["작성일자"], 1, 0, "C")
        pdf.cell(20, 10, "소속", 1, 0, "C")
        pdf.cell(80, 10, data["department"], 1, 1, "C")
        pdf.cell(20, 10, "직책", 1, 0, "C")
        pdf.cell(30, 10, data["position"], 1, 0, "C")
        pdf.cell(20, 10, "성명", 1, 0, "C")
        pdf.cell(120, 10, data["name"], 1, 1, "C")

        # 사례 정보 표
        pdf.cell(30, 10, "사례명", 1, 0, "C")
        pdf.cell(80, 10, data["사례명"], 1, 0, "C")
        pdf.cell(30, 10, "발생일시", 1, 0, "C")
        pdf.cell(50, 10, data["발생일시"], 1, 1, "C")
        pdf.cell(30, 10, "발생개요", 1, 0, "C")
        pdf.cell(130, 10, data["발생개요"], 1, 1, "C")
        pdf.cell(30, 10, "발생장소", 1, 0, "C")
        pdf.cell(130, 10, data["발생장소"], 1, 1, "C")
        pdf.cell(30, 10, "설비", 1, 0, "C")
        pdf.cell(130, 10, data["설비"], 1, 1, "C")
        pdf.cell(30, 10, "발생원인", 1, 0, "C")
        pdf.cell(130, 10, data["발생원인"], 1, 1, "C")
        pdf.cell(30, 10, "예상피해", 1, 0, "C")
        pdf.cell(130, 10, data["예상피해"], 1, 1, "C")
        pdf.cell(30, 10, "위험성추정및결정", 1, 0, "C")
        pdf.cell(130, 10, data["위험성추정및결정"], 1, 1, "C")
        pdf.cell(30, 10, "재발방지대책", 1, 0, "C")
        pdf.cell(130, 10, data["재발방지대책"], 1, 1, "C")

        # 관련사진
        pdf.cell(0, 10, "관련사진", 1, 1, "C")
        pdf.cell(90, 10, "개선 전 사진", 1, 0, "C")
        pdf.cell(90, 10, "개선 후 사진", 1, 1, "C")
        y_now = pdf.get_y()
        if data["before_image_path"] and os.path.exists(data["before_image_path"].lstrip("/")):
            pdf.image(data["before_image_path"].lstrip("/"), x=10, y=y_now+2, w=85)
        if data["after_image_path"] and os.path.exists(data["after_image_path"].lstrip("/")):
            pdf.image(data["after_image_path"].lstrip("/"), x=110, y=y_now+2, w=85)
        pdf.ln(50)
        pdf.cell(0, 10, "사진설명: 차량 하단 발판 미끄러짐 방지 사포 설치 등", 0, 1, "L")

        pdf.output(pdf_path)
        print(f"✅ PDF 생성 완료: {pdf_path}")
        return f"/pdf_reports/{pdf_filename}"
    except Exception as e:
        print(f"🚨 PDF 생성 중 예외 발생: {str(e)}")
        return None

def generate_image(data, timestamp):
    try:
        # 이미지 저장 디렉토리 생성
        img_dir = "image_reports"
        os.makedirs(img_dir, exist_ok=True)
        img_filename = f"{timestamp}.png"
        img_path = os.path.join(img_dir, img_filename)

        # Chrome 옵션 설정
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')

        # Selenium WebDriver 초기화
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            # HTML 템플릿 생성
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 20px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                    th, td {{ border: 1px solid black; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    img {{ max-width: 300px; max-height: 200px; }}
                </style>
            </head>
            <body>
                <h1>아차사고 경험사례</h1>
                <table>
                    <tr>
                        <th>작성일자</th><td>{data['작성일자']}</td>
                        <th>소속</th><td>{data['department']}</td>
                    </tr>
                    <tr>
                        <th>직책</th><td>{data['position']}</td>
                        <th>성명</th><td>{data['name']}</td>
                    </tr>
                    <tr><th>사례명</th><td colspan="3">{data['사례명']}</td></tr>
                    <tr><th>발생일시</th><td colspan="3">{data['발생일시']}</td></tr>
                    <tr><th>발생개요</th><td colspan="3">{data['발생개요']}</td></tr>
                    <tr><th>발생장소</th><td colspan="3">{data['발생장소']}</td></tr>
                    <tr><th>설비</th><td colspan="3">{data['설비']}</td></tr>
                    <tr><th>발생원인</th><td colspan="3">{data['발생원인']}</td></tr>
                    <tr><th>예상피해</th><td colspan="3">{data['예상피해']}</td></tr>
                    <tr><th>위험성추정및결정</th><td colspan="3">{data['위험성추정및결정']}</td></tr>
                    <tr><th>재발방지대책</th><td colspan="3">{data['재발방지대책']}</td></tr>
                </table>
                <h2>관련 사진</h2>
                <table>
                    <tr>
                        <th>개선 전 사진</th>
                        <th>개선 후 사진</th>
                    </tr>
                    <tr>
                        <td>
                            {'<img src="' + data["before_image_path"] + '">' if data["before_image_path"] else '(없음)'}
                        </td>
                        <td>
                            {'<img src="' + data["after_image_path"] + '">' if data["after_image_path"] else '(없음)'}
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
            
            # HTML 파일 임시 저장
            temp_html = f"temp_{timestamp}.html"
            with open(temp_html, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            # HTML 파일을 로드하고 스크린샷 캡처
            driver.get(f"file:///{os.path.abspath(temp_html)}")
            driver.save_screenshot(img_path)
            
            # 임시 HTML 파일 삭제
            os.remove(temp_html)
            
            return f"/image_reports/{img_filename}"
        finally:
            driver.quit()
            
    except Exception as e:
        print(f"🚨 이미지 생성 중 예외 발생: {str(e)}")
        return None

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    error = request.query_params.get('error')
    error_message = None
    if error == 'generation_failed':
        error_message = "보고서 생성에 실패했습니다. 다시 시도해주세요."
    elif error == 'submission_failed':
        error_message = "제출 처리 중 오류가 발생했습니다. 다시 시도해주세요."
    
    # API Key 상태 확인
    is_valid, message = validate_api_key()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "error_message": error_message,
        "api_key_valid": is_valid
    })

@app.get("/list", response_class=HTMLResponse)
async def list_cases(request: Request):
    conn = sqlite3.connect("reports.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, description, image_path, timestamp, pdf_path, report_image_path FROM cases ORDER BY timestamp DESC")
    cases = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("list.html", {"request": request, "cases": cases})

@app.post("/preview", response_class=HTMLResponse)
async def preview_case(request: Request,
    department: str = Form(...),
    position: str = Form(...),
    name: str = Form(...),
    description: str = Form(...),
    before_image: UploadFile = File(None),
    after_image: UploadFile = File(None)):
    try:
        # API Key 검증
        is_valid, message = validate_api_key()
        if not is_valid:
            return templates.TemplateResponse("preview.html", {
                "request": request,
                "error": f"OpenAI API Key 검증 실패: {message}"
            })

        # GPT-4를 사용하여 필드 자동 채우기 (openai 1.x 방식)
        print("🤖 OpenAI API 호출 중...")
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "너는 아차사고 사례를 작성하는 전문가입니다. 입력된 사고 내용을 바탕으로 사례명, 발생일시, 발생개요, 발생장소, 설비, 발생원인, 예상피해, 위험성추정및결정, 재발방지대책을 자동으로 작성하세요."},
                {"role": "user", "content": f"사고 내용: {description}\n필드를 다음 형식으로 채우세요:\n\n사례명:\n발생일시:\n발생개요:\n발생장소:\n설비:\n발생원인:\n예상피해:\n위험성추정및결정:\n재발방지대책:"}
            ],
            max_tokens=700,
            temperature=0.7
        )
        print("✅ OpenAI API 호출 성공")

        generated_text = response.choices[0].message.content.strip()
        sections = {"사례명": "", "발생일시": "", "발생개요": "", "발생장소": "", "설비": "", "발생원인": "", "예상피해": "", "위험성추정및결정": "", "재발방지대책": ""}
        for line in generated_text.splitlines():
            for key in sections.keys():
                if line.startswith(key):
                    sections[key] = line.replace(key + ":", "").strip()

        # 이미지 처리
        before_image_path = ""
        after_image_path = ""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        if before_image is not None and before_image.filename != "":
            before_file_ext = before_image.filename.split(".")[-1]
            before_file_name = f"before_{timestamp}.{before_file_ext}"
            before_file_path = os.path.join(upload_dir, before_file_name)
            with open(before_file_path, "wb") as f:
                f.write(await before_image.read())
            before_image_path = f"/uploads/{before_file_name}"
        if after_image is not None and after_image.filename != "":
            after_file_ext = after_image.filename.split(".")[-1]
            after_file_name = f"after_{timestamp}.{after_file_ext}"
            after_file_path = os.path.join(upload_dir, after_file_name)
            with open(after_file_path, "wb") as f:
                f.write(await after_image.read())
            after_image_path = f"/uploads/{after_file_name}"

        # 오늘 날짜를 작성일자로 자동 입력
        today_str = datetime.now().strftime("%Y.%m.%d")

        return templates.TemplateResponse("preview.html", {
            "request": request,
            "department": department,
            "position": position,
            "name": name,
            "작성일자": today_str,
            "description": description,
            "before_image_path": before_image_path,
            "after_image_path": after_image_path,
            **sections
        })

    except Exception as e:
        print(f"🚨 미리보기 생성 중 예외 발생: {str(e)}")
        return templates.TemplateResponse("preview.html", {
            "request": request,
            "error": f"미리보기 생성 중 오류가 발생했습니다: {str(e)}"
        })

@app.post("/submit", response_class=RedirectResponse)
async def submit_case(
    department: str = Form(...),
    position: str = Form(...),
    name: str = Form(...),
    작성일자: str = Form(...),
    description: str = Form(...),
    before_image_path: str = Form(""),
    after_image_path: str = Form(""),
    사례명: str = Form(...),
    발생일시: str = Form(...),
    발생개요: str = Form(...),
    발생장소: str = Form(...),
    설비: str = Form(...),
    발생원인: str = Form(...),
    예상피해: str = Form(...),
    위험성추정및결정: str = Form(...),
    재발방지대책: str = Form(...)):
    try:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        data = {
            "department": department,
            "position": position,
            "name": name,
            "작성일자": 작성일자,
            "description": description,
            "before_image_path": before_image_path,
            "after_image_path": after_image_path,
            "사례명": 사례명,
            "발생일시": 발생일시,
            "발생개요": 발생개요,
            "발생장소": 발생장소,
            "설비": 설비,
            "발생원인": 발생원인,
            "예상피해": 예상피해,
            "위험성추정및결정": 위험성추정및결정,
            "재발방지대책": 재발방지대책
        }
        
        # PDF 생성
        pdf_path = generate_pdf(data, timestamp)
        
        # 이미지 생성
        img_path = generate_image(data, timestamp)
        
        if pdf_path is None and img_path is None:
            return RedirectResponse(url="/?error=generation_failed", status_code=303)

        # 데이터베이스 저장
        conn = sqlite3.connect("reports.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO cases (description, image_path, timestamp, pdf_path, report_image_path) VALUES (?, ?, ?, ?, ?)", 
                      (description, before_image_path, timestamp, pdf_path, img_path))
        conn.commit()
        conn.close()

        return RedirectResponse(url="/list", status_code=303)
    except Exception as e:
        print(f"🚨 제출 처리 중 예외 발생: {str(e)}")
        return RedirectResponse(url="/?error=submission_failed", status_code=303)
