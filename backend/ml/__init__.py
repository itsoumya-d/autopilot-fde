"""Email Machine Learning and Natural Language Understanding module.

Provides deep learning (TensorFlow / Keras) and vectorized NLP classification for
incoming enterprise communication streams.
"""

from .email_classifier import EmailClassifier, EmailClassificationResult

__all__ = ["EmailClassifier", "EmailClassificationResult"]
