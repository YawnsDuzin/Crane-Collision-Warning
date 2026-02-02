"""
크레인 모델 모듈
================

이 모듈은 타워크레인을 소프트웨어 객체로 표현합니다.
실제 크레인의 물리적 특성(위치, 크기, 각도 등)을 숫자로 저장하고,
이를 기반으로 3D 좌표를 계산합니다.

[클래스 구조]

TowerCrane (타워크레인)
├── 고정 속성 (설치 후 변하지 않음)
│   ├── id: 고유 식별자 (예: "TC-1")
│   ├── name: 표시 이름 (예: "1호기")
│   ├── base_x, base_y: 기초 위치 (미터)
│   ├── mast_height: 마스트 높이 (미터)
│   └── boom_length: 붐대 길이 (미터)
│
├── 변동 속성 (운전 중 계속 변함)
│   ├── slew_angle: 선회각 (도)
│   ├── luffing_angle: 기복각 (도)
│   ├── slew_speed: 선회 속도 (도/초)
│   └── luffing_speed: 기복 속도 (도/초)
│
└── 계산 속성 (변동 속성으로부터 자동 계산)
    ├── boom_tip_position: 붐대 끝점 3D 좌표
    ├── working_radius: 현재 작업 반경
    └── boom_segment: 붐대 선분 (시작점~끝점)
"""

import math
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple

from core.geometry import (
    Point3D,
    calculate_boom_tip_position,
    calculate_boom_line_segment,
)


