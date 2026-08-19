"""Rich realistic enterprise fixture data representing 8 business departments and 250+ events."""

from datetime import datetime, timedelta, timezone
from .models.schema import Channel, ChannelType, ChannelStatus, Message


def demo_channel() -> Channel:
    return Channel(
        id="slack-enterprise-demo",
        type=ChannelType.SLACK,
        credentials={"team_id": "T089ENTERPRISE", "workspace": "Nexus Global Ops"},
        status=ChannelStatus.ACTIVE,
    )


def demo_messages() -> list[Message]:
    start = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
    messages: list[Message] = []

    def add(case: str, offset_hours: float, sender: str, content: str, dept: str = "general") -> None:
        messages.append(Message(
            id=f"{case}-{int(offset_hours*10)}",
            channel_id="slack-enterprise-demo",
            sender=sender,
            content=content,
            timestamp=start + timedelta(hours=offset_hours),
            thread_id=case,
            metadata={"department": dept, "demo": True, "source": "slack_thread"},
        ))

    # 1. DevOps Incident Response & Triage (5 traces)
    for i, service in enumerate(("AuthGateway", "PaymentService", "DataIngestor", "SearchIndex", "NotificationBus")):
        base = i * 14.0
        case = f"incident-p1-{100 + i}"
        add(case, base + 0.0, "pagerduty-bot", f"ALERT: High latency & error budget breach on {service} in us-east-1. Customer traffic affected.", "devops")
        add(case, base + 0.2, "alex-sre", f"Acknowledging alert for {service}. Investigating logs and metrics. Triaging severity.", "devops")
        add(case, base + 0.8, "elena-dev", f"Found root cause in commit hash 4a8f9b: memory leak in connection pool. Assigned to platform team.", "devops")
        add(case, base + 1.5, "alex-sre", f"Rollback executed to v3.14.2 for {service}. Pods recycled. Drafted incident status update for executive team.", "devops")
        add(case, base + 2.5, "alex-sre", f"Telemetry nominal. Post-mortem scheduled. Resolution confirmed and verified with monitoring.", "devops")

    # 2. Support Escalation Resolution (5 traces)
    for i, client in enumerate(("Acme Corp", "Orbit Global", "Juniper Health", "Fintech Labs", "Apex Retail")):
        base = 70.0 + i * 12.0
        case = f"support-esc-{400 + i}"
        add(case, base + 0.0, "maya-csm", f"{client} reports critical export failure after yesterday's release. Customer is blocked on payroll.", "support")
        add(case, base + 0.3, "noah-support", f"Triaged as P2 for {client}. Replicated issue on staging environment with client dataset.", "support")
        add(case, base + 1.2, "noah-support", "Assigned bug ticket HS-492 to core engineering platform team for hotfix.", "support")
        add(case, base + 2.5, "maya-csm", f"Drafted customer update email for {client} leadership with workaround steps and timeline.", "support")
        add(case, base + 4.5, "noah-support", f"Hotfix deployed to production. Tested client export. Fix verified and resolution confirmed.", "support")

    # 3. Enterprise Deal Desk & Discount Approval (4 traces)
    for i, prospect in enumerate(("Stripe Enterprise", "Snowflake AI", "Palantir Gov", "Databricks Scale")):
        base = 135.0 + i * 16.0
        case = f"dealdesk-{200 + i}"
        add(case, base + 0.0, "david-ae", f"Submitted discount request for {prospect}: 3-year agreement with 35% discount ($450k ARR).", "sales")
        add(case, base + 1.0, "clara-dealdesk", f"Reviewed margin analysis for {prospect}. Multi-year commitment qualifies for tier-2 discounting.", "sales")
        add(case, base + 2.5, "marcus-vp-sales", f"Discount approval requested from VP Sales and CFO for {prospect}.", "sales")
        add(case, base + 4.0, "marcus-vp-sales", f"Discount approved with net-30 payment terms clause. Drafted revised quote schedule.", "sales")
        add(case, base + 5.0, "david-ae", f"Executed contract sent via DocuSign to {prospect} general counsel.", "sales")

    # 4. Inbound SDR Lead Routing & Demo Scheduling (5 traces)
    for i, company in enumerate(("Vercel Partner", "Scale AI", "Mistral Hub", "Anthropic Labs", "Cerebras")):
        base = 200.0 + i * 8.0
        case = f"sdr-lead-{300 + i}"
        add(case, base + 0.0, "hubspot-bot", f"New inbound demo request from {company}. ICP score: 94/100. Tech stack: Next.js + Python.", "sales")
        add(case, base + 0.2, "ava-sdr", f"Qualified the lead for {company}: budget >$100k, timeline Q4, decision maker identified.", "sales")
        add(case, base + 0.8, "ava-sdr", f"Assigned account executive David and demo scheduled on calendar for next Tuesday 2 PM EST.", "sales")
        add(case, base + 1.2, "ava-sdr", f"Sent pre-demo questionnaire and customer research briefing to AE.", "sales")

    # 5. Finance Invoice Exception Handling (5 traces)
    for i, vendor in enumerate(("AWS Cloud", "Datadog Telemetry", "Snowflake Warehouse", "Twilio API", "Cloudflare CDN")):
        base = 245.0 + i * 10.0
        case = f"invoice-exc-{800 + i}"
        add(case, base + 0.0, "lee-ap", f"Received invoice exception for {vendor} monthly bill: billed $42,500 vs PO allocation $35,000. Invoice mismatch.", "finance")
        add(case, base + 1.5, "lee-ap", f"Reconciled the invoice against usage logs. Identified unallocated surge egress bandwidth.", "finance")
        add(case, base + 3.0, "sam-controller", f"Payment approval requested from Infrastructure Director for variance.", "finance")
        add(case, base + 5.5, "sam-controller", f"Variance approved. Payment confirmed and remittance slip sent to {vendor}.", "finance")

    # 6. HR Employee Onboarding & IT Provisioning (4 traces)
    for i, name in enumerate(("Sarah Jenkins (SWE)", "Rohan Mehta (Product)", "Chloe Chen (Design)", "Marcus Vance (Sales)")):
        base = 300.0 + i * 15.0
        case = f"hr-onboard-{500 + i}"
        add(case, base + 0.0, "greenhouse-bot", f"Offer signed for new hire {name}. Starting in two weeks.", "hr")
        add(case, base + 1.0, "jordan-hr", f"Initiated background check and generated I-9 verification package for {name}.", "hr")
        add(case, base + 3.0, "kyle-it", f"IT hardware provisioning requested: MacBook M3 Max + Yubikey + Okta profile configured.", "hr")
        add(case, base + 8.0, "jordan-hr", f"Welcome kit dispatched. Onboarding buddy assigned and day-1 calendar invites sent.", "hr")

    # 7. Legal Contract NDA & Vendor Review (4 traces)
    for i, partner in enumerate(("Palantir Foundry", "OpenAI RedTeam", "Cohere Enterprise", "NVIDIA Inception")):
        base = 365.0 + i * 14.0
        case = f"legal-review-{700 + i}"
        add(case, base + 0.0, "rachel-legal", f"Inbound custom Mutual NDA received from {partner} with non-standard IP and indemnity clauses.", "legal")
        add(case, base + 2.0, "rachel-legal", f"Triaged contract against company standard fallback terms. Redlined liability cap and governing law.", "legal")
        add(case, base + 5.0, "rachel-legal", f"Drafted revised contract terms and transmitted redline draft back to {partner} legal counsel.", "legal")
        add(case, base + 10.0, "rachel-legal", f"Counterparty accepted revisions. Final execution copy prepared for CEO signature.", "legal")

    # 8. Customer Success Renewal Triage (4 traces)
    for i, enterprise in enumerate(("Siemens Cloud", "Boeing Digital", "Target Retail", "Pfizer Labs")):
        base = 425.0 + i * 12.0
        case = f"cs-renewal-{600 + i}"
        add(case, base + 0.0, "gainsight-bot", f"Annual contract renewal alert: {enterprise} expiring in 90 days. ARR: $320k. Health Score: 78.", "cs")
        add(case, base + 1.0, "lisa-csm", f"Conducted executive business review (EBR) prep for {enterprise}. Pulled product usage statistics.", "cs")
        add(case, base + 3.5, "lisa-csm", f"Drafted 15% expansion proposal with dedicated support add-on for {enterprise}.", "cs")
        add(case, base + 7.0, "lisa-csm", f"Executive renewal presentation delivered. Client confirmed intent to renew 3-year extension.", "cs")

    return messages
