"""
WebSocket 실시간 통신 모듈
============================

이 모듈은 서버와 웹 브라우저 사이의 실시간 통신을 담당합니다.

[WebSocket이란?]
일반적인 HTTP 통신은 "질문 → 응답" 방식입니다.
브라우저가 물어봐야 서버가 대답합니다.

WebSocket은 한번 연결하면 양방향으로 자유롭게 데이터를 주고받습니다.
서버가 새 데이터가 있을 때 즉시 브라우저에 보낼 수 있습니다.

[왜 필요한가?]
크레인 위치가 0.1~0.2초마다 바뀌기 때문에,
매번 브라우저가 요청하는 것보다 서버가 자동으로 보내주는 게 효율적입니다.

[동작 흐름]

    브라우저                              서버
       │                                    │
       │── WebSocket 연결 요청 ──────────→ │
       │                                    │
       │←── 연결 확인 ───────────────────── │
       │                                    │
       │←── 크레인 데이터 (0.2초마다) ────── │
       │←── 크레인 데이터 ─────────────────  │
       │←── 크레인 데이터 ─────────────────  │
       │                                    │
       │── 크레인 속도 변경 명령 ─────────→  │
       │                                    │
       │←── 변경 확인 + 새 데이터 ────────── │
       │                                    │
       │←── (계속 데이터 전송) ────────────── │
       │                                    │
"""

import asyncio
import json
import time
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config.settings import WEBSOCKET_BROADCAST_INTERVAL_MS

router = APIRouter()

# ============================================================
# 연결된 클라이언트 관리
# ============================================================
# 현재 WebSocket으로 연결된 모든 브라우저를 추적합니다.
# 여러 브라우저가 동시에 접속할 수 있으므로 Set으로 관리합니다.
connected_clients: Set[WebSocket] = set()


async def broadcast_state(state: dict) -> None:
    """
    모든 연결된 클라이언트에게 상태 데이터를 전송합니다.

    [동작]
    연결된 모든 브라우저에 동시에 데이터를 보냅니다.
    연결이 끊어진 클라이언트는 자동으로 목록에서 제거합니다.

    Args:
        state: 전송할 데이터 딕셔너리 (자동으로 JSON 변환)
    """
    if not connected_clients:
        return

    # 전송할 JSON 문자열 생성 (한 번만 변환)
    message = json.dumps(state, ensure_ascii=False)

    # 연결이 끊어진 클라이언트를 기록할 목록
    disconnected = set()

    for client in connected_clients.copy():
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)

    # 끊어진 연결 정리
    for client in disconnected:
        connected_clients.discard(client)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 연결 엔드포인트

    [브라우저에서 연결하는 방법]
    JavaScript:
        const ws = new WebSocket("ws://localhost:8000/ws");
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            // data에 크레인 상태, 충돌 결과 등이 들어있음
        };

    [동작 흐름]
    1. 브라우저의 WebSocket 연결 수락
    2. 연결된 클라이언트 목록에 추가
    3. 시뮬레이션 엔진에 브로드캐스트 콜백 등록
    4. 브라우저로부터 메시지 수신 대기 (크레인 제어 명령 등)
    5. 연결 종료 시 목록에서 제거
    """
    await websocket.accept()
    connected_clients.add(websocket)

    print(f"[WebSocket] 새 클라이언트 연결 (현재 {len(connected_clients)}명)")

    # 시뮬레이션 엔진에 브로드캐스트 콜백 등록
    from server.app import get_simulation_engine
    engine = get_simulation_engine()
    engine.set_on_update(broadcast_state)

    # 연결 즉시 현재 상태 전송
    try:
        initial_state = engine.get_full_state()
        await websocket.send_text(json.dumps(initial_state, ensure_ascii=False))
    except Exception:
        pass

    try:
        while True:
            # 브라우저로부터 메시지 수신 대기
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                await _handle_client_message(engine, message, websocket)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "error": "잘못된 JSON 형식입니다"
                }))

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[WebSocket] 클라이언트 연결 해제 (현재 {len(connected_clients)}명)")


async def _handle_client_message(
    engine, message: dict, websocket: WebSocket
) -> None:
    """
    브라우저에서 보낸 메시지를 처리합니다.

    [지원하는 메시지 타입]

    1. 크레인 속도 변경
    {
        "type": "control",
        "crane_id": "TC-1",
        "slew_speed": 0.5
    }

    2. 시나리오 적용
    {
        "type": "scenario",
        "scenario_id": "approaching"
    }

    3. 시뮬레이션 속도 변경
    {
        "type": "sim_speed",
        "speed": 2.0
    }

    4. 모든 크레인 정지
    {
        "type": "stop_all"
    }
    """
    msg_type = message.get("type", "")

    if msg_type == "control":
        # 크레인 제어
        crane_id = message.get("crane_id")
        if crane_id:
            if "slew_speed" in message:
                engine.set_crane_slew_speed(crane_id, message["slew_speed"])
            if "luffing_speed" in message:
                engine.set_crane_luffing_speed(crane_id, message["luffing_speed"])
            if "slew_angle" in message:
                engine.set_crane_slew_angle(crane_id, message["slew_angle"])
            if "luffing_angle" in message:
                engine.set_crane_luffing_angle(crane_id, message["luffing_angle"])

        await websocket.send_text(json.dumps({"ack": True, "type": "control"}))

    elif msg_type == "scenario":
        # 시나리오 적용
        from simulator.scenarios import apply_scenario
        scenario_id = message.get("scenario_id", "")
        success = apply_scenario(engine, scenario_id)
        await websocket.send_text(json.dumps({
            "ack": True,
            "type": "scenario",
            "success": success,
            "scenario_id": scenario_id,
        }))

    elif msg_type == "sim_speed":
        # 시뮬레이션 속도
        speed = message.get("speed", 1.0)
        engine.speed_multiplier = max(0.1, min(10.0, speed))
        await websocket.send_text(json.dumps({
            "ack": True,
            "type": "sim_speed",
            "speed": engine.speed_multiplier,
        }))

    elif msg_type == "stop_all":
        # 모든 크레인 정지
        for crane in engine.collision_engine.cranes.values():
            crane.slew_speed = 0.0
            crane.luffing_speed = 0.0
        await websocket.send_text(json.dumps({
            "ack": True,
            "type": "stop_all",
        }))

    else:
        await websocket.send_text(json.dumps({
            "error": f"알 수 없는 메시지 타입: {msg_type}"
        }))
