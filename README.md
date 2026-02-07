<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>Ultimate Clock - Fixed</title>
<style>
  body{
    margin:0;
    min-height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
    background:#111;
    color:#00ffcc;
    font-family:Arial, sans-serif;
    transition:0.3s;
  }
  body.light{ background:#f4f4f4; color:#111; }
  .container{ text-align:center; width:760px; max-width:95%; }
  .time{ font-size:46px; letter-spacing:2px; }
  .date{ font-size:20px; color:#aaa; }
  button, select, input { margin:5px; padding:7px 14px; background:transparent; color:inherit; border:1px solid currentColor; border-radius:6px; cursor:pointer; }
  #greeting,#yearLeft,#swLaps{ color:#aaa; margin-top:6px; }
  #countdowns{ color:#aaa; margin-top:6px; text-align:left; }
  #sw{ font-size:18px; }
  #lapsList{ margin-top:5px; max-height:100px; overflow-y:auto; text-align:left; font-size:14px; border-top:1px solid currentColor; padding-top:6px; }
  .countdown-item{ border-top:1px solid currentColor; padding:6px 0; display:flex; gap:8px; align-items:center; justify-content:space-between; }
  .countdown-left { flex:1; }
  input[type="text"], input[type="datetime-local"] { padding:6px; border-radius:6px; border:1px solid currentColor; background:transparent; color:inherit; }
  ul{ list-style:none; padding:0; margin:0; text-align:left; }
  li{ margin:6px 0; }
  
  <link rel="manifest" href="manifest.json">

</style>
</head>

<body>
  <div class="container">

    <div id="greeting"></div>
    <div class="time" id="time">00:00:00.000</div>
    <div class="date" id="date">00 00 0000</div>

    <button id="focusBtn">Focus Mode</button>

    <div id="extras">

      <h3>Joke of the Hour</h3>
      <p id="joke"></p>

      <h3>To Do</h3>
      <input id="taskInput" placeholder="New task" />
      <button id="addTaskBtn">Add</button>
      <ul id="tasks"></ul>

<div class="separator">_____________________________________________________________</div>

      <h3>Stopwatch</h3>
      <button id="swStartBtn">Start</button>
      <button id="swPauseBtn"> Pause </button>
      <button id="swLapBtn">Lap</button>
      <button id="swResetBtn">Reset</button>
      <div id="sw">0.0</div>
      <div id="lapsList"></div>

<div class="separator">______________________________________________________________</div>

      <h3>Countdowns</h3>
      <input type="text" id="countdownName" placeholder="Event name" />
      <input type="datetime-local" id="countdownInput" />
      <button id="addCountdownBtn">Add</button>
      <div id="countdowns"></div>
      <div id="yearLeft"></div>

<div class="separator">_____________________________________________________________</div>

      <button id="themeBtn">Change theme</button>
      <button id="formatBtn">Change Date Format</button>
      <button onclick="changeTextColor()">Change Color</button><br>

      <button id="toggle12Btn">12h / 24h</button>
      <select id="tzSelect">
        <option value="local">Local Time</option>
        <option value="UTC">UTC</option>
      </select>
      <button id="ssBtn">ScreenShot</button>

    </div>

  </div>

  <!-- load html2canvas first -->
  <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>

  <script>
      const textColors = [
  "#00FFCC", // ازرق فاتح
  "#7CFC00", // اخضر فاتح
  "#FF6B6B", // احمر فاتح
  "#FFD93D", // اصفر فاتح
  "#D2B48C", // brown فاتح
  "#FFFFFF"  // ابيض
];

let colorIndex = Number(localStorage.getItem("colorIndex")) || 0;

document.body.style.color = textColors[colorIndex];
function changeTextColor(){
  colorIndex = (colorIndex + 1) % textColors.length;
  document.body.style.color = textColors[colorIndex];
  localStorage.setItem("colorIndex", colorIndex);
}

    // --------- SETTINGS & STATE (persistent) ----------
    let is24h = JSON.parse(localStorage.getItem("is24h") ?? "true");
    let formatIndex = Number(localStorage.getItem("formatIndex") ?? 0);
    let tz = localStorage.getItem("tz") || "local";
    let focusMode = localStorage.getItem("focusMode") === "true";
    if(localStorage.getItem("theme") === "light") document.body.classList.add("light");

    // --------- DOM references (after elements exist) ----------
    const timeEl = document.getElementById("time");
    const dateEl = document.getElementById("date");
    const greetingEl = document.getElementById("greeting");
    const extrasEl = document.getElementById("extras");
    const formatBtn = document.getElementById("formatBtn");
    const themeBtn = document.getElementById("themeBtn");
    const toggle12Btn = document.getElementById("toggle12Btn");
    const tzSelect = document.getElementById("tzSelect");
    const focusBtn = document.getElementById("focusBtn");
    const ssBtn = document.getElementById("ssBtn");

    // ToDo DOM
    const taskInput = document.getElementById("taskInput");
    const addTaskBtn = document.getElementById("addTaskBtn");
    const tasksUl = document.getElementById("tasks");

    // Stopwatch DOM
    const swE = document.getElementById("sw");
    const lapsList = document.getElementById("lapsList");
    const swStartBtn = document.getElementById("swStartBtn");
    const swPauseBtn = document.getElementById("swPauseBtn");
    const swResetBtn = document.getElementById("swResetBtn");
    const swLapBtn = document.getElementById("swLapBtn");

    // Countdowns DOM
    const countdownsEl = document.getElementById("countdowns");
    const yearLeftEl = document.getElementById("yearLeft");
    const countdownNameInput = document.getElementById("countdownName");
    const countdownInput = document.getElementById("countdownInput");
    const addCountdownBtn = document.getElementById("addCountdownBtn");

    // Jokes DOM
    const jokeEl = document.getElementById("joke");

    // initial values
    tzSelect.value = tz;
    extrasEl.style.display = focusMode ? "none" : "block";

    // --------- CLOCK ----------
    function getNowForTZ() {
      if (tz === "UTC") {
        const now = new Date();
        // create Date from UTC string to get UTC components
        return new Date(now.toUTCString());
      }
      return new Date();
    }

    function updateClock() {
      const now = getNowForTZ();

      let hour = now.getHours();
      let suffix = "";
      if (!is24h) {
        suffix = hour >= 12 ? " PM" : " AM";
        hour = hour % 12 || 12;
      }

      const h = String(hour).padStart(2, "0");
      const m = String(now.getMinutes()).padStart(2, "0");
      const s = String(now.getSeconds()).padStart(2, "0");
      const ms = String(now.getMilliseconds()).padStart(3, "0");

      const d = String(now.getDate()).padStart(2, "0");
      const mo = String(now.getMonth() + 1).padStart(2, "0");
      const y = now.getFullYear();

      const formats = [
        `${d} ${mo} ${y}`,
        `${d}/${mo}/${y}`,
        `${y}-${mo}-${d}`
      ];

      timeEl.textContent = `${h}:${m}:${s}.${ms}${suffix}`;
      dateEl.textContent = formats[formatIndex];

      greetingEl.textContent =
        now.getHours() < 12 ? "Good Morning ☀️" :
        now.getHours() < 18 ? "Good Afternoon 🌤️" :
        "Good Evening 🌙";
    }

    // --------- CONTROLS ----------
    formatBtn.addEventListener("click", () => {
      formatIndex = (formatIndex + 1) % 3;
      localStorage.setItem("formatIndex", formatIndex);
    });

    themeBtn.addEventListener("click", () => {
      document.body.classList.toggle("light");
      localStorage.setItem("theme", document.body.classList.contains("light") ? "light" : "dark");
    });

    toggle12Btn.addEventListener("click", () => {
      is24h = !is24h;
      localStorage.setItem("is24h", JSON.stringify(is24h));
    });

    tzSelect.addEventListener("change", (e) => {
      tz = e.target.value;
      localStorage.setItem("tz", tz);
    });

    focusBtn.addEventListener("click", () => {
      focusMode = !focusMode;
      extrasEl.style.display = focusMode ? "none" : "block";
      localStorage.setItem("focusMode", focusMode);
    });

    ssBtn.addEventListener("click", () => {
      takeShot();
    });

    // --------- STOPWATCH ----------
const swElement = document.getElementById("sw");
const swStartBotton = document.getElementById("swStartBtn");
const swPauseBotton = document.getElementById("swPauseBtn");
const swResetBotton = document.getElementById("swResetBtn");
const swLapBotton = document.getElementById("swLapBtn");
const swlapsListBotton = document.getElementById("lapsList");

let swTime = 0;          // الوقت بالثواني مع العشرية
let swInterval = null;   
let swStartTs = 0;       
let swRunning = false;   
let swPaused = false;    
let swLaps = [];

function renderSW() {
  swElement.textContent = (Math.floor(swTime * 10) / 10).toFixed(1);
}

// START
function startSW() {
  if(swRunning) return;

  swRunning = true;
  swPaused = false;
  swPauseBtn.textContent = "Pause";

  swStartTs = Date.now() - swTime * 1000;

  localStorage.setItem("swRunning", "true");
  localStorage.setItem("swStartTs", swStartTs);
  localStorage.setItem("swPaused", "false");

  swInterval = setInterval(() => {
    swTime = (Date.now() - swStartTs) / 1000;
    renderSW();
    localStorage.setItem("swTime", swTime);
  }, 100);
}

// PAUSE / RESUME
function pauseResumeSW() {
  if(!swRunning) return;

  if(swPaused) {
    // Resume
    swStartTs = Date.now() - swTime * 1000;
    swInterval = setInterval(() => {
      swTime = (Date.now() - swStartTs) / 1000;
      renderSW();
    }, 100);
    swPaused = false;
    swPauseBtn.textContent = "Pause"; // غيّر اسم الزر
  } else {
    // Pause
    clearInterval(swInterval);
    swPaused = true;
    swPauseBtn.textContent = "Resume"; // غيّر اسم الزر
  }
}



// RESET
function resetSW() {
  clearInterval(swInterval);
  swTime = 0;
  swRunning = false;
  swPaused = false;
  swLaps = [];
  swElement.textContent = "0.0";
  lapsList.innerHTML = "";
  swPauseBtn.textContent = "Pause";

  localStorage.removeItem("swTime");
  localStorage.removeItem("swRunning");
  localStorage.removeItem("swPaused");
  localStorage.removeItem("swStartTs");
}

// LAP
function lapSW() {
  if(!swRunning && !swPaused) return;
  swLaps.push((Math.floor(swTime * 10) / 10).toFixed(1));
  lapsList.innerHTML = swLaps.map((v,i)=>`<div>Lap ${i+1}: ${v}s</div>`).join("");
}

// Event listeners
swStartBtn.addEventListener("click", startSW);
swPauseBtn.addEventListener("click", pauseResumeSW);
swResetBtn.addEventListener("click", resetSW);
swLapBtn.addEventListener("click", lapSW);

// Restore saved state
const savedTime = Number(localStorage.getItem("swTime")) || 0;
const savedRunning = localStorage.getItem("swRunning") === "true";
const savedPaused = localStorage.getItem("swPaused") === "true";
const savedStartTs = Number(localStorage.getItem("swStartTs")) || 0;
const savedLaps = JSON.parse(localStorage.getItem("swLaps") || "[]");

if(savedTime) swTime = savedTime;
if(savedLaps.length) {
  swLaps = savedLaps;
  lapsList.innerHTML = swLaps.map((v,i)=>`<div>Lap ${i+1}: ${v}s</div>`).join("");
}
renderSW();

if(savedRunning && !savedPaused){
  swStartTs = savedStartTs;
  startSW();
} else if(savedPaused){
  swPaused = true;
  swPauseBtn.textContent = "Resume";
}


    // --------- TODOs ----------
    let todos = JSON.parse(localStorage.getItem("todos") || "[]");
    function saveTodos() { localStorage.setItem("todos", JSON.stringify(todos)); }
    function renderTodos() {
      tasksUl.innerHTML = "";
      todos.forEach((t, i) => {
        const li = document.createElement("li");
        li.innerHTML = `${escapeHtml(t)} <button data-i="${i}">Done</button>`;
        tasksUl.appendChild(li);
      });
      // attach handlers
      tasksUl.querySelectorAll("button").forEach(b => {
        b.addEventListener("click", (e) => {
          const idx = Number(e.target.getAttribute("data-i"));
          todos.splice(idx, 1);
          saveTodos(); renderTodos();
        });
      });
    }
    addTaskBtn.addEventListener("click", () => {
      const v = taskInput.value.trim();
      if (!v) return;
      todos.push(v);
      taskInput.value = "";
      saveTodos(); renderTodos();
    });
    renderTodos();

    // --------- JOKES ----------
    const jokes = [
      "Why do programmers hate nature? Too many bugs.",
      "I told my PC I needed space… it froze.",
      "There are 10 types of people…",
      "Debugging is like being a detective.",
      "My code works; I have no idea why.",
      "I tried to be normal… worst two minutes of my life.",
      "Why don’t programmers sleep? Because they have bugs.",
      "Time flies like an arrow. Fruit flies like a banana.",
      "I would tell you a UDP joke, but you might not get it.",
      "Computers make very fast, very accurate mistakes.",
      "Why did the clock get kicked out of school? It kept ticking during the exam.",
      "I told my clock a joke… it took a second to get it.",
      "Why was the clock always calm? Because it knew how to pass the time.",
      "My clock and I are not friends anymore… it keeps reminding me I'm late.",
      "Why did the clock break up with the calendar? Too many dates.",
      "The clock went to therapy… it had too much time on its hands.",
      "Why don’t clocks ever argue? They just let things go, one second at a time.",
      "I asked my clock for advice… it said: take your time.",
      "Why was the digital clock embarrassed? Everyone saw its seconds.",
      "The clock applied for a job… great timing, terrible deadlines.",
      "Why did the clock go to jail? It killed time.",
      "My clock is so honest… it always tells the time, even when it hurts.",
      "Why did the clock bring a ladder? To reach the next level of time.",
      "Clocks are bad liars… sooner or later, they give you the time."
    ];
    function showJoke(){
      const idx = new Date().getHours() % jokes.length;
      jokeEl.textContent = jokes[idx];
    }
    showJoke();
    setInterval(showJoke, 3600000);

    // --------- MULTI COUNTDOWN WITH NAME & DELETE ----------
    let countdowns = JSON.parse(localStorage.getItem("countdowns") || "[]");

    function addCountdownWithName() {
      const name = countdownNameInput.value.trim();
      const dateVal = countdownInput.value;
      if (!name || !dateVal) { alert("Please enter event name and date/time."); return; }
      countdowns.push({ name, date: new Date(dateVal).toISOString() });
      localStorage.setItem("countdowns", JSON.stringify(countdowns));
      countdownNameInput.value = "";
      countdownInput.value = "";
      updateCountdowns();
    }

    function removeCountdown(index) {
      countdowns.splice(index, 1);
      localStorage.setItem("countdowns", JSON.stringify(countdowns));
      updateCountdowns();
    }

    function updateCountdowns() {
      const now = getNowForTZ();
      countdownsEl.innerHTML = "";
      countdowns.forEach((c, i) => {
        const diff = new Date(c.date) - now;
        const item = document.createElement("div");
        item.className = "countdown-item";
        const left = document.createElement("div");
        left.className = "countdown-left";

        if (diff > 0) {
          const t = Math.floor(diff / 1000);
          const days = Math.floor(t / 86400);
          const hours = Math.floor((t % 86400) / 3600);
          const mins = Math.floor((t % 3600) / 60);
          const secs = t % 60;
          left.textContent = `${c.name}: ${days}d ${hours}h ${mins}m ${secs}s`;
        } else {
          left.textContent = `${c.name}: Event reached 🎉`;
        }

        const btns = document.createElement("div");
        btns.style.display = "flex";
        btns.style.gap = "6px";

        const delBtn = document.createElement("button");
        delBtn.textContent = "Delete";
        delBtn.addEventListener("click", () => removeCountdown(i));
        btns.appendChild(delBtn);

        item.appendChild(left);
        item.appendChild(btns);
        countdownsEl.appendChild(item);
      });

      // year left
      const end = new Date(getNowForTZ().getFullYear(), 11, 31);
      const daysLeft = Math.floor((end - getNowForTZ()) / 86400000);
      yearLeftEl.textContent = `${daysLeft} days left this year`;
    }

    addCountdownBtn.addEventListener("click", addCountdownWithName);

    // --------- Screenshot ----------
    function takeShot(){
      html2canvas(document.body).then(canvas => {
        const a = document.createElement("a");
        a.href = canvas.toDataURL();
        a.download = "clock.png";
        a.click();
      }).catch(err => alert("Screenshot failed: " + err));
    }

    // --------- small helpers ----------
    function escapeHtml(text) {
      return text.replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    }

    // --------- INITIAL RUN / INTERVALS ----------
    setInterval(updateClock, 50);
    setInterval(updateCountdowns, 1000);
    updateClock();
    updateCountdowns();
    
    // --------- EASTER EGG ----------
document.addEventListener("keydown", (e) => {
  const key = e.key.toLowerCase();
  if(!window.secretCode) window.secretCode = "";
  window.secretCode += key;

  if(window.secretCode.length > 5) {
    window.secretCode = window.secretCode.slice(-5);
  }

  if(window.secretCode === "bilal") {
    alert("🎉 You found the secret code for this file! 🎉");
    document.body.style.background = "#FFFF00";
    document.body.style.color = "#228B22";
  }
});

  </script>
</body>
</html>
