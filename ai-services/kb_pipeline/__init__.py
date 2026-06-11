"""
TWHC Knowledge Base Pipeline — Reusable library for vectorization and graph extraction.
"""

from kb_pipeline.chunker import chunk_text
from kb_pipeline.embedder import Embedder
from kb_pipeline.qdrant_ops import QdrantStore
from kb_pipeline.arango_ops import ArangoOps
from kb_pipeline.graph import GraphExtractor
from kb_pipeline.pipeline import Pipeline
from kb_pipeline.models import (
    DocumentClassification,
    ImageRef,
    ProcessingReport,
    Span,
    SpanKind,
)
from kb_pipeline.timeline import TimelineBuilder
from kb_pipeline.classifier import DocumentClassifier
from kb_pipeline.pdf_extractor import PDFImageExtractor
from kb_pipeline.docx_extractor import DOCXImageExtractor
from kb_pipeline.vlm_client import OllamaVLMClient
from kb_pipeline.image_preprocessor import ImagePreprocessor

__all__ = [
    "chunk_text",
    "Embedder",
    "QdrantStore",
    "ArangoOps",
    "GraphExtractor",
    "Pipeline",
    "Span",
    "SpanKind",
    "ImageRef",
    "DocumentClassification",
    "ProcessingReport",
    "TimelineBuilder",
    "DocumentClassifier",
    "PDFImageExtractor",
    "DOCXImageExtractor",
    "OllamaVLMClient",
    "ImagePreprocessor",
]
