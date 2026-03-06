// extension/offscreen.js
// Offscreen audio recorder with streaming chunk support and error recovery

let mediaRecorder;
let audioChunks = [];
let currentStream;
let audioContext;
let heartbeatInterval;

chrome.runtime.onMessage.addListener(async (message) => {
    if (message.target !== 'offscreen') return;

    if (message.action === 'START_RECORDING') {
        console.log("Offscreen: START_RECORDING received");
        startRecording(message.streamId);
    }

    if (message.action === 'STOP_RECORDING') {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
    }

    if (message.action === 'PAUSE_RECORDING') {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.pause();
        }
    }

    if (message.action === 'RESUME_RECORDING') {
        if (mediaRecorder && mediaRecorder.state === 'paused') {
            mediaRecorder.resume();
        }
    }
});

async function startRecording(streamId) {
    try {
        currentStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                mandatory: {
                    chromeMediaSource: 'tab',
                    chromeMediaSourceId: streamId
                }
            },
            video: false
        });

        audioContext = new AudioContext();

        // Handle suspended state (Chrome autoplay policy)
        if (audioContext.state === 'suspended') {
            await audioContext.resume();
        }

        const source = audioContext.createMediaStreamSource(currentStream);
        source.connect(audioContext.destination);

        mediaRecorder = new MediaRecorder(currentStream, {
            mimeType: 'audio/webm',
            audioBitsPerSecond: 128000
        });

        audioChunks = [];

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
                audioChunks.push(e.data);

                // Stream each chunk to background for WebSocket forwarding
                const reader = new FileReader();
                reader.onloadend = () => {
                    try {
                        chrome.runtime.sendMessage({
                            action: 'AUDIO_CHUNK',
                            data: reader.result
                        }).catch(() => { });
                    } catch (err) {
                        console.warn("Chunk send failed:", err);
                    }
                };
                reader.readAsDataURL(e.data);
            }
        };

        mediaRecorder.onstop = () => {
            cleanup();

            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            const reader = new FileReader();

            reader.readAsDataURL(audioBlob);
            reader.onloadend = () => {
                try {
                    chrome.runtime.sendMessage({
                        action: 'AUDIO_DATA_READY',
                        data: reader.result
                    });
                } catch (err) {
                    console.error("Final audio send failed:", err);
                }
            };
        };

        mediaRecorder.onerror = (event) => {
            console.error("MediaRecorder error:", event.error);
            cleanup();
        };

        // 5s timeslice for streaming chunks
        mediaRecorder.start(5000);
        console.log("Offscreen: MediaRecorder started (5s chunks)");

        // Heartbeat to background every 10s
        heartbeatInterval = setInterval(() => {
            try {
                chrome.runtime.sendMessage({ action: "OFFSCREEN_HEARTBEAT" }).catch(() => { });
            } catch (e) { }
        }, 10000);

    } catch (err) {
        console.error("Offscreen recording error:", err);
        cleanup();
    }
}

function cleanup() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }

    if (currentStream) {
        try {
            currentStream.getTracks().forEach(t => t.stop());
        } catch (e) { }
        currentStream = null;
    }

    if (audioContext) {
        try {
            audioContext.close();
        } catch (e) { }
        audioContext = null;
    }
}
