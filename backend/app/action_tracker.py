# app/action_tracker.py
# Smart action item tracking with status lifecycle, priority, and follow-up detection

import logging
from datetime import datetime
from typing import Any, Dict, List

from app.database import get_db, save_action_items, get_action_items, update_action_item
from app.models import ActionItem

logger = logging.getLogger("ActionTracker")


class ActionTracker:
    """
    Manages action item lifecycle:
    - Status: pending → in_progress → completed → overdue
    - Priority: high / medium / low
    - Follow-up detection across meetings
    """

    def process_new_actions(self, meeting_id: str,
                            action_items: List[Dict],
                            pending_from_context: List[Dict] = None) -> List[Dict]:
        """
        Process newly extracted action items:
        1. Assign priority
        2. Check for follow-ups from previous actions
        3. Save to database
        Returns: enriched action items list
        """
        enriched = []

        for item in action_items:
            task = item.get("task", "")
            owner = item.get("owner", "TBD")
            deadline = item.get("deadline", "TBD")
            priority = item.get("priority", self._infer_priority(task, deadline))

            enriched_item = {
                "task": task,
                "owner": owner,
                "deadline": deadline,
                "priority": priority,
                "status": "pending",
                "is_follow_up": False,
                "original_meeting_id": None,
            }

            # Check if this is a follow-up of a pending item
            if pending_from_context:
                match = self._find_matching_pending(task, owner, pending_from_context)
                if match:
                    enriched_item["is_follow_up"] = True
                    enriched_item["original_meeting_id"] = match.get("from_meeting")
                    # Update the original item status
                    self._update_original_status(match, task)

            enriched.append(enriched_item)

        # Save to database
        save_action_items(meeting_id, enriched)

        return enriched

    def check_overdue(self) -> List[Dict]:
        """Find all action items past their deadline."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        all_pending = get_action_items(status="pending")
        overdue = []

        for item in all_pending:
            deadline = item.get("deadline", "TBD")
            if deadline != "TBD" and self._is_past_deadline(deadline, today):
                update_action_item(item["id"], status="overdue")
                item["status"] = "overdue"
                overdue.append(item)

        return overdue

    def get_summary_for_owner(self, owner: str) -> Dict[str, Any]:
        """Get action item summary for a specific person."""
        items = get_action_items(owner=owner)

        summary = {
            "owner": owner,
            "total": len(items),
            "pending": [i for i in items if i["status"] == "pending"],
            "in_progress": [i for i in items if i["status"] == "in_progress"],
            "completed": [i for i in items if i["status"] == "completed"],
            "overdue": [i for i in items if i["status"] == "overdue"],
        }
        summary["pending_count"] = len(summary["pending"])
        summary["overdue_count"] = len(summary["overdue"])

        return summary

    def _infer_priority(self, task: str, deadline: str) -> str:
        """Infer priority from task description and deadline."""
        lower = task.lower()

        # High priority keywords
        if any(k in lower for k in ["asap", "urgent", "critical", "immediately",
                                      "today", "emergency", "blocker", "p0"]):
            return "high"

        # Deadline proximity
        if deadline and deadline != "TBD":
            lower_deadline = deadline.lower()
            if any(k in lower_deadline for k in ["today", "tomorrow", "asap"]):
                return "high"
            if any(k in lower_deadline for k in ["this week", "friday"]):
                return "medium"

        # Low priority keywords
        if any(k in lower for k in ["nice to have", "optional", "when possible",
                                      "eventually", "low priority"]):
            return "low"

        return "medium"

    def _find_matching_pending(self, new_task: str, owner: str,
                                pending: List[Dict]) -> Dict | None:
        """Find a matching pending item from previous meetings."""
        new_lower = new_task.lower()

        for item in pending:
            old_task = item.get("task", "").lower()
            old_owner = item.get("owner", "").lower()

            # Same owner and similar task description
            if owner.lower() in old_owner or old_owner in owner.lower():
                # Simple word overlap check
                new_words = set(new_lower.split())
                old_words = set(old_task.split())
                overlap = new_words & old_words
                # Remove common words
                overlap -= {"the", "a", "an", "to", "and", "or", "is", "will",
                            "be", "by", "for", "in", "on", "it", "of"}
                if len(overlap) >= 2:
                    return item

        return None

    def _update_original_status(self, original: Dict, new_task: str):
        """Update the status of the original action item based on follow-up mention."""
        new_lower = new_task.lower()

        # Check for completion signals
        if any(k in new_lower for k in ["completed", "done", "finished",
                                          "delivered", "resolved", "closed"]):
            # Try to find and update the original item by meeting_id
            items = get_action_items(meeting_id=original.get("from_meeting"))
            for item in items:
                if item.get("task", "").lower() in original.get("task", "").lower():
                    update_action_item(item["id"], status="completed")
                    break
        else:
            # Still in progress
            items = get_action_items(meeting_id=original.get("from_meeting"))
            for item in items:
                if item.get("task", "").lower() in original.get("task", "").lower():
                    update_action_item(item["id"], status="in_progress")
                    break

    def _is_past_deadline(self, deadline: str, today: str) -> bool:
        """Check if a deadline string represents a past date."""
        import re

        low = deadline.lower()
        # Skip non-date deadlines
        if low in ["tbd", "none", "n/a", ""]:
            return False

        # Try to detect day names (Monday, Tuesday, etc.) — can't reliably compare
        days = ["monday", "tuesday", "wednesday", "thursday", "friday",
                "saturday", "sunday"]
        if any(d in low for d in days):
            return False  # Can't compare without knowing which week

        # Try date formats
        date_patterns = [
            r"(\d{4}-\d{2}-\d{2})",
            r"(\d{1,2}/\d{1,2}/\d{2,4})",
            r"(\d{1,2}-\d{1,2}-\d{2,4})",
        ]
        for pattern in date_patterns:
            match = re.search(pattern, deadline)
            if match:
                try:
                    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y",
                                "%m/%d/%y", "%d-%m-%y"):
                        try:
                            d = datetime.strptime(match.group(1), fmt)
                            return d.strftime("%Y-%m-%d") < today
                        except ValueError:
                            continue
                except Exception:
                    pass

        return False
