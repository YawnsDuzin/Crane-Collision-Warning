"""
시뮬레이션 시나리오 모듈
=========================

미리 정의된 시나리오를 통해 다양한 상황을 재현할 수 있습니다.

[시나리오 목록]

1. normal_operation (정상 운행)
   - 모든 크레인이 안전한 범위에서 작업
   - 충돌 경고 없음

2. approaching (접근 상황)
   - 두 크레인이 서로 접근하는 상황
   - 주의 → 경고 → 위험 순서로 등급 상승

3. head_on_collision (정면 충돌 코스)
   - 두 크레인이 서로를 향해 직진하는 최악의 시나리오
   - 즉시 위험 경고 발생

4. crossing_paths (교차 통과)
   - 두 크레인의 붐대가 같은 영역을 지나가는 상황
   - 타이밍에 따라 위험도가 변함

5. multi_crane_congestion (다중 크레인 혼잡)
   - 3대 이상의 크레인이 좁은 구역에서 동시 작업
   - 복수의 경고가 동시 발생

[사용 방법]
engine = SimulationEngine()
apply_scenario(engine, "approaching")
"""

from typing import Dict, Any, List
from simulator.engine import SimulationEngine


# ============================================================
# 시나리오 정의
# ============================================================

SCENARIOS: Dict[str, Dict[str, Any]] = {
    # ────────────────────────────────────────
    # 시나리오 1: 정상 운행
    # ────────────────────────────────────────
    "normal_operation": {
        "name": "정상 운행",
        "description": (
            "3대의 크레인이 각자의 작업 영역에서 안전하게 운행합니다. "
            "충돌 위험이 없는 상태입니다."
        ),
        "cranes": [
            {
                "id": "TC-1", "name": "1호기",
                "base_x": 0.0, "base_y": 0.0,
                "mast_height": 40.0, "boom_length": 60.0,
                "initial_slew_angle": 45.0,
                "initial_luffing_angle": 15.0,
                "slew_speed": 0.3,  # 천천히 시계방향 회전
            },
            {
                "id": "TC-2", "name": "2호기",
                "base_x": 150.0, "base_y": 0.0,
                "mast_height": 45.0, "boom_length": 55.0,
                "initial_slew_angle": 200.0,
                "initial_luffing_angle": 10.0,
                "slew_speed": -0.2,  # 천천히 반시계방향 회전
            },
            {
                "id": "TC-3", "name": "3호기",
                "base_x": 75.0, "base_y": 130.0,
                "mast_height": 42.0, "boom_length": 50.0,
                "initial_slew_angle": 270.0,
                "initial_luffing_angle": 12.0,
                "slew_speed": 0.0,  # 정지 상태
            },
        ],
    },

    # ────────────────────────────────────────
    # 시나리오 2: 접근 상황
    # ────────────────────────────────────────
    "approaching": {
        "name": "접근 상황",
        "description": (
            "TC-1과 TC-2가 서로 가까이 설치되어 있고, "
            "붐대가 서로를 향해 회전하고 있습니다. "
            "시간이 지남에 따라 위험 등급이 상승합니다."
        ),
        "cranes": [
            {
                "id": "TC-1", "name": "1호기",
                "base_x": 0.0, "base_y": 0.0,
                "mast_height": 40.0, "boom_length": 60.0,
                "initial_slew_angle": 30.0,    # 동쪽을 향하는 중
                "initial_luffing_angle": 10.0,
                "slew_speed": 0.5,  # TC-2 방향으로 회전 중
            },
            {
                "id": "TC-2", "name": "2호기",
                "base_x": 80.0, "base_y": 0.0,  # TC-1에서 80m 거리
                "mast_height": 45.0, "boom_length": 55.0,
                "initial_slew_angle": 210.0,   # 서쪽을 향하는 중
                "initial_luffing_angle": 10.0,
                "slew_speed": -0.5,  # TC-1 방향으로 회전 중
            },
        ],
    },

    # ────────────────────────────────────────
    # 시나리오 3: 정면 충돌 코스
    # ────────────────────────────────────────
    "head_on_collision": {
        "name": "정면 충돌 코스",
        "description": (
            "두 크레인의 붐대가 서로를 정면으로 가리키고 있으며, "
            "작업 반경이 크게 겹쳐 있습니다. "
            "즉시 위험 경고가 발생해야 하는 상황입니다."
        ),
        "cranes": [
            {
                "id": "TC-1", "name": "1호기",
                "base_x": 0.0, "base_y": 0.0,
                "mast_height": 40.0, "boom_length": 60.0,
                "initial_slew_angle": 90.0,    # 정동쪽 (TC-2 방향)
                "initial_luffing_angle": 5.0,  # 거의 수평
                "slew_speed": 0.0,
            },
            {
                "id": "TC-2", "name": "2호기",
                "base_x": 70.0, "base_y": 0.0,  # 70m 거리 (붐대가 겹침!)
                "mast_height": 40.0, "boom_length": 60.0,
                "initial_slew_angle": 270.0,   # 정서쪽 (TC-1 방향)
                "initial_luffing_angle": 5.0,
                "slew_speed": 0.0,
            },
        ],
    },

    # ────────────────────────────────────────
    # 시나리오 4: 교차 통과
    # ────────────────────────────────────────
    "crossing_paths": {
        "name": "교차 통과",
        "description": (
            "두 크레인의 붐대가 같은 영역을 지나가면서 교차합니다. "
            "타이밍에 따라 충돌 위험이 달라집니다."
        ),
        "cranes": [
            {
                "id": "TC-1", "name": "1호기",
                "base_x": 0.0, "base_y": 0.0,
                "mast_height": 40.0, "boom_length": 55.0,
                "initial_slew_angle": 0.0,     # 북쪽에서 시작
                "initial_luffing_angle": 10.0,
                "slew_speed": 0.8,  # 빠르게 시계방향 회전
            },
            {
                "id": "TC-2", "name": "2호기",
                "base_x": 60.0, "base_y": 60.0,
                "mast_height": 42.0, "boom_length": 50.0,
                "initial_slew_angle": 180.0,   # 남쪽에서 시작
                "initial_luffing_angle": 10.0,
                "slew_speed": -0.8,  # 빠르게 반시계방향 회전
            },
        ],
    },

    # ────────────────────────────────────────
    # 시나리오 5: 다중 크레인 혼잡
    # ────────────────────────────────────────
    "multi_crane_congestion": {
        "name": "다중 크레인 혼잡",
        "description": (
            "4대의 크레인이 비교적 좁은 구역에 배치되어 있고, "
            "여러 쌍에서 동시에 경고가 발생합니다."
        ),
        "cranes": [
            {
                "id": "TC-1", "name": "1호기",
                "base_x": 0.0, "base_y": 0.0,
                "mast_height": 40.0, "boom_length": 55.0,
                "initial_slew_angle": 60.0,
                "initial_luffing_angle": 12.0,
                "slew_speed": 0.4,
            },
            {
                "id": "TC-2", "name": "2호기",
                "base_x": 70.0, "base_y": 0.0,
                "mast_height": 42.0, "boom_length": 50.0,
                "initial_slew_angle": 180.0,
                "initial_luffing_angle": 10.0,
                "slew_speed": -0.3,
            },
            {
                "id": "TC-3", "name": "3호기",
                "base_x": 70.0, "base_y": 60.0,
                "mast_height": 38.0, "boom_length": 52.0,
                "initial_slew_angle": 240.0,
                "initial_luffing_angle": 15.0,
                "slew_speed": 0.5,
            },
            {
                "id": "TC-4", "name": "4호기",
                "base_x": 0.0, "base_y": 60.0,
                "mast_height": 44.0, "boom_length": 48.0,
                "initial_slew_angle": 330.0,
                "initial_luffing_angle": 8.0,
                "slew_speed": -0.4,
            },
        ],
    },
}


