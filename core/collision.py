"""
충돌 예측 엔진
===============

이 모듈은 시스템의 "두뇌"입니다.
여러 크레인의 위치 데이터를 받아서, 충돌 위험이 있는지 판단하고,
미래 충돌 가능성까지 예측합니다.

[동작 흐름]

1. 모든 크레인 쌍(pair)을 만듭니다
   - 크레인이 3대면: (A,B), (A,C), (B,C) = 3쌍
   - 크레인이 4대면: (A,B), (A,C), (A,D), (B,C), (B,D), (C,D) = 6쌍
   - 일반적으로 N대면 N×(N-1)/2 쌍

2. 각 쌍에 대해 다음을 계산합니다:
   a) 작업 반경이 겹치는가? (빠른 사전 필터링)
   b) 현재 붐대 간 최소 거리는?
   c) 미래에 충돌 가능성이 있는가? (궤적 예측)

3. 위험 등급을 판정합니다 (정상/주의/경고/위험)

[성능 고려사항]
크레인 쌍 수가 많아지면 계산량이 늘어납니다.
하지만 일반적인 건설현장에서 크레인은 2~5대 정도이므로,
최대 10쌍 정도만 계산하면 됩니다. 0.1초 이내에 충분히 처리 가능합니다.
"""

import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from core.crane import TowerCrane
from core.geometry import (
    Point3D,
    calculate_distance_3d,
    check_working_radius_overlap,
    closest_distance_between_segments,
    predict_future_position,
)
from config.settings import (
    ALERT_THRESHOLDS,
    PREDICTION_TIME_SECONDS,
    PREDICTION_STEP_SECONDS,
    SAFETY_MARGIN_METERS,
)


# ============================================================
# 위험 등급 상수
# ============================================================
LEVEL_NORMAL = "NORMAL"     # 정상 - 안전
LEVEL_CAUTION = "CAUTION"   # 주의 - 알림
LEVEL_WARNING = "WARNING"   # 경고 - 속도 제한
LEVEL_DANGER = "DANGER"     # 위험 - 비상 정지

# 위험 등급 우선순위 (숫자가 클수록 위험)
LEVEL_PRIORITY = {
    LEVEL_NORMAL: 0,
    LEVEL_CAUTION: 1,
    LEVEL_WARNING: 2,
    LEVEL_DANGER: 3,
}


@dataclass
class CollisionCheckResult:
    """
    두 크레인 사이의 충돌 검사 결과를 담는 클래스

    [포함 정보]
    - 어떤 크레인 쌍인지 (crane_a_id, crane_b_id)
    - 현재 거리와 위험 등급
    - 예상 충돌 시간 (충돌이 예상되는 경우)
    - 작업 반경 중첩 여부
    """
    crane_a_id: str                    # 크레인A의 ID
    crane_b_id: str                    # 크레인B의 ID
    alert_level: str = LEVEL_NORMAL    # 위험 등급

    # 현재 상태
    current_distance: float = 999.0    # 현재 붐대 간 최소 거리 (미터)
    boom_tip_distance: float = 999.0   # 붐대 끝점 간 거리 (미터)
    overlap_exists: bool = False       # 작업 반경 중첩 여부

    # 예측 결과
    time_to_collision: Optional[float] = None  # 예상 충돌 시간 (초), None=충돌 예상 없음
    min_predicted_distance: float = 999.0      # 예측 기간 내 최소 접근 거리
    min_predicted_time: float = 0.0            # 최소 접근 시점 (초)

    # 메타 정보
    timestamp: float = field(default_factory=time.time)  # 검사 시각

    def to_dict(self) -> Dict[str, Any]:
        """웹 브라우저로 전송하기 위해 딕셔너리로 변환"""
        return {
            "crane_a_id": self.crane_a_id,
            "crane_b_id": self.crane_b_id,
            "alert_level": self.alert_level,
            "current_distance": round(self.current_distance, 2),
            "boom_tip_distance": round(self.boom_tip_distance, 2),
            "overlap_exists": self.overlap_exists,
            "time_to_collision": (
                round(self.time_to_collision, 1)
                if self.time_to_collision is not None
                else None
            ),
            "min_predicted_distance": round(self.min_predicted_distance, 2),
            "min_predicted_time": round(self.min_predicted_time, 1),
            "timestamp": self.timestamp,
        }


