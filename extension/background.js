// extension/background.js
// Service worker: manages recording, WebSocket streaming, persistence, crash recovery

let keepAliveInterval = null;
let recordingState = "inactive";
let attendanceEvents = [];
let activeMeetTabId = null;
let websocket = null;
let wsReconnectAttempts = 0;
const MAX_WS_RECONNECT = 10;
const BACKEND_REST = "http://127.0.0.1:8000";
const BACKEND_WS = "ws://127.0.0.1:8000/ws/stream-audio";

// ─── Keep-alive ──────────────────────────────────────────────
function startKeepAlive() {
  if (keepAliveInterval) return;
  keepAliveInterval = setInterval(() => {
    chrome.runtime.getPlatformInfo(() => { });
  }, 10000);
}

function stopKeepAlive() {
  if (keepAliveInterval) { clearInterval(keepAliveInterval); keepAliveInterval = null; }
}

// ─── State Persistence ───────────────────────────────────────
async function saveState() {
  try {
    await chrome.storage.local.set({
      _bgState: {
        recordingState,
        activeMeetTabId,
        startedAt: recordingState !== "inactive" ? Date.now() : null,
      }
    });
  } catch (e) { console.warn("State save failed:", e); }
}

async function restoreState() {
  try {
    const { _bgState } = await chrome.storage.local.get("_bgState");
    if (_bgState) {
      // If we were recording before service worker restart, mark as inactive
      // (can't resume MediaRecorder after restart)
      if (_bgState.recordingState !== "inactive") {
        console.warn("Service worker restarted during recording. State reset.");
        recordingState = "inactive";
      }
    }
  } catch (e) { console.warn("State restore failed:", e); }
}

// Restore state on startup
restoreState();

// ─── API Key Helper ──────────────────────────────────────────
function getHeaders() {
  // Add API key if configured (stored in extension settings)
  return {};  // Add X-API-Key header here if auth is enabled
}

// ─── Offscreen Document Helpers ──────────────────────────────
async function safeSendToOffscreen(message) {
  try {
    const contexts = await chrome.runtime.getContexts({ contextTypes: ["OFFSCREEN_DOCUMENT"] });
    if (contexts.length === 0) {
      await chrome.offscreen.createDocument({
        url: "offscreen.html",
        reasons: ["USER_MEDIA"],
        justification: "Recording meeting audio for transcription"
      });
    }
    chrome.runtime.sendMessage({ ...message, target: "offscreen" });
  } catch (err) {
    console.error("Offscreen send failed:", err);
  }
}

async function closeOffscreen() {
  try {
    const contexts = await chrome.runtime.getContexts({ contextTypes: ["OFFSCREEN_DOCUMENT"] });
    if (contexts.length > 0) await chrome.offscreen.closeDocument();
  } catch (err) { console.warn("Offscreen close error:", err); }
}

// ─── WebSocket Streaming ─────────────────────────────────────
function connectWebSocket() {
  if (websocket && websocket.readyState <= 1) return; // CONNECTING or OPEN

  try {
    websocket = new WebSocket(BACKEND_WS);

    websocket.onopen = () => {
      console.log("WebSocket connected");
      wsReconnectAttempts = 0;
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "partial_transcript") {
          // Store partial transcripts for live display
          chrome.storage.local.get("liveTranscripts", (res) => {
            const transcripts = res.liveTranscripts || [];
            transcripts.push(data);
            chrome.storage.local.set({ liveTranscripts: transcripts });
          });
          // Notify popup
          chrome.runtime.sendMessage({
            action: "LIVE_TRANSCRIPT",
            data: data
          }).catch(() => { });
        }
        if (data.type === "session_complete") {
          chrome.storage.local.set({ lastStreamResult: data });
        }
      } catch (e) { console.warn("WS message parse error:", e); }
    };

    websocket.onerror = (err) => {
      console.warn("WebSocket error:", err);
    };

    websocket.onclose = () => {
      console.log("WebSocket closed");
      websocket = null;

      // Auto-reconnect with exponential backoff
      if (recordingState === "recording" && wsReconnectAttempts < MAX_WS_RECONNECT) {
        wsReconnectAttempts++;
        const delay = Math.min(30000, 1000 * Math.pow(2, wsReconnectAttempts));
        console.log(`WS reconnect in ${delay}ms (attempt ${wsReconnectAttempts})`);
        setTimeout(connectWebSocket, delay);
      }
    };
  } catch (e) {
    console.error("WebSocket creation failed:", e);
  }
}

