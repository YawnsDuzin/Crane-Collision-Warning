/**
 * Three.js 3D 시각화 모듈
 * ========================
 *
 * 이 파일은 3D 공간에서 크레인을 시각적으로 표현합니다.
 *
 * [Three.js 기본 개념]
 * Three.js는 웹에서 3D 그래픽을 그리는 라이브러리입니다.
 *
 * 필요한 3가지 요소:
 * 1. Scene (장면): 3D 물체들이 놓이는 공간
 * 2. Camera (카메라): 장면을 어디서 바라볼지
 * 3. Renderer (렌더러): 카메라가 본 것을 화면에 그림
 *
 * [크레인 3D 표현]
 * 각 크레인은 다음 요소로 구성됩니다:
 * - 마스트 (기둥): 가느다란 직육면체
 * - 붐대 (팔): 회전하는 긴 막대
 * - 작업 반경: 반투명 원 (바닥에 표시)
 * - 라벨: 크레인 이름 표시
 *
 * [좌표 체계]
 * Three.js: X(오른쪽), Y(위), Z(앞쪽)
 * 우리 시스템: X(동쪽), Y(북쪽), Z(높이)
 * → Y와 Z를 교환하여 매핑합니다
 */

// ============================================================
// 전역 변수
// ============================================================
let scene, camera, renderer, controls;
let craneObjects = {};  // 크레인 3D 객체들 { "TC-1": { mast, boom, ... }, ... }
let gridHelper, axesHelper;
let isInitialized = false;

// 색상 상수
const CRANE_COLORS = [
    0x4a90d9,  // 파랑
    0xe67e22,  // 주황
    0x2ecc71,  // 초록
    0x9b59b6,  // 보라
    0xe74c3c,  // 빨강
    0x1abc9c,  // 청록
];

const ALERT_LEVEL_COLORS = {
    "NORMAL": 0x00CC00,
    "CAUTION": 0xFFD700,
    "WARNING": 0xFF8C00,
    "DANGER": 0xFF0000,
};

// ============================================================
// 초기화
// ============================================================

/**
 * 3D 장면을 초기화합니다.
 * 페이지 로드 시 한 번만 호출됩니다.
 */
function initThreeScene() {
    const container = document.getElementById('three-canvas-wrapper');
    if (!container) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    // 1. 장면 생성
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a1e);  // 어두운 배경
    scene.fog = new THREE.Fog(0x0a0a1e, 300, 600);  // 안개 효과 (원거리 물체 흐리게)

    // 2. 카메라 생성
    // PerspectiveCamera: 원근법이 적용된 카메라 (가까운 건 크게, 먼 건 작게)
    camera = new THREE.PerspectiveCamera(
        60,              // 시야각 (도)
        width / height,  // 화면 비율
        0.1,             // 최소 렌더링 거리
        1000             // 최대 렌더링 거리
    );
    camera.position.set(100, 120, 150);  // 카메라 위치 (비스듬히 위에서)
    camera.lookAt(40, 0, 30);            // 현장 중심을 바라봄

    // 3. 렌더러 생성
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    // 4. 카메라 컨트롤 (마우스로 회전/확대)
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;    // 부드러운 감속
    controls.dampingFactor = 0.05;
    controls.target.set(40, 0, 30);   // 회전 중심점
    controls.update();

    // 5. 조명 설정
    setupLighting();

    // 6. 바닥 그리드 생성
    setupGround();

    // 7. 창 크기 변경 대응
    window.addEventListener('resize', onWindowResize);

    // 8. 애니메이션 루프 시작
    isInitialized = true;
    animate();
}

/**
 * 조명을 설정합니다.
 */
function setupLighting() {
    // 주변광 (전체적으로 밝게)
    const ambientLight = new THREE.AmbientLight(0x404060, 0.6);
    scene.add(ambientLight);

    // 방향광 (그림자 생성)
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(100, 200, 100);
    directionalLight.castShadow = true;
    scene.add(directionalLight);

    // 반대편에서 오는 보조광
    const fillLight = new THREE.DirectionalLight(0x8888cc, 0.3);
    fillLight.position.set(-100, 100, -100);
    scene.add(fillLight);
}

