/**
 * 메인 JavaScript 모듈
 * ======================
 *
 * 이 파일은 관제 화면의 전체 동작을 제어합니다.
 *
 * [역할]
 * 1. 페이지 로드 시 초기화 (3D 장면, WebSocket 연결)
 * 2. 서버에서 받은 데이터로 UI 업데이트
 * 3. 사용자 입력(슬라이더, 버튼) 처리
 * 4. 시간 표시 등 유틸리티
 *
 * [데이터 흐름]
 * 서버 → WebSocket → onDataReceived() → updateUI() + updateThreeScene()
 */

// ============================================================
// 전역 상태
// ============================================================
let selectedCraneId = null;  // 현재 선택된 크레인 ID
let currentState = null;     // 최근 수신 데이터

// ============================================================
// 페이지 초기화
// ============================================================

/**
 * 페이지 로드 완료 시 실행됩니다.
 */
window.addEventListener('DOMContentLoaded', function () {
    console.log('크레인 충돌 예측 시스템 초기화...');

    // 1. 시간 표시 시작
    updateClock();
    setInterval(updateClock, 1000);

    // 2. 3D 장면 초기화
    initThreeScene();

    // 3. WebSocket 연결
    connectWebSocket();

    // 4. 시나리오 목록 로드
    loadScenarios();

    console.log('초기화 완료');
});

// ============================================================
// 데이터 수신 처리
// ============================================================

/**
 * WebSocket에서 새 데이터를 받았을 때 호출됩니다.
 * (websocket-client.js에서 호출)
 *
 * @param {Object} state - 서버에서 받은 전체 상태 데이터
 */
function onDataReceived(state) {
    currentState = state;

    // 1. 3D 장면 업데이트
    updateThreeScene(state);

    // 2. UI 업데이트
    updateStatusSummary(state);
    updateCollisionTable(state);
    updateAlertMessages(state);
    updateEventLog(state);
    updateCraneSelector(state);
    updateSelectedCraneInfo(state);
}

// ============================================================
// UI 업데이트 함수들
// ============================================================

/**
 * 상태 요약 패널을 업데이트합니다.
 */
function updateStatusSummary(state) {
    if (!state || !state.status) return;

    const status = state.status;
    const cranes = state.cranes || [];

    // 크레인 수
    setTextContent('total-cranes', cranes.length);

    // 등급별 크레인 수 계산
    const craneAlerts = status.crane_alerts || {};
    let counts = { NORMAL: 0, CAUTION: 0, WARNING: 0, DANGER: 0 };
    Object.values(craneAlerts).forEach(level => {
        counts[level] = (counts[level] || 0) + 1;
    });

    setTextContent('count-normal', counts.NORMAL);
    setTextContent('count-caution', counts.CAUTION);
    setTextContent('count-warning', counts.WARNING);
    setTextContent('count-danger', counts.DANGER);
}

/**
 * 충돌 검사 결과 테이블을 업데이트합니다.
 */
function updateCollisionTable(state) {
    const tbody = document.getElementById('collision-tbody');
    if (!tbody || !state) return;

    const collisions = state.collisions || [];
    const cranes = state.cranes || [];

    // 크레인 이름 매핑
    const nameMap = {};
    cranes.forEach(c => { nameMap[c.id] = c.name; });

    let html = '';
    collisions.forEach(col => {
        const nameA = nameMap[col.crane_a_id] || col.crane_a_id;
        const nameB = nameMap[col.crane_b_id] || col.crane_b_id;
        const levelKo = getLevelKorean(col.alert_level);
        const ttc = col.time_to_collision !== null
            ? `${col.time_to_collision}초 후`
            : '-';

        html += `<tr class="row-${col.alert_level}">
            <td>${nameA} ↔ ${nameB}</td>
            <td>${col.current_distance}m</td>
            <td>${col.boom_tip_distance}m</td>
            <td>${ttc}</td>
            <td>${levelKo}</td>
        </tr>`;
    });

    if (html === '') {
        html = '<tr><td colspan="5" style="text-align:center; color: #666;">검사 대상 없음</td></tr>';
    }

    tbody.innerHTML = html;
}