function sendAudioChunk(chunk) {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.send(chunk);
  }
}

function closeWebSocket() {
  if (websocket) {
    try {
      websocket.send("STOP");
      setTimeout(() => {
        if (websocket) { websocket.close(); websocket = null; }
      }, 1000);
    } catch (e) {
      if (websocket) { websocket.close(); websocket = null; }
    }
  }
}

// ─── Start Capture ───────────────────────────────────────────
async function startCapture(streamId) {
  await closeOffscreen();
  await new Promise(r => setTimeout(r, 200));

  try {
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["USER_MEDIA"],
      justification: "Recording meeting audio for transcription"
    });

    // Try WebSocket streaming first
    connectWebSocket();

    await safeSendToOffscreen({ action: "START_RECORDING", streamId });
  } catch (err) {
    console.error("Capture start failed:", err);
  }
}

// ─── Send to Meet Tracker ────────────────────────────────────
function sendMeetTrack(tabId, action) {
  if (!tabId) return;
  chrome.tabs.get(tabId, (tab) => {
    if (chrome.runtime.lastError || !tab) return;
    chrome.tabs.sendMessage(tabId, { action }, () => {
      if (chrome.runtime.lastError) {
        console.warn("Meet track msg failed:", chrome.runtime.lastError.message);
      }
    });
  });
}

// ─── Handle Audio Data ───────────────────────────────────────
async function handleOffscreenAudio(dataUrl) {
  try {
    const [meta, base64] = dataUrl.split(",");
    const mime = meta.match(/:(.*?);/)[1];
    const binary = atob(base64);
    const buffer = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) buffer[i] = binary.charCodeAt(i);
    const blob = new Blob([buffer], { type: mime });

    await closeOffscreen();
    await sendToBackend(blob);
  } catch (err) {
    console.error("Audio processing failed:", err);
  }
}

// Handle streamed chunk from offscreen
async function handleAudioChunk(chunkData) {
  try {
    const [meta, base64] = chunkData.split(",");
    const binary = atob(base64);
    const buffer = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) buffer[i] = binary.charCodeAt(i);
    sendAudioChunk(buffer.buffer);
  } catch (e) {
    console.warn("Chunk forward failed:", e);
  }
}

