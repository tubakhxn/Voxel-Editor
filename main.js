import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.1/build/three.module.js";

const GRID_COLS = 14;
const GRID_ROWS = 7;
const CELL_STEP = 0.8;
const CELL_SIZE = 0.68;
const PINCH_THRESHOLD = 0.045;

const COLORS = {
	grid: 0x69d8e0,
	block: 0x6edfe7,
	blockOpacity: 0.88,
	highlight: 0xcdf68c,
	highlightWire: 0xdefcc1,
};
const state = {
	blockCount: 0,
	isPinching: false,
	currentCell: { x: 0, y: 0 },
	pinchMode: null,
	lastCellKey: null,
};
const blockCountEl = document.getElementById("blockCount");
const modeLabelEl = document.getElementById("modeLabel");
const container = document.getElementById("scene-container");
const overlayCanvas = document.getElementById("hand-overlay");
const overlayCtx = overlayCanvas.getContext("2d");
const videoElement = document.getElementById("webcam");
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.toneMappingExposure = 1.2;
container.appendChild(renderer.domElement);

const aspectHeight = GRID_ROWS * CELL_STEP;
const aspectWidth = GRID_COLS * CELL_STEP;
const camera = new THREE.OrthographicCamera(
	-aspectWidth * 0.55,
	aspectWidth * 0.55,
	aspectHeight * 0.4,
	-aspectHeight * 0.65,
	0.1,
	50
);
camera.position.set(0, 0, 10);

const scene = new THREE.Scene();
scene.background = null;

const ambient = new THREE.AmbientLight(0xffffff, 0.9);
const dir = new THREE.DirectionalLight(0xffffff, 0.65);
dir.position.set(-2, 2, 5);
scene.add(ambient, dir);
const gridLines = buildGridLines();
scene.add(gridLines);

const voxelGeometry = new THREE.BoxGeometry(CELL_SIZE, CELL_SIZE, CELL_SIZE);
const blockMaterial = new THREE.MeshPhongMaterial({
	color: COLORS.block,
	emissive: 0x2c9aa5,
	emissiveIntensity: 0.08,
	transparent: true,
	opacity: COLORS.blockOpacity,
	shininess: 90,
});

const highlightMaterial = new THREE.MeshPhongMaterial({
	color: COLORS.highlight,
	transparent: true,
	opacity: 0.75,
	shininess: 5,
});
const highlightCube = new THREE.Mesh(voxelGeometry, highlightMaterial);
const highlightEdges = new THREE.LineSegments(
	new THREE.EdgesGeometry(voxelGeometry),
	new THREE.LineBasicMaterial({ color: COLORS.highlightWire, linewidth: 2 })
);
highlightCube.add(highlightEdges);
highlightCube.visible = false;
scene.add(highlightCube);

const blockMap = new Map();
function buildGridLines() {
	const positions = [];
	const width = (GRID_COLS - 1) * CELL_STEP;
	const height = (GRID_ROWS - 1) * CELL_STEP;
	const left = -width / 2;
	const top = height / 2;
	for (let c = 0; c < GRID_COLS; c += 1) {
		const x = left + c * CELL_STEP;
		positions.push(x, top, 0, x, top - height, 0);
	}
	for (let r = 0; r < GRID_ROWS; r += 1) {
		const y = top - r * CELL_STEP;
		positions.push(left, y, 0, left + width, y, 0);
	}

	const geometry = new THREE.BufferGeometry();
	geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
	return new THREE.LineSegments(
		geometry,
		new THREE.LineBasicMaterial({
			color: COLORS.grid,
			transparent: true,
			opacity: 0.55,
			linewidth: 2,
		})
	);
}

function cellToWorld(x, y) {
	const originX = -((GRID_COLS - 1) * CELL_STEP) / 2;
	const originY = ((GRID_ROWS - 1) * CELL_STEP) / 2;
	return {
		x: originX + x * CELL_STEP,
		y: originY - y * CELL_STEP,
	};
}

function updateHighlight(cellX, cellY) {
	const { x, y } = cellToWorld(cellX, cellY);
	highlightCube.position.set(x, y, 0);
	highlightCube.visible = true;
	state.currentCell = { x: cellX, y: cellY };
}

function setModeLabel(text) {
	modeLabelEl.textContent = text;
}

function updateBlockCount() {
	blockCountEl.textContent = state.blockCount.toString().padStart(2, "0");
}

