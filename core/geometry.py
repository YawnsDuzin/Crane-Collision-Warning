"""
3D 기하학 계산 모듈
====================

이 모듈은 크레인의 위치를 3차원 좌표로 계산하는 함수들을 모아놓은 곳입니다.

[핵심 개념 - 왜 3D 좌표가 필요한가?]

크레인의 붐대(팔)는 3차원 공간에서 움직입니다.
- 좌우로 회전 (선회, slew) → 수평 위치가 변함
- 위아래로 올리고 내림 (기복, luffing) → 높이가 변함
- 붐대의 길이 → 도달 거리가 정해짐

이 세 가지 정보를 조합하면, 붐대 끝점이 3D 공간의 어디에 있는지
정확히 계산할 수 있습니다.

[좌표 체계]
- X축: 동쪽 방향 (오른쪽)
- Y축: 북쪽 방향 (위쪽)
- Z축: 하늘 방향 (높이)
- 원점(0,0,0): 현장 기준점
"""

import math
from typing import Tuple

# ============================================================
# 타입 정의
# ============================================================
# 3D 좌표를 나타내는 타입 (x, y, z)
Point3D = Tuple[float, float, float]


def calculate_boom_tip_position(
    base_x: float,
    base_y: float,
    mast_height: float,
    boom_length: float,
    slew_angle_deg: float,
    luffing_angle_deg: float,
) -> Point3D:
    """
    크레인 붐대 끝점의 3D 좌표를 계산합니다.

    [원리 설명]
    타워크레인을 옆에서 보면 이런 모양입니다:

                    붐대 끝점 (이것을 계산!)
                       ●
                      ╱
                     ╱  붐대 길이 (boom_length)
                    ╱
                   ╱ ← 기복각 (luffing_angle)
                  ╱
        마스트 꼭대기 ●
                  │
                  │  마스트 높이 (mast_height)
                  │
        ─────────●───────── 지면
               기초 (base_x, base_y)

    그리고 위에서 내려다보면:
                    Y (북)
                    │
                    │   ● 붐대 끝점
                    │  ╱
                    │╱  ← 선회각 (slew_angle)
        ────────────●──────── X (동)
                  기초

    [계산 방법]
    1단계: 붐대의 수평 거리 계산
        수평거리 = 붐대길이 × cos(기복각)
        → 기복각이 0도(수평)이면 수평거리 = 붐대길이 전체
        → 기복각이 90도(수직)이면 수평거리 = 0 (팔을 완전히 세운 상태)

    2단계: X, Y 좌표 계산 (선회각으로 방향 결정)
        X = 기초X + 수평거리 × sin(선회각)
        Y = 기초Y + 수평거리 × cos(선회각)
        → 선회각 0도 = 북쪽 방향
        → 선회각 90도 = 동쪽 방향

    3단계: Z 좌표 계산 (높이)
        Z = 마스트높이 + 붐대길이 × sin(기복각)

    Args:
        base_x: 크레인 기초 X좌표 (미터)
        base_y: 크레인 기초 Y좌표 (미터)
        mast_height: 마스트(기둥) 높이 (미터)
        boom_length: 붐대(팔) 길이 (미터)
        slew_angle_deg: 선회각 (도, 0=북쪽, 시계방향)
        luffing_angle_deg: 기복각 (도, 0=수평, 위로 양수)

    Returns:
        (x, y, z) 튜플 - 붐대 끝점의 3D 좌표
    """
    # 각도를 라디안으로 변환 (컴퓨터 삼각함수는 라디안 사용)
    slew_rad = math.radians(slew_angle_deg)
    luff_rad = math.radians(luffing_angle_deg)

    # 1단계: 붐대의 수평 투영 거리
    # cos(기복각)이 0에 가까우면 붐대가 거의 수직 → 수평 거리가 짧아짐
    horizontal_reach = boom_length * math.cos(luff_rad)

    # 2단계: X, Y 좌표 (수평 위치)
    # sin(선회각)으로 동서 방향 성분, cos(선회각)으로 남북 방향 성분
    tip_x = base_x + horizontal_reach * math.sin(slew_rad)
    tip_y = base_y + horizontal_reach * math.cos(slew_rad)

    # 3단계: Z 좌표 (높이)
    tip_z = mast_height + boom_length * math.sin(luff_rad)

    return (tip_x, tip_y, tip_z)


