// extension/meet_tracker.js
// Participant tracker with platform detection, reliable join/leave tracking,
// periodic re-scan, and the previously missing diffAndEmit function

let tracking = false;
let observer = null;
let rescanInterval = null;

// Map: name -> { joinedAt, lastSeenAt, active }
const known = new Map();

function nowISO() {
  return new Date().toISOString();
}

function send(event) {
  try {
    chrome.runtime.sendMessage({ source: "meet_tracker", ...event }, () => {
      if (chrome.runtime.lastError) {
        console.warn("meet_tracker send failed:", chrome.runtime.lastError.message);
      }
    });
  } catch (e) {
    console.warn("meet_tracker send error:", e);
  }
}

// ─── Platform Detection ──────────────────────────────────────
function getSelectors() {
  const url = window.location.href.toLowerCase();

  if (url.includes("meet.google.com")) {
    return [
      '[data-participant-id] [data-self-name]',
      '.Zj7Ypf', '.z38b6',
      '[role="listitem"] span[dir="auto"]',
      'div[jsname="W297wb"]',
      '[data-self-name]',
      // Additional fallback selectors for newer Meet versions
      '[data-requested-participant-id] span',
      '[jsname="yblkhe"]',
      '[data-participant-id] span[class]',
    ];
  }
  if (url.includes("zoom.us")) {
    return [
      '.participants-item__display-name',
      '.participant-item-name',
      '[class*="participant"] [class*="name"]',
    ];
  }
  if (url.includes("teams.microsoft.com") || url.includes("teams.live.com")) {
    return [
      '[data-tid="roster-participant"]',
      '[class*="participant-name"]',
      '[role="listitem"] [class*="name"]',
    ];
  }
  return [];
}

// ─── Read Participant Names ──────────────────────────────────
function readParticipantNames() {
  const names = new Set();
  const selectors = getSelectors();

  for (const selector of selectors) {
    try {
      const elements = document.querySelectorAll(selector);
      for (const node of elements) {
        // Handle Meet's text masking
        let txt = "";
        if (node.getAttribute('data-self-name')) {
          txt = node.getAttribute('data-self-name');
        } else if (node.getAttribute('data-participant-id')) {
          // Traverse down to find actual text if this is a wrapper
          const span = node.querySelector('span[dir="auto"], span[class]');
          if (span) txt = span.innerText || span.textContent;
          else txt = node.innerText || node.textContent;
        } else {
          txt = node.innerText || node.textContent;
        }

        txt = (txt || "").trim();
        if (!txt) continue;

        // Grab just the first line (name)
        const candidate = txt.split("\n")[0].trim();
        if (isValidName(candidate)) {
          names.add(candidate);
        }
      }
    } catch (e) {
      // Skip invalid selectors silently
    }
  }

  // Self name detection explicit
  try {
    const selfEl = document.querySelector('[data-self-name]');
    if (selfEl) {
      const selfName = (selfEl.getAttribute('data-self-name') || selfEl.innerText || "").trim();
      if (selfName && isValidName(selfName)) {
        names.add(selfName);
      }
    }
  } catch (e) { }

  return names;
}

function isValidName(name) {
  if (!name || name.length < 2 || name.length > 50) return false;
  const lower = name.toLowerCase();

  const badExactStrings = [
    "you", "(you)", "presentation", "presenting", "microphone", "camera", "host",
    "meeting details", "recording", "caption", "settings"
  ];

  if (badExactStrings.includes(lower)) return false;

  const badIncludes = [
    "turn on", "turn off", "raise hand", "lower hand", "more options"
  ];

  if (badIncludes.some(b => lower.includes(b))) return false;
  if (/^\d+[:.]?\d*$/.test(name)) return false;
  if (name.length > 40) return false;

  return true;
}

