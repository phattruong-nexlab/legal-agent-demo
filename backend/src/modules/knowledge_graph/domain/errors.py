"""Pipeline error taxonomy (LEGAL_KG_PIPELINE.md section 7.1)."""


class PipelineError(Exception):
    """Base class for any failure inside the KG ingestion pipeline."""


class PDFParseError(PipelineError):
    """PDF could not be read at all."""


class ScannedPDFError(PDFParseError):
    """PDF is an image scan with no extractable text layer."""


class MetadataParseError(PipelineError):
    """Mandatory metadata (số hiệu / ngày ban hành) could not be parsed."""


class StructureValidationError(PipelineError):
    """Parsed Điều/Khoản/Điểm structure failed validation."""


class AmendmentExtractionError(PipelineError):
    """Amendment instructions could not be extracted."""


class CitationResolutionError(PipelineError):
    """A citation could not be resolved to a document node."""


class Neo4jLoadError(PipelineError):
    """Loading the document graph into Neo4j failed."""
