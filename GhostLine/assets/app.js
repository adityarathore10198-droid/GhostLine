// ============================================================================
// GhostLine: AI-Powered RC Racing - Arcade HUD Frontend Controller
// Component: assets/app.js
// Description: Live USB camera feed manager, 60 FPS AR Canvas overlay,
//              Pre-Race Driver/Car registration, and App Lab WebSockets.
// ============================================================================

// ----------------------------------------------------------------------------
// Audio Synthesizer Engine (Web Audio API)
// ----------------------------------------------------------------------------
class ArcadeAudioEngine {
  constructor() {
    this.ctx = null;
  }

  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.ctx = new AudioCtx();
    }
  }

  playTone(freq, durationMs, type = 'sine') {
    this.init();
    if (!this.ctx) return;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
    gain.gain.setValueAtTime(0.25, this.ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + durationMs / 1000);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start();
    osc.stop(this.ctx.currentTime + durationMs / 1000);
  }

  playCountdownLow() {
    this.playTone(440, 180, 'triangle');
  }

  playCountdownGo() {
    this.playTone(880, 400, 'square');
  }

  playLapChime() {
    this.playTone(659.25, 120, 'sine');
    setTimeout(() => this.playTone(880, 180, 'sine'), 100);
  }

  playVictoryFanfare() {
    const notes = [523.25, 659.25, 783.99, 1046.50];
    notes.forEach((freq, idx) => {
      setTimeout(() => this.playTone(freq, 220, 'triangle'), idx * 120);
    });
  }
}

const audio = new ArcadeAudioEngine();

// ----------------------------------------------------------------------------
// State & Variables
// ----------------------------------------------------------------------------
let latestTelemetry = null;
let ghostTrailPoints = [];
let isCalibrating = false;
let currentTargetLaps = 5;
let currentMode = "TIME_ATTACK";
let currentRaceState = "IDLE";
let countdownTimerId = null;

// DOM Elements: Header
const hdrP1Driver = document.getElementById('hdrP1Driver');
const hdrP2Driver = document.getElementById('hdrP2Driver');
const hdrLapTarget = document.getElementById('hdrLapTarget');
const statusPill = document.getElementById('statusPill');
const raceStateText = document.getElementById('raceStateText');
const camStatusTag = document.getElementById('camStatusTag');

// Buttons
const btnOpenRegistration = document.getElementById('btnOpenRegistration');
const btnStart = document.getElementById('btnStartRace');
const btnCompleteRace = document.getElementById('btnCompleteRace');
const btnReset = document.getElementById('btnResetRace');
const btnHazard = document.getElementById('btnToggleHazard');
const btnDemo = document.getElementById('btnToggleDemo');
const btnCalibrate = document.getElementById('btnCalibrateLine');
const btnCloseBanner = document.getElementById('btnCloseBanner');

// Camera & Canvas
const iframe = document.getElementById('dynamicIframe');
const placeholder = document.getElementById('videoPlaceholder');
const canvas = document.getElementById('trackCanvas');
const ctx = canvas.getContext('2d');
const cameraViewport = document.getElementById('cameraViewport');

// Overlays
const countdownOverlay = document.getElementById('countdownOverlay');
const countdownNumber = document.getElementById('countdownNumber');
const winnerBanner = document.getElementById('winnerBanner');
const winnerText = document.getElementById('winnerText');
const winnerLapStats = document.getElementById('winnerLapStats');

// Strips
const stripP1Name = document.getElementById('stripP1Name');
const p1SpeedEl = document.getElementById('p1Speed');
const p1LapEl = document.getElementById('p1Lap');
const p1TargetLapEl = document.getElementById('p1TargetLap');
const p1CurrentLapEl = document.getElementById('p1CurrentLap');
const p1BestLapEl = document.getElementById('p1BestLap');

const stripP2Name = document.getElementById('stripP2Name');
const p2SpeedEl = document.getElementById('p2Speed');
const p2LapEl = document.getElementById('p2Lap');
const p2TargetLapEl = document.getElementById('p2TargetLap');
const p2CurrentLapEl = document.getElementById('p2CurrentLap');
const p2BestLapEl = document.getElementById('p2BestLap');

// Delta
const deltaContainer = document.getElementById('deltaContainer');
const deltaSign = document.getElementById('deltaSign');
const deltaNumber = document.getElementById('deltaNumber');
const deltaStatusLabel = document.getElementById('deltaStatusLabel');
const deltaBarFill = document.getElementById('deltaBarFill');
const ghostRecordBadge = document.getElementById('ghostRecordBadge');

