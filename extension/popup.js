// --- Recording Controls ---

document.getElementById('start').onclick = () => {
    chrome.runtime.sendMessage({ action: "START_RECORDING" });
    
    // Updated: Inject the pulse animation and update text
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

// Function to update the UI with saved data from Chrome Storage
function displayResults() {
    chrome.storage.local.get(['lastMOM'], (result) => {
        if (result.lastMOM) {
            const data = result.lastMOM;
            
            // 1. Reveal the results section
            document.getElementById('resultsSection').style.display = 'block';
            
            // 2. Set the Summary
            document.getElementById('summaryText').innerText = data.summary;
            
            // 3. Clear and Populate Action Items
            const actionList = document.getElementById('actionList');
            actionList.innerHTML = ''; // Clear old items
            
            if (data.action_items && data.action_items.length > 0) {
                data.action_items.forEach(item => {
                    const li = document.createElement('li');
                    li.innerText = item;
                    actionList.appendChild(li);
                });
            } else {
                const li = document.createElement('li');
                li.innerText = "No specific action items detected.";
                actionList.appendChild(li);
            }
            
            // 4. Update Status (Ensure pulse is gone)
            document.getElementById('status').innerText = "Analysis Complete!";
        }
    });
}

// Check for existing results immediately when the popup is opened
displayResults();

// Listen for storage changes (triggered when background.js receives data from backend)
chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.lastMOM) {
        displayResults();
    }
});

chrome.runtime.onMessage.addListener((request) => {
    if (request.action === "ERROR_OCCURRED") {
        document.getElementById('statusText').innerText = "Error!";
        document.getElementById('statusText').style.color = "red";
        alert(request.message);
    }
});
