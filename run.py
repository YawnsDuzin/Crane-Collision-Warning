"""
크레인 충돌 예측 시스템 - 실행 스크립트
=========================================

이 파일을 실행하면 웹 서버가 시작됩니다.

[실행 방법]
    python run.py

[접속 방법]
    웹 브라우저에서 http://localhost:8000 접속

[중지 방법]
    터미널에서 Ctrl+C
"""

import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from config.settings import SERVER_HOST, SERVER_PORT


def main():
    """메인 실행 함수"""
    print()
    print("=" * 60)
    print("  크레인 충돌 예측 시스템")
    print("  Crane Collision Warning System")
    print("=" * 60)
    print()
    print(f"  서버 시작 중...")
    print(f"  접속 주소: http://localhost:{SERVER_PORT}")
    print(f"  중지: Ctrl+C")
    print()
    print("=" * 60)
    print()

    uvicorn.run(
        "server.app:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,     # 코드 수정 시 자동 재시작
        log_level="info",
    )


if __name__ == "__main__":
    main()
