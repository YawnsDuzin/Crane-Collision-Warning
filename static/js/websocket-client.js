/**
 * WebSocket 클라이언트 모듈
 * ==========================
 *
 * 서버와의 실시간 통신을 담당합니다.
 *
 * [WebSocket 통신 흐름]
 *
 *  브라우저 (이 파일)                    서버 (websocket.py)
 *       │                                    │
 *       │── 1. 연결 요청 ──────────────────→ │
 *       │                                    │
 *       │←── 2. 연결 확인 ───────────────── │
 *       │                                    │
 *       │←── 3. 초기 상태 데이터 ────────── │
 *       │                                    │
 *       │←── 4. 실시간 데이터 (0.2초마다) ── │
 *       │    → onDataReceived() 호출          │
 *       │    → 3D 뷰 업데이트               │
 *       │    → UI 업데이트                   │
 *       │                                    │
 *       │── 5. 크레인 제어 명령 ──────────→  │
 *       │                                    │
 *       │←── 6. 확인 응답 ─────────────────  │
 *       │                                    │
 *
 * [자동 재연결]
 * 네트워크 문제로 연결이 끊어지면 자동으로 다시 연결을 시도합니다.
 * 3초 간격으로 최대 무한 재시도합니다.
 */

// ============================================================
// 전역 변수
// ============================================================
let ws = null;                    // WebSocket 연결 객체
let isConnected = false;          // 연결 상태
let reconnectTimer = null;        // 재연결 타이머
let lastData = null;              // 마지막으로 받은 데이터
const RECONNECT_INTERVAL = 3000;  // 재연결 시도 간격 (3초)

// ============================================================
// 연결 관리
// ============================================================

/**
 * WebSocket 서버에 연결합니다.
 */
function connectWebSocket() {
    // 이미 연결 중이면 무시
    if (ws && ws.readyState === WebSocket.OPEN) return;

    // WebSocket URL 생성 (현재 페이지의 호스트 사용)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    console.log(`[WebSocket] 연결 시도: ${wsUrl}`);

    try {
        ws = new WebSocket(wsUrl);
    } catch (e) {
        console.error('[WebSocket] 연결 생성 실패:', e);
        scheduleReconnect();
        return;
    }

    // --- 연결 성공 ---
    ws.onopen = function () {
        console.log('[WebSocket] 연결 성공');
        isConnected = true;
        updateConnectionStatus(true);

        // 재연결 타이머 정리
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
    };

    // --- 데이터 수신 ---
    ws.onmessage = function (event) {
        try {
            const data = JSON.parse(event.data);
            lastData = data;

            // 에러 응답 처리
            if (data.error) {
                console.warn('[WebSocket] 서버 오류:', data.error);
                return;
            }

            // 확인 응답 (ack) 처리
            if (data.ack) {
                return;
            }

            // 상태 데이터 처리
            onDataReceived(data);

        } catch (e) {
            console.error('[WebSocket] 데이터 파싱 오류:', e);
        }
    };

    // --- 연결 종료 ---
    ws.onclose = function (event) {
        console.log('[WebSocket] 연결 종료 (코드:', event.code, ')');
        isConnected = false;
        updateConnectionStatus(false);
        scheduleReconnect();
    };

    // --- 에러 ---
    ws.onerror = function (error) {
        console.error('[WebSocket] 오류 발생');
        isConnected = false;
        updateConnectionStatus(false);
    };
}

/**
 * 재연결을 예약합니다.
 */
function scheduleReconnect() {
    if (reconnectTimer) return;  // 이미 예약됨

    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        console.log('[WebSocket] 재연결 시도...');
        connectWebSocket();
    }, RECONNECT_INTERVAL);
}

/**
 * 연결 상태를 화면에 표시합니다.
 */
function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('connection-status');
    if (!statusEl) return;

    if (connected) {
        statusEl.textContent = '연결됨';
        statusEl.className = 'status-connected';
    } else {
        statusEl.textContent = '연결 끊김';
        statusEl.className = 'status-disconnected';
    }
}

// ============================================================
// 메시지 전송
// ============================================================

/**
 * 서버에 메시지를 보냅니다.
 *
 * @param {Object} message - 보낼 메시지 객체
 */
function sendMessage(message) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.warn('[WebSocket] 연결되지 않아 메시지를 보낼 수 없습니다');
        return false;
    }

    try {
        ws.send(JSON.stringify(message));
        return true;
    } catch (e) {
        console.error('[WebSocket] 메시지 전송 실패:', e);
        return false;
    }
}

/**
 * 크레인 제어 명령을 보냅니다.
 *
 * @param {string} craneId - 크레인 ID
 * @param {Object} controls - 제어 값 { slew_speed, luffing_speed, ... }
 */
function sendCraneControl(craneId, controls) {
    return sendMessage({
        type: 'control',
        crane_id: craneId,
        ...controls,
    });
}

/**
 * 시나리오 적용 명령을 보냅니다.
 *
 * @param {string} scenarioId - 시나리오 ID
 */
function sendScenarioApply(scenarioId) {
    return sendMessage({
        type: 'scenario',
        scenario_id: scenarioId,
    });
}

/**
 * 모든 크레인 정지 명령을 보냅니다.
 */
function sendStopAll() {
    return sendMessage({ type: 'stop_all' });
}

/**
 * 시뮬레이션 속도 변경 명령을 보냅니다.
 *
 * @param {number} speed - 속도 배율 (1.0 = 실시간)
 */
function sendSimSpeed(speed) {
    return sendMessage({
        type: 'sim_speed',
        speed: speed,
    });
}
