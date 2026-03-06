// extension/popup.js
// UI controller for popup with live transcript and error handling

const statusBar = document.getElementById("statusBar");
const btnStart = document.getElementById("btnStart");
const btnStop = document.getElementById("btnStop");
const btnPause = document.getElementById("btnPause");
const btnResume = document.getElementById("btnResume");
const btnRetry = document.getElementById("btnRetry");
const liveTranscript = document.getElementById("liveTranscript");
const transcriptLines = document.getElementById("transcriptLines");
const chunkCount = document.getElementById("chunkCount");
const speakerIndicator = document.getElementById("speakerIndicator");
const errorMsg = document.getElementById("errorMsg");
const errorText = document.getElementById("errorText");

let currentState = "inactive";

function updateUI(state) {
    currentState = state;

    statusBar.className = `status-bar ${state}`;
    btnStart.style.display = "none";
    btnStop.style.display = "none";
    btnPause.style.display = "none";
    btnResume.style.display = "none";

    switch (state) {
        case "recording":
            statusBar.textContent = "● Recording in progress...";
            btnStop.style.display = "inline-block";
            btnPause.style.display = "inline-block";
            liveTranscript.classList.add("active");
            break;
        case "paused":
            statusBar.textContent = "⏸ Recording paused";
            btnStop.style.display = "inline-block";
            btnResume.style.display = "inline-block";
            break;
        case "processing":
            statusBar.textContent = "⏳ Processing meeting...";
            break;
        default:
            statusBar.textContent = "● Ready to record";
            btnStart.style.display = "inline-block";
            liveTranscript.classList.remove("active");
            speakerIndicator.classList.remove("active");
    }

    // Persist state
    chrome.storage.local.set({ popupState: state });
}

// ─── Restore state on popup open ─────────────────────────────
chrome.runtime.sendMessage({ action: "GET_STATE" }, (response) => {
    if (chrome.runtime.lastError) {
        updateUI("inactive");
        return;
    }
    updateUI(response?.state || "inactive");
});

// Restore live transcripts
chrome.storage.local.get("liveTranscripts", (res) => {
    const transcripts = res.liveTranscripts || [];
    if (transcripts.length > 0) {
        liveTranscript.classList.add("active");
        transcripts.forEach(addTranscriptLine);
        chunkCount.textContent = `${transcripts.length} chunks processed`;
    }
});

// ─── Button Handlers ─────────────────────────────────────────
btnStart.addEventListener("click", async () => {
    try {
        errorMsg.classList.remove("show");

        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab) {
            showError("No active tab found.");
            return;
        }

        const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });

        chrome.runtime.sendMessage({ action: "START_RECORDING", streamId }, (response) => {
            if (chrome.runtime.lastError) {
                showError("Failed to start: " + chrome.runtime.lastError.message);
                return;
            }
            if (response?.status === "already_running") {
                showError("Recording already in progress.");
                updateUI("recording");
                return;
            }
            updateUI("recording");
            // Clear previous transcripts
            transcriptLines.innerHTML = "";
            chunkCount.textContent = "0 chunks processed";
        });
    } catch (err) {
        showError("Start failed: " + err.message);
    }
});

btnStop.addEventListener("click", () => {
    updateUI("processing");
    chrome.runtime.sendMessage({ action: "STOP_RECORDING" }, () => {
        if (chrome.runtime.lastError) {
            showError("Stop failed: " + chrome.runtime.lastError.message);
            updateUI("inactive");
        }
    });
});

btnPause.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "PAUSE_RECORDING" }, () => {
        if (!chrome.runtime.lastError) updateUI("paused");
    });
});

btnResume.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "RESUME_RECORDING" }, () => {
        if (!chrome.runtime.lastError) updateUI("recording");
    });
});

btnRetry.addEventListener("click", () => {
    errorMsg.classList.remove("show");
    updateUI("inactive");
});

// ─── Live Transcript Updates ─────────────────────────────────
chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === "LIVE_TRANSCRIPT" && msg.data) {
        addTranscriptLine(msg.data);
        chunkCount.textContent = `${msg.data.chunk_number || '?'} chunks processed`;

        // Speaker indicator
        if (msg.data.speaker) {
            speakerIndicator.textContent = `🎤 ${msg.data.speaker} is speaking`;
            speakerIndicator.classList.add("active");
        }
    }

    if (msg.action === "ERROR_OCCURRED") {
        showError(msg.message || "An error occurred.");
        updateUI("inactive");
    }
});

function addTranscriptLine(data) {
    const line = document.createElement("div");
    line.className = "line";

    if (data.speaker) {
        line.innerHTML = `<span class="speaker">${data.speaker}:</span> ${data.text || "..."}`;
    } else {
        line.textContent = data.text || "...";
    }

    transcriptLines.appendChild(line);
    transcriptLines.scrollTop = transcriptLines.scrollHeight;
}

function showError(msg) {
    errorText.textContent = msg;
    errorMsg.classList.add("show");
}