/**
 * 바닥 그리드를 생성합니다.
 * 현장의 지면을 격자 무늬로 표현합니다.
 */
function setupGround() {
    // 격자 (10m 간격, 300m × 300m)
    gridHelper = new THREE.GridHelper(300, 30, 0x2a2a4e, 0x1a1a3e);
    gridHelper.position.set(50, 0, 50);
    scene.add(gridHelper);

    // 바닥 평면 (반투명)
    const groundGeometry = new THREE.PlaneGeometry(300, 300);
    const groundMaterial = new THREE.MeshPhongMaterial({
        color: 0x111122,
        transparent: true,
        opacity: 0.5,
    });
    const ground = new THREE.Mesh(groundGeometry, groundMaterial);
    ground.rotation.x = -Math.PI / 2;  // 수평으로 눕히기
    ground.position.set(50, -0.1, 50);
    ground.receiveShadow = true;
    scene.add(ground);

    // 방위 표시 (N, E, S, W)
    addDirectionMarker('N', 50, 0, -10, 0x4a90d9);
    addDirectionMarker('E', 160, 0, 50, 0x888888);
    addDirectionMarker('S', 50, 0, 110, 0x888888);
    addDirectionMarker('W', -60, 0, 50, 0x888888);
}

/**
 * 방위 표시 텍스트를 추가합니다.
 */
function addDirectionMarker(text, x, y, z, color) {
    // 간단한 표시용 구체로 대체
    const geometry = new THREE.SphereGeometry(1.5, 8, 8);
    const material = new THREE.MeshBasicMaterial({ color: color });
    const marker = new THREE.Mesh(geometry, material);
    marker.position.set(x, y + 1, z);
    scene.add(marker);
}

// ============================================================
// 크레인 3D 객체 생성/업데이트
// ============================================================

/**
 * 크레인의 3D 모델을 생성합니다.
 *
 * [구성 요소]
 * 1. 기초 (base): 바닥의 작은 직육면체
 * 2. 마스트 (mast): 수직 기둥
 * 3. 붐대 (boom): 수평 팔 (회전)
 * 4. 작업 반경 (radius): 바닥의 반투명 원
 * 5. 연결선 (line): 붐대에서 지면까지의 와이어 표현
 *
 * @param {Object} craneData - 크레인 상태 데이터
 * @param {number} colorIndex - 색상 인덱스
 */
