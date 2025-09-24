# rhythm_game.py
# Streamlit rhythm game (single-file)
# Run: pip install streamlit
#      streamlit run rhythm_game.py

import streamlit as st
import base64
import json
import time
from pathlib import Path
import streamlit.components.v1 as components

st.set_page_config(page_title="리듬 게임 (Streamlit)", layout="wide")

st.title("🎵 간단한 리듬 게임 — Streamlit 버전")

left_col, right_col = st.columns([2, 1])

with right_col:
    st.markdown("**설정**")
    uploaded = st.file_uploader("MP3 파일 업로드 (선택) — 없으면 기본 소리 사용", type=["mp3", "wav"], key="uploader")
    bpm = st.slider("BPM (속도)", min_value=60, max_value=220, value=120)
    difficulty = st.selectbox("난이도", ["Easy", "Normal", "Hard"], index=1)
    columns = st.slider("칼럼 수 (키 개수)", min_value=2, max_value=6, value=4)
    key_map_text = st.text_input("키 매핑 (쉼표로 구분, 예: d,f,j,k)", value=",".join(["d","f","j","k"][:columns]))
    start_btn = st.button("Start / Restart")
    st.markdown("---")
    st.markdown("**조작법**: 입력한 키들로 노트를 맞추세요. 화면 포커스를 유지해야 키 입력이 정확합니다.")
    st.markdown("**팁**: mp3 파일을 올리면 해당 음악으로 플레이됩니다. 모바일에서는 키보드 입력이 제한될 수 있습니다.")

# Read uploaded audio or fallback to a tiny generated beep (base64)
if uploaded is not None:
    audio_bytes = uploaded.read()
    audio_mime = uploaded.type or "audio/mp3"
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    audio_src = f"data:{audio_mime};base64,{audio_b64}"
else:
    # small built-in beep (sine wave) encoded as wav base64 (very short). We will embed a tiny silent mp3 alternative if no upload.
    # To keep the file self-contained we embed a short data URI generated beforehand (a short silence mp3). If you'd like to test with music, upload an mp3.
    # Here we use an empty 1-second silent WAV base64 (RIFF) — small and safe.
    silent_wav_b64 = (
        "UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA="
    )
    audio_src = f"data:audio/wav;base64,{silent_wav_b64}"

# Prepare JS parameters
params = {
    "bpm": bpm,
    "difficulty": difficulty,
    "columns": columns,
    "keymap": [k.strip() for k in key_map_text.split(",") if k.strip()][:columns],
}

# If keymap length is less than columns, fill with default keys
default_keys = ["d", "f", "j", "k", "s", "l"]
if len(params["keymap"]) < columns:
    params["keymap"] = default_keys[:columns]

params_json = json.dumps(params)