/**
 * 경고 메시지 영역을 업데이트합니다.
 */
function updateAlertMessages(state) {
    const container = document.getElementById('alert-messages');
    if (!container || !state) return;

    const alerts = state.alerts || [];

    if (alerts.length === 0) {
        container.innerHTML = '<div class="no-alerts">경고 없음 - 모든 크레인 안전</div>';
        return;
    }

    let html = '';
    alerts.forEach(alert => {
        html += `<div class="alert-item alert-${alert.alert_level}">
            ${alert.message}
        </div>`;
    });

    container.innerHTML = html;
}

/**
 * 이벤트 로그를 업데이트합니다.
 */
function updateEventLog(state) {
    const container = document.getElementById('event-log');
    if (!container || !state || !state.status) return;

    const events = state.status.recent_events || [];

    if (events.length === 0) {
        container.innerHTML = '<div style="color: #666; font-size: 0.8em;">이벤트 없음</div>';
        return;
    }

    // 최신 이벤트가 위에 오도록 역순
    let html = '';
    for (let i = events.length - 1; i >= 0; i--) {
        const evt = events[i];
        const time = formatTimestamp(evt.timestamp);
        const fromKo = getLevelKorean(evt.from_level);
        const toKo = getLevelKorean(evt.to_level);

        html += `<div class="event-item">
            <span class="event-time">${time}</span>
            ${evt.pair}: ${fromKo} → ${toKo} (${evt.distance.toFixed(1)}m)
        </div>`;
    }

    container.innerHTML = html;
}

/**
 * 크레인 선택 드롭다운을 업데이트합니다.
 */
function updateCraneSelector(state) {
    const select = document.getElementById('select-crane');
    if (!select || !state) return;

    const cranes = state.cranes || [];
    const currentValue = select.value;

    // 옵션 수가 변했을 때만 재생성
    if (select.options.length !== cranes.length + 1) {
        let html = '<option value="">-- 선택 --</option>';
        cranes.forEach(c => {
            html += `<option value="${c.id}">${c.name} (${c.id})</option>`;
        });
        select.innerHTML = html;
        select.value = currentValue;
    }
}

/**
 * 선택된 크레인의 상세 정보를 업데이트합니다.
 */
function updateSelectedCraneInfo(state) {
    if (!selectedCraneId || !state) return;

    const cranes = state.cranes || [];
    const crane = cranes.find(c => c.id === selectedCraneId);
    if (!crane) return;

    // 슬라이더와 정보 업데이트 (사용자가 조작 중이 아닐 때만)
    const slewSlider = document.getElementById('slew-angle-slider');
    if (slewSlider && document.activeElement !== slewSlider) {
        slewSlider.value = crane.slew_angle;
    }

    const slewSpeedSlider = document.getElementById('slew-speed-slider');
    if (slewSpeedSlider && document.activeElement !== slewSpeedSlider) {
        slewSpeedSlider.value = crane.slew_speed;
    }

    const luffSlider = document.getElementById('luffing-angle-slider');
    if (luffSlider && document.activeElement !== luffSlider) {
        luffSlider.value = crane.luffing_angle;
    }

    setTextContent('current-slew', crane.slew_angle.toFixed(1));
    setTextContent('current-slew-speed', crane.slew_speed.toFixed(1));
    setTextContent('current-luffing', crane.luffing_angle.toFixed(1));
    setTextContent('info-base-x', crane.base_x);
    setTextContent('info-base-y', crane.base_y);
    setTextContent('info-mast-height', crane.mast_height);
    setTextContent('info-boom-length', crane.boom_length);
    setTextContent('info-working-radius', crane.working_radius);
}