// Leaderboard table
const tblP1Driver = document.getElementById('tblP1Driver');
const tblP1Car = document.getElementById('tblP1Car');
const tableP1Lap = document.getElementById('tableP1Lap');
const tableP1Last = document.getElementById('tableP1Last');
const tableP1Best = document.getElementById('tableP1Best');

const tblP2Driver = document.getElementById('tblP2Driver');
const tblP2Car = document.getElementById('tblP2Car');
const tableP2Lap = document.getElementById('tableP2Lap');
const tableP2Last = document.getElementById('tableP2Last');
const tableP2Best = document.getElementById('tableP2Best');
const tableP2Gap = document.getElementById('tableP2Gap');

// Registration Modal
const registrationModal = document.getElementById('registrationModal');
const btnCloseModal = document.getElementById('btnCloseModal');
const btnCancelModal = document.getElementById('btnCancelModal');
const registrationForm = document.getElementById('registrationForm');
const inputP1Driver = document.getElementById('inputP1Driver');
const inputP1Car = document.getElementById('inputP1Car');
const inputP2Driver = document.getElementById('inputP2Driver');
const inputP2Car = document.getElementById('inputP2Car');
const inputTargetLaps = document.getElementById('inputTargetLaps');
const btnLapMinus = document.getElementById('btnLapMinus');
const btnLapPlus = document.getElementById('btnLapPlus');
const presetPills = document.querySelectorAll('.preset-pill');
const inputConfidence = document.getElementById('inputConfidence');
const lblConfVal = document.getElementById('lblConfVal');

// ----------------------------------------------------------------------------
// Live USB Camera Stream Integration (Port 4912 /embed)
// ----------------------------------------------------------------------------
const currentHostname = window.location.hostname || 'localhost';
const streamUrl = `http://${currentHostname}:4912/embed`;
let camRetryInterval = null;

function initCameraStream() {
  iframe.onload = () => {
    if (camRetryInterval) clearInterval(camRetryInterval);
    placeholder.style.display = 'none';
    iframe.style.display = 'block';
    camStatusTag.textContent = 'ONLINE (4912)';
    camStatusTag.style.color = 'var(--green-go)';
  };

  iframe.onerror = () => {
    camStatusTag.textContent = 'CONNECTING...';
  };

  // Attempt initial load
  iframe.src = streamUrl;

  // Retry every 2.5s if not loaded yet
  camRetryInterval = setInterval(() => {
    if (iframe.style.display !== 'block') {
      iframe.src = streamUrl;
    }
  }, 2500);
}

initCameraStream();

// Sync Canvas Resolution with Viewport
function resizeCanvas() {
  if (cameraViewport) {
    canvas.width = cameraViewport.clientWidth;
    canvas.height = cameraViewport.clientHeight;
  }
}
window.addEventListener('resize', resizeCanvas);
setTimeout(resizeCanvas, 300);

// ----------------------------------------------------------------------------
// App Lab WebSockets Integration
// ----------------------------------------------------------------------------
const ui = new WebUI();

ui.on_connect(() => {
  console.log('[GhostLine] Connected to Arduino App Lab WebUI Brick');
});

ui.on_disconnect(() => {
  console.warn('[GhostLine] Disconnected from Arduino UNO Q');
  raceStateText.textContent = 'OFFLINE / DISCONNECTED';
});

// Telemetry stream from Python MPU
ui.on_message('telemetry_update', (data) => {
  latestTelemetry = data;
  updateTelemetryHUD(data);
});

// State changes
ui.on_message('state_changed', (data) => {
  currentRaceState = data.state;
  updateStateUI(data.state);
});

// Lap complete
ui.on_message('lap_completed', (data) => {
  audio.playLapChime();
});

// New ghost record
ui.on_message('new_ghost_record', (data) => {
  ghostRecordBadge.textContent = `RECORD: ${data.best_time.toFixed(2)}s`;
  if (data.trail) {
    ghostTrailPoints = data.trail;
  }
});

// Race finished
ui.on_message('race_finished', (data) => {
  audio.playVictoryFanfare();
  const winner = data.leaderboard && data.leaderboard[0] ? data.leaderboard[0].driver_name : 'RACER';
  winnerText.textContent = `VICTORY: ${winner}!`;
  winnerLapStats.textContent = `Winning Time: ${data.leaderboard[0]?.best_lap_time || '--'}s`;
  winnerBanner.style.display = 'flex';
});

