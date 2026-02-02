"""
기하학 계산 모듈 테스트
========================

geometry.py의 각 함수가 올바르게 동작하는지 검증합니다.

[테스트 실행 방법]
프로젝트 루트에서:
    python -m pytest tests/ -v

특정 파일만:
    python -m pytest tests/test_geometry.py -v
"""

import math
import sys
import os
import pytest

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.geometry import (
    calculate_boom_tip_position,
    calculate_distance_3d,
    calculate_distance_2d,
    check_working_radius_overlap,
    predict_future_position,
    closest_distance_between_segments,
)


class TestBoomTipPosition:
    """붐대 끝점 좌표 계산 테스트"""

    def test_boom_horizontal_north(self):
        """
        기복각 0도(수평), 선회각 0도(북쪽)일 때
        붐대 끝점이 정북 방향에 위치해야 합니다.
        """
        x, y, z = calculate_boom_tip_position(
            base_x=0, base_y=0,
            mast_height=40, boom_length=60,
            slew_angle_deg=0, luffing_angle_deg=0,
        )
        assert abs(x - 0) < 0.01, f"X 좌표가 0이어야 함 (실제: {x})"
        assert abs(y - 60) < 0.01, f"Y 좌표가 60이어야 함 (실제: {y})"
        assert abs(z - 40) < 0.01, f"Z 좌표가 40이어야 함 (실제: {z})"

    def test_boom_horizontal_east(self):
        """
        선회각 90도(동쪽)일 때
        붐대 끝점이 정동 방향에 위치해야 합니다.
        """
        x, y, z = calculate_boom_tip_position(
            base_x=0, base_y=0,
            mast_height=40, boom_length=60,
            slew_angle_deg=90, luffing_angle_deg=0,
        )
        assert abs(x - 60) < 0.01, f"X 좌표가 60이어야 함 (실제: {x})"
        assert abs(y - 0) < 0.01, f"Y 좌표가 0이어야 함 (실제: {y})"

    def test_boom_with_luffing(self):
        """
        기복각이 있을 때 수평 거리가 줄고 높이가 증가해야 합니다.
        기복각 30도, 붐대 60m일 때:
          수평거리 = 60 × cos(30°) = 60 × 0.866 ≈ 51.96m
          높이증가 = 60 × sin(30°) = 60 × 0.5 = 30m
        """
        x, y, z = calculate_boom_tip_position(
            base_x=0, base_y=0,
            mast_height=40, boom_length=60,
            slew_angle_deg=0, luffing_angle_deg=30,
        )
        expected_y = 60 * math.cos(math.radians(30))
        expected_z = 40 + 60 * math.sin(math.radians(30))
        assert abs(y - expected_y) < 0.01
        assert abs(z - expected_z) < 0.01

    def test_boom_with_base_offset(self):
        """
        기초 위치가 원점이 아닌 경우에도 올바르게 계산되어야 합니다.
        """
        x, y, z = calculate_boom_tip_position(
            base_x=100, base_y=50,
            mast_height=40, boom_length=60,
            slew_angle_deg=0, luffing_angle_deg=0,
        )
        assert abs(x - 100) < 0.01
        assert abs(y - 110) < 0.01  # 50 + 60


class TestDistance:
    """거리 계산 테스트"""

    def test_distance_3d_simple(self):
        """기본 3D 거리 계산: (0,0,0)과 (3,4,0) 사이 = 5m"""
        d = calculate_distance_3d((0, 0, 0), (3, 4, 0))
        assert abs(d - 5.0) < 0.01

    def test_distance_3d_same_point(self):
        """같은 점 사이의 거리는 0"""
        d = calculate_distance_3d((10, 20, 30), (10, 20, 30))
        assert abs(d) < 0.001

    def test_distance_3d_with_height(self):
        """높이 차이를 포함한 3D 거리"""
        d = calculate_distance_3d((0, 0, 0), (0, 0, 10))
        assert abs(d - 10.0) < 0.01

    def test_distance_2d(self):
        """2D 거리 계산"""
        d = calculate_distance_2d(0, 0, 3, 4)
        assert abs(d - 5.0) < 0.01