function createCraneObject(craneData, colorIndex) {
    const color = CRANE_COLORS[colorIndex % CRANE_COLORS.length];
    const group = new THREE.Group();
    group.name = craneData.id;

    // 좌표 변환: 우리 시스템(X,Y,Z) → Three.js(X,Z,Y를 뒤집음)
    // 우리: X=동, Y=북, Z=높이
    // Three.js: X=오른쪽, Y=위, Z=앞쪽
    const baseX = craneData.base_x;
    const baseZ = craneData.base_y;  // Y→Z
    const mastH = craneData.mast_height;
    const boomL = craneData.boom_length;

    // --- 1. 기초 ---
    const baseGeom = new THREE.BoxGeometry(4, 2, 4);
    const baseMat = new THREE.MeshPhongMaterial({ color: 0x555555 });
    const baseMesh = new THREE.Mesh(baseGeom, baseMat);
    baseMesh.position.set(0, 1, 0);
    baseMesh.castShadow = true;
    group.add(baseMesh);

    // --- 2. 마스트 (기둥) ---
    const mastGeom = new THREE.BoxGeometry(2, mastH, 2);
    const mastMat = new THREE.MeshPhongMaterial({ color: color });
    const mastMesh = new THREE.Mesh(mastGeom, mastMat);
    mastMesh.position.set(0, mastH / 2, 0);
    mastMesh.castShadow = true;
    group.add(mastMesh);

    // --- 3. 붐대 (팔) - 별도 그룹으로 회전 가능하게 ---
    const boomGroup = new THREE.Group();
    boomGroup.position.set(0, mastH, 0);  // 마스트 꼭대기에 위치

    const boomGeom = new THREE.BoxGeometry(boomL, 1.2, 1.2);
    const boomMat = new THREE.MeshPhongMaterial({ color: color, emissive: color, emissiveIntensity: 0.1 });
    const boomMesh = new THREE.Mesh(boomGeom, boomMat);
    boomMesh.position.set(boomL / 2, 0, 0);  // 한쪽 끝이 회전축
    boomMesh.castShadow = true;
    boomGroup.add(boomMesh);

    // 붐대 끝점 표시 (작은 구체)
    const tipGeom = new THREE.SphereGeometry(1.5, 8, 8);
    const tipMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const tipMesh = new THREE.Mesh(tipGeom, tipMat);
    tipMesh.position.set(boomL, 0, 0);
    boomGroup.add(tipMesh);

    group.add(boomGroup);

    // --- 4. 작업 반경 표시 (바닥의 원) ---
    const radiusGeom = new THREE.RingGeometry(boomL - 1, boomL + 1, 64);
    const radiusMat = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.15,
        side: THREE.DoubleSide,
    });
    const radiusMesh = new THREE.Mesh(radiusGeom, radiusMat);
    radiusMesh.rotation.x = -Math.PI / 2;
    radiusMesh.position.set(0, 0.5, 0);
    group.add(radiusMesh);

    // 작업 반경 원 (외곽선)
    const circleGeom = new THREE.BufferGeometry();
    const circlePoints = [];
    for (let i = 0; i <= 64; i++) {
        const angle = (i / 64) * Math.PI * 2;
        circlePoints.push(new THREE.Vector3(
            Math.cos(angle) * boomL,
            0.5,
            Math.sin(angle) * boomL
        ));
    }
    circleGeom.setFromPoints(circlePoints);
    const circleMat = new THREE.LineBasicMaterial({ color: color, transparent: true, opacity: 0.4 });
    const circleLine = new THREE.Line(circleGeom, circleMat);
    group.add(circleLine);

    // 그룹을 현장 좌표로 이동
    group.position.set(baseX, 0, baseZ);

    scene.add(group);

    // 객체 저장
    craneObjects[craneData.id] = {
        group: group,
        boomGroup: boomGroup,
        boomMesh: boomMesh,
        tipMesh: tipMesh,
        radiusMesh: radiusMesh,
        circleLine: circleLine,
        color: color,
        mastHeight: mastH,
        boomLength: boomL,
    };
}

/**
 * 크레인의 3D 위치를 업데이트합니다.
 *
 * @param {Object} craneData - 크레인 상태 데이터
 * @param {string} alertLevel - 현재 위험 등급
 */
function updateCraneObject(craneData, alertLevel) {
    const obj = craneObjects[craneData.id];
    if (!obj) return;

    // 선회각 적용 (Y축 기준 회전)
    // Three.js의 Y축 회전은 반시계방향이 양수이므로,
    // 시계방향인 우리 선회각을 음수로 변환
    const slewRad = -craneData.slew_angle * (Math.PI / 180);
    obj.boomGroup.rotation.y = slewRad;

    // 기복각 적용 (Z축 기준 회전)
    const luffRad = craneData.luffing_angle * (Math.PI / 180);
    obj.boomGroup.rotation.z = luffRad;

    // 위험 등급에 따른 색상 변경
    if (alertLevel && alertLevel !== "NORMAL") {
        const alertColor = ALERT_LEVEL_COLORS[alertLevel] || obj.color;
        obj.tipMesh.material.color.setHex(alertColor);

        // 위험 등급이 높으면 작업 반경도 색상 변경
        if (alertLevel === "DANGER" || alertLevel === "WARNING") {
            obj.radiusMesh.material.color.setHex(alertColor);
            obj.radiusMesh.material.opacity = 0.25;
        }
    } else {
        obj.tipMesh.material.color.setHex(0xffffff);
        obj.radiusMesh.material.color.setHex(obj.color);
        obj.radiusMesh.material.opacity = 0.15;
    }
}