// ─── Send to Backend (REST fallback) ─────────────────────────
async function sendToBackend(blob) {
  try {
    startKeepAlive();

    const storage = await chrome.storage.local.get("attendanceEvents");
    const events = storage.attendanceEvents || attendanceEvents;

    const formData = new FormData();
    formData.append("file", blob, "meeting.webm");
    formData.append("attendance_events", JSON.stringify(events || []));

    // Platform detection (Note: window is NOT defined in Service Workers)
    let platform = "google_meet";
    try {
      if (activeMeetTabId) {
        const tab = await chrome.tabs.get(activeMeetTabId);
        const tabUrl = tab.url || "";
        if (tabUrl.includes("zoom")) platform = "zoom";
        else if (tabUrl.includes("teams")) platform = "teams";
      }
    } catch (e) {
      console.warn("Platform detection failed, defaulting to google_meet:", e);
    }
    formData.append("platform", platform);

    console.log("Sending to backend:", `${BACKEND_REST}/analyze-meeting`);
    const response = await fetch(`${BACKEND_REST}/analyze-meeting`, {
      method: "POST",
      body: formData,
      headers: getHeaders(),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend failed (${response.status}): ${errorText}`);
    }

    const result = await response.json();

    if (result?.mom) await chrome.storage.local.set({ lastMOM: result.mom });
    if (result?.attendance_events) await chrome.storage.local.set({ lastAttendance: result.attendance_events });
    if (result?.insights) await chrome.storage.local.set({ lastInsights: result.insights });
    if (result?.warnings) await chrome.storage.local.set({ lastWarnings: result.warnings });
    if (result?.action_items) await chrome.storage.local.set({ lastActionItems: result.action_items });
    if (result?.speaker_transcript) await chrome.storage.local.set({ lastSpeakerTranscript: result.speaker_transcript });

    // Store full result
    await chrome.storage.local.set({ lastFullResult: result });

    chrome.tabs.create({ url: chrome.runtime.getURL("dashboard.html") });
  } catch (err) {
    console.error("Upload failed:", err);
    chrome.runtime.sendMessage({
      action: "ERROR_OCCURRED",
      message: err.message || "Upload failed"
    }).catch(() => { });
  } finally {
    stopKeepAlive();
    attendanceEvents = [];
    chrome.storage.local.remove("attendanceEvents");
  }
}

// ─── Message Handler ─────────────────────────────────────────
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Attendance events from meet_tracker
  if (request?.source === "meet_tracker") {
    attendanceEvents.push(request);
    chrome.storage.local.set({ attendanceEvents });
    sendResponse({ ok: true });
    return true;
  }

  // Audio chunk from offscreen (streaming mode)
  if (request.action === "AUDIO_CHUNK") {
    handleAudioChunk(request.data);
    sendResponse({ ok: true });
    return true;
  }

  if (request.action === "START_RECORDING") {
    if (recordingState !== "inactive") {
      sendResponse({ status: "already_running" });
      return true;
    }

    recordingState = "recording";
    attendanceEvents = [];
    chrome.storage.local.set({ attendanceEvents, liveTranscripts: [] });

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs?.[0];
      activeMeetTabId = tab?.id || null;

      if (activeMeetTabId) sendMeetTrack(activeMeetTabId, "MEET_TRACK_START");
      startCapture(request.streamId);
      saveState();
      sendResponse({ status: "started" });
    });
    return true;
  }

  if (request.action === "STOP_RECORDING") {
    recordingState = "inactive";
    if (activeMeetTabId) sendMeetTrack(activeMeetTabId, "MEET_TRACK_STOP");
    closeWebSocket();
    safeSendToOffscreen({ action: "STOP_RECORDING" });
    saveState();
    sendResponse({ status: "stopped" });
    return true;
  }

  if (request.action === "PAUSE_RECORDING") {
    if (recordingState === "recording") {
      recordingState = "paused";
      safeSendToOffscreen({ action: "PAUSE_RECORDING" });
      saveState();
    }
    sendResponse({ status: "paused" });
    return true;
  }

  if (request.action === "RESUME_RECORDING") {
    if (recordingState === "paused") {
      recordingState = "recording";
      safeSendToOffscreen({ action: "RESUME_RECORDING" });
      saveState();
    }
    sendResponse({ status: "resumed" });
    return true;
  }

  if (request.action === "GET_STATE") {
    sendResponse({ state: recordingState });
    return false;
  }

  if (request.action === "AUDIO_DATA_READY") {
    handleOffscreenAudio(request.data)
      .then(() => sendResponse({ status: "processed" }))
      .catch(err => sendResponse({ error: err.message }));
    return true;
  }

  return false;
});

// ─── Auto-stop after 4 hours ─────────────────────────────────
setInterval(() => {
  if (recordingState !== "inactive") {
    chrome.storage.local.get("_bgState", (res) => {
      const state = res._bgState;
      if (state?.startedAt && (Date.now() - state.startedAt > 4 * 60 * 60 * 1000)) {
        console.warn("Auto-stopping recording after 4 hours");
        recordingState = "inactive";
        closeWebSocket();
        safeSendToOffscreen({ action: "STOP_RECORDING" });
        saveState();
      }
    });
  }
}, 60000);
