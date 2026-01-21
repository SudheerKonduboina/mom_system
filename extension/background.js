let recordingState = "inactive";

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "START_RECORDING") {
        if (recordingState === "inactive") {
            recordingState = "recording";
            startCapture(request.streamId);
        }
    } 
    else if (request.action === "STOP_RECORDING") {
        recordingState = "inactive";
        chrome.runtime.sendMessage({ action: 'STOP_RECORDING', target: 'offscreen' });
    } 
    else if (request.action === "GET_STATE") {
        sendResponse({ state: recordingState });
    } 
    else if (request.action === "AUDIO_DATA_READY") {
        handleOffscreenAudio(request.data);
    }

    if (["PAUSE_RECORDING", "RESUME_RECORDING"].includes(request.action)) {
        recordingState = (request.action === "PAUSE_RECORDING") ? "paused" : "recording";
        chrome.runtime.sendMessage({ action: request.action, target: 'offscreen' });
    }

    return true;
});

async function startCapture(streamId) {
    await closeOffscreen();
    const contexts = await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] });

    if (contexts.length === 0) {
        await chrome.offscreen.createDocument({
            url: 'offscreen.html',
            reasons: ['USER_MEDIA'],
            justification: 'Recording meeting audio for transcription'
        });
    }

    setTimeout(() => {
        chrome.runtime.sendMessage({
            action: 'START_RECORDING',
            target: 'offscreen',
            streamId
        });
    }, 600);
}

async function handleOffscreenAudio(dataUrl) {
    try {
        const [meta, base64] = dataUrl.split(',');
        const mime = meta.match(/:(.*?);/)[1];
        const binary = atob(base64);
        const buffer = new Uint8Array(binary.length);

        for (let i = 0; i < binary.length; i++) {
            buffer[i] = binary.charCodeAt(i);
        }

        const blob = new Blob([buffer], { type: mime });

        await closeOffscreen();
        await sendToBackend(blob);

    } catch (e) {
        console.error("Audio processing error:", e);
    }
}

async function closeOffscreen() {
    const contexts = await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] });
    if (contexts.length > 0) {
        await chrome.offscreen.closeDocument();
    }
}

async function sendToBackend(blob) {
    const BACKEND_URL = "http://127.0.0.1:8000/analyze-meeting";

    try {
        const formData = new FormData();
        formData.append("file", blob, "meeting.webm");

        const response = await fetch(BACKEND_URL, {
            method: "POST",
            body: formData
        });

        if (!response.ok) throw new Error("Backend error");

        const result = await response.json();

        // ✅ SAVE MOM ONLY
        await chrome.storage.local.set({
            lastMOM: result.mom
        });

        await chrome.tabs.create({
            url: chrome.runtime.getURL("dashboard.html")
        });

    } catch (e) {
        console.error("Upload failed:", e);
    }
}
