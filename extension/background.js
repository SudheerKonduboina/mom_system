let keepAliveInterval = null;

function startKeepAlive() {
    if (keepAliveInterval) return;
    keepAliveInterval = setInterval(() => {
        chrome.runtime.getPlatformInfo(() => {});
    }, 10000); // every 10s
}

function stopKeepAlive() {
    if (keepAliveInterval) {
        clearInterval(keepAliveInterval);
        keepAliveInterval = null;
    }
}

let recordingState = "inactive";

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

    if (request.action === "START_RECORDING") {
        if (recordingState === "inactive") {
            recordingState = "recording";
            startCapture(request.streamId);
        }
        sendResponse({ status: "started" });
        return true;
    }

    if (request.action === "STOP_RECORDING") {
        recordingState = "inactive";
        safeSendToOffscreen({ action: "STOP_RECORDING" });
        sendResponse({ status: "stopped" });
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


// ✅ SAFE OFFSCREEN SEND (CRITICAL FIX)
async function safeSendToOffscreen(message) {
    const contexts = await chrome.runtime.getContexts({
        contextTypes: ["OFFSCREEN_DOCUMENT"]
    });

    if (contexts.length === 0) {
        console.warn("Offscreen not available, skipping message:", message.action);
        return;
    }

    chrome.runtime.sendMessage({
        ...message,
        target: "offscreen"
    });
}


async function startCapture(streamId) {
    await closeOffscreen();

    const contexts = await chrome.runtime.getContexts({
        contextTypes: ["OFFSCREEN_DOCUMENT"]
    });

    if (contexts.length === 0) {
        await chrome.offscreen.createDocument({
            url: "offscreen.html",
            reasons: ["USER_MEDIA"],
            justification: "Recording meeting audio for transcription"
        });
    }

    // ✅ SAFE SEND
    safeSendToOffscreen({
        action: "START_RECORDING",
        streamId
    });
}


async function handleOffscreenAudio(dataUrl) {
    const [meta, base64] = dataUrl.split(",");
    const mime = meta.match(/:(.*?);/)[1];
    const binary = atob(base64);
    const buffer = new Uint8Array(binary.length);

    for (let i = 0; i < binary.length; i++) {
        buffer[i] = binary.charCodeAt(i);
    }

    const blob = new Blob([buffer], { type: mime });

    await closeOffscreen();
    await sendToBackend(blob);
}


async function closeOffscreen() {
    const contexts = await chrome.runtime.getContexts({
        contextTypes: ["OFFSCREEN_DOCUMENT"]
    });

    if (contexts.length > 0) {
        await chrome.offscreen.closeDocument();
    }
}

async function sendToBackend(blob) {
    const BACKEND_URL = "http://127.0.0.1:8000/analyze-meeting";

    try {
        startKeepAlive(); // ✅ KEEP WORKER ALIVE

        const formData = new FormData();
        formData.append("file", blob, "meeting.webm");

        const response = await fetch(BACKEND_URL, {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            throw new Error("Backend failed");
        }

        const result = await response.json();

        if (!result.mom) return;

        await chrome.storage.local.set({ lastMOM: result.mom });

        chrome.tabs.create({
            url: chrome.runtime.getURL("dashboard.html")
        });

    } catch (err) {
        console.error("Upload failed:", err);
    } finally {
        stopKeepAlive(); // ✅ STOP AFTER DONE
    }
}
