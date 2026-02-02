"""
경보 시스템 모듈
================

이 모듈은 충돌 예측 결과를 사람이 이해할 수 있는 경고 메시지로
변환하는 역할을 합니다.

[역할]
- 위험 등급에 따른 경고 메시지 생성
- 운전자에게 보낼 간단한 알림 텍스트 생성
- 관제실에 보낼 상세 이벤트 정보 생성
- 음성 안내 텍스트 생성 (TTS 연동용)

[경고 등급별 동작]

NORMAL (정상)
  → 별도 동작 없음, 정상 상태 표시

CAUTION (주의)
  → 관제 화면에 노란색 표시
  → 운전자에게 알림 메시지

WARNING (경고)
  → 관제 화면에 주황색 표시
  → 운전자에게 음성 경고
  → 선택적: 선회 속도 제한

DANGER (위험)
  → 관제 화면에 빨간색 깜박임
  → 운전자에게 긴급 음성 경고
  → 자동 정지 신호 (선택적)
  → 관제실 알림음
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from core.collision import CollisionCheckResult, LEVEL_NORMAL, LEVEL_CAUTION, LEVEL_WARNING, LEVEL_DANGER
from config.settings import ALERT_COLORS


@dataclass
class AlertMessage:
    """
    경고 메시지를 담는 클래스

    하나의 경고 메시지에는 다음 정보가 포함됩니다:
    - 어떤 크레인 쌍의 경고인지
    - 위험 등급
    - 사람이 읽을 수 있는 메시지
    - 음성 안내 텍스트
    """
    crane_a_id: str             # 관련 크레인 A
    crane_b_id: str             # 관련 크레인 B
    alert_level: str            # 위험 등급
    message: str                # 화면 표시용 메시지
    voice_text: str             # 음성 안내 텍스트
    color: str                  # 표시 색상 (#RRGGBB)
    distance: float             # 현재 거리 (미터)
    time_to_collision: Optional[float] = None  # 예상 충돌 시간
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 전송용)"""
        return {
            "crane_a_id": self.crane_a_id,
            "crane_b_id": self.crane_b_id,
            "alert_level": self.alert_level,
            "message": self.message,
            "voice_text": self.voice_text,
            "color": self.color,
            "distance": round(self.distance, 1),
            "time_to_collision": (
                round(self.time_to_collision, 1)
                if self.time_to_collision is not None
                else None
            ),
            "timestamp": self.timestamp,
        }