/**
 * 두 크레인 사이에 경고 선을 그립니다.
 *
 * @param {Object} collision - 충돌 검사 결과
 */
let warningLines = [];

function updateWarningLines(collisions) {
    // 기존 경고 선 제거
    warningLines.forEach(line => scene.remove(line));
    warningLines = [];

    if (!collisions) return;

    collisions.forEach(collision => {
        if (collision.alert_level === "NORMAL") return;

        const objA = craneObjects[collision.crane_a_id];
        const objB = craneObjects[collision.crane_b_id];
        if (!objA || !objB) return;

        // 붐대 끝점 위치 계산 (대략적)
        const posA = new THREE.Vector3();
        objA.tipMesh.getWorldPosition(posA);

        const posB = new THREE.Vector3();
        objB.tipMesh.getWorldPosition(posB);

        // 경고 선 그리기
        const color = ALERT_LEVEL_COLORS[collision.alert_level] || 0xFFFFFF;
        const geometry = new THREE.BufferGeometry().setFromPoints([posA, posB]);
        const material = new THREE.LineBasicMaterial({
            color: color,
            linewidth: 2,
        });

        // 점선 효과를 위해 LineDashedMaterial 사용
        const dashedMaterial = new THREE.LineDashedMaterial({
            color: color,
            dashSize: 3,
            gapSize: 2,
        });

        const line = new THREE.Line(geometry, dashedMaterial);
        line.computeLineDistances();
        scene.add(line);
        warningLines.push(line);
    });
}

// ============================================================
// 전체 3D 장면 업데이트
// ============================================================

/**
 * 서버에서 받은 데이터로 전체 3D 장면을 업데이트합니다.
 * WebSocket에서 새 데이터를 받을 때마다 호출됩니다.
 *
 * @param {Object} state - 서버에서 받은 전체 상태 데이터
 */
function updateThreeScene(state) {
    if (!isInitialized || !state) return;

    const cranes = state.cranes || [];
    const collisions = state.collisions || [];
    const craneAlerts = state.status?.crane_alerts || {};

    // 크레인 객체가 없으면 생성
    cranes.forEach((craneData, index) => {
        if (!craneObjects[craneData.id]) {
            createCraneObject(craneData, index);
        }
        updateCraneObject(craneData, craneAlerts[craneData.id]);
    });

    // 삭제된 크레인 제거
    Object.keys(craneObjects).forEach(id => {
        if (!cranes.find(c => c.id === id)) {
            scene.remove(craneObjects[id].group);
            delete craneObjects[id];
        }
    });

    // 경고 선 업데이트
    updateWarningLines(collisions);
}

// ============================================================
// 카메라 뷰 제어
// ============================================================

function resetCamera() {
    camera.position.set(100, 120, 150);
    controls.target.set(40, 0, 30);
    controls.update();
}

function toggleTopView() {
    camera.position.set(40, 200, 30);
    controls.target.set(40, 0, 30);
    controls.update();
}

function toggleSideView() {
    camera.position.set(40, 60, 200);
    controls.target.set(40, 30, 30);
    controls.update();
}

// ============================================================
// 창 크기 변경 대응
// ============================================================
function onWindowResize() {
    const container = document.getElementById('three-canvas-wrapper');
    if (!container) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
}

// ============================================================
// 애니메이션 루프
// ============================================================
function animate() {
    requestAnimationFrame(animate);
    if (controls) controls.update();
    if (renderer && scene && camera) {
        renderer.render(scene, camera);
    }
}
