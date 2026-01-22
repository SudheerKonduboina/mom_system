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

        chrome.runtime.sendMessage({
            action: "STOP_RECORDING",
            target: "offscreen"
        });

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

    // ✅ THIS WAS MISSING (CRITICAL)
    chrome.runtime.sendMessage({
        action: "START_RECORDING",
        target: "offscreen",
        streamId: streamId
    });
}


async function handleOffscreenAudio(dataUrl) {
    try {
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

    } catch (e) {
        console.error("Audio processing error:", e);
    }
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
        const formData = new FormData();
        formData.append("file", blob, "meeting.webm");

        console.log("Uploading audio...");

        const response = await fetch(BACKEND_URL, {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            throw new Error("Backend failed");
        }

        const result = await response.json();
        console.log("Backend response:", result);

        if (!result.mom) {
            console.error("MOM missing in response");
            return;
        }

        await chrome.storage.local.set({ lastMOM: result.mom });

        console.log("MOM saved successfully");

        await chrome.tabs.create({
            url: chrome.runtime.getURL("dashboard.html")
        });

    } catch (err) {
        console.error("Upload failed:", err);
    }
}
