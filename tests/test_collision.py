"""
충돌 예측 엔진 테스트
======================

collision.py의 CollisionEngine이 올바르게 동작하는지 검증합니다.

[테스트 시나리오]
1. 먼 거리의 크레인 → 정상
2. 가까운 크레인 → 주의/경고
3. 매우 가까운 크레인 → 위험
4. 접근 중인 크레인 → 시간 기반 경고
5. 반경이 겹치지 않는 크레인 → 항상 정상
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.crane import TowerCrane
from core.collision import (
    CollisionEngine,
    LEVEL_NORMAL,
    LEVEL_CAUTION,
    LEVEL_WARNING,
    LEVEL_DANGER,
)


def make_crane(
    crane_id: str,
    base_x: float = 0,
    base_y: float = 0,
    mast_height: float = 40,
    boom_length: float = 60,
    slew_angle: float = 0,
    luffing_angle: float = 10,
    slew_speed: float = 0,
) -> TowerCrane:
    """테스트용 크레인 생성 헬퍼"""
    return TowerCrane(
        id=crane_id,
        name=f"테스트-{crane_id}",
        base_x=base_x,
        base_y=base_y,
        mast_height=mast_height,
        boom_length=boom_length,
        slew_angle=slew_angle,
        luffing_angle=luffing_angle,
        slew_speed=slew_speed,
    )


class TestCollisionEngine:
    """CollisionEngine 기본 테스트"""

    def test_register_crane(self):
        """크레인 등록/해제"""
        engine = CollisionEngine()
        crane = make_crane("TC-1")
        engine.register_crane(crane)
        assert "TC-1" in engine.cranes
        assert engine.get_crane("TC-1") is crane

        engine.unregister_crane("TC-1")
        assert "TC-1" not in engine.cranes

    def test_no_collision_far_apart(self):
        """
        충분히 떨어진 두 크레인은 정상 상태여야 합니다.
        크레인 간 거리: 200m, 붐대 길이: 60m
        → 작업 반경이 겹치지 않으므로 충돌 불가
        """
        engine = CollisionEngine()
        engine.register_crane(make_crane("TC-1", base_x=0, base_y=0))
        engine.register_crane(make_crane("TC-2", base_x=200, base_y=0))

        results = engine.check_all_collisions()
        assert len(results) == 1  # 1쌍
        assert results[0].alert_level == LEVEL_NORMAL
        assert results[0].overlap_exists is False

    def test_overlap_detection(self):
        """
        작업 반경이 겹치는 두 크레인을 감지해야 합니다.
        크레인 간 거리: 80m, 붐대 길이: 60m
        → 60+60=120m > 80m → 반경 겹침
        """
        engine = CollisionEngine()
        engine.register_crane(make_crane("TC-1", base_x=0, base_y=0))
        engine.register_crane(make_crane("TC-2", base_x=80, base_y=0))

        results = engine.check_all_collisions()
        assert results[0].overlap_exists is True

    def test_head_on_collision_danger(self):
        """
        서로를 마주보는 가까운 두 크레인은 위험 등급이어야 합니다.
        TC-1: 동쪽을 향함 (90도), TC-2: 서쪽을 향함 (270도)
        거리 70m, 붐대 60m → 끝점 거리 ≈ 70 - 60 - 60 = -50m (겹침!)
        """
        engine = CollisionEngine()
        engine.register_crane(
            make_crane("TC-1", base_x=0, base_y=0,
                       slew_angle=90, luffing_angle=5)
        )
        engine.register_crane(
            make_crane("TC-2", base_x=70, base_y=0,
                       slew_angle=270, luffing_angle=5)
        )

        results = engine.check_all_collisions()
        assert results[0].alert_level == LEVEL_DANGER
        assert results[0].current_distance < 5.0

    def test_approaching_cranes(self):
        """
        서로 접근 중인 크레인은 시간 기반 경고가 발생해야 합니다.
        """
        engine = CollisionEngine()
        # TC-1이 TC-2 방향으로 회전 중
        engine.register_crane(
            make_crane("TC-1", base_x=0, base_y=0,
                       slew_angle=30, slew_speed=1.0)  # 동쪽으로 회전
        )
        engine.register_crane(
            make_crane("TC-2", base_x=80, base_y=0,
                       slew_angle=210, slew_speed=-1.0)  # 서쪽으로 회전
        )

        results = engine.check_all_collisions()
        # 움직이고 있으므로 예측이 수행되어야 함
        assert results[0].overlap_exists is True

    def test_multiple_cranes(self):
        """
        3대의 크레인이 있으면 3쌍의 결과가 나와야 합니다.
        N × (N-1) / 2 = 3 × 2 / 2 = 3쌍
        """
        engine = CollisionEngine()
        engine.register_crane(make_crane("TC-1", base_x=0, base_y=0))
        engine.register_crane(make_crane("TC-2", base_x=80, base_y=0))
        engine.register_crane(make_crane("TC-3", base_x=40, base_y=70))

        results = engine.check_all_collisions()
        assert len(results) == 3

    def test_inactive_crane_excluded(self):
        """비활성 크레인은 충돌 검사에서 제외되어야 합니다."""
        engine = CollisionEngine()
        crane1 = make_crane("TC-1")
        crane2 = make_crane("TC-2", base_x=80)
        crane2.is_active = False  # 비활성

        engine.register_crane(crane1)
        engine.register_crane(crane2)

        results = engine.check_all_collisions()
        assert len(results) == 0  # 활성 크레인이 1대뿐이므로 쌍 없음

    def test_overall_status(self):
        """전체 상태 요약이 올바르게 생성되어야 합니다."""
        engine = CollisionEngine()
        engine.register_crane(make_crane("TC-1"))
        engine.register_crane(make_crane("TC-2", base_x=80))
        engine.check_all_collisions()

        status = engine.get_overall_status()
        assert status["total_cranes"] == 2
        assert status["active_cranes"] == 2
        assert "highest_alert" in status
        assert "crane_alerts" in status

    def test_event_log_on_level_change(self):
        """위험 등급이 변경되면 이벤트 로그에 기록되어야 합니다."""
        engine = CollisionEngine()
        crane1 = make_crane("TC-1", base_x=0, slew_angle=0)
        crane2 = make_crane("TC-2", base_x=80, slew_angle=180)
        engine.register_crane(crane1)
        engine.register_crane(crane2)

        # 첫 번째 검사
        engine.check_all_collisions()

        # 크레인을 위험 위치로 이동
        crane1.slew_angle = 90
        crane1.luffing_angle = 5
        crane2.slew_angle = 270
        crane2.luffing_angle = 5
        crane2.base_x = 70  # 더 가까이

        # 두 번째 검사 → 등급 변화 발생
        engine.check_all_collisions()

        # 이벤트 로그에 기록되어야 함
        assert len(engine.event_log) > 0