class CollisionEngine:
    """
    충돌 예측 엔진 - 시스템의 핵심 클래스

    [역할]
    - 등록된 모든 크레인 쌍의 충돌 위험을 실시간으로 분석
    - 미래 궤적을 예측하여 사전 경고 생성
    - 위험 등급 판정 및 이력 관리

    [사용 예시]
    engine = CollisionEngine()
    engine.register_crane(crane1)
    engine.register_crane(crane2)

    # 크레인 위치가 갱신될 때마다 호출
    results = engine.check_all_collisions()
    for result in results:
        print(f"{result.crane_a_id} ↔ {result.crane_b_id}: {result.alert_level}")
    """

    def __init__(self):
        # 등록된 크레인 목록 {id: TowerCrane}
        self.cranes: Dict[str, TowerCrane] = {}

        # 최근 충돌 검사 결과 저장
        self.last_results: List[CollisionCheckResult] = []

        # 이벤트 기록 (경고 이력)
        self.event_log: List[Dict[str, Any]] = []

        # 최대 이벤트 기록 수 (메모리 관리)
        self.max_event_log_size = 1000

    def register_crane(self, crane: TowerCrane) -> None:
        """
        크레인을 엔진에 등록합니다.
        등록된 크레인만 충돌 검사 대상이 됩니다.

        Args:
            crane: 등록할 TowerCrane 객체
        """
        self.cranes[crane.id] = crane

    def unregister_crane(self, crane_id: str) -> None:
        """
        크레인을 엔진에서 해제합니다.

        Args:
            crane_id: 해제할 크레인의 ID
        """
        self.cranes.pop(crane_id, None)

    def get_crane(self, crane_id: str) -> Optional[TowerCrane]:
        """ID로 크레인을 조회합니다."""
        return self.cranes.get(crane_id)

    def check_all_collisions(self) -> List[CollisionCheckResult]:
        """
        등록된 모든 크레인 쌍의 충돌 위험을 검사합니다.

        [동작 과정]
        1. 활성 크레인 목록 확인
        2. 모든 크레인 쌍(pair) 생성
        3. 각 쌍에 대해 충돌 검사 수행
        4. 결과 저장 및 반환

        Returns:
            CollisionCheckResult 목록 (각 크레인 쌍별 결과)
        """
        results = []

        # 활성 크레인만 필터링
        active_cranes = [c for c in self.cranes.values() if c.is_active]

        # 모든 크레인 쌍에 대해 검사
        # 예: [A, B, C] → (A,B), (A,C), (B,C)
        for i in range(len(active_cranes)):
            for j in range(i + 1, len(active_cranes)):
                result = self._check_pair(active_cranes[i], active_cranes[j])
                results.append(result)

                # 이전 결과와 비교하여 등급 변화 감지
                self._check_level_change(result)

        self.last_results = results
        return results

    def _check_pair(
        self, crane_a: TowerCrane, crane_b: TowerCrane
    ) -> CollisionCheckResult:
        """
        두 크레인 사이의 충돌 위험을 상세 검사합니다.

        [검사 순서]

        빠른 필터 (계산 비용 낮음)
        ┌─────────────────────────────┐
        │ 1. 작업 반경 중첩 확인       │
        │    → 중첩 없으면 "정상"      │
        └─────────────┬───────────────┘
                      │ 중첩 있음
                      ▼
        상세 검사 (계산 비용 높음)
        ┌─────────────────────────────┐
        │ 2. 현재 거리 계산            │
        │    - 붐대 끝점 간 거리       │
        │    - 붐대 선분 간 최소 거리  │
        └─────────────┬───────────────┘
                      │
                      ▼
        미래 예측 (계산 비용 가장 높음)
        ┌─────────────────────────────┐
        │ 3. 궤적 예측                │
        │    - 미래 위치 계산          │
        │    - 최소 접근 시점 찾기     │
        │    - 충돌 예상 시간 계산     │
        └─────────────┬───────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │ 4. 위험 등급 판정            │
        │    거리 + 시간 → 등급 결정   │
        └─────────────────────────────┘

        Args:
            crane_a, crane_b: 검사할 두 크레인

        Returns:
            CollisionCheckResult 객체
        """
        result = CollisionCheckResult(
            crane_a_id=crane_a.id,
            crane_b_id=crane_b.id,
        )

        # ────────────────────────────────────────────
        # 1단계: 작업 반경 중첩 확인 (빠른 사전 필터)
        # ────────────────────────────────────────────
        result.overlap_exists = check_working_radius_overlap(
            crane_a.base_x, crane_a.base_y, crane_a.get_max_working_radius(),
            crane_b.base_x, crane_b.base_y, crane_b.get_max_working_radius(),
        )

        if not result.overlap_exists:
            # 작업 반경이 겹치지 않으면 물리적으로 충돌 불가
            result.alert_level = LEVEL_NORMAL
            tip_a = crane_a.get_boom_tip_position()
            tip_b = crane_b.get_boom_tip_position()
            result.boom_tip_distance = calculate_distance_3d(tip_a, tip_b)
            result.current_distance = result.boom_tip_distance
            return result

        # ────────────────────────────────────────────
        # 2단계: 현재 거리 측정
        # ────────────────────────────────────────────

        # 2-a: 붐대 끝점 간 거리
        tip_a = crane_a.get_boom_tip_position()
        tip_b = crane_b.get_boom_tip_position()
        result.boom_tip_distance = calculate_distance_3d(tip_a, tip_b)

        # 2-b: 붐대 선분 간 최소 거리 (더 정확한 측정)
        seg_a = crane_a.get_boom_segment()
        seg_b = crane_b.get_boom_segment()
        result.current_distance = closest_distance_between_segments(
            seg_a[0], seg_a[1], seg_b[0], seg_b[1]
        )

        # ────────────────────────────────────────────
        # 3단계: 미래 궤적 예측
        # ────────────────────────────────────────────

        # 크레인이 움직이고 있는 경우에만 예측 수행
        is_moving = (
            abs(crane_a.slew_speed) > 0.01
            or abs(crane_b.slew_speed) > 0.01
            or abs(crane_a.luffing_speed) > 0.01
            or abs(crane_b.luffing_speed) > 0.01
        )

        if is_moving:
            prediction = self._predict_collision(crane_a, crane_b)
            result.time_to_collision = prediction["time_to_collision"]
            result.min_predicted_distance = prediction["min_distance"]
            result.min_predicted_time = prediction["min_distance_time"]

        # ────────────────────────────────────────────
        # 4단계: 위험 등급 판정
        # ────────────────────────────────────────────
        result.alert_level = self._determine_alert_level(result)

        return result

    def _predict_collision(
        self, crane_a: TowerCrane, crane_b: TowerCrane
    ) -> Dict[str, Any]:
        """
        두 크레인의 미래 궤적을 예측하여 충돌 가능성을 분석합니다.

        [원리 설명]
        현재 속도가 유지된다고 가정하고, 미래 시점별로 위치를 계산합니다.

        시간:  0초   0.5초   1.0초   1.5초   2.0초  ...  30초
        A위치: ●━━━━●━━━━●━━━━●━━━━●━━━━━━━━●
        B위치: ●━━━━●━━━━●━━━━●━━━━●━━━━━━━━●

        각 시점에서 A와 B 사이 거리를 계산하여,
        가장 가까워지는 시점과 그 때의 거리를 찾습니다.

        거리가 안전 여유 거리(SAFETY_MARGIN) 이하가 되는 시점이 있으면
        → "충돌 예상 시간"으로 보고

        Returns:
            {
                "time_to_collision": 충돌 예상 시간(초) 또는 None,
                "min_distance": 예측 기간 내 최소 거리(m),
                "min_distance_time": 최소 거리 시점(초),
            }
        """
        min_distance = float("inf")
        min_distance_time = 0.0
        time_to_collision = None

        # 0초부터 PREDICTION_TIME_SECONDS초까지 PREDICTION_STEP_SECONDS 간격으로 검사
        t = PREDICTION_STEP_SECONDS
        while t <= PREDICTION_TIME_SECONDS:
            # 크레인 A의 미래 붐대 끝점
            future_tip_a = predict_future_position(
                crane_a.base_x, crane_a.base_y,
                crane_a.mast_height, crane_a.boom_length,
                crane_a.slew_angle, crane_a.luffing_angle,
                crane_a.slew_speed, crane_a.luffing_speed,
                t,
            )

            # 크레인 B의 미래 붐대 끝점
            future_tip_b = predict_future_position(
                crane_b.base_x, crane_b.base_y,
                crane_b.mast_height, crane_b.boom_length,
                crane_b.slew_angle, crane_b.luffing_angle,
                crane_b.slew_speed, crane_b.luffing_speed,
                t,
            )

            # 미래 시점에서의 거리
            dist = calculate_distance_3d(future_tip_a, future_tip_b)

            # 최소 거리 갱신
            if dist < min_distance:
                min_distance = dist
                min_distance_time = t

            # 안전 여유 거리 이하로 접근하는 첫 시점을 충돌 예상 시간으로 기록
            if dist <= SAFETY_MARGIN_METERS and time_to_collision is None:
                time_to_collision = t

            t += PREDICTION_STEP_SECONDS

        return {
            "time_to_collision": time_to_collision,
            "min_distance": min_distance,
            "min_distance_time": min_distance_time,
        }

    def _determine_alert_level(self, result: CollisionCheckResult) -> str:
        """
        충돌 검사 결과를 바탕으로 위험 등급을 판정합니다.

        [판정 로직]
        거리 기준과 시간 기준 중 더 위험한 쪽을 채택합니다.

        예: 현재 거리 7m (→ 주의), 예상 충돌 8초 후 (→ 경고)
            → 더 위험한 "경고" 등급 채택

        Args:
            result: 충돌 검사 결과

        Returns:
            위험 등급 문자열 ("NORMAL", "CAUTION", "WARNING", "DANGER")
        """
        distance = result.current_distance
        ttc = result.time_to_collision  # time to collision

        # 거리 기반 등급 판정
        distance_level = LEVEL_NORMAL
        if distance <= ALERT_THRESHOLDS["DANGER"]["distance"]:
            distance_level = LEVEL_DANGER
        elif distance <= ALERT_THRESHOLDS["WARNING"]["distance"]:
            distance_level = LEVEL_WARNING
        elif distance <= ALERT_THRESHOLDS["CAUTION"]["distance"]:
            distance_level = LEVEL_CAUTION

        # 시간 기반 등급 판정 (예상 충돌 시간이 있는 경우)
        time_level = LEVEL_NORMAL
        if ttc is not None:
            if ttc <= ALERT_THRESHOLDS["DANGER"]["time_to_collision"]:
                time_level = LEVEL_DANGER
            elif ttc <= ALERT_THRESHOLDS["WARNING"]["time_to_collision"]:
                time_level = LEVEL_WARNING
            elif ttc <= ALERT_THRESHOLDS["CAUTION"]["time_to_collision"]:
                time_level = LEVEL_CAUTION

        # 두 기준 중 더 높은(위험한) 등급 채택
        if LEVEL_PRIORITY[distance_level] >= LEVEL_PRIORITY[time_level]:
            return distance_level
        else:
            return time_level

    def _check_level_change(self, result: CollisionCheckResult) -> None:
        """
        이전 결과와 비교하여 위험 등급이 변경되었는지 확인합니다.
        등급이 변경되면 이벤트 로그에 기록합니다.

        [왜 필요한가?]
        관제 화면에 "14:22 TC-1↔TC-2 주의→정상" 같은 이력을 표시하려면,
        등급 변화 시점을 기록해야 합니다.
        """
        pair_key = f"{result.crane_a_id}↔{result.crane_b_id}"

        # 이전 결과에서 같은 쌍의 결과 찾기
        prev_level = None
        for prev_result in self.last_results:
            prev_key = f"{prev_result.crane_a_id}↔{prev_result.crane_b_id}"
            if prev_key == pair_key:
                prev_level = prev_result.alert_level
                break

        # 등급이 변경되었으면 이벤트 기록
        if prev_level is not None and prev_level != result.alert_level:
            event = {
                "timestamp": time.time(),
                "pair": pair_key,
                "crane_a_id": result.crane_a_id,
                "crane_b_id": result.crane_b_id,
                "from_level": prev_level,
                "to_level": result.alert_level,
                "distance": result.current_distance,
            }
            self.event_log.append(event)

            # 로그 크기 제한 (오래된 것부터 삭제)
            if len(self.event_log) > self.max_event_log_size:
                self.event_log = self.event_log[-self.max_event_log_size:]

    def get_overall_status(self) -> Dict[str, Any]:
        """
        전체 현장의 안전 상태 요약을 반환합니다.

        Returns:
            {
                "total_cranes": 총 크레인 수,
                "active_cranes": 가동 중 크레인 수,
                "total_pairs": 검사 대상 쌍 수,
                "status_counts": {"NORMAL": 2, "CAUTION": 1, ...},
                "highest_alert": 현재 최고 위험 등급,
                "recent_events": 최근 이벤트 목록,
            }
        """
        status_counts = {
            LEVEL_NORMAL: 0,
            LEVEL_CAUTION: 0,
            LEVEL_WARNING: 0,
            LEVEL_DANGER: 0,
        }

        highest_alert = LEVEL_NORMAL
        for result in self.last_results:
            status_counts[result.alert_level] += 1
            if LEVEL_PRIORITY[result.alert_level] > LEVEL_PRIORITY[highest_alert]:
                highest_alert = result.alert_level

        # 각 크레인의 최고 위험 등급 계산
        crane_alerts = {}
        for crane_id in self.cranes:
            crane_alerts[crane_id] = LEVEL_NORMAL
        for result in self.last_results:
            for cid in [result.crane_a_id, result.crane_b_id]:
                if cid in crane_alerts:
                    if LEVEL_PRIORITY[result.alert_level] > LEVEL_PRIORITY[crane_alerts[cid]]:
                        crane_alerts[cid] = result.alert_level

        active_count = sum(1 for c in self.cranes.values() if c.is_active)

        return {
            "total_cranes": len(self.cranes),
            "active_cranes": active_count,
            "total_pairs": len(self.last_results),
            "status_counts": status_counts,
            "highest_alert": highest_alert,
            "crane_alerts": crane_alerts,
            "recent_events": self.event_log[-20:],  # 최근 20개 이벤트
        }