function addBlock(cellX, cellY) {
	const key = `${cellX},${cellY}`;
	if (blockMap.has(key)) {
		return false;
	}
	const mesh = new THREE.Mesh(voxelGeometry, blockMaterial.clone());
	const { x, y } = cellToWorld(cellX, cellY);
	mesh.position.set(x, y, 0.05);
	mesh.rotation.z = 0.02;
	blockMap.set(key, mesh);
	scene.add(mesh);
	state.blockCount += 1;
	updateBlockCount();
	return true;
}

function removeBlock(cellX, cellY) {
	const key = `${cellX},${cellY}`;
	if (!blockMap.has(key)) {
		return false;
	}
	const mesh = blockMap.get(key);
	scene.remove(mesh);
	blockMap.delete(key);
	state.blockCount -= 1;
	updateBlockCount();
	return true;
}

function handleGesture(landmarks) {
	const indexTip = landmarks[8];
	const thumbTip = landmarks[4];
	const pinchDistance = Math.hypot(
	indexTip.x - thumbTip.x,
	indexTip.y - thumbTip.y,
	(indexTip.z || 0) - (thumbTip.z || 0)
	);
	const pointerX = 1 - indexTip.x;
	const pointerY = indexTip.y;
	const cellX = THREE.MathUtils.clamp(Math.floor(pointerX * GRID_COLS), 0, GRID_COLS - 1);
	const cellY = THREE.MathUtils.clamp(Math.floor(pointerY * GRID_ROWS), 0, GRID_ROWS - 1);
	updateHighlight(cellX, cellY);

	const pinchActive = pinchDistance < PINCH_THRESHOLD;
	if (pinchActive) {
		handlePinch(cellX, cellY);
	} else {
		resetPinch();
	}
}

function handlePinch(cellX, cellY) {
	const cellKey = `${cellX},${cellY}`;
	if (!state.isPinching) {
		state.isPinching = true;
		state.pinchMode = blockMap.has(cellKey) ? "erase" : "draw";
		applyPinch(cellX, cellY);
		state.lastCellKey = cellKey;
		return;
	}

	if (cellKey !== state.lastCellKey) {
		applyPinch(cellX, cellY);
		state.lastCellKey = cellKey;
	}
}

function resetPinch() {
	if (!state.isPinching) {
		return;
	}
	state.isPinching = false;
	state.pinchMode = null;
	state.lastCellKey = null;
	setModeLabel("TRACK");
}

function applyPinch(cellX, cellY) {
	if (state.pinchMode === "draw") {
		addBlock(cellX, cellY);
		setModeLabel("DRAW");
		return;
	}
	if (state.pinchMode === "erase") {
		removeBlock(cellX, cellY);
		setModeLabel("ERASE");
	}
}

function drawHandOverlay(results) {
	overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
	if (!results.multiHandLandmarks || !results.multiHandLandmarks.length) {
		return;
	}

	overlayCtx.lineWidth = 2.5;
	overlayCtx.strokeStyle = "rgba(105, 214, 224, 0.55)";
	overlayCtx.fillStyle = "rgba(205, 246, 140, 0.85)";

	results.multiHandLandmarks.forEach((landmarks) => {
		overlayCtx.beginPath();
		landmarks.forEach((point, idx) => {
			const canvasX = (1 - point.x) * overlayCanvas.width;
	const canvasY = point.y * overlayCanvas.height;
	overlayCtx.moveTo(canvasX, canvasY);
	overlayCtx.arc(canvasX, canvasY, idx === 8 ? 8 : 5, 0, Math.PI * 2);
		});
		overlayCtx.fill();
	});
}

function onResults(results) {
	drawHandOverlay(results);
	if (results.multiHandLandmarks && results.multiHandLandmarks.length) {
		handleGesture(results.multiHandLandmarks[0]);
	} else {
		highlightCube.visible = false;
		resetPinch();
		setModeLabel("IDLE");
	}
}

function resize() {
	const { innerWidth, innerHeight } = window;
	renderer.setSize(innerWidth, innerHeight);
	overlayCanvas.width = innerWidth;
	overlayCanvas.height = innerHeight;
}

resize();
window.addEventListener("resize", resize);

function animate() {
	requestAnimationFrame(animate);
	renderer.render(scene, camera);
}

animate();
const hands = new Hands({
	locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/${file}`,
});
hands.setOptions({
	maxNumHands: 1,
	modelComplexity: 1,
	minDetectionConfidence: 0.6,
	minTrackingConfidence: 0.5,
});
hands.onResults(onResults);

const cameraFeed = new Camera(videoElement, {
	onFrame: async () => {
		await hands.send({ image: videoElement });
	},
	width: 1280,
	height: 720,
});

cameraFeed.start().catch((error) => {
	console.error("Unable to start camera", error);
	setModeLabel("CAMERA ERROR");
});
