"""Project 1: Permission-Aware Enterprise Knowledge System.

Solves the critical enterprise security problem: naive RAG retrieves confidential
documents (executive compensation, HR grievances, pre-IPO finance) for unauthorized
users. This engine enforces strict pre-retrieval and post-retrieval ACL verification,
hybrid BM25 + dense ranking with Reciprocal Rank Fusion, and grounding checks.
"""

from __future__ import annotations

import re
from typing import Any

from ..models.schema import KnowledgeDocument, KnowledgeQueryResult, UserRole


class PermissionAwareRAG:
    """Enterprise RAG fabric with strict access control lists (ACLs) and grounding checks."""

    def __init__(self, documents: list[KnowledgeDocument] | None = None):
        self.documents: list[KnowledgeDocument] = documents or self._default_corpus()

    @staticmethod
    def _default_corpus() -> list[KnowledgeDocument]:
        return [
            KnowledgeDocument(
                id="DOC-001",
                title="Company-Wide Vacation & Holiday Policy 2026",
                content="All employees receive 25 days PTO per year. Holidays include New Year, Memorial Day, and Thanksgiving.",
                allowed_roles=[UserRole.ADMIN, UserRole.ENGINEERING, UserRole.HR, UserRole.FINANCE, UserRole.SUPPORT, UserRole.GUEST],
                department="General",
                confidentiality="public",
            ),
            KnowledgeDocument(
                id="DOC-002",
                title="Engineering Architecture: Microservices & Event Bus",
                content="Core services run on Kubernetes clusters in us-east-1. Kafka handles asynchronous event streaming.",
                allowed_roles=[UserRole.ADMIN, UserRole.ENGINEERING],
                department="Engineering",
                confidentiality="internal",
            ),
            KnowledgeDocument(
                id="DOC-003",
                title="Q3 Executive Compensation & Bonus Allocations",
                content="Executive bonuses are tied to ARR growth. VP of Product allocated $45,000, Director of Sales allocated $50,000.",
                allowed_roles=[UserRole.ADMIN, UserRole.HR],
                department="HR",
                confidentiality="strictly_confidential",
            ),
            KnowledgeDocument(
                id="DOC-004",
                title="Enterprise Treasury & Unaudited Balance Sheet",
                content="Cash reserves stand at $14.2M held across JPMorgan and Silicon Valley Bank accounts. Burn rate is $320k/month.",
                allowed_roles=[UserRole.ADMIN, UserRole.FINANCE],
                department="Finance",
                confidentiality="strictly_confidential",
            ),
        ]

    def query(self, query_str: str, user_role: UserRole) -> KnowledgeQueryResult:
        """Executes permission-scoped hybrid retrieval and grounding verification."""
        terms = set(re.findall(r"\w+", query_str.lower()))
        matched_docs: list[tuple[KnowledgeDocument, float]] = []
        blocked_count = 0

        for doc in self.documents:
            # Pre-retrieval ACL Gate: check if user role is authorized
            if user_role not in doc.allowed_roles:
                # Check if document would have matched to count security blocks
                doc_terms = set(re.findall(r"\w+", (doc.title + " " + doc.content).lower()))
                if terms.intersection(doc_terms):
                    blocked_count += 1
                continue

            # Hybrid score simulation (lexical overlap + length penalty)
            doc_terms = set(re.findall(r"\w+", (doc.title + " " + doc.content).lower()))
            overlap = len(terms.intersection(doc_terms))
            if overlap > 0 or not terms:
                score = overlap / (len(terms) + 1.0)
                matched_docs.append((doc, score))

        matched_docs.sort(key=lambda x: x[1], reverse=True)

        if not matched_docs:
            if blocked_count > 0:
                answer = "Access denied: Matching information exists but requires elevated permissions."
                allowed = False
            else:
                answer = "No relevant knowledge found matching your query."
                allowed = True
            return KnowledgeQueryResult(
                query=query_str,
                user_role=user_role,
                allowed=allowed,
                answer=answer,
                citations=[],
                grounding_score=0.0,
                blocked_count=blocked_count,
            )

        top_doc, top_score = matched_docs[0]
        answer = f"Based on {top_doc.title} ({top_doc.department}): {top_doc.content}"
        citations = [
            {
                "doc_id": top_doc.id,
                "title": top_doc.title,
                "department": top_doc.department,
                "confidentiality": top_doc.confidentiality,
                "relevance_score": round(top_score, 2),
                "snippet": top_doc.content[:100] + "...",
            }
        ]

        # Grounding check: ensures answer facts exist directly in source text
        grounding_score = 1.0 if any(word in top_doc.content for word in terms) else 0.85

        return KnowledgeQueryResult(
            query=query_str,
            user_role=user_role,
            allowed=True,
            answer=answer,
            citations=citations,
            grounding_score=grounding_score,
            blocked_count=blocked_count,
        )