@dataclass
class TowerCrane:
    """
    타워크레인 한 대를 나타내는 클래스

    [dataclass란?]
    Python에서 데이터를 담는 클래스를 쉽게 만들어주는 기능입니다.
    __init__, __repr__ 등을 자동으로 만들어줍니다.

    [사용 예시]
    crane = TowerCrane(
        id="TC-1",
        name="1호기",
        base_x=0.0,
        base_y=0.0,
        mast_height=40.0,
        boom_length=60.0,
    )

    # 선회각 변경 (붐대를 90도 방향으로 돌림)
    crane.slew_angle = 90.0

    # 현재 붐대 끝점 위치 확인
    x, y, z = crane.get_boom_tip_position()
    print(f"붐대 끝점: ({x:.1f}, {y:.1f}, {z:.1f})")
    """

    # --- 고유 식별 정보 ---
    id: str                     # 크레인 ID (예: "TC-1")
    name: str                   # 표시 이름 (예: "1호기")

    # --- 기초 위치 (설치 위치, 고정값) ---
    base_x: float               # X 좌표 (미터)
    base_y: float               # Y 좌표 (미터)

    # --- 구조 치수 (크레인 스펙, 고정값) ---
    mast_height: float          # 마스트(기둥) 높이 (미터)
    boom_length: float          # 붐대(팔) 길이 (미터)

    # --- 현재 자세 (운전 중 변하는 값) ---
    slew_angle: float = 0.0     # 선회각 (도, 0=북, 시계방향)
    luffing_angle: float = 0.0  # 기복각 (도, 0=수평, 위로 양수)

    # --- 현재 속도 (운전 중 변하는 값) ---
    slew_speed: float = 0.0     # 선회 속도 (도/초, 양수=시계방향)
    luffing_speed: float = 0.0  # 기복 속도 (도/초, 양수=올림)

    # --- 상태 정보 ---
    is_active: bool = True      # 가동 중 여부
    last_update: float = field(default_factory=time.time)  # 마지막 데이터 갱신 시각

    def get_boom_tip_position(self) -> Point3D:
        """
        현재 붐대 끝점의 3D 좌표를 반환합니다.

        Returns:
            (x, y, z) 튜플 - 붐대 끝점의 3D 좌표 (미터)
        """
        return calculate_boom_tip_position(
            self.base_x, self.base_y,
            self.mast_height, self.boom_length,
            self.slew_angle, self.luffing_angle,
        )

    def get_boom_segment(self) -> Tuple[Point3D, Point3D]:
        """
        붐대를 선분으로 표현합니다 (마스트 꼭대기 ~ 붐대 끝점).

        Returns:
            (시작점, 끝점) 튜플
        """
        return calculate_boom_line_segment(
            self.base_x, self.base_y,
            self.mast_height, self.boom_length,
            self.slew_angle, self.luffing_angle,
        )

    def get_working_radius(self) -> float:
        """
        현재 작업 반경을 계산합니다 (수평 거리).

        [원리]
        작업 반경 = 붐대 길이 × cos(기복각)
        기복각이 0도(수평)이면 → 작업 반경 = 붐대 길이 (최대)
        기복각이 높을수록 → 작업 반경이 줄어듦

        Returns:
            현재 작업 반경 (미터)
        """
        return self.boom_length * math.cos(math.radians(self.luffing_angle))

    def get_max_working_radius(self) -> float:
        """
        최대 작업 반경을 반환합니다.
        기복각이 0도(붐대가 완전히 수평)일 때의 반경입니다.

        Returns:
            최대 작업 반경 (미터) = 붐대 길이
        """
        return self.boom_length

    def update_position(self, dt: float) -> None:
        """
        시간 경과에 따라 크레인 자세를 갱신합니다.

        [원리]
        등속 운동: 새 각도 = 현재 각도 + 속도 × 시간

        Args:
            dt: 경과 시간 (초)
        """
        if not self.is_active:
            return

        # 선회각 갱신 (0~360도 범위 유지)
        self.slew_angle = (self.slew_angle + self.slew_speed * dt) % 360.0

        # 기복각 갱신 (0~80도 범위 제한)
        self.luffing_angle += self.luffing_speed * dt
        self.luffing_angle = max(0.0, min(80.0, self.luffing_angle))

        # 갱신 시각 기록
        self.last_update = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """
        크레인 상태를 딕셔너리(사전)로 변환합니다.
        JSON으로 변환하여 웹 브라우저에 보내기 위해 사용합니다.

        Returns:
            크레인 상태 정보가 담긴 딕셔너리
        """
        tip = self.get_boom_tip_position()
        segment = self.get_boom_segment()

        return {
            "id": self.id,
            "name": self.name,
            # 기초 위치
            "base_x": round(self.base_x, 2),
            "base_y": round(self.base_y, 2),
            # 구조 치수
            "mast_height": round(self.mast_height, 2),
            "boom_length": round(self.boom_length, 2),
            # 현재 자세
            "slew_angle": round(self.slew_angle, 2),
            "luffing_angle": round(self.luffing_angle, 2),
            # 현재 속도
            "slew_speed": round(self.slew_speed, 2),
            "luffing_speed": round(self.luffing_speed, 2),
            # 계산된 위치
            "boom_tip": {
                "x": round(tip[0], 2),
                "y": round(tip[1], 2),
                "z": round(tip[2], 2),
            },
            "boom_segment": {
                "start": {
                    "x": round(segment[0][0], 2),
                    "y": round(segment[0][1], 2),
                    "z": round(segment[0][2], 2),
                },
                "end": {
                    "x": round(segment[1][0], 2),
                    "y": round(segment[1][1], 2),
                    "z": round(segment[1][2], 2),
                },
            },
            # 작업 반경
            "working_radius": round(self.get_working_radius(), 2),
            "max_working_radius": round(self.get_max_working_radius(), 2),
            # 상태
            "is_active": self.is_active,
        }

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "TowerCrane":
        """
        설정 딕셔너리로부터 TowerCrane 객체를 생성합니다.

        [사용 예시]
        config = {
            "id": "TC-1",
            "name": "1호기",
            "base_x": 0.0,
            "base_y": 0.0,
            "mast_height": 40.0,
            "boom_length": 60.0,
            "initial_slew_angle": 45.0,
            "initial_luffing_angle": 15.0,
            "slew_speed": 0.5,
        }
        crane = TowerCrane.from_config(config)

        Args:
            config: 설정 딕셔너리 (config/settings.py의 DEFAULT_CRANES 형식)

        Returns:
            생성된 TowerCrane 객체
        """
        return cls(
            id=config["id"],
            name=config["name"],
            base_x=config["base_x"],
            base_y=config["base_y"],
            mast_height=config["mast_height"],
            boom_length=config["boom_length"],
            slew_angle=config.get("initial_slew_angle", 0.0),
            luffing_angle=config.get("initial_luffing_angle", 0.0),
            slew_speed=config.get("slew_speed", 0.0),
            luffing_speed=config.get("luffing_speed", 0.0),
        )