// Registration confirmed by backend
ui.on_message('registration_confirmed', (data) => {
  applyRegistrationToUI(data);
});

// ----------------------------------------------------------------------------
// Registration Modal Logic
// ----------------------------------------------------------------------------
btnOpenRegistration.addEventListener('click', () => {
  registrationModal.style.display = 'flex';
});

btnCloseModal.addEventListener('click', () => {
  registrationModal.style.display = 'none';
});

btnCancelModal.addEventListener('click', () => {
  registrationModal.style.display = 'none';
});

btnLapMinus.addEventListener('click', () => {
  let val = parseInt(inputTargetLaps.value) || 5;
  if (val > 1) val--;
  inputTargetLaps.value = val;
  updatePresetActive(val);
});

btnLapPlus.addEventListener('click', () => {
  let val = parseInt(inputTargetLaps.value) || 5;
  if (val < 100) val++;
  inputTargetLaps.value = val;
  updatePresetActive(val);
});

presetPills.forEach(pill => {
  pill.addEventListener('click', () => {
    const laps = parseInt(pill.getAttribute('data-laps'));
    inputTargetLaps.value = laps;
    updatePresetActive(laps);
  });
});

function updatePresetActive(laps) {
  presetPills.forEach(p => {
    if (parseInt(p.getAttribute('data-laps')) === laps) p.classList.add('active');
    else p.classList.remove('active');
  });
}

inputConfidence.addEventListener('input', (e) => {
  lblConfVal.textContent = parseFloat(e.target.value).toFixed(2);
});

registrationForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const p1Driver = inputP1Driver.value.trim() || 'Driver 1';
  const p1Car = inputP1Car.value.trim() || 'Apex GT';
  const p2Driver = inputP2Driver.value.trim() || 'Driver 2';
  const p2Car = inputP2Car.value.trim() || 'Blaze RC';
  const laps = parseInt(inputTargetLaps.value) || 5;
  const mode = document.querySelector('input[name="raceModeRadio"]:checked')?.value || 'TIME_ATTACK';
  const conf = parseFloat(inputConfidence.value);

  // Send registration message to Python MPU
  ui.send_message('register_race', {
    p1_driver: p1Driver,
    p1_car: p1Car,
    p2_driver: p2Driver,
    p2_car: p2Car,
    target_laps: laps,
    mode: mode
  });

  ui.send_message('override_th', conf);

  applyRegistrationToUI({
    p1_driver: p1Driver,
    p1_car: p1Car,
    p2_driver: p2Driver,
    p2_car: p2Car,
    target_laps: laps,
    mode: mode
  });

  registrationModal.style.display = 'none';
});

function applyRegistrationToUI(info) {
  currentTargetLaps = info.target_laps;
  currentMode = info.mode;

  hdrP1Driver.textContent = `P1: ${info.p1_driver}`;
  hdrP2Driver.textContent = `P2: ${info.p2_driver}`;
  hdrLapTarget.textContent = `${info.target_laps} LAPS`;

  stripP1Name.textContent = info.p1_driver;
  p1TargetLapEl.textContent = info.target_laps;
  tblP1Driver.textContent = info.p1_driver;
  tblP1Car.textContent = info.p1_car;

  stripP2Name.textContent = info.p2_driver;
  p2TargetLapEl.textContent = info.target_laps;
  tblP2Driver.textContent = info.p2_driver;
  tblP2Car.textContent = info.p2_car;

  const modePill = document.getElementById('leaderboardModePill');
  if (modePill) modePill.textContent = info.mode.replace('_', ' ');
}

// ----------------------------------------------------------------------------
// Button Actions
// ----------------------------------------------------------------------------
btnStart.addEventListener('click', () => {
  audio.init();
  ui.send_message('start_race', {});
  triggerClientCountdown();
});

btnCompleteRace.addEventListener('click', () => {
  audio.init();
  ui.send_message('force_complete_race', {});
});

btnReset.addEventListener('click', () => {
  ui.send_message('reset_race', {});
  winnerBanner.style.display = 'none';
  if (countdownTimerId) clearInterval(countdownTimerId);
  countdownOverlay.style.display = 'none';
});

btnHazard.addEventListener('click', () => {
  ui.send_message('toggle_hazard', {});
});

btnDemo.addEventListener('click', () => {
  ui.send_message('toggle_sim_demo', {});
  btnDemo.classList.toggle('active');
});

