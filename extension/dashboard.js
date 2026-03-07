// extension/dashboard.js
// Renders meeting intelligence report from stored results

const SPEAKER_COLORS = [
  "#ab47bc", "#4fc3f7", "#66bb6a", "#ffb74d",
  "#ef5350", "#26c6da", "#ffa726", "#7e57c2"
];

document.addEventListener("DOMContentLoaded", () => {
  chrome.storage.local.get(
    ["lastFullResult", "lastMOM", "lastAttendance", "lastInsights",
      "lastWarnings", "lastActionItems", "lastSpeakerTranscript"],
    (data) => {
      const result = data.lastFullResult || {};
      const mom = result.mom || data.lastMOM || {};
      const attendance = result.attendance_events || data.lastAttendance || [];
      const insights = result.insights || data.lastInsights || {};
      const warnings = result.warnings || data.lastWarnings || [];
      const actionItems = result.action_items || data.lastActionItems || mom.action_items || [];
      const speakerTranscript = result.speaker_transcript || data.lastSpeakerTranscript || "";

      renderMeta(mom, result);
      renderWarnings(warnings);
      renderInsights(insights);
      renderTopics(insights.topics || mom.topics_detected || []);
      renderSpeakingTime(insights.speaking_time_analytics || []);
      renderList("discussions", mom.key_discussions || []);
      renderList("decisions", mom.decisions || []);
      renderActionItems(actionItems);
      renderList("risks", mom.risks || []);
      document.getElementById("conclusion").textContent = mom.conclusion || "No conclusion recorded.";
      renderSpeakerTranscript(speakerTranscript);
      renderAttendance(attendance);
    }
  );

  document.getElementById("btnDownloadPDF")?.addEventListener("click", downloadPDF);
  document.getElementById("btnPrint")?.addEventListener("click", () => window.print());
});

function renderMeta(mom, result) {
  document.getElementById("metaDate").textContent = mom.meetDate || new Date().toLocaleDateString();
  document.getElementById("metaPlatform").textContent =
    (result.platform || "google_meet").replace("_", " ").replace(/\b\w/g, c => c.toUpperCase());

  const participants = mom.participants || result.participants || [];
  document.getElementById("metaParticipants").textContent =
    participants.length > 0 ? participants.join(", ") : "No participants detected";

  if (mom.agenda) {
    document.getElementById("meetingTitle").textContent = `📋 ${mom.agenda}`;
  }
}

function renderWarnings(warnings) {
  const banner = document.getElementById("warningsBanner");
  if (!warnings.length) return;

  banner.innerHTML = warnings.map(w => `
    <div class="warning-item ${w.level || 'warning'}">
      <span>${w.level === 'error' ? '❌' : '⚠️'}</span>
      <span>${w.message}</span>
    </div>
  `).join("");
}

function renderInsights(insights) {
  const grid = document.getElementById("insightsGrid");

  const sentiment = insights.sentiment || {};
  const sentimentValue = sentiment.overall || "neutral";
  const engagementScore = insights.engagement_score || 0;

  grid.innerHTML = `
    <div class="insight-card">
      <div class="label">Sentiment</div>
      <div class="value ${sentimentValue}">${sentimentValue.charAt(0).toUpperCase() + sentimentValue.slice(1)}</div>
    </div>
    <div class="insight-card">
      <div class="label">Engagement Score</div>
      <div class="value" style="color: ${engagementScore > 60 ? 'var(--success)' : engagementScore > 30 ? 'var(--warning)' : 'var(--danger)'}">${engagementScore.toFixed(1)}</div>
    </div>
  `;
}

function renderTopics(topics) {
  if (!topics.length) return;
  const card = document.getElementById("topicsCard");
  const tags = document.getElementById("topicsTags");
  card.style.display = "block";
  tags.innerHTML = topics.map(t => `<span class="topic-tag">${t}</span>`).join("");
}

