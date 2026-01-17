let mediaRecorder;
let audioChunks = [];

// Listen for commands from the background service worker
chrome.runtime.onMessage.addListener(async (message) => {
    // Only handle messages meant for the offscreen document
    if (message.target !== 'offscreen') return;

    try {
        if (message.action === 'START_RECORDING') {
            // 1. Capture the tab stream using the ID passed from background.js
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    mandatory: {
                        chromeMediaSource: 'tab',
                        chromeMediaSourceId: message.streamId
                    }
                },
                video: false
            });

            // 2. Keep audio audible for the user while recording (Loopback)
            const audioContext = new AudioContext();
            const source = audioContext.createMediaStreamSource(stream);
            source.connect(audioContext.destination);

            // 3. Initialize MediaRecorder
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            // 4. Handle the "Stop" event and send data back to background.js
            mediaRecorder.onstop = async () => {
                const blob = new Blob(audioChunks, { type: 'audio/webm' });
                const reader = new FileReader();
                
                reader.onload = () => {
                    // This sends the audio data string back to background.js
                    chrome.runtime.sendMessage({
                        action: 'AUDIO_DATA_READY',
                        target: 'background', 
                        data: reader.result
                    });
                };
                
                reader.readAsDataURL(blob);
            };

            mediaRecorder.start();
            console.log("Offscreen recording started...");

        } else if (message.action === 'STOP_RECORDING') {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                
                // 5. Clean up: Stop all tracks to release the tab audio
                mediaRecorder.stream.getTracks().forEach(track => track.stop());
                console.log("Offscreen recording stopped.");
            }
        }
    } catch (error) {
        console.error("Offscreen Recording Error:", error);
    }
});