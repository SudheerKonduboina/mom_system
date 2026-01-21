document.addEventListener('DOMContentLoaded', () => {
    // 1. Load Data from Storage
    chrome.storage.local.get(['lastMOM'], (result) => {
        if (!result.lastMOM) {
            alert("No MOM data found");
            return;
        }

        //  NEW: Handle wrapped or direct MOM safely
        const momData = result.lastMOM.mom ? result.lastMOM.mom : result.lastMOM;
        updateDashboard(momData);
    });

    // 2. PDF Download Logic (UNCHANGED)
    document.getElementById('downloadPdf').addEventListener('click', () => {
        const element = document.getElementById('mom-content');

        const opt = {
            margin: [10, 10, 10, 10],
            filename: 'Meeting_Minutes.pdf',
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2 },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
        };

        html2pdf().set(opt).from(element).save();
    });
});


// Function to update the dashboard with backend data
function updateDashboard(data) {

    //  SAFETY CHECK (NEW – REQUIRED)
    if (!data || !data.key_discussions) {
        alert("Invalid MOM data received");
        console.error("Invalid MOM payload:", data);
        return;
    }

    // 1. Meta Data
    document.getElementById('meetDate').innerText =
        data.meetDate || new Date().toLocaleString();

    document.getElementById('participants').innerText =
        (Array.isArray(data.participants) && data.participants.length > 0)
            ? data.participants.join(", ")
            : "Participants not detected";

    document.getElementById('agenda').innerText =
        data.agenda || "Meeting Summary";

    // 2. Key Discussions
    document.getElementById('discussions').innerText =
        data.key_discussions || data.summary || "No discussions extracted";

    // 3. Decisions
    const decisionsUl = document.getElementById('decisions');
    decisionsUl.innerHTML = '';

    if (Array.isArray(data.decisions) && data.decisions.length > 0) {
        data.decisions.forEach(text => {
            const li = document.createElement('li');
            li.innerText = text;
            decisionsUl.appendChild(li);
        });
    } else {
        decisionsUl.innerHTML = "<li>No decisions recorded.</li>";
    }

    // 4. Action Items
    const actionBody = document.getElementById('actionBody');
    actionBody.innerHTML = '';

    if (Array.isArray(data.action_items) && data.action_items.length > 0) {
        data.action_items.forEach(item => {
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
        actionBody.insertAdjacentHTML(
            'beforeend',
            `<tr><td>No tasks identified</td><td>-</td><td>-</td></tr>`
        );
    }

    // 5. Risks & Conclusion
    document.getElementById('risks').innerText =
        data.risks || "No significant risks identified.";

    document.getElementById('conclusion').innerText =
        data.conclusion || "Meeting adjourned.";
}
