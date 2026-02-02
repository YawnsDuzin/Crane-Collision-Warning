"""
시뮬레이션 엔진 테스트
========================

시뮬레이션 엔진과 시나리오의 동작을 검증합니다.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.crane import TowerCrane
from simulator.engine import SimulationEngine
from simulator.scenarios import apply_scenario, get_scenario_list, SCENARIOS


class TestSimulationEngine:
    """SimulationEngine 기본 테스트"""

    def test_setup_default_cranes(self):
        """기본 크레인 설정이 올바르게 로드되어야 합니다."""
        engine = SimulationEngine()
        engine.setup_default_cranes()

        cranes = engine.collision_engine.cranes
        assert len(cranes) > 0
        assert "TC-1" in cranes
        assert "TC-2" in cranes

    def test_add_and_remove_crane(self):
        """크레인 추가 및 제거"""
        engine = SimulationEngine()

        config = {
            "id": "TC-99",
            "name": "테스트기",
            "base_x": 100,
            "base_y": 100,
            "mast_height": 40,
            "boom_length": 50,
        }

        crane = engine.add_crane(config)
        assert crane.id == "TC-99"
        assert "TC-99" in engine.collision_engine.cranes

        engine.remove_crane("TC-99")
        assert "TC-99" not in engine.collision_engine.cranes

    def test_set_crane_speed(self):
        """크레인 속도 설정"""
        engine = SimulationEngine()
        engine.setup_default_cranes()

        assert engine.set_crane_slew_speed("TC-1", 1.5) is True
        assert engine.collision_engine.cranes["TC-1"].slew_speed == 1.5

        assert engine.set_crane_slew_speed("INVALID", 1.0) is False

    def test_tick_once(self):
        """시뮬레이션 한 틱 실행"""
        engine = SimulationEngine()
        engine.setup_default_cranes()

        # TC-1에 속도 부여
        engine.set_crane_slew_speed("TC-1", 1.0)
        initial_angle = engine.collision_engine.cranes["TC-1"].slew_angle

        # 1초 경과 시뮬레이션
        state = engine.tick_once(dt=1.0)

        new_angle = engine.collision_engine.cranes["TC-1"].slew_angle
        assert abs(new_angle - initial_angle - 1.0) < 0.01

        # 반환 데이터 구조 검증
        assert "cranes" in state
        assert "collisions" in state
        assert "alerts" in state
        assert "status" in state
        assert "simulation" in state

    def test_full_state_structure(self):
        """get_full_state 반환 데이터 구조 검증"""
        engine = SimulationEngine()
        engine.setup_default_cranes()
        state = engine.get_full_state()

        # 크레인 데이터
        assert len(state["cranes"]) > 0
        crane = state["cranes"][0]
        assert "id" in crane
        assert "boom_tip" in crane
        assert "working_radius" in crane

        # 상태 요약
        assert "total_cranes" in state["status"]
        assert "crane_alerts" in state["status"]


class TestScenarios:
    """시나리오 테스트"""

    def test_scenario_list(self):
        """시나리오 목록이 비어있지 않아야 합니다."""
        scenarios = get_scenario_list()
        assert len(scenarios) > 0
        assert all("id" in s for s in scenarios)
        assert all("name" in s for s in scenarios)

    def test_apply_normal_operation(self):
        """정상 운행 시나리오 적용"""
        engine = SimulationEngine()
        success = apply_scenario(engine, "normal_operation")
        assert success is True
        assert len(engine.collision_engine.cranes) == 3

    def test_apply_approaching(self):
        """접근 상황 시나리오 적용"""
        engine = SimulationEngine()
        success = apply_scenario(engine, "approaching")
        assert success is True
        assert len(engine.collision_engine.cranes) == 2

    def test_apply_head_on(self):
        """정면 충돌 시나리오 적용 후 즉시 위험 감지"""
        engine = SimulationEngine()
        apply_scenario(engine, "head_on_collision")

        state = engine.tick_once(dt=0)
        collisions = state["collisions"]
        assert len(collisions) == 1

        # 정면 충돌 코스이므로 높은 위험도
        assert collisions[0]["alert_level"] in ["WARNING", "DANGER"]

    def test_apply_multi_crane(self):
        """다중 크레인 시나리오"""
        engine = SimulationEngine()
        apply_scenario(engine, "multi_crane_congestion")
        assert len(engine.collision_engine.cranes) == 4

        # 4대 → 6쌍
        state = engine.tick_once(dt=0)
        assert len(state["collisions"]) == 6

    def test_apply_invalid_scenario(self):
        """존재하지 않는 시나리오는 실패해야 합니다."""
        engine = SimulationEngine()
        success = apply_scenario(engine, "nonexistent")
        assert success is False

    def test_scenario_replaces_cranes(self):
        """시나리오 적용 시 기존 크레인이 제거되어야 합니다."""
        engine = SimulationEngine()
        engine.setup_default_cranes()
        initial_count = len(engine.collision_engine.cranes)

        apply_scenario(engine, "head_on_collision")  # 2대 시나리오
        assert len(engine.collision_engine.cranes) == 2

    def test_all_scenarios_valid(self):
        """모든 시나리오가 유효한 크레인 데이터를 포함해야 합니다."""
        for scenario_id, scenario_data in SCENARIOS.items():
            assert "name" in scenario_data
            assert "description" in scenario_data
            assert "cranes" in scenario_data
            assert len(scenario_data["cranes"]) >= 2

            for crane_config in scenario_data["cranes"]:
                assert "id" in crane_config
                assert "name" in crane_config
                assert "base_x" in crane_config
                assert "base_y" in crane_config
