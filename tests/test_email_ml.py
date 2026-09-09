"""Unit tests for the Email Machine Learning intent classifier and entity extractor."""

import pytest
from backend.ml.email_classifier import EmailClassifier, INTENT_CLASSES


@pytest.fixture
def classifier() -> EmailClassifier:
    """Provides a fresh instance of EmailClassifier (with vectorized fallback support)."""
    return EmailClassifier(use_tf=False)


def test_intent_classes_completeness(classifier: EmailClassifier):
    """Verify that all 8 enterprise intent classes are registered."""
    assert len(INTENT_CLASSES) == 8
    assert "devops_incident" in INTENT_CLASSES
    assert "sales_discount" in INTENT_CLASSES
    assert "security_vulnerability" in INTENT_CLASSES
    assert "support_escalation" in INTENT_CLASSES


def test_classify_devops_outage(classifier: EmailClassifier):
    """Ensure DevOps critical incident email is properly classified."""
    subject = "[ALERT] Production 5xx spike and database connection pool exhausted"
    body = "Grafana triggered P99 latency breach (>4500ms). Multiple pods in crashloop. Please rollback deploy."

    result = classifier.predict(subject, body)
    assert result.primary_intent == "devops_incident"
    assert result.confidence > 0.50
    assert result.is_actionable is True
    assert "Mitigate Production Incident" in result.recommended_activity


def test_classify_sales_discount_request(classifier: EmailClassifier):
    """Ensure deal desk discount approval email is recognized."""
    subject = "Urgent: 25% ARR Discount Request for Acme Corp Enterprise Plan"
    body = "Customer is asking for custom pricing on 500 seats. Margin analysis completed. Needs executive approval via DocuSign."

    result = classifier.predict(subject, body)
    assert result.primary_intent == "sales_discount"
    assert result.confidence > 0.50
    assert result.is_actionable is True
    assert "Deal Desk" in result.recommended_activity


def test_classify_support_escalation_with_entities(classifier: EmailClassifier):
    """Verify entity extraction (ticket ID, severity) on customer escalations."""
    subject = "P0 Escalation: Enterprise client locked out of SSO"
    body = "Customer is blocked on JIRA-4821 and cannot log in. SLA breached in 30 minutes. Contact cto@acme.com."

    result = classifier.predict(subject, body)
    assert result.primary_intent == "support_escalation"
    assert result.is_actionable is True

    # Check extracted entities
    entities = result.entities
    assert "JIRA-4821" in entities.get("ticket_ids", [])
    assert "P0" in entities.get("severities", [])
    assert "cto@acme.com" in entities.get("email_addresses", [])


def test_classify_security_vulnerability(classifier: EmailClassifier):
    """Ensure security vulnerability reports are triaged."""
    subject = "CRITICAL: OWASP SQL injection detected in billing webhook"
    body = "Security audit found CVE vulnerability in payment endpoint. Remediation patch required immediately."

    result = classifier.predict(subject, body)
    assert result.primary_intent == "security_vulnerability"
    assert result.confidence > 0.50
    assert result.is_actionable is True
    assert "CRITICAL" in result.entities.get("severities", [])


def test_general_inquiry_non_actionable(classifier: EmailClassifier):
    """Verify general conversation is not flagged as high-urgency action."""
    subject = "Catching up next week?"
    body = "Hey Soumya, hope you are doing well. Let me know if you have time for a quick coffee sync next Thursday."

    result = classifier.predict(subject, body)
    assert result.primary_intent == "general_inquiry"
    assert result.is_actionable is False


def test_result_to_dict_structure(classifier: EmailClassifier):
    """Verify JSON serialization contract of classification output."""
    result = classifier.predict("Invoice #9021 payment failed", "Stripe charge declined for $4,500.00.")
    d = result.to_dict()

    assert "primary_intent" in d
    assert "confidence" in d
    assert "secondary_intents" in d
    assert "entities" in d
    assert "is_actionable" in d
    assert d["primary_intent"] == "billing_inquiry"
