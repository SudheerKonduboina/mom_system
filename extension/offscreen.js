let mediaRecorder;
let audioChunks = [];
let currentStream;

chrome.runtime.onMessage.addListener(async (message) => {
    // Ensure the message is intended for the offscreen document
    if (message.target !== 'offscreen') return;

    if (message.action === 'START_RECORDING') {
        startRecording(message.streamId);
    } else if (message.action === 'STOP_RECORDING') {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
    } else if (message.action === 'PAUSE_RECORDING') {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.pause();
        }
    } else if (message.action === 'RESUME_RECORDING') {
        if (mediaRecorder && mediaRecorder.state === 'paused') {
            mediaRecorder.resume();
        }
    }
});

async function startRecording(streamId) {
    try {
        // Capture the tab audio using the streamId passed from the popup/background
        currentStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                mandatory: {
                    chromeMediaSource: 'tab',
                    chromeMediaSourceId: streamId
                }
            },
            video: false
        });

        // Loop the audio back to the user's speakers so they can still hear the meeting
        const audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(currentStream);
        source.connect(audioContext.destination);

        // Configure the recorder with high bitrate for better AI transcription accuracy
        mediaRecorder = new MediaRecorder(currentStream, { 
            mimeType: 'audio/webm',
            audioBitsPerSecond: 128000 
        });

        audioChunks = [];

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            const reader = new FileReader();
            
            reader.readAsDataURL(audioBlob);
            reader.onloadend = () => {
                // Send the final recording back to background.js for processing
                chrome.runtime.sendMessage({ 
                    action: 'AUDIO_DATA_READY', 
                    data: reader.result 
                });

                // Cleanup: Stop all audio tracks and release memory
                currentStream.getTracks().forEach(t => t.stop());
                audioContext.close();
            };
        };

        // Collect data in 5-second intervals to ensure stability during long sessions
        mediaRecorder.start(5000);

    } catch (error) {
        console.error("Error starting recording in offscreen:", error);
    }
}