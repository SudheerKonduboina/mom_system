console.log("CONTROLLER LOADED");

const startBtn = document.getElementById('start');
const pauseBtn = document.getElementById('pause');
const resumeBtn = document.getElementById('resume');
const stopBtn = document.getElementById('stop');
const statusEl = document.getElementById('status');

// --- RECORDING STATE LOGIC ---

function updateUI(state) {
    // Show/Hide buttons based on state
    startBtn.style.display = (state === 'inactive') ? 'block' : 'none';
    pauseBtn.style.display = (state === 'recording') ? 'block' : 'none';
    resumeBtn.style.display = (state === 'paused') ? 'block' : 'none';
    stopBtn.style.display = (state !== 'inactive') ? 'block' : 'none';
    
    // Update status text
    if (state === 'recording') {
        updateStatus("Recording meeting audio...", true);
    } 
    else if (state === 'paused') {
        updateStatus("Recording paused", false, "#f39c12");
    } 
    else {
        updateStatus("Ready to record", false);
    }
}

// MERGED LOGIC: Safety check added to prevent duplicate capture errors
startBtn.onclick = () => {
    // Check if we are already recording to prevent the "Active Stream" error
    chrome.runtime.sendMessage({ action: "GET_STATE" }, (response) => {
        if (response && response.state !== 'inactive') {
            console.warn("Already recording!");
            updateUI(response.state);
            return; 
        }

        // Only capture if inactive
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            const currentTab = tabs[0];
            if (!currentTab) return;

            chrome.tabCapture.getMediaStreamId({ targetTabId: currentTab.id }, (streamId) => {
                if (chrome.runtime.lastError) {
                    console.error("Capture Error:", chrome.runtime.lastError.message);
                    updateStatus("Error: Tab already being captured", false, "red");
                    return;
                }

                chrome.runtime.sendMessage({ 
                    action: "START_RECORDING", 
                    streamId: streamId 
                });
                
                updateUI('recording');
            });
        });
    });
};

pauseBtn.onclick = () => {
    chrome.runtime.sendMessage({ action: "PAUSE_RECORDING" });
    updateUI('paused');
};

resumeBtn.onclick = () => {
    chrome.runtime.sendMessage({ action: "RESUME_RECORDING" });
    updateUI('recording');
};

stopBtn.onclick = () => {
    updateStatus("Generating MOM in background...", false);
    chrome.runtime.sendMessage({ action: "STOP_RECORDING" });
    
    // Briefly show finished status before resetting
    setTimeout(() => {
        updateUI('inactive');
    }, 2000);
};

function updateStatus(message, isPulse, color = "inherit") {
    if (statusEl) {
        statusEl.style.color = color;
        statusEl.innerHTML = isPulse ? `<span class="pulse"></span> ${message}` : message;
    }
}

// --- INITIALIZATION ---

document.addEventListener('DOMContentLoaded', () => {
    // Ask background script what the current state is
    chrome.runtime.sendMessage({ action: "GET_STATE" }, (response) => {
        if (response) updateUI(response.state);
    });
});

// Listener for errors from background
chrome.runtime.onMessage.addListener((request) => {
    if (request.action === "ERROR_OCCURRED") {
        updateStatus("Error: " + request.message, false, "red");
        updateUI('inactive');
    }
});