btnCalibrate.addEventListener('click', () => {
  isCalibrating = !isCalibrating;
  btnCalibrate.style.background = isCalibrating ? '#00f3ff' : '#232c3f';
  btnCalibrate.style.color = isCalibrating ? '#000' : '#7f8ca3';
});

btnCloseBanner.addEventListener('click', () => {
  winnerBanner.style.display = 'none';
});

function triggerClientCountdown() {
  let count = 3;
  countdownNumber.textContent = count;
  countdownOverlay.style.display = 'flex';
  audio.playCountdownLow();

  if (countdownTimerId) clearInterval(countdownTimerId);

  countdownTimerId = setInterval(() => {
    count--;
    if (count > 0) {
      countdownNumber.textContent = count;
      audio.playCountdownLow();
    } else if (count === 0) {
      countdownNumber.textContent = 'GO!';
      audio.playCountdownGo();
    } else {
      clearInterval(countdownTimerId);
      countdownOverlay.style.display = 'none';
    }
  }, 1000);
}

// ----------------------------------------------------------------------------
// Telemetry HUD Updates
// ----------------------------------------------------------------------------
function updateStateUI(state) {
  raceStateText.textContent = `STATE: ${state}`;
  const dot = statusPill.querySelector('.pulse-dot');
  if (state === 'RACING') {
    dot.style.backgroundColor = 'var(--green-go)';
    dot.style.boxShadow = '0 0 10px var(--green-go)';
  } else if (state === 'HAZARD') {
    dot.style.backgroundColor = 'var(--yellow-hazard)';
    dot.style.boxShadow = '0 0 10px var(--yellow-hazard)';
  } else if (state === 'FINISHED') {
    dot.style.backgroundColor = 'var(--purple-ghost)';
    dot.style.boxShadow = '0 0 10px var(--purple-ghost)';
  } else {
    dot.style.backgroundColor = '#7f8ca3';
    dot.style.boxShadow = 'none';
  }
}

function updateTelemetryHUD(data) {
  const v1 = data.vehicles?.car_1;
  const v2 = data.vehicles?.car_2;
  const ghost = data.ghost;
  const board = data.leaderboard || [];

  // P1 Strip & Table
  if (v1) {
    p1SpeedEl.textContent = v1.speed_kmh.toFixed(1);
    const p1Stats = board.find(b => b.id === 'car_1');
    if (p1Stats) {
      p1LapEl.textContent = p1Stats.current_lap;
      p1CurrentLapEl.textContent = `${p1Stats.current_lap_elapsed.toFixed(2)}s`;
      p1BestLapEl.textContent = p1Stats.best_lap_time ? `${p1Stats.best_lap_time.toFixed(2)}s` : '--.--';
      tableP1Lap.textContent = `${p1Stats.current_lap}/${p1Stats.total_laps}`;
      tableP1Last.textContent = p1Stats.last_lap_time ? `${p1Stats.last_lap_time.toFixed(2)}s` : '--.--';
      tableP1Best.textContent = p1Stats.best_lap_time ? `${p1Stats.best_lap_time.toFixed(2)}s` : '--.--';
    }
  }

  // P2 Strip & Table
  if (v2) {
    p2SpeedEl.textContent = v2.speed_kmh.toFixed(1);
    const p2Stats = board.find(b => b.id === 'car_2');
    if (p2Stats) {
      p2LapEl.textContent = p2Stats.current_lap;
      p2CurrentLapEl.textContent = `${p2Stats.current_lap_elapsed.toFixed(2)}s`;
      p2BestLapEl.textContent = p2Stats.best_lap_time ? `${p2Stats.best_lap_time.toFixed(2)}s` : '--.--';
      tableP2Lap.textContent = `${p2Stats.current_lap}/${p2Stats.total_laps}`;
      tableP2Last.textContent = p2Stats.last_lap_time ? `${p2Stats.last_lap_time.toFixed(2)}s` : '--.--';
      tableP2Best.textContent = p2Stats.best_lap_time ? `${p2Stats.best_lap_time.toFixed(2)}s` : '--.--';
      
      // Calculate gap
      if (p1Stats && p2Stats.best_lap_time && p1Stats.best_lap_time) {
        const gap = p2Stats.best_lap_time - p1Stats.best_lap_time;
        tableP2Gap.textContent = gap >= 0 ? `+${gap.toFixed(2)}s` : `${gap.toFixed(2)}s`;
      }
    }
  }

  // Ghost Comparator
  if (ghost && ghost.has_ghost) {
    ghostRecordBadge.textContent = `RECORD: ${ghost.best_lap_time.toFixed(2)}s`;
    deltaNumber.textContent = ghost.delta_sec.toFixed(2);

    if (ghost.ahead_of_ghost) {
      deltaSign.textContent = '-';
      deltaContainer.className = 'delta-value-box delta-ahead';
      deltaStatusLabel.textContent = `🚀 +${ghost.delta_sec.toFixed(2)}s FASTER THAN GHOST!`;
      deltaBarFill.style.background = 'var(--green-go)';
      const pct = Math.min(50, (ghost.delta_sec / 1.0) * 50);
      deltaBarFill.style.left = `${50 - pct}%`;
      deltaBarFill.style.width = `${pct}%`;
    } else {
      deltaSign.textContent = '+';
      deltaContainer.className = 'delta-value-box delta-behind';
      deltaStatusLabel.textContent = `⚠️ -${ghost.delta_sec.toFixed(2)}s BEHIND GHOST`;
      deltaBarFill.style.background = 'var(--red-stop)';
      const pct = Math.min(50, (ghost.delta_sec / 1.0) * 50);
      deltaBarFill.style.left = '50%';
      deltaBarFill.style.width = `${pct}%`;
    }
  } else {
    deltaSign.textContent = '±';
    deltaNumber.textContent = '0.00';
    deltaContainer.className = 'delta-value-box';
    deltaStatusLabel.textContent = 'ESTABLISH FASTEST LAP TO SPAWN GHOST';
    deltaBarFill.style.width = '0%';
  }
}

