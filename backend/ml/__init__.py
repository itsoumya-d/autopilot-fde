"""Email Machine Learning and Natural Language Understanding module.

Provides deep learning (TensorFlow / Keras) and vectorized NLP classification for
incoming enterprise communication streams.
"""

from .email_classifier import EmailClassificationResult, EmailClassifier

__all__ = ["EmailClassifier", "EmailClassificationResult"]