// ============================================================
// 사용자 입력 처리
// ============================================================

/**
 * 크레인 선택 변경 시 호출됩니다.
 */
function onCraneSelected() {
    const select = document.getElementById('select-crane');
    selectedCraneId = select.value || null;

    const detailPanel = document.getElementById('crane-detail');
    if (detailPanel) {
        detailPanel.style.display = selectedCraneId ? 'block' : 'none';
    }

    // 선택된 크레인 정보 즉시 업데이트
    if (currentState) {
        updateSelectedCraneInfo(currentState);
    }
}

/**
 * 선회각 슬라이더 변경 시
 */
function onSlewAngleChange(value) {
    if (!selectedCraneId) return;
    sendCraneControl(selectedCraneId, { slew_angle: parseFloat(value) });
    setTextContent('current-slew', parseFloat(value).toFixed(1));
}

/**
 * 선회 속도 슬라이더 변경 시
 */
function onSlewSpeedChange(value) {
    if (!selectedCraneId) return;
    sendCraneControl(selectedCraneId, { slew_speed: parseFloat(value) });
    setTextContent('current-slew-speed', parseFloat(value).toFixed(1));
}

/**
 * 기복각 슬라이더 변경 시
 */
function onLuffingAngleChange(value) {
    if (!selectedCraneId) return;
    sendCraneControl(selectedCraneId, { luffing_angle: parseFloat(value) });
    setTextContent('current-luffing', parseFloat(value).toFixed(1));
}

/**
 * 모든 크레인 정지 버튼
 */
function stopAllCranes() {
    sendStopAll();
}

/**
 * 시뮬레이션 속도 변경
 */
function onSimSpeedChange(value) {
    const speed = parseFloat(value);
    sendSimSpeed(speed);
    setTextContent('sim-speed-label', speed.toFixed(1));
}

// ============================================================
// 시나리오 관련
// ============================================================

/**
 * 서버에서 시나리오 목록을 로드합니다.
 */
async function loadScenarios() {
    try {
        const response = await fetch('/api/scenarios');
        const data = await response.json();
        const scenarios = data.scenarios || [];

        const container = document.getElementById('scenario-list');
        if (!container) return;

        let html = '';
        scenarios.forEach(s => {
            html += `<button class="scenario-btn" data-id="${s.id}"
                        onclick="applyScenario('${s.id}')"
                        title="${s.description}">
                ${s.name}
            </button>`;
        });

        container.innerHTML = html;
    } catch (e) {
        console.error('시나리오 목록 로드 실패:', e);
    }
}

/**
 * 시나리오를 적용합니다.
 */
function applyScenario(scenarioId) {
    // 기존 3D 객체 정리
    Object.keys(craneObjects).forEach(id => {
        scene.remove(craneObjects[id].group);
    });
    craneObjects = {};

    // 서버에 시나리오 적용 요청
    sendScenarioApply(scenarioId);

    // 활성 버튼 표시
    document.querySelectorAll('.scenario-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.id === scenarioId);
    });
}

// ============================================================
// 유틸리티 함수
// ============================================================

/**
 * 현재 시각을 업데이트합니다.
 */
function updateClock() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('ko-KR', { hour12: false });
    setTextContent('current-time', timeStr);
}

/**
 * 타임스탬프를 시:분:초 형식으로 변환합니다.
 */
function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString('ko-KR', { hour12: false });
}

/**
 * 위험 등급을 한국어로 변환합니다.
 */
function getLevelKorean(level) {
    const map = {
        'NORMAL': '정상',
        'CAUTION': '주의',
        'WARNING': '경고',
        'DANGER': '위험',
    };
    return map[level] || level;
}

/**
 * 요소의 텍스트를 안전하게 설정합니다.
 */
function setTextContent(elementId, text) {
    const el = document.getElementById(elementId);
    if (el) el.textContent = text;
}
