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
    const existingContexts = await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] });

    if (existingContexts.length === 0) {
        try {
            await chrome.offscreen.createDocument({
                url: 'offscreen.html',
                reasons: ['USER_MEDIA'],
                justification: 'Recording meeting audio for transcription'
            });
        } catch (e) {
            console.error("Offscreen creation failed:", e);
        }
    }

    setTimeout(() => {
        chrome.runtime.sendMessage({
            action: 'START_RECORDING',
            target: 'offscreen',
            streamId: streamId
        });
    }, 600);
}

async function handleOffscreenAudio(dataUrl) {
    try {
        const arr = dataUrl.split(',');
        const mime = arr[0].match(/:(.*?);/)[1];
        const bstr = atob(arr[1]);
        let n = bstr.length;
        const u8arr = new Uint8Array(n);
        while (n--) { u8arr[n] = bstr.charCodeAt(n); }
        const blob = new Blob([u8arr], { type: mime });
        
        // We close offscreen FIRST to free up memory before the heavy fetch
        await closeOffscreen();
        await sendToBackend(blob); 
    } catch (e) { 
        console.error("Audio processing error:", e); 
    }
}

async function closeOffscreen() {
    const contexts = await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] });
    if (contexts.length > 0) await chrome.offscreen.closeDocument();
}

async function sendToBackend(blob) {
    const BACKEND_URL = "http://127.0.0.1:8000/analyze-meeting";
    
    // Increased keep-alive frequency for local Whisper processing
    const keepAlive = setInterval(() => { 
        console.log("Keep-alive: Backend is processing...");
        chrome.runtime.getPlatformInfo(() => {}); 
    }, 500);

    try {
        const formData = new FormData();
        formData.append("file", blob, "meeting.webm");

        console.log("Uploading to Local Engine...");
        const response = await fetch(BACKEND_URL, { 
            method: "POST", 
            body: formData 
        });

        if (!response.ok) throw new Error(`Server error: ${response.status}`);

        const result = await response.json();
        
        // Save to storage
        await chrome.storage.local.set({ lastMOM: result });
        console.log("Analysis complete. Data saved to storage.");

        // OPEN DASHBOARD
        // Use chrome.runtime.getURL to ensure pathing is absolute within the extension
        const dashboardUrl = chrome.runtime.getURL('dashboard.html');
        await chrome.tabs.create({ url: dashboardUrl });

    } catch (error) { 
        console.error("Critical Error:", error);
        // Optional: Open an error page or alert user
    } finally { 
        clearInterval(keepAlive); 
    }
}