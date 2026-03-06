# app/context_memory.py
# Cross-meeting intelligence: recurring meeting detection, context injection, follow-up tracking

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import get_db
from app.models import (
    Meeting, MOMRecord, ActionItem, MeetingSeries, ContextLink, Participant
)

logger = logging.getLogger("ContextMemory")


class ContextMemory:
    """
    Manages cross-meeting intelligence:
    - Detects recurring meetings by participant overlap
    - Retrieves pending action items from previous meetings
    - Builds context prompt for AI MOM generation
    """

    def get_context_for_meeting(self, participant_names: List[str],
                                 current_meeting_id: str = "") -> Dict[str, Any]:
        """
        Retrieve relevant context from past meetings for the current meeting.
        Returns context dict that can be injected into AI prompt.
        """
        context = {
            "is_recurring": False,
            "series_name": None,
            "previous_meetings": [],
            "pending_action_items": [],
            "recurring_topics": [],
            "context_prompt": "",
        }

        if not participant_names:
            return context

        db = get_db()
        try:
            # Find matching meeting series
            p_hash = self._participant_hash(participant_names)
            series = db.query(MeetingSeries).filter(
                MeetingSeries.participant_hash == p_hash
            ).first()

            if series:
                context["is_recurring"] = True
                context["series_name"] = series.name
                context["meeting_count"] = series.meeting_count

            # Find previous meetings with overlapping participants
            prev_meetings = self._find_related_meetings(
                db, participant_names, current_meeting_id, limit=3
            )
            context["previous_meetings"] = prev_meetings

            # Get pending action items from related meetings
            pending = self._get_pending_actions(db, participant_names)
            context["pending_action_items"] = pending

            # Get recurring topics
            topics = self._get_recurring_topics(db, participant_names, limit=5)
            context["recurring_topics"] = topics

            # Build context prompt for AI
            context["context_prompt"] = self._build_context_prompt(context)

            return context
        except Exception as e:
            logger.error(f"Context retrieval failed: {e}")
            return context
        finally:
            db.close()

    def update_after_meeting(self, meeting_id: str, participant_names: List[str],
                              topics: List[str] = None):
        """Update context memory after a meeting is processed."""
        if not participant_names:
            return

        db = get_db()
        try:
            p_hash = self._participant_hash(participant_names)

            # Update or create meeting series
            series = db.query(MeetingSeries).filter(
                MeetingSeries.participant_hash == p_hash
            ).first()

            if series:
                series.last_meeting_id = meeting_id
                series.meeting_count += 1
                series.updated_at = datetime.utcnow()
            else:
                series = MeetingSeries(
                    name=f"Meeting with {', '.join(participant_names[:3])}",
                    participant_hash=p_hash,
                    last_meeting_id=meeting_id,
                    meeting_count=1,
                )
                db.add(series)

            # Link to previous meeting if same series
            prev_meetings = self._find_related_meetings(
                db, participant_names, meeting_id, limit=1
            )
            if prev_meetings:
                link = ContextLink(
                    source_meeting_id=meeting_id,
                    target_meeting_id=prev_meetings[0]["meeting_id"],
                    link_type="continuation",
                )
                db.add(link)

            db.commit()
        except Exception as e:
            logger.error(f"Context update failed: {e}")
            db.rollback()
        finally:
            db.close()

    def _participant_hash(self, names: List[str]) -> str:
        """Generate consistent hash from sorted participant names."""
        normalized = sorted(set(n.strip().lower() for n in names if n.strip()))
        return hashlib.sha256(",".join(normalized).encode()).hexdigest()[:16]

    def _find_related_meetings(self, db, participant_names: List[str],
                                exclude_id: str = "", limit: int = 3) -> List[Dict]:
        """Find past meetings with similar participants."""
        results = []
        try:
            # Get all past meetings (most recent first)
            meetings = db.query(Meeting).filter(
                Meeting.status == "completed",
                Meeting.meeting_id != exclude_id
            ).order_by(Meeting.created_at.desc()).limit(20).all()

            for meeting in meetings:
                participants = db.query(Participant).filter(
                    Participant.meeting_id == meeting.meeting_id
                ).all()
                names = {p.name.strip().lower() for p in participants if p.name}
                input_names = {n.strip().lower() for n in participant_names if n}

                overlap = names & input_names
                if len(overlap) >= 2 or (len(overlap) >= 1 and len(input_names) <= 2):
                    mom = db.query(MOMRecord).filter(
                        MOMRecord.meeting_id == meeting.meeting_id
                    ).first()

                    results.append({
                        "meeting_id": meeting.meeting_id,
                        "date": meeting.meet_date.strftime("%Y-%m-%d") if meeting.meet_date else "",
                        "title": meeting.title,
                        "agenda": mom.agenda if mom else "",
                        "conclusion": mom.conclusion if mom else "",
                        "overlap_participants": list(overlap),
                    })

                    if len(results) >= limit:
                        break
        except Exception as e:
            logger.warning(f"Related meeting search failed: {e}")

        return results

    def _get_pending_actions(self, db, participant_names: List[str]) -> List[Dict]:
        """Get pending action items owned by any of the participants."""
        pending = []
        try:
            for name in participant_names:
                items = db.query(ActionItem).filter(
                    ActionItem.owner.ilike(f"%{name.strip()}%"),
                    ActionItem.status.in_(["pending", "in_progress"])
                ).order_by(ActionItem.created_at.desc()).limit(5).all()

                for item in items:
                    pending.append({
                        "task": item.task,
                        "owner": item.owner,
                        "deadline": item.deadline,
                        "status": item.status,
                        "from_meeting": item.meeting_id,
                        "created_at": item.created_at.strftime("%Y-%m-%d") if item.created_at else "",
                    })
        except Exception as e:
            logger.warning(f"Pending action retrieval failed: {e}")

        return pending[:10]  # Max 10

    def _get_recurring_topics(self, db, participant_names: List[str],
                               limit: int = 5) -> List[str]:
        """Find topics that recur across meetings with these participants."""
        try:
            related = self._find_related_meetings(db, participant_names, limit=5)
            all_topics = []
            for meeting in related:
                mom = db.query(MOMRecord).filter(
                    MOMRecord.meeting_id == meeting["meeting_id"]
                ).first()
                if mom and mom.topics:
                    all_topics.extend(mom.topics if isinstance(mom.topics, list) else [])

            # Count frequency
            from collections import Counter
            topic_counts = Counter(all_topics)
            return [t for t, c in topic_counts.most_common(limit) if c >= 2]
        except Exception as e:
            logger.warning(f"Recurring topic detection failed: {e}")
            return []

    def _build_context_prompt(self, context: Dict) -> str:
        """Build a context string to inject into AI MOM generation prompt."""
        parts = []

        if context["is_recurring"]:
            parts.append(f"This is a recurring meeting (#{context.get('meeting_count', '?')}).")

        if context["pending_action_items"]:
            parts.append("Pending action items from previous meetings:")
            for item in context["pending_action_items"][:5]:
                parts.append(
                    f"  - {item['owner']}: {item['task']} "
                    f"(due: {item['deadline']}, status: {item['status']})"
                )

        if context["previous_meetings"]:
            last = context["previous_meetings"][0]
            parts.append(f"Last meeting ({last['date']}): {last.get('conclusion', 'N/A')}")

        if context["recurring_topics"]:
            parts.append(f"Recurring topics: {', '.join(context['recurring_topics'])}")

        return "\n".join(parts) if parts else ""