function renderSpeakingTime(analytics) {
  if (!analytics.length) return;
  const card = document.getElementById("speakingTimeCard");
  const bars = document.getElementById("speakingTimeBars");
  card.style.display = "block";

  bars.innerHTML = analytics.map((item, i) => {
    const color = SPEAKER_COLORS[i % SPEAKER_COLORS.length];
    return `
      <div class="speaker-bar">
        <div class="bar-label">
          <span style="color: ${color}">${item.speaker}</span>
          <span>${item.display} (${item.percentage}%)</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill" style="width: ${item.percentage}%; background: ${color};"></div>
        </div>
      </div>
    `;
  }).join("");
}

function renderList(containerId, items) {
  const container = document.getElementById(containerId);
  if (!items.length) {
    container.innerHTML = `<div class="list-item" style="color: var(--text-dim);">None recorded.</div>`;
    return;
  }
  container.innerHTML = items.map(item => {
    if (typeof item === "string") {
      return `<div class="list-item">${item}</div>`;
    }
    return `<div class="list-item">${JSON.stringify(item)}</div>`;
  }).join("");
}

function renderActionItems(items) {
  const container = document.getElementById("actionItems");
  if (!items.length) {
    container.innerHTML = `<div class="list-item" style="color: var(--text-dim);">No action items extracted.</div>`;
    return;
  }

  container.innerHTML = items.map(item => {
    const task = item.task || (typeof item === "string" ? item : "Task");
    const owner = item.owner || "TBD";
    const deadline = item.deadline || "TBD";
    const priority = item.priority || "medium";
    const status = item.status || "pending";

    return `
      <div class="action-item">
        <div class="action-priority ${priority}"></div>
        <div style="flex: 1;">
          <div>${task}</div>
          <div class="action-meta">
            👤 ${owner} &nbsp;|&nbsp; 📅 ${deadline}
            &nbsp;|&nbsp; <span class="action-status ${status}">${status.toUpperCase()}</span>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function renderSpeakerTranscript(text) {
  if (!text) return;
  const card = document.getElementById("speakerTranscriptCard");
  const container = document.getElementById("speakerTranscript");
  card.style.display = "block";

  const lines = text.split("\n").filter(l => l.trim());
  let colorMap = {};
  let colorIdx = 0;

  container.innerHTML = lines.map(line => {
    const colonIdx = line.indexOf(":");
    if (colonIdx > 0 && colonIdx < 40) {
      const speaker = line.substring(0, colonIdx).trim();
      const content = line.substring(colonIdx + 1).trim();
      if (!colorMap[speaker]) {
        colorMap[speaker] = SPEAKER_COLORS[colorIdx++ % SPEAKER_COLORS.length];
      }
      return `<div class="speaker-line"><span class="speaker-name" style="color: ${colorMap[speaker]}">${speaker}:</span> ${content}</div>`;
    }
    return `<div class="speaker-line">${line}</div>`;
  }).join("");
}

function renderAttendance(events) {
  const tbody = document.getElementById("attendanceBody");
  if (!events.length) {
    tbody.innerHTML = `<tr><td colspan="3" style="color: var(--text-dim);">No attendance data</td></tr>`;
    return;
  }

  tbody.innerHTML = events.map(e => {
    const type = e.type || "";
    const icon = type.includes("JOIN") ? "🟢" : type.includes("LEAVE") ? "🔴" : "⚪";
    const time = e.at ? new Date(e.at).toLocaleTimeString() : "—";
    return `<tr><td>${e.name || "Unknown"}</td><td>${icon} ${type}</td><td>${time}</td></tr>`;
  }).join("");
}

function downloadPDF() {
  const element = document.querySelector(".container");
  const btnGroup = document.querySelector(".btn-group");
  if (btnGroup) btnGroup.style.display = "none";

  if (window.html2pdf) {
    html2pdf().set({
      margin: 10,
      filename: `meeting_report_${new Date().toISOString().slice(0, 10)}.pdf`,
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2 },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" }
    }).from(element).save().then(() => {
      if (btnGroup) btnGroup.style.display = "flex";
    });
  } else {
    window.print();
    if (btnGroup) btnGroup.style.display = "flex";
  }
}