class AlertManager:
    """
    경보 관리자 - 충돌 검사 결과를 경고 메시지로 변환

    [사용 예시]
    alert_mgr = AlertManager()

    # 충돌 검사 결과를 받아서 경고 메시지 생성
    results = collision_engine.check_all_collisions()
    alerts = alert_mgr.process_results(results)

    for alert in alerts:
        print(alert.message)
        # 예: "⚠️ 1호기 ↔ 2호기: 거리 8.5m (주의)"
    """

    def __init__(self):
        # 크레인 이름 매핑 (ID → 표시 이름)
        self.crane_names: Dict[str, str] = {}

    def set_crane_names(self, names: Dict[str, str]) -> None:
        """
        크레인 ID와 표시 이름을 매핑합니다.

        Args:
            names: {"TC-1": "1호기", "TC-2": "2호기", ...}
        """
        self.crane_names = names

    def _get_crane_name(self, crane_id: str) -> str:
        """크레인 ID에 대한 표시 이름을 반환합니다."""
        return self.crane_names.get(crane_id, crane_id)

    def process_results(
        self, results: List[CollisionCheckResult]
    ) -> List[AlertMessage]:
        """
        충돌 검사 결과 목록을 경고 메시지 목록으로 변환합니다.

        [동작]
        - NORMAL 등급은 경고 메시지를 생성하지 않습니다.
        - CAUTION 이상 등급만 경고 메시지를 생성합니다.

        Args:
            results: CollisionCheckResult 목록

        Returns:
            AlertMessage 목록 (CAUTION 이상만 포함)
        """
        alerts = []
        for result in results:
            if result.alert_level != LEVEL_NORMAL:
                alert = self._create_alert(result)
                alerts.append(alert)
        return alerts

    def _create_alert(self, result: CollisionCheckResult) -> AlertMessage:
        """
        하나의 충돌 검사 결과를 경고 메시지로 변환합니다.

        [메시지 생성 규칙]
        - 주의: "X호기 ↔ Y호기: 거리 8.5m (주의)"
        - 경고: "X호기 ↔ Y호기: 거리 4.2m - Z초 후 접근 예상 (경고)"
        - 위험: "X호기 ↔ Y호기: 거리 2.1m - 즉시 정지 필요! (위험)"
        """
        name_a = self._get_crane_name(result.crane_a_id)
        name_b = self._get_crane_name(result.crane_b_id)
        level = result.alert_level
        dist = result.current_distance
        ttc = result.time_to_collision

        # --- 화면 표시용 메시지 생성 ---
        if level == LEVEL_DANGER:
            message = (
                f"{name_a} ↔ {name_b}: 거리 {dist:.1f}m - "
                f"즉시 정지 필요! (위험)"
            )
        elif level == LEVEL_WARNING:
            if ttc is not None:
                message = (
                    f"{name_a} ↔ {name_b}: 거리 {dist:.1f}m - "
                    f"{ttc:.0f}초 후 접근 예상 (경고)"
                )
            else:
                message = (
                    f"{name_a} ↔ {name_b}: 거리 {dist:.1f}m (경고)"
                )
        else:  # CAUTION
            if ttc is not None:
                message = (
                    f"{name_a} ↔ {name_b}: 거리 {dist:.1f}m - "
                    f"{ttc:.0f}초 후 접근 예상 (주의)"
                )
            else:
                message = (
                    f"{name_a} ↔ {name_b}: 거리 {dist:.1f}m (주의)"
                )

        # --- 음성 안내 텍스트 생성 ---
        voice_text = self._generate_voice_text(
            name_a, name_b, level, dist, ttc
        )

        return AlertMessage(
            crane_a_id=result.crane_a_id,
            crane_b_id=result.crane_b_id,
            alert_level=level,
            message=message,
            voice_text=voice_text,
            color=ALERT_COLORS.get(level, "#FFFFFF"),
            distance=dist,
            time_to_collision=ttc,
        )

    def _generate_voice_text(
        self,
        name_a: str,
        name_b: str,
        level: str,
        distance: float,
        ttc: Optional[float],
    ) -> str:
        """
        음성 안내 텍스트를 생성합니다.

        [설계 원칙]
        - 짧고 명확하게
        - 운전자가 즉시 이해할 수 있도록
        - 등급이 높을수록 긴급한 어조

        실제 현장에서는 이 텍스트를 TTS(음성합성) 엔진에 넣어
        스피커로 출력합니다.
        """
        if level == LEVEL_DANGER:
            return f"위험! {name_a}와 {name_b} 충돌 위험. 즉시 정지하세요. 거리 {distance:.0f}미터."

        elif level == LEVEL_WARNING:
            if ttc is not None:
                return f"경고. {name_b} 접근 중. {ttc:.0f}초 후 충돌 예상. 거리 {distance:.0f}미터."
            else:
                return f"경고. {name_b} 방향 주의. 거리 {distance:.0f}미터."

        else:  # CAUTION
            return f"{name_b} 방향 주의. 거리 {distance:.0f}미터."

    def get_alerts_for_crane(
        self, crane_id: str, alerts: List[AlertMessage]
    ) -> List[AlertMessage]:
        """
        특정 크레인에 관련된 경고만 필터링합니다.

        [용도]
        운전실 단말에서는 해당 크레인과 관련된 경고만 보여줘야 합니다.
        예: TC-1 운전실 → TC-1이 포함된 경고만 표시

        Args:
            crane_id: 대상 크레인 ID
            alerts: 전체 경고 목록

        Returns:
            해당 크레인과 관련된 경고 목록
        """
        return [
            alert for alert in alerts
            if alert.crane_a_id == crane_id or alert.crane_b_id == crane_id
        ]