// ----------------------------------------------------------------------------
// 60 FPS Transparent AR Canvas Rendering Loop
// Overlaid directly on top of the live USB Camera video feed!
// ----------------------------------------------------------------------------
function renderARCanvas() {
  const w = canvas.width;
  const h = canvas.height;

  // Clear transparent canvas for AR overlay
  ctx.clearRect(0, 0, w, h);

  // 1. Draw Virtual Start/Finish Line across the camera view
  if (latestTelemetry && latestTelemetry.finish_line) {
    const f1 = latestTelemetry.finish_line[0];
    const f2 = latestTelemetry.finish_line[1];
    drawCheckeredLine(f1[0] * w, f1[1] * h, f2[0] * w, f2[1] * h);
  }

  // 2. Draw Recorded GhostLine (Fastest Lap Path)
  if (ghostTrailPoints.length > 2) {
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(189, 66, 255, 0.6)';
    ctx.lineWidth = 3;
    ctx.setLineDash([8, 6]);
    ctx.moveTo(ghostTrailPoints[0].x * w, ghostTrailPoints[0].y * h);
    for (let i = 1; i < ghostTrailPoints.length; i++) {
      ctx.lineTo(ghostTrailPoints[i].x * w, ghostTrailPoints[i].y * h);
    }
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // 3. Draw Ghost Car Hologram
  if (latestTelemetry?.ghost?.has_ghost && latestTelemetry.ghost.ghost_x != null) {
    const gx = latestTelemetry.ghost.ghost_x * w;
    const gy = latestTelemetry.ghost.ghost_y * h;
    drawHologramGhost(gx, gy);
  }

  // 4. Draw Live Detected Vehicles, Bounding Boxes & Trails
  if (latestTelemetry?.vehicles) {
    const v1 = latestTelemetry.vehicles.car_1;
    const v2 = latestTelemetry.vehicles.car_2;

    if (v2?.is_detected) {
      drawDetectedCar(v2, '#ff5500', 'P2: ' + (v2.driver_name || 'Blaze'));
    }
    if (v1?.is_detected) {
      drawDetectedCar(v1, '#00f3ff', 'P1: ' + (v1.driver_name || 'Cyan'));
    }
  }

  requestAnimationFrame(renderARCanvas);
}

// Draw Checkered Virtual Finish Line
function drawCheckeredLine(x1, y1, x2, y2) {
  ctx.save();
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 6;
  ctx.setLineDash([8, 8]);
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();

  // Checkered badge
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 10px "Roboto Mono", monospace';
  ctx.fillText('🏁 FINISH LINE', x1 - 36, y1 - 8);
  ctx.restore();
}

// Draw Ghost Hologram
function drawHologramGhost(gx, gy) {
  ctx.save();
  ctx.fillStyle = 'rgba(189, 66, 255, 0.4)';
  ctx.strokeStyle = '#bd42ff';
  ctx.lineWidth = 2;
  ctx.shadowColor = '#bd42ff';
  ctx.shadowBlur = 16;

  ctx.beginPath();
  ctx.arc(gx, gy, 10, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 9px "Roboto Mono", monospace';
  ctx.fillText('👻 GHOST', gx + 12, gy + 3);
  ctx.restore();
}

// Draw Detected Vehicle with YOLOX Bounding Box & HUD Tag
function drawDetectedCar(vehicle, colorHex, label) {
  const w = canvas.width;
  const h = canvas.height;
  const vx = vehicle.x * w;
  const vy = vehicle.y * h;

  ctx.save();

  // Draw Bounding Box if available from YOLOX detection
  if (vehicle.bbox && vehicle.bbox.length === 4) {
    const bx = vehicle.bbox[0] * w;
    const by = vehicle.bbox[1] * h;
    const bw = (vehicle.bbox[2] - vehicle.bbox[0]) * w;
    const bh = (vehicle.bbox[3] - vehicle.bbox[1]) * h;

    ctx.strokeStyle = colorHex;
    ctx.lineWidth = 2;
    ctx.strokeRect(bx, by, bw, bh);

    // Corner targeting brackets
    const bracketLen = Math.min(12, bw / 3);
    ctx.lineWidth = 3;
    // Top-left
    ctx.beginPath(); ctx.moveTo(bx, by + bracketLen); ctx.lineTo(bx, by); ctx.lineTo(bx + bracketLen, by); ctx.stroke();
    // Top-right
    ctx.beginPath(); ctx.moveTo(bx + bw - bracketLen, by); ctx.lineTo(bx + bw, by); ctx.lineTo(bx + bw, by + bracketLen); ctx.stroke();
    // Bottom-left
    ctx.beginPath(); ctx.moveTo(bx, by + bh - bracketLen); ctx.lineTo(bx, by + bh); ctx.lineTo(bx + bracketLen, by + bh); ctx.stroke();
    // Bottom-right
    ctx.beginPath(); ctx.moveTo(bx + bw - bracketLen, by + bh); ctx.lineTo(bx + bw, by + bh); ctx.lineTo(bx + bw, by + bh - bracketLen); ctx.stroke();
  }

  // Draw Trail
  if (vehicle.trail && vehicle.trail.length > 1) {
    ctx.beginPath();
    ctx.strokeStyle = colorHex;
    ctx.lineWidth = 2;
    for (let i = 0; i < vehicle.trail.length; i++) {
      const tx = vehicle.trail[i][0] * w;
      const ty = vehicle.trail[i][1] * h;
      if (i === 0) ctx.moveTo(tx, ty);
      else ctx.lineTo(tx, ty);
    }
    ctx.stroke();
  }

  // Centroid Reticle
  ctx.fillStyle = colorHex;
  ctx.shadowColor = colorHex;
  ctx.shadowBlur = 14;
  ctx.beginPath();
  ctx.arc(vx, vy, 6, 0, Math.PI * 2);
  ctx.fill();

  // Floating HUD Tag with Edge Impulse Detection Info
  ctx.shadowBlur = 0;
  const tagW = 114;
  const tagH = 30;
  ctx.fillStyle = 'rgba(10, 14, 24, 0.90)';
  ctx.fillRect(vx + 10, vy - 20, tagW, tagH);
  ctx.strokeStyle = colorHex;
  ctx.lineWidth = 1.5;
  ctx.strokeRect(vx + 10, vy - 20, tagW, tagH);

  // Driver & Vehicle Label
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 9px "Roboto Mono", monospace';
  const labelText = vehicle.detected_label ? `${label}` : label;
  ctx.fillText(labelText, vx + 14, vy - 8);

  // Speed and AI Confidence
  ctx.fillStyle = colorHex;
  ctx.font = 'bold 9px "Roboto Mono", monospace';
  const confText = vehicle.confidence ? ` • ${Math.round(vehicle.confidence * 100)}%` : '';
  const aiTag = vehicle.detected_label ? `[${vehicle.detected_label.toUpperCase()}] ` : '';
  ctx.fillText(`${aiTag}${vehicle.speed_kmh.toFixed(1)} km/h${confText}`, vx + 14, vy + 5);

  ctx.restore();
}

// Start AR Canvas Loop
requestAnimationFrame(renderARCanvas);
