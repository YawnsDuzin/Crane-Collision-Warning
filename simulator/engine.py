"""
시뮬레이션 엔진
================

실제 크레인 없이 가상의 크레인을 만들어 충돌 예측 시스템을 테스트합니다.

[왜 시뮬레이션이 필요한가?]
- 실제 크레인으로 테스트하면 위험하고 비용이 많이 듭니다
- 시뮬레이션으로 다양한 상황(충돌, 근접, 정상 등)을 안전하게 재현
- 소프트웨어 로직의 정확성을 먼저 검증
- 현장 투입 전 충분한 테스트 가능

[동작 원리]
1. 가상 크레인 생성 (위치, 크기, 초기 각도 설정)
2. 매 시간 단위(tick)마다:
   a) 각 크레인의 위치를 속도에 따라 갱신
   b) 충돌 검사 수행
   c) 결과를 저장하고 WebSocket으로 브라우저에 전송
3. 사용자가 웹 화면에서 크레인 속도를 조절하며 테스트

[시뮬레이션 vs 실제]
시뮬레이션 모드: engine.py가 가상 데이터 생성
실제 모드: 센서에서 실제 데이터 수신 (나중에 구현)
→ 충돌 예측 엔진(collision.py)은 동일하게 동작!
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Callable

from core.crane import TowerCrane
from core.collision import CollisionEngine, CollisionCheckResult
from core.alert import AlertManager, AlertMessage
from config.settings import DEFAULT_CRANES, SIMULATION_INTERVAL_MS


class SimulationEngine:
    """
    시뮬레이션 엔진 - 가상 크레인을 생성하고 움직이며 충돌을 검사

    [사용 예시]
    engine = SimulationEngine()
    engine.setup_default_cranes()  # 기본 크레인 3대 생성

    # 시뮬레이션 실행 (비동기)
    await engine.start()

    # 크레인 속도 변경 (사용자 입력)
    engine.set_crane_slew_speed("TC-1", 0.5)  # TC-1을 시계방향 0.5도/초로 회전
    """

    def __init__(self):
        # 충돌 예측 엔진
        self.collision_engine = CollisionEngine()

        # 경보 관리자
        self.alert_manager = AlertManager()

        # 시뮬레이션 상태
        self.is_running = False
        self.tick_count = 0        # 시뮬레이션 진행 횟수
        self.last_tick_time = 0.0  # 마지막 tick 시각

        # 시뮬레이션 속도 배율 (1.0 = 실시간, 2.0 = 2배속)
        self.speed_multiplier = 1.0

        # 데이터 변경 시 호출될 콜백 함수
        # (WebSocket으로 브라우저에 데이터를 보내는 함수가 여기 등록됨)
        self._on_update_callback: Optional[Callable] = None

        # 시나리오 관련
        self._active_scenario: Optional[str] = None

    def setup_default_cranes(self) -> None:
        """
        config/settings.py에 정의된 기본 크레인들을 생성합니다.

        [동작]
        DEFAULT_CRANES 리스트를 읽어서 TowerCrane 객체를 만들고
        충돌 엔진에 등록합니다.
        """
        for crane_config in DEFAULT_CRANES:
            crane = TowerCrane.from_config(crane_config)
            self.collision_engine.register_crane(crane)

        # 경보 관리자에 크레인 이름 등록
        names = {
            crane.id: crane.name
            for crane in self.collision_engine.cranes.values()
        }
        self.alert_manager.set_crane_names(names)

    def add_crane(self, config: Dict[str, Any]) -> TowerCrane:
        """
        크레인을 동적으로 추가합니다.

        Args:
            config: 크레인 설정 딕셔너리

        Returns:
            생성된 TowerCrane 객체
        """
        crane = TowerCrane.from_config(config)
        self.collision_engine.register_crane(crane)

        # 이름 갱신
        self.alert_manager.crane_names[crane.id] = crane.name
        return crane

    def remove_crane(self, crane_id: str) -> None:
        """크레인을 제거합니다."""
        self.collision_engine.unregister_crane(crane_id)
        self.alert_manager.crane_names.pop(crane_id, None)

    def set_crane_slew_speed(self, crane_id: str, speed: float) -> bool:
        """
        크레인의 선회 속도를 설정합니다.

        [사용 예시]
        # TC-1을 시계방향으로 0.5도/초 회전
        engine.set_crane_slew_speed("TC-1", 0.5)

        # TC-1을 반시계방향으로 1.0도/초 회전
        engine.set_crane_slew_speed("TC-1", -1.0)

        # TC-1 정지
        engine.set_crane_slew_speed("TC-1", 0.0)

        Args:
            crane_id: 크레인 ID
            speed: 선회 속도 (도/초, 양수=시계방향)

        Returns:
            성공 여부
        """
        crane = self.collision_engine.get_crane(crane_id)
        if crane is None:
            return False
        crane.slew_speed = speed
        return True

    def set_crane_luffing_speed(self, crane_id: str, speed: float) -> bool:
        """
        크레인의 기복 속도를 설정합니다.

        Args:
            crane_id: 크레인 ID
            speed: 기복 속도 (도/초, 양수=올림)

        Returns:
            성공 여부
        """
        crane = self.collision_engine.get_crane(crane_id)
        if crane is None:
            return False
        crane.luffing_speed = speed
        return True

    def set_crane_slew_angle(self, crane_id: str, angle: float) -> bool:
        """
        크레인의 선회각을 직접 설정합니다.

        Args:
            crane_id: 크레인 ID
            angle: 선회각 (도)

        Returns:
            성공 여부
        """
        crane = self.collision_engine.get_crane(crane_id)
        if crane is None:
            return False
        crane.slew_angle = angle % 360.0
        return True

    def set_crane_luffing_angle(self, crane_id: str, angle: float) -> bool:
        """
        크레인의 기복각을 직접 설정합니다.

        Args:
            crane_id: 크레인 ID
            angle: 기복각 (도, 0~80)

        Returns:
            성공 여부
        """
        crane = self.collision_engine.get_crane(crane_id)
        if crane is None:
            return False
        crane.luffing_angle = max(0.0, min(80.0, angle))
        return True

    def set_on_update(self, callback: Callable) -> None:
        """
        데이터가 갱신될 때마다 호출될 콜백 함수를 등록합니다.

        [용도]
        WebSocket 핸들러에서 이 콜백을 등록하면,
        시뮬레이션이 갱신될 때마다 자동으로 브라우저에 데이터가 전송됩니다.

        Args:
            callback: 호출될 함수 (state_dict를 인자로 받음)
        """
        self._on_update_callback = callback

    async def start(self) -> None:
        """
        시뮬레이션을 시작합니다 (비동기 루프).

        [동작 흐름]
        while 실행중:
            1. 시간 경과 계산
            2. 각 크레인 위치 갱신
            3. 충돌 검사 수행
            4. 경고 메시지 생성
            5. 콜백 호출 (브라우저에 데이터 전송)
            6. 다음 tick까지 대기
        """
        self.is_running = True
        self.last_tick_time = time.time()

        interval = SIMULATION_INTERVAL_MS / 1000.0  # 밀리초 → 초

        while self.is_running:
            current_time = time.time()
            dt = (current_time - self.last_tick_time) * self.speed_multiplier
            self.last_tick_time = current_time

            # 1. 각 크레인 위치 갱신
            for crane in self.collision_engine.cranes.values():
                crane.update_position(dt)

            # 2. 충돌 검사
            collision_results = self.collision_engine.check_all_collisions()

            # 3. 경고 메시지 생성
            alerts = self.alert_manager.process_results(collision_results)

            # 4. 콜백 호출 (데이터 전송)
            if self._on_update_callback:
                state = self.get_full_state(collision_results, alerts)
                try:
                    await self._on_update_callback(state)
                except Exception:
                    pass  # 콜백 오류는 무시 (연결 끊김 등)

            self.tick_count += 1

            # 5. 다음 tick까지 대기
            await asyncio.sleep(interval)

    def stop(self) -> None:
        """시뮬레이션을 정지합니다."""
        self.is_running = False

    def tick_once(self, dt: float = 0.1) -> Dict[str, Any]:
        """
        시뮬레이션을 한 번만 실행합니다 (테스트용).

        Args:
            dt: 경과 시간 (초)

        Returns:
            현재 전체 상태 딕셔너리
        """
        # 크레인 위치 갱신
        for crane in self.collision_engine.cranes.values():
            crane.update_position(dt)

        # 충돌 검사
        collision_results = self.collision_engine.check_all_collisions()

        # 경고 생성
        alerts = self.alert_manager.process_results(collision_results)

        self.tick_count += 1
        return self.get_full_state(collision_results, alerts)

    def get_full_state(
        self,
        collision_results: Optional[List[CollisionCheckResult]] = None,
        alerts: Optional[List[AlertMessage]] = None,
    ) -> Dict[str, Any]:
        """
        시스템 전체 상태를 딕셔너리로 반환합니다.
        이 데이터가 WebSocket을 통해 브라우저로 전송됩니다.

        [반환 데이터 구조]
        {
            "cranes": [ {크레인1 상태}, {크레인2 상태}, ... ],
            "collisions": [ {충돌검사 결과1}, {결과2}, ... ],
            "alerts": [ {경고 메시지1}, {메시지2}, ... ],
            "status": { 전체 현황 요약 },
            "simulation": { 시뮬레이션 정보 },
        }
        """
        # 충돌 결과가 없으면 새로 계산
        if collision_results is None:
            collision_results = self.collision_engine.check_all_collisions()
        if alerts is None:
            alerts = self.alert_manager.process_results(collision_results)

        return {
            # 각 크레인의 현재 상태
            "cranes": [
                crane.to_dict()
                for crane in self.collision_engine.cranes.values()
            ],
            # 크레인 쌍별 충돌 검사 결과
            "collisions": [r.to_dict() for r in collision_results],
            # 활성 경고 메시지 목록
            "alerts": [a.to_dict() for a in alerts],
            # 전체 현황 요약
            "status": self.collision_engine.get_overall_status(),
            # 시뮬레이션 메타 정보
            "simulation": {
                "is_running": self.is_running,
                "tick_count": self.tick_count,
                "speed_multiplier": self.speed_multiplier,
                "active_scenario": self._active_scenario,
            },
        }

    def get_cranes_dict(self) -> Dict[str, Dict[str, Any]]:
        """등록된 모든 크레인의 상태를 딕셔너리로 반환합니다."""
        return {
            crane_id: crane.to_dict()
            for crane_id, crane in self.collision_engine.cranes.items()
        }