def apply_scenario(engine: SimulationEngine, scenario_name: str) -> bool:
    """
    시나리오를 시뮬레이션 엔진에 적용합니다.

    [동작]
    1. 기존 크레인을 모두 제거
    2. 시나리오에 정의된 크레인을 생성
    3. 시뮬레이션 엔진에 등록

    Args:
        engine: SimulationEngine 인스턴스
        scenario_name: 시나리오 이름 (SCENARIOS 딕셔너리의 키)

    Returns:
        성공 여부
    """
    if scenario_name not in SCENARIOS:
        return False

    scenario = SCENARIOS[scenario_name]

    # 기존 크레인 모두 제거
    crane_ids = list(engine.collision_engine.cranes.keys())
    for crane_id in crane_ids:
        engine.remove_crane(crane_id)

    # 새 크레인 추가
    for crane_config in scenario["cranes"]:
        engine.add_crane(crane_config)

    # 시나리오 이름 기록
    engine._active_scenario = scenario_name
    engine.tick_count = 0

    return True


def get_scenario_list() -> List[Dict[str, str]]:
    """
    사용 가능한 시나리오 목록을 반환합니다.

    Returns:
        [{"id": "normal_operation", "name": "정상 운행", "description": "..."}, ...]
    """
    return [
        {
            "id": scenario_id,
            "name": scenario_data["name"],
            "description": scenario_data["description"],
        }
        for scenario_id, scenario_data in SCENARIOS.items()
    ]
