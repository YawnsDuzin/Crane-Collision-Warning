"""
FastAPI 웹 서버 메인 모듈
===========================

이 파일은 웹 서버의 진입점입니다.
모든 것을 하나로 묶어주는 역할을 합니다.

[웹 서버가 하는 일]
1. 관제 화면(HTML)을 브라우저에 제공
2. REST API로 크레인 제어 명령을 받음
3. WebSocket으로 실시간 데이터를 브라우저에 전송
4. 시뮬레이션 엔진을 백그라운드에서 실행

[실행 방법]
터미널에서:
    python -m server.app

또는:
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

브라우저에서:
    http://localhost:8000
"""

import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
# (어디서 실행하든 import가 동작하도록)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request

from server.routes import router as api_router
from server.websocket import router as ws_router
from simulator.engine import SimulationEngine

from config.settings import SERVER_HOST, SERVER_PORT


# ============================================================
# FastAPI 앱 생성
# ============================================================
app = FastAPI(
    title="크레인 충돌 예측 시스템",
    description="건설현장 타워크레인 간 충돌을 실시간으로 예측하고 경고하는 시스템",
    version="1.0.0",
)

# ============================================================
# 정적 파일 및 템플릿 설정
# ============================================================
# 프로젝트 루트 디렉토리 계산
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 정적 파일 (CSS, JS, 이미지 등)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# HTML 템플릿
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ============================================================
# 시뮬레이션 엔진 (전역 인스턴스)
# ============================================================
# 앱 전체에서 하나의 엔진을 공유합니다
simulation_engine = SimulationEngine()


def get_simulation_engine() -> SimulationEngine:
    """시뮬레이션 엔진 인스턴스를 반환합니다."""
    return simulation_engine


# ============================================================
# 라우터 등록
# ============================================================
# REST API 라우트 (/api/...)
app.include_router(api_router, prefix="/api")

# WebSocket 라우트 (/ws)
app.include_router(ws_router)


# ============================================================
# 메인 페이지
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    """
    메인 관제 화면을 반환합니다.
    브라우저에서 http://localhost:8000 접속 시 이 페이지가 표시됩니다.
    """
    return templates.TemplateResponse("index.html", {"request": request})


# ============================================================
# 앱 시작/종료 이벤트
# ============================================================
@app.on_event("startup")
async def startup_event():
    """
    서버 시작 시 실행되는 초기화 코드

    [동작]
    1. 기본 크레인 설정 로드
    2. 시뮬레이션 엔진을 백그라운드 태스크로 시작
    """
    print("=" * 60)
    print("  크레인 충돌 예측 시스템 서버 시작")
    print("=" * 60)

    # 기본 크레인 설정 로드
    simulation_engine.setup_default_cranes()
    crane_count = len(simulation_engine.collision_engine.cranes)
    print(f"  크레인 {crane_count}대 등록 완료")

    # 시뮬레이션 엔진을 백그라운드에서 시작
    asyncio.create_task(simulation_engine.start())
    print("  시뮬레이션 엔진 시작")
    print(f"  웹 브라우저에서 http://localhost:{SERVER_PORT} 접속")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 정리 코드"""
    simulation_engine.stop()
    print("서버 종료")


# ============================================================
# 직접 실행 시
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.app:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,  # 코드 변경 시 자동 재시작 (개발 편의)
    )
