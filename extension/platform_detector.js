// extension/platform_detector.js
// Detects meeting platform from URL and returns platform-specific selectors

const PLATFORMS = {
    google_meet: {
        urlPatterns: ["meet.google.com"],
        name: "Google Meet",
        selectors: {
            participantName: [
                '[data-participant-id] [data-self-name]',
                '.Zj7Ypf', '.z38b6',
                '[role="listitem"] span[dir="auto"]',
                'div[jsname="W297wb"]',
                '[data-self-name]',
            ],
            meetingTitle: ['[data-meeting-title]', '.lefKab'],
            selfName: ['[data-self-name]'],
        }
    },
    zoom: {
        urlPatterns: ["zoom.us/wc", "app.zoom.us"],
        name: "Zoom",
        selectors: {
            participantName: [
                '.participants-item__display-name',
                '.participant-item-name',
                '[class*="participant"] [class*="name"]',
            ],
            meetingTitle: ['.meeting-title', '[class*="meeting-topic"]'],
            selfName: ['[class*="my-name"]'],
        }
    },
    teams: {
        urlPatterns: ["teams.microsoft.com", "teams.live.com"],
        name: "Microsoft Teams",
        selectors: {
            participantName: [
                '[data-tid="roster-participant"]',
                '[class*="participant-name"]',
                '[role="listitem"] [class*="name"]',
            ],
            meetingTitle: ['[data-tid="meeting-title"]'],
            selfName: ['[data-tid="self-name"]'],
        }
    },
    generic: {
        urlPatterns: [],
        name: "Generic",
        selectors: {
            participantName: [],
            meetingTitle: [],
            selfName: [],
        }
    }
};

function detectPlatform() {
    const url = window.location.href.toLowerCase();

    for (const [key, config] of Object.entries(PLATFORMS)) {
        if (config.urlPatterns.some(pattern => url.includes(pattern))) {
            return { platform: key, ...config };
        }
    }

    return { platform: "generic", ...PLATFORMS.generic };
}

// Export for use in trackers
if (typeof window !== 'undefined') {
    window.MeetingPlatform = { detectPlatform, PLATFORMS };
}
