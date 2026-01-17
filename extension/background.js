// Service Worker: Acts as the orchestrator between the UI and the Audio Engine
let isRecording = false;

// 1. Listen for messages from popup.js
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    try {
        if (request.action === "START_RECORDING") {
            startCapture();
        } else if (request.action === "STOP_RECORDING") {
            stopCapture();
        } else if (request.action === "AUDIO_DATA_READY") {
            // Handle audio data received from the offscreen document
            handleOffscreenAudio(request.data);
        }
    } catch (error) {
        console.error("Background Orchestration Error:", error);
    }
    return true; // Keep the message channel open for async responses
});

// 2. Optimized startCapture to satisfy Chrome's User Gesture requirement
function startCapture() {
    if (isRecording) return;

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const tab = tabs[0];
        if (!tab) {
            console.error("No active tab found.");
            return;
        }

        chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id }, async (streamId) => {
            if (chrome.runtime.lastError) {
                console.error("Stream ID Error:", chrome.runtime.lastError.message);
                return;
            }

            try {
                // 3. Create or find the Offscreen Document
                const existingContexts = await chrome.runtime.getContexts({
                    contextTypes: ['OFFSCREEN_DOCUMENT']
                });

                if (existingContexts.length === 0) {
                    await chrome.offscreen.createDocument({
                        url: 'offscreen.html',
                        reasons: ['USER_MEDIA'],
                        justification: 'Capturing tab audio for AI Meeting Intelligence'
                    });
                }

                // 4. Trigger recording in offscreen
                chrome.runtime.sendMessage({
                    action: 'START_RECORDING',
                    target: 'offscreen',
                    streamId: streamId
                });

                isRecording = true;
                console.log("Recording state: ACTIVE");

            } catch (e) {
                console.error("Offscreen Document Setup Failed:", e);
            }
        });
    });
}

// 5. Signals the offscreen document to finalize recording
async function stopCapture() {
    try {
        if (!isRecording) return;

        chrome.runtime.sendMessage({
            action: 'STOP_RECORDING',
            target: 'offscreen'
        });

        isRecording = false;
        console.log("Recording state: STOPPED. Processing audio...");
    } catch (e) {
        console.error("Stop Sequence Failed:", e);
    }
}

// 6. Bridge: Converts DataURL from Offscreen back to a Blob for Upload
async function handleOffscreenAudio(dataUrl) {
    try {
        const response = await fetch(dataUrl);
        const audioBlob = await response.blob();
        
        await sendToBackend(audioBlob);

        // Cleanup: Close offscreen document to free up memory
        await chrome.offscreen.closeDocument();
    } catch (e) {
        console.error("Audio conversion failed:", e);
    }
}

// 7. Transmission: Sends the final file to your FastAPI Server
async function sendToBackend(blob) {
    try {
        console.log("Sending audio to AI Backend...");
        const formData = new FormData();
        formData.append("file", blob, "meeting_audio.webm");

        const response = await fetch("http://localhost:8000/analyze-meeting", {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            const errorDetail = await response.text();
            throw new Error(`Server Error (${response.status}): ${errorDetail}`);
        }

        const result = await response.json();
        console.log("MOM Intelligence Received:", result);
        
        // Save to local storage so the popup can display the summary
        chrome.storage.local.set({ lastMOM: result });

    } catch (error) {
        // --- NEW ERROR HANDLING BLOCK ---
        console.error("Backend Transmission Failed:", error);
        
        // Notify the popup that something went wrong
        chrome.runtime.sendMessage({
            action: "ERROR_OCCURRED",
            message: "Could not connect to AI Server. Is it running?"
        });
    }
}