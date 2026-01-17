// --- Recording Controls ---

document.getElementById('start').onclick = () => {
    chrome.runtime.sendMessage({ action: "START_RECORDING" });
    
    // Inject the pulse animation and update text
    document.getElementById('status').innerHTML = '<span class="pulse"></span> Recording...';
    
    // Hide old results when starting a new session
    document.getElementById('resultsSection').style.display = 'none';
};

document.getElementById('stop').onclick = () => {
    chrome.runtime.sendMessage({ action: "STOP_RECORDING" });
    
    // Update status to processing (Pulse is removed here)
    document.getElementById('status').innerText = "Processing MOM...";
    
    // Show a loading state in the summary area
    document.getElementById('resultsSection').style.display = 'block';
    document.getElementById('summaryText').innerText = "AI is analyzing your meeting audio, please wait...";
    document.getElementById('actionList').innerHTML = '';
};

// --- Display Logic ---

/**
 * Function to update the UI with saved data from Chrome Storage
 * Handles the new intelligence features: Clarity Score, Owners, and Speaker IDs
 */
function displayResults() {
    chrome.storage.local.get(['lastMOM'], (result) => {
        if (result.lastMOM) {
            const data = result.lastMOM;
            
            // 1. Reveal the results section
            document.getElementById('resultsSection').style.display = 'block';
            
            // 2. Set the Summary
            document.getElementById('summaryText').innerText = data.summary;
            
            // 3. Update Status with Clarity Score
            const scorePercent = (data.clarity_score * 100).toFixed(0);
            document.getElementById('status').innerHTML = `Analysis Complete! (Clarity: <b>${scorePercent}%</b>)`;
            
            // 4. Clear and Populate Action Items with Metadata
            const actionList = document.getElementById('actionList');
            actionList.innerHTML = ''; // Clear old items
            
            if (data.action_items && data.action_items.length > 0) {
                data.action_items.forEach(item => {
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <div style="margin-bottom: 8px;">
                            <span style="color: #007bff; font-weight: bold;">${item.owner}:</span> 
                            ${item.task}
                            <br>
                            <small style="color: #666;">— ${item.speaker} at ${formatTime(item.timestamp)}</small>
                        </div>
                    `;
                    actionList.appendChild(li);
                });
            } else {
                const li = document.createElement('li');
                li.innerText = "No specific action items detected.";
                actionList.appendChild(li);
            }
        }
    });
    // Refresh history whenever results are updated
    loadHistory();
}

/**
 * Function to load meeting history from the backend
 */
async function loadHistory() {
    try {
        const response = await fetch('http://localhost:8000/meetings');
        const data = await response.json();
        const historyList = document.getElementById('historyList');
        historyList.innerHTML = ''; // Clear current list

        if (data.meetings && data.meetings.length > 0) {
            data.meetings.forEach(fileName => {
                const li = document.createElement('li');
                li.className = "history-item"; // Matches the CSS class we added
                
                // Create a clickable link for each meeting
                const link = document.createElement('a');
                link.href = "#";
                link.innerText = fileName.replace('_meeting.webm', '').replace(/-/g, '/'); // Pretty format date
                
                link.onclick = (e) => {
                    e.preventDefault();
                    alert("Feature: Re-analyzing " + fileName);
                    // Add logic here to re-fetch this specific file if needed
                };

                li.appendChild(link);
                historyList.appendChild(li);
            });
        } else {
            historyList.innerHTML = '<li style="padding: 5px;">No history found.</li>';
        }
    } catch (error) {
        console.error("Failed to load history:", error);
    }
}

// Helper function to format seconds into MM:SS for the UI
function formatTime(seconds) {
    if (!seconds) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// --- Initialization & Listeners ---

// Initialize UI
displayResults();
loadHistory();

// Listen for storage changes (triggered when background.js receives data from backend)
chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.lastMOM) {
        displayResults();
    }
});

// Listen for errors from the background script
chrome.runtime.onMessage.addListener((request) => {
    if (request.action === "ERROR_OCCURRED") {
        const statusEl = document.getElementById('status');
        statusEl.innerText = "Error!";
        statusEl.style.color = "red";
        alert(request.message);
    }
});