# HTML + JS game (canvas + audio)
html_code = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>Streamlit Rhythm Game</title>
<style>
  body {{ margin:0; padding:0; font-family: sans-serif; background:#0f172a; color:#fff }}
  #game {{ display:flex; justify-content:center; align-items:center; height:100%; }}
  canvas {{ background: linear-gradient(180deg, #071034 0%, #02101a 100%); border-radius:8px }}
  .hud {{ position: absolute; top:10px; left:10px; color:#fff; font-size:14px }}
  .center-msg {{ position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); color:#fff; font-size:18px; text-align:center }}
</style>
</head>
<body>
<div id="game">
  <canvas id="canvas" width="900" height="600"></canvas>
  <div class="hud" id="hud"></div>
  <div class="center-msg" id="center-msg"></div>
</div>

<audio id="audio" src="{audio_src}" crossorigin="anonymous"></audio>

<script>
const params = {params_json};
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const hud = document.getElementById('hud');
const centerMsg = document.getElementById('center-msg');
const audio = document.getElementById('audio');

let w = canvas.width, h = canvas.height;
let columns = params.columns;
let keymap = params.keymap;
let bpm = Number(params.bpm) || 120;
let difficulty = params.difficulty;
let score = 0;
let combo = 0;
let maxCombo = 0;
let notes = [];
let startTime = null;
let running = false;
let scrollSpeed = 250; // px per beat; adjust by difficulty

if (difficulty === 'Easy') scrollSpeed *= 0.8;
if (difficulty === 'Hard') scrollSpeed *= 1.2;

const laneWidth = Math.floor(w / columns);
const hitY = h - 120;

function genNotes() {
  // Simple generator: spawn notes based on BPM and difficulty for demonstration
  notes = [];
  const beats = 64; // number of beats to generate
  // density based on difficulty
  let density = 0.5;
  if (difficulty === 'Easy') density = 0.35;
  if (difficulty === 'Hard') density = 0.85;
  for (let i = 4; i < beats; i++) {
    if (Math.random() < density) {
      const lane = Math.floor(Math.random() * columns);
      const beatTime = i * (60 / bpm);
      notes.push({lane: lane, time: beatTime, hit:false, judged:false});
    }
  }
}

function draw() {
  ctx.clearRect(0,0,w,h);
  // draw lanes
  for (let i=0;i<columns;i++){
    const x = i*laneWidth;
    ctx.fillStyle = 'rgba(255,255,255,0.03)';
    ctx.fillRect(x+2,0,laneWidth-4,h);
    // key label
    ctx.fillStyle = 'rgba(255,255,255,0.6)';
    ctx.font = '18px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(keymap[i].toUpperCase(), x + laneWidth/2, h - 60);
  }
  // draw hit line
  ctx.fillStyle = 'rgba(255,255,255,0.08)';
  ctx.fillRect(0, hitY-6, w, 6);

  // draw notes
  const now = (performance.now()/1000) - startTime;
  for (let note of notes){
    const dt = note.time - now; // seconds until hit
    const y = hitY - dt * scrollSpeed;
    const x = note.lane*laneWidth + laneWidth/2;
    if (!note.judged) {
      ctx.beginPath();
      ctx.fillStyle = 'rgba(255,255,255,0.9)';
      ctx.arc(x, y, 18, 0, Math.PI*2);
      ctx.fill();
    }
  }

  // HUD
  hud.innerHTML = `Score: ${score} &nbsp;|&nbsp; Combo: ${combo} &nbsp;|&nbsp; Max Combo: ${maxCombo}`;
}

function gameLoop() {
  if (!running) return;
  draw();
  requestAnimationFrame(gameLoop);
}

function startGame() {
  score = 0; combo = 0; maxCombo = 0;
  genNotes();
  startTime = performance.now()/1000 + 0.5; // slight delay
  audio.currentTime = 0;
  // ensure audio is allowed to play by user gesture
  audio.play().catch(e => {
    centerMsg.innerText = '브라우저에서 자동 재생이 차단되었습니다. 화면을 클릭하거나 Start 버튼을 다시 누르세요.';
  });
  running = true;
  centerMsg.innerText = '';
  requestAnimationFrame(gameLoop);
}

function stopGame() {
  running = false;
  audio.pause();
}

function judge(lane){
  // find closest unjudged note in lane
  const now = (performance.now()/1000) - startTime;
  let candidate = null; let best = 999;
  for (let note of notes){
    if (note.judged || note.lane !== lane) continue;
    const delta = Math.abs(note.time - now);
    if (delta < best) { best = delta; candidate = note; }
  }
  if (candidate && best < 0.25) {
    candidate.judged = true;
    // scoring: perfect <0.07, great <0.15, good <0.25
    if (best < 0.07) { score += 300; combo +=1; centerMsg.innerText='Perfect'; }
    else if (best < 0.15) { score += 100; combo +=1; centerMsg.innerText='Great'; }
    else { score += 50; combo = 0; centerMsg.innerText='Good'; }
    if (combo > maxCombo) maxCombo = combo;
    setTimeout(()=> centerMsg.innerText='', 400);
  } else {
    // miss
    combo = 0;
    centerMsg.innerText = 'Miss';
    setTimeout(()=> centerMsg.innerText='', 400);
  }
}

// key handling
window.addEventListener('keydown', (e)=>{
  const k = e.key.toLowerCase();
  const idx = keymap.indexOf(k);
  if (idx !== -1) {
    judge(idx);
    // small visual effect: flash lane
    const x = idx*laneWidth;
    ctx.fillStyle='rgba(255,255,255,0.06)';
    ctx.fillRect(x,0,laneWidth,h);
  }
});

// Start control from parent (Streamlit will re-render when Start button clicked). To allow starting, expose a global function.
function resetAndStart(){
  stopGame();
  genNotes();
  startTime = performance.now()/1000 + 0.5;
  score = 0; combo = 0; maxCombo = 0;
  audio.currentTime = 0;
  audio.play().catch(()=>{});
  running = true;
  requestAnimationFrame(gameLoop);
}

// Attach a click listener to ensure user gesture for audio playback
canvas.addEventListener('click', ()=>{
  if (!running) {
    startGame();
  } else {
    // toggle pause
    if (audio.paused) { audio.play(); running=true; requestAnimationFrame(gameLoop); }
    else { audio.pause(); running=false; }
  }
});

// Expose function for Streamlit button via postMessage hack (Streamlit will re-render component on button click, triggering reload of HTML)

// On load, draw static frame
startTime = performance.now()/1000;
draw();

</script>
</body>
</html>
"""

# Render the HTML game inside Streamlit
components.html(html_code, height=720, scrolling=True)

st.markdown("---")
st.markdown("**실행 방법**")
st.code("""
# 필요한 패키지 설치
pip install streamlit

# 실행
streamlit run rhythm_game.py
""")

st.markdown("**메모**: 이 데모는 브라우저 내에서 HTML/JS 캔버스를 사용해 간단한 리듬 동작(노트 스폰, 판정, 점수)을 구현합니다. 더 정교한 리듬 게임 (정확한 시퀀스, 스프라이트, 네트워크 기능 등)을 원하면 알려주세요 — 추가 기능으로 업그레이드해 드립니다.")
