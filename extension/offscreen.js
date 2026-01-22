let mediaRecorder;
let audioChunks = [];
let currentStream;

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

        const audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(currentStream);
        source.connect(audioContext.destination);

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
                chrome.runtime.sendMessage({
                    action: 'AUDIO_DATA_READY',
                    data: reader.result
                });

                currentStream.getTracks().forEach(t => t.stop());
                audioContext.close();
            };
        };

        mediaRecorder.start(5000);
        console.log("Offscreen: MediaRecorder started");

    } catch (err) {
        console.error("Offscreen recording error:", err);
    }
}