def calculate_distance_3d(point1: Point3D, point2: Point3D) -> float:
    """
    두 3D 좌표 사이의 거리를 계산합니다.

    [원리 설명]
    피타고라스 정리의 3D 확장입니다.

    2D에서 두 점 사이 거리: √[(x₁-x₂)² + (y₁-y₂)²]
    3D에서 두 점 사이 거리: √[(x₁-x₂)² + (y₁-y₂)² + (z₁-z₂)²]

    예: 점A(0,0,0)과 점B(3,4,0)의 거리 = √(9+16+0) = 5m

    Args:
        point1: 첫 번째 점 (x, y, z)
        point2: 두 번째 점 (x, y, z)

    Returns:
        두 점 사이의 거리 (미터)
    """
    dx = point1[0] - point2[0]
    dy = point1[1] - point2[1]
    dz = point1[2] - point2[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def calculate_distance_2d(
    x1: float, y1: float, x2: float, y2: float
) -> float:
    """
    두 2D 좌표 사이의 거리를 계산합니다 (수평 거리만).
    높이 차이를 무시하고 평면상의 거리만 볼 때 사용합니다.

    Args:
        x1, y1: 첫 번째 점의 좌표
        x2, y2: 두 번째 점의 좌표

    Returns:
        수평 거리 (미터)
    """
    dx = x1 - x2
    dy = y1 - y2
    return math.sqrt(dx * dx + dy * dy)


def check_working_radius_overlap(
    base_x1: float, base_y1: float, radius1: float,
    base_x2: float, base_y2: float, radius2: float,
) -> bool:
    """
    두 크레인의 작업 반경이 겹치는지 확인합니다.

    [원리 설명]
    각 크레인의 작업 반경을 위에서 보면 원(circle)입니다.
    두 원이 겹치려면, 중심 사이 거리가 두 반지름의 합보다 작아야 합니다.

        ╭───╮   ╭───╮
       │ A │   │ B │   ← 겹치지 않음 (거리 > r1 + r2)
        ╰───╯   ╰───╯

        ╭───╮╭───╮
       │ A ╳ B │          ← 겹침! (거리 < r1 + r2)
        ╰───╯╰───╯

    Args:
        base_x1, base_y1: 크레인A 기초 위치
        radius1: 크레인A 작업 반경 (미터)
        base_x2, base_y2: 크레인B 기초 위치
        radius2: 크레인B 작업 반경 (미터)

    Returns:
        True = 작업 반경이 겹침 (충돌 가능성 있음)
        False = 작업 반경이 안 겹침 (충돌 불가)
    """
    center_distance = calculate_distance_2d(base_x1, base_y1, base_x2, base_y2)
    return center_distance < (radius1 + radius2)


def predict_future_position(
    base_x: float,
    base_y: float,
    mast_height: float,
    boom_length: float,
    current_slew_deg: float,
    current_luffing_deg: float,
    slew_speed_deg_per_sec: float,
    luffing_speed_deg_per_sec: float,
    time_seconds: float,
) -> Point3D:
    """
    현재 속도를 유지할 때 미래 특정 시점의 붐대 끝점 위치를 예측합니다.

    [원리 설명]
    등속 운동(일정한 속도로 움직임)을 가정합니다.

    미래 선회각 = 현재 선회각 + (선회 속도 × 시간)
    미래 기복각 = 현재 기복각 + (기복 속도 × 시간)

    예: 현재 선회각 90도, 선회 속도 2도/초
        → 5초 후: 90 + (2 × 5) = 100도

    이렇게 계산한 미래 각도로 calculate_boom_tip_position을 호출하면
    미래의 붐대 끝점 위치를 알 수 있습니다.

    Args:
        base_x, base_y: 크레인 기초 위치
        mast_height: 마스트 높이
        boom_length: 붐대 길이
        current_slew_deg: 현재 선회각 (도)
        current_luffing_deg: 현재 기복각 (도)
        slew_speed_deg_per_sec: 선회 속도 (도/초, 양수=시계방향)
        luffing_speed_deg_per_sec: 기복 속도 (도/초, 양수=올림)
        time_seconds: 예측할 미래 시간 (초)

    Returns:
        예측된 붐대 끝점의 3D 좌표
    """
    # 미래 각도 계산
    future_slew = current_slew_deg + slew_speed_deg_per_sec * time_seconds
    future_luffing = current_luffing_deg + luffing_speed_deg_per_sec * time_seconds

    # 기복각은 물리적 제한이 있으므로 범위를 제한
    # 0도(수평) ~ 80도(거의 수직) 사이로 제한
    future_luffing = max(0.0, min(80.0, future_luffing))

    # 선회각은 0~360도 범위로 정규화
    future_slew = future_slew % 360.0

    return calculate_boom_tip_position(
        base_x, base_y, mast_height, boom_length,
        future_slew, future_luffing,
    )


def calculate_boom_line_segment(
    base_x: float,
    base_y: float,
    mast_height: float,
    boom_length: float,
    slew_angle_deg: float,
    luffing_angle_deg: float,
) -> Tuple[Point3D, Point3D]:
    """
    크레인 붐대를 선분(시작점~끝점)으로 표현합니다.

    [왜 필요한가?]
    충돌 판단을 더 정확하게 하려면, 붐대 끝점만이 아니라
    붐대 전체(마스트 꼭대기 ~ 붐대 끝점)를 고려해야 합니다.
    두 선분 사이의 최소 거리를 계산하면 더 정확한 충돌 판단이 가능합니다.

    Args:
        (calculate_boom_tip_position과 동일)

    Returns:
        (시작점, 끝점) 튜플
        시작점 = 마스트 꼭대기 (붐대가 달린 곳)
        끝점 = 붐대 끝 (후크가 달린 곳)
    """
    # 시작점: 마스트 꼭대기 (붐대의 회전 중심)
    start = (base_x, base_y, mast_height)

    # 끝점: 붐대 끝
    end = calculate_boom_tip_position(
        base_x, base_y, mast_height, boom_length,
        slew_angle_deg, luffing_angle_deg,
    )

    return (start, end)


def closest_distance_between_segments(
    p1: Point3D, p2: Point3D,
    p3: Point3D, p4: Point3D,
) -> float:
    """
    3D 공간에서 두 선분 사이의 최소 거리를 계산합니다.

    [원리 설명]
    두 크레인의 붐대는 각각 선분(직선의 일부)입니다.
    이 두 선분이 가장 가까운 지점의 거리를 구하면,
    단순히 끝점 거리만 보는 것보다 훨씬 정확한 충돌 판단이 가능합니다.

    예: 두 붐대가 엇갈리는 경우
        끝점은 멀어도 중간 부분이 가까울 수 있음!

        붐대A: ●────────────●
                        ╲
                         ╲  ← 이 부분이 가장 가까움
                          ╲
        붐대B:              ●────────────●

    [알고리즘]
    두 선분을 매개변수(0~1) 방정식으로 표현하고,
    거리가 최소가 되는 매개변수 값을 찾습니다.

    선분1 위의 점 = P1 + s × (P2 - P1), s는 0~1
    선분2 위의 점 = P3 + t × (P4 - P3), t는 0~1

    Args:
        p1, p2: 첫 번째 선분의 시작점과 끝점
        p3, p4: 두 번째 선분의 시작점과 끝점

    Returns:
        두 선분 사이의 최소 거리 (미터)
    """
    # 방향 벡터 계산
    d1 = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])  # 선분1 방향
    d2 = (p4[0] - p3[0], p4[1] - p3[1], p4[2] - p3[2])  # 선분2 방향
    r = (p1[0] - p3[0], p1[1] - p3[1], p1[2] - p3[2])   # 시작점 차이

    # 내적 계산 (dot product)
    a = _dot(d1, d1)  # |d1|²
    e = _dot(d2, d2)  # |d2|²
    f = _dot(d2, r)

    # 두 선분이 모두 점(길이=0)인 경우
    EPSILON = 1e-8
    if a < EPSILON and e < EPSILON:
        return calculate_distance_3d(p1, p3)

    if a < EPSILON:
        # 첫 번째 선분이 점인 경우
        s = 0.0
        t = max(0.0, min(1.0, f / e))
    else:
        c = _dot(d1, r)
        if e < EPSILON:
            # 두 번째 선분이 점인 경우
            t = 0.0
            s = max(0.0, min(1.0, -c / a))
        else:
            # 일반적인 경우
            b = _dot(d1, d2)
            denom = a * e - b * b

            if abs(denom) > EPSILON:
                s = max(0.0, min(1.0, (b * f - c * e) / denom))
            else:
                s = 0.0

            t = (b * s + f) / e

            if t < 0.0:
                t = 0.0
                s = max(0.0, min(1.0, -c / a))
            elif t > 1.0:
                t = 1.0
                s = max(0.0, min(1.0, (b - c) / a))

    # 최소 거리 점 계산
    closest1 = (
        p1[0] + s * d1[0],
        p1[1] + s * d1[1],
        p1[2] + s * d1[2],
    )
    closest2 = (
        p3[0] + t * d2[0],
        p3[1] + t * d2[1],
        p3[2] + t * d2[2],
    )

    return calculate_distance_3d(closest1, closest2)


def _dot(v1: Tuple[float, float, float], v2: Tuple[float, float, float]) -> float:
    """두 3D 벡터의 내적(dot product)을 계산합니다."""
    return v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]