// ─── DIFF AND EMIT (previously missing!) ─────────────────────
function diffAndEmit(currentNames) {
  const now = nowISO();
  const currentSet = new Set(currentNames);

  // Normalize for comparison
  const normalizeKey = (name) => name.trim().toLowerCase();

  // Detect new participants (JOIN)
  for (const name of currentSet) {
    const key = normalizeKey(name);
    const existing = findKnownByKey(key);

    if (!existing) {
      // New participant
      known.set(key, {
        name: name,
        joinedAt: now,
        lastSeenAt: now,
        active: true
      });
      send({ type: "PARTICIPANT_JOIN", name: name, at: now });
    } else if (!existing.active) {
      // Rejoined
      existing.active = true;
      existing.lastSeenAt = now;
      known.set(key, existing);
      send({ type: "PARTICIPANT_JOIN", name: name, at: now });
    } else {
      // Still here — update lastSeen
      existing.lastSeenAt = now;
      known.set(key, existing);
    }
  }

  // Detect left participants (LEAVE)
  for (const [key, info] of known.entries()) {
    if (info.active && !hasNameInSet(currentSet, info.name)) {
      info.active = false;
      known.set(key, info);
      send({ type: "PARTICIPANT_LEAVE", name: info.name, at: now });
    }
  }
}

function findKnownByKey(key) {
  return known.get(key) || null;
}

function hasNameInSet(nameSet, targetName) {
  const targetKey = targetName.trim().toLowerCase();
  for (const name of nameSet) {
    if (name.trim().toLowerCase() === targetKey) return true;
  }
  return false;
}

// ─── UI Hint ─────────────────────────────────────────────────
function showHint() {
  const hintId = "ai-mom-hint";
  if (document.getElementById(hintId)) return;

  const hint = document.createElement("div");
  hint.id = hintId;
  hint.innerHTML = `
    <div style="position: fixed; top: 10px; right: 10px; z-index: 10000;
                background: #1a73e8; color: white; padding: 12px 16px;
                border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                font-family: 'Google Sans', Roboto, Arial, sans-serif; font-size: 14px;
                display: flex; align-items: center; gap: 10px; cursor: pointer;">
      <span>🎙️ AI MOM recording. Keep <b>Participants</b> panel open for tracking.</span>
      <span style="font-weight: bold; margin-left: 5px;">×</span>
    </div>
  `;
  hint.onclick = () => hint.remove();
  document.body.appendChild(hint);
  setTimeout(() => { if (hint.parentNode) hint.remove(); }, 10000);
}

// ─── Tracking Lifecycle ──────────────────────────────────────
function startTracking() {
  if (tracking) return;
  tracking = true;

  showHint();
  send({ type: "TRACKING_STARTED", at: nowISO() });

  // Initial snapshot
  const initial = readParticipantNames();
  if (initial.size > 0) diffAndEmit(initial);

  // MutationObserver for DOM changes
  observer = new MutationObserver(() => {
    if (!tracking) return;
    const names = readParticipantNames();
    if (names.size > 0) diffAndEmit(names);
  });
  observer.observe(document.body, { childList: true, subtree: true });

  // Periodic re-scan every 10s (reliability backup)
  rescanInterval = setInterval(() => {
    if (!tracking) return;
    const names = readParticipantNames();
    if (names.size > 0) diffAndEmit(names);
  }, 10000);
}

function stopTracking() {
  if (!tracking) return;
  tracking = false;

  if (observer) observer.disconnect();
  observer = null;

  if (rescanInterval) clearInterval(rescanInterval);
  rescanInterval = null;

  // Emit leave for all active participants
  const now = nowISO();
  for (const [key, info] of known.entries()) {
    if (info.active) {
      info.active = false;
      known.set(key, info);
      send({ type: "PARTICIPANT_LEAVE", name: info.name, at: now });
    }
  }

  send({ type: "TRACKING_STOPPED", at: now });
  known.clear();
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg?.action === "MEET_TRACK_START") startTracking();
  if (msg?.action === "MEET_TRACK_STOP") stopTracking();
});