class TestWorkingRadiusOverlap:
    """작업 반경 중첩 테스트"""

    def test_no_overlap(self):
        """두 크레인이 충분히 떨어져 있으면 중첩 없음"""
        overlap = check_working_radius_overlap(
            0, 0, 50,      # 크레인A: (0,0), 반경 50m
            200, 0, 50,    # 크레인B: (200,0), 반경 50m
        )
        assert overlap is False  # 거리 200m > 50+50=100m

    def test_overlap_exists(self):
        """두 크레인의 반경이 겹치는 경우"""
        overlap = check_working_radius_overlap(
            0, 0, 60,      # 크레인A: (0,0), 반경 60m
            80, 0, 60,     # 크레인B: (80,0), 반경 60m
        )
        assert overlap is True  # 거리 80m < 60+60=120m

    def test_touching_boundary(self):
        """정확히 반경 합과 거리가 같으면 중첩 없음 (strict less than)"""
        overlap = check_working_radius_overlap(
            0, 0, 50,
            100, 0, 50,
        )
        assert overlap is False  # 거리 100m = 50+50


class TestFuturePosition:
    """미래 위치 예측 테스트"""

    def test_stationary(self):
        """속도가 0이면 위치가 변하지 않아야 합니다."""
        current = calculate_boom_tip_position(0, 0, 40, 60, 45, 10)
        future = predict_future_position(0, 0, 40, 60, 45, 10, 0, 0, 10)
        assert abs(current[0] - future[0]) < 0.01
        assert abs(current[1] - future[1]) < 0.01
        assert abs(current[2] - future[2]) < 0.01

    def test_slew_rotation(self):
        """선회 속도가 있으면 미래 선회각이 변해야 합니다."""
        # 선회각 0도, 속도 10도/초, 9초 후 → 선회각 90도
        future = predict_future_position(0, 0, 40, 60, 0, 0, 10, 0, 9)
        expected = calculate_boom_tip_position(0, 0, 40, 60, 90, 0)
        assert abs(future[0] - expected[0]) < 0.01
        assert abs(future[1] - expected[1]) < 0.01

    def test_luffing_limit(self):
        """기복각이 80도를 초과하지 않아야 합니다."""
        future = predict_future_position(0, 0, 40, 60, 0, 70, 0, 5, 100)
        # 70 + 5*100 = 570도이지만 80도로 제한되어야 함
        expected = calculate_boom_tip_position(0, 0, 40, 60, 0, 80)
        assert abs(future[2] - expected[2]) < 0.01


class TestSegmentDistance:
    """선분 간 최소 거리 테스트"""

    def test_parallel_segments(self):
        """평행한 두 선분 사이의 거리"""
        d = closest_distance_between_segments(
            (0, 0, 0), (10, 0, 0),  # X축 위의 선분
            (0, 5, 0), (10, 5, 0),  # Y=5 위의 평행 선분
        )
        assert abs(d - 5.0) < 0.01

    def test_perpendicular_segments(self):
        """수직으로 교차하는 두 선분 (높이 차이 있음)"""
        d = closest_distance_between_segments(
            (0, 0, 0), (10, 0, 0),   # X축 위
            (5, 0, 3), (5, 10, 3),   # Y축 방향, 높이 3m
        )
        assert abs(d - 3.0) < 0.01  # 교차점에서의 높이 차이

    def test_same_segment(self):
        """같은 선분이면 거리 0"""
        d = closest_distance_between_segments(
            (0, 0, 0), (10, 0, 0),
            (0, 0, 0), (10, 0, 0),
        )
        assert abs(d) < 0.01

    def test_point_segments(self):
        """두 점(길이 0 선분) 사이의 거리"""
        d = closest_distance_between_segments(
            (0, 0, 0), (0, 0, 0),
            (3, 4, 0), (3, 4, 0),
        )
        assert abs(d - 5.0) < 0.01
