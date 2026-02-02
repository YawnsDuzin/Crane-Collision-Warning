"""
REST API 라우트 모듈
=====================

이 모듈은 HTTP 요청을 처리하는 API 엔드포인트를 정의합니다.

[REST API란?]
웹 브라우저(또는 다른 프로그램)가 서버에 요청을 보내고 응답을 받는 방식입니다.
- GET: 데이터 조회 (예: 크레인 상태 조회)
- POST: 데이터 변경 (예: 크레인 속도 변경)

[API 목록]

크레인 관련:
  GET  /api/cranes              - 모든 크레인 상태 조회
  GET  /api/cranes/{id}         - 특정 크레인 상태 조회
  POST /api/cranes/{id}/control - 크레인 제어 (속도 변경 등)

시스템 관련:
  GET  /api/status              - 전체 시스템 상태 조회
  GET  /api/collisions          - 충돌 검사 결과 조회

시나리오 관련:
  GET  /api/scenarios           - 사용 가능한 시나리오 목록
  POST /api/scenarios/apply     - 시나리오 적용

시뮬레이션 제어:
  POST /api/simulation/speed    - 시뮬레이션 속도 변경
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from simulator.scenarios import apply_scenario, get_scenario_list

router = APIRouter()


# ============================================================
# 요청 데이터 모델 (Pydantic)
# ============================================================
# Pydantic 모델은 클라이언트가 보내는 JSON 데이터의 형식을 정의합니다.
# 형식에 맞지 않으면 자동으로 에러 메시지를 반환합니다.

class CraneControlRequest(BaseModel):
    """크레인 제어 요청 데이터"""
    slew_speed: Optional[float] = None      # 선회 속도 (도/초)
    luffing_speed: Optional[float] = None   # 기복 속도 (도/초)
    slew_angle: Optional[float] = None      # 선회각 직접 설정 (도)
    luffing_angle: Optional[float] = None   # 기복각 직접 설정 (도)


class ScenarioApplyRequest(BaseModel):
    """시나리오 적용 요청 데이터"""
    scenario_id: str    # 시나리오 ID


class SimulationSpeedRequest(BaseModel):
    """시뮬레이션 속도 변경 요청"""
    speed_multiplier: float  # 속도 배율 (1.0=실시간)


class CraneAddRequest(BaseModel):
    """크레인 추가 요청 데이터"""
    id: str
    name: str
    base_x: float
    base_y: float
    mast_height: float = 40.0
    boom_length: float = 55.0
    initial_slew_angle: float = 0.0
    initial_luffing_angle: float = 10.0
    slew_speed: float = 0.0


# ============================================================
# 엔진 접근 헬퍼
# ============================================================
def _get_engine():
    """시뮬레이션 엔진 인스턴스를 가져옵니다."""
    from server.app import get_simulation_engine
    return get_simulation_engine()


# ============================================================
# 크레인 API
# ============================================================

@router.get("/cranes", tags=["크레인"])
async def get_all_cranes() -> Dict[str, Any]:
    """
    모든 크레인의 현재 상태를 조회합니다.

    [응답 예시]
    {
        "cranes": [
            {
                "id": "TC-1",
                "name": "1호기",
                "slew_angle": 45.2,
                "boom_tip": {"x": 42.3, "y": 42.3, "z": 55.5},
                ...
            },
            ...
        ]
    }
    """
    engine = _get_engine()
    cranes = [
        crane.to_dict()
        for crane in engine.collision_engine.cranes.values()
    ]
    return {"cranes": cranes}


@router.get("/cranes/{crane_id}", tags=["크레인"])
async def get_crane(crane_id: str) -> Dict[str, Any]:
    """
    특정 크레인의 상태를 조회합니다.

    Args:
        crane_id: 크레인 ID (예: "TC-1")
    """
    engine = _get_engine()
    crane = engine.collision_engine.get_crane(crane_id)
    if crane is None:
        raise HTTPException(status_code=404, detail=f"크레인 '{crane_id}'을(를) 찾을 수 없습니다")
    return {"crane": crane.to_dict()}


@router.post("/cranes/{crane_id}/control", tags=["크레인"])
async def control_crane(crane_id: str, request: CraneControlRequest) -> Dict[str, Any]:
    """
    크레인의 속도 또는 각도를 변경합니다.

    [요청 예시]
    POST /api/cranes/TC-1/control
    {
        "slew_speed": 0.5    // 시계방향 0.5도/초로 회전
    }

    [요청 예시 2]
    POST /api/cranes/TC-1/control
    {
        "slew_speed": 0.0    // 정지
    }

    Args:
        crane_id: 크레인 ID
        request: 제어 요청 데이터
    """
    engine = _get_engine()
    crane = engine.collision_engine.get_crane(crane_id)
    if crane is None:
        raise HTTPException(status_code=404, detail=f"크레인 '{crane_id}'을(를) 찾을 수 없습니다")

    # 요청된 값만 변경
    if request.slew_speed is not None:
        crane.slew_speed = request.slew_speed

    if request.luffing_speed is not None:
        crane.luffing_speed = request.luffing_speed

    if request.slew_angle is not None:
        crane.slew_angle = request.slew_angle % 360.0

    if request.luffing_angle is not None:
        crane.luffing_angle = max(0.0, min(80.0, request.luffing_angle))

    return {"success": True, "crane": crane.to_dict()}


@router.post("/cranes", tags=["크레인"])
async def add_crane(request: CraneAddRequest) -> Dict[str, Any]:
    """
    새 크레인을 추가합니다.

    [요청 예시]
    POST /api/cranes
    {
        "id": "TC-4",
        "name": "4호기",
        "base_x": 100.0,
        "base_y": 50.0,
        "mast_height": 45.0,
        "boom_length": 50.0
    }
    """
    engine = _get_engine()

    # 이미 같은 ID가 있는지 확인
    if engine.collision_engine.get_crane(request.id):
        raise HTTPException(status_code=400, detail=f"크레인 '{request.id}'이(가) 이미 존재합니다")

    crane = engine.add_crane(request.model_dump())
    return {"success": True, "crane": crane.to_dict()}


@router.delete("/cranes/{crane_id}", tags=["크레인"])
async def remove_crane(crane_id: str) -> Dict[str, Any]:
    """크레인을 제거합니다."""
    engine = _get_engine()
    if not engine.collision_engine.get_crane(crane_id):
        raise HTTPException(status_code=404, detail=f"크레인 '{crane_id}'을(를) 찾을 수 없습니다")

    engine.remove_crane(crane_id)
    return {"success": True, "message": f"크레인 '{crane_id}' 제거됨"}


# ============================================================
# 시스템 상태 API
# ============================================================

@router.get("/status", tags=["시스템"])
async def get_system_status() -> Dict[str, Any]:
    """
    전체 시스템 상태를 조회합니다.

    [응답에 포함되는 정보]
    - 총 크레인 수, 활성 크레인 수
    - 등급별 크레인 쌍 수 (정상/주의/경고/위험)
    - 최고 위험 등급
    - 최근 이벤트 목록
    """
    engine = _get_engine()
    return engine.get_full_state()


@router.get("/collisions", tags=["충돌"])
async def get_collision_results() -> Dict[str, Any]:
    """
    현재 충돌 검사 결과를 조회합니다.

    [응답에 포함되는 정보]
    각 크레인 쌍별:
    - 위험 등급
    - 현재 거리
    - 예상 충돌 시간
    - 작업 반경 중첩 여부
    """
    engine = _get_engine()
    results = engine.collision_engine.last_results
    return {
        "collisions": [r.to_dict() for r in results],
    }


# ============================================================
# 시나리오 API
# ============================================================

@router.get("/scenarios", tags=["시나리오"])
async def list_scenarios() -> Dict[str, Any]:
    """
    사용 가능한 시나리오 목록을 조회합니다.

    [응답 예시]
    {
        "scenarios": [
            {"id": "normal_operation", "name": "정상 운행", "description": "..."},
            {"id": "approaching", "name": "접근 상황", "description": "..."},
            ...
        ]
    }
    """
    return {"scenarios": get_scenario_list()}


@router.post("/scenarios/apply", tags=["시나리오"])
async def apply_scenario_endpoint(request: ScenarioApplyRequest) -> Dict[str, Any]:
    """
    시나리오를 적용합니다.

    [요청 예시]
    POST /api/scenarios/apply
    {
        "scenario_id": "approaching"
    }
    """
    engine = _get_engine()
    success = apply_scenario(engine, request.scenario_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"시나리오 '{request.scenario_id}'을(를) 찾을 수 없습니다"
        )
    return {
        "success": True,
        "message": f"시나리오 '{request.scenario_id}' 적용됨",
        "state": engine.get_full_state(),
    }


# ============================================================
# 시뮬레이션 제어 API
# ============================================================

@router.post("/simulation/speed", tags=["시뮬레이션"])
async def set_simulation_speed(request: SimulationSpeedRequest) -> Dict[str, Any]:
    """
    시뮬레이션 속도를 변경합니다.

    [요청 예시]
    POST /api/simulation/speed
    {
        "speed_multiplier": 2.0    // 2배속
    }
    """
    engine = _get_engine()
    engine.speed_multiplier = max(0.1, min(10.0, request.speed_multiplier))
    return {
        "success": True,
        "speed_multiplier": engine.speed_multiplier,
    }
