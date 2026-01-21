document.addEventListener('DOMContentLoaded', () => {
    // 1. Load Data from Storage
    chrome.storage.local.get(['lastMOM'], (result) => {
    if (!result.lastMOM) {
        alert("No MOM data found");
        return;
    }
    updateDashboard(result.lastMOM);
    });


    // 2. PDF Download Logic
    document.getElementById('downloadPdf').addEventListener('click', () => {
        const element = document.getElementById('mom-content');
        
        // PDF Options
        const opt = {
            margin:       [10, 10, 10, 10],
            filename:     'Meeting_Minutes.pdf',
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2 },
            jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
        };

        // Run Library
        html2pdf().set(opt).from(element).save();
    });
});

// Function to update the dashboard with backend data
function updateDashboard(data) {
    // 1. Meta Data
    document.getElementById('meetDate').innerText = data.meetDate || new Date().toLocaleString();
    document.getElementById('participants').innerText = (Array.isArray(data.participants) && data.participants.length > 0) 
        ? data.participants.join(", ") 
        : "Enter participants...";
    document.getElementById('agenda').innerText = data.agenda || "Meeting Summary";

    // 2. Key Discussions
    document.getElementById('discussions').innerText = data.key_discussions || data.summary || "Enter discussions...";

    // 3. Decisions (List)
    const decisionsUl = document.getElementById('decisions');
    decisionsUl.innerHTML = ''; 
    if (data.decisions && data.decisions.length > 0) {
        data.decisions.forEach(text => {
            const li = document.createElement('li');
            li.innerText = text;
            decisionsUl.appendChild(li);
        });
    } else {
        decisionsUl.innerHTML = "<li>No decisions recorded.</li>";
    }

    // 4. Action Items (Table)
    const actionBody = document.getElementById('actionBody');
    actionBody.innerHTML = '';
    if (data.action_items && data.action_items.length > 0) {
        data.action_items.forEach(item => {
            // Check if item is an object (new code) or string (old code fallback)
            const task = item.task || item;
            const owner = item.owner || "Assignee TBD";
            const deadline = item.deadline || "TBD";

            const row = `<tr>
                <td>${task}</td>
                <td>${owner}</td>
                <td>${deadline}</td>
            </tr>`;
            actionBody.insertAdjacentHTML('beforeend', row);
        });
    } else {
        const emptyRow = `<tr><td>No tasks identified</td><td>-</td><td>-</td></tr>`;
        actionBody.insertAdjacentHTML('beforeend', emptyRow);
    }

    // 5. Risks & Conclusion
    document.getElementById('risks').innerText = data.risks || "No significant risks identified.";
    document.getElementById('conclusion').innerText = data.conclusion || "Meeting adjourned.";
}
