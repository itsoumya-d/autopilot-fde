"""Safe draft generation boundary for future provider adapters."""

from backend.models.schema import AgentBranch, AgentStatus, Message


class AgentExecutor:
    def draft(self, agent: AgentBranch, message: Message) -> dict[str, str]:
        if agent.status != AgentStatus.RUNNING:
            raise ValueError("Agent must be approved before it can create a draft")
        return {
            "status": "pending_human_review",
            "draft": "Thanks for your message. We are reviewing the details and will send a confirmed update shortly.",
            "source_message_id": message.id,
            "safety_note": "No external action is available in draft-only mode.",
        }
