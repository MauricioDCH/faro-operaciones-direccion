"""Central registry for Faro input-format capabilities.

The registry identifies formats and their delivery status. It does not parse files.
Format-specific validation and ingestion belong to dedicated adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from os import PathLike


class CapabilityStatus(StrEnum):
    """Delivery state exposed by the product contract."""

    IMPLEMENTED = "implemented"
    PLANNED = "planned"
    OUT_OF_SCOPE = "out_of_scope"


class InputFormat(StrEnum):
    """Stable identifiers for recognized input families."""

    XLSX = "xlsx"
    PDF = "pdf"
    CSV = "csv"
    TSV = "tsv"
    UBL_XML = "ubl_xml"
    JPEG = "jpeg"
    PNG = "png"
    TIFF = "tiff"
    WEBP = "webp"
    JSON = "json"
    NDJSON = "ndjson"
    EML = "eml"
    MBOX = "mbox"
    ZIP = "zip"
    DOCX = "docx"
    ODT = "odt"
    OFX = "ofx"
    QFX = "qfx"
    MT940 = "mt940"
    CAMT053 = "camt053"
    PARQUET = "parquet"


@dataclass(frozen=True, slots=True)
class FormatCapability:
    """One recognized format and its current product status."""

    format_id: InputFormat
    extensions: tuple[str, ...]
    media_types: tuple[str, ...]
    phase: str
    status: CapabilityStatus
    adapter: str
    description: str


_CAPABILITIES = (
    FormatCapability(InputFormat.XLSX, (".xlsx",), ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",), "current", CapabilityStatus.IMPLEMENTED, "excel", "Excel workbooks"),
    FormatCapability(InputFormat.PDF, (".pdf",), ("application/pdf",), "current", CapabilityStatus.IMPLEMENTED, "pdf", "Native or scanned PDF documents"),
    FormatCapability(InputFormat.CSV, (".csv",), ("text/csv",), "phase_1", CapabilityStatus.IMPLEMENTED, "delimited", "Profiled delimited tabular exports"),
    FormatCapability(InputFormat.TSV, (".tsv",), ("text/tab-separated-values",), "phase_1", CapabilityStatus.IMPLEMENTED, "delimited", "Profiled tab-delimited exports"),
    FormatCapability(InputFormat.UBL_XML, (".xml",), ("application/xml", "text/xml"), "phase_1", CapabilityStatus.PLANNED, "ubl_xml", "UBL electronic business documents"),
    FormatCapability(InputFormat.JPEG, (".jpg", ".jpeg"), ("image/jpeg",), "phase_1", CapabilityStatus.PLANNED, "image_document", "JPEG document images"),
    FormatCapability(InputFormat.PNG, (".png",), ("image/png",), "phase_1", CapabilityStatus.PLANNED, "image_document", "PNG document images"),
    FormatCapability(InputFormat.TIFF, (".tif", ".tiff"), ("image/tiff",), "phase_1", CapabilityStatus.PLANNED, "image_document", "TIFF document images"),
    FormatCapability(InputFormat.WEBP, (".webp",), ("image/webp",), "phase_1", CapabilityStatus.PLANNED, "image_document", "WebP document images"),
    FormatCapability(InputFormat.JSON, (".json",), ("application/json",), "phase_1", CapabilityStatus.IMPLEMENTED, "json_records", "Versioned JSON documents or batches"),
    FormatCapability(InputFormat.NDJSON, (".ndjson", ".jsonl"), ("application/x-ndjson", "application/jsonl"), "phase_1", CapabilityStatus.IMPLEMENTED, "json_records", "Newline-delimited JSON records"),
    FormatCapability(InputFormat.EML, (".eml",), ("message/rfc822",), "phase_2", CapabilityStatus.PLANNED, "email_archive", "Individual exported email messages"),
    FormatCapability(InputFormat.MBOX, (".mbox",), ("application/mbox",), "phase_2", CapabilityStatus.PLANNED, "email_archive", "Mailbox archives"),
    FormatCapability(InputFormat.ZIP, (".zip",), ("application/zip",), "phase_2", CapabilityStatus.PLANNED, "archive", "Manifest-controlled source batches"),
    FormatCapability(InputFormat.DOCX, (".docx",), ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",), "phase_2", CapabilityStatus.PLANNED, "office_document", "Controlled Word documents"),
    FormatCapability(InputFormat.ODT, (".odt",), ("application/vnd.oasis.opendocument.text",), "phase_2", CapabilityStatus.PLANNED, "office_document", "Controlled OpenDocument text files"),
    FormatCapability(InputFormat.OFX, (".ofx",), ("application/x-ofx",), "phase_3", CapabilityStatus.OUT_OF_SCOPE, "bank_statement", "OFX statements"),
    FormatCapability(InputFormat.QFX, (".qfx",), ("application/vnd.intu.qfx",), "phase_3", CapabilityStatus.OUT_OF_SCOPE, "bank_statement", "QFX statements"),
    FormatCapability(InputFormat.MT940, (".mt940", ".sta"), ("text/plain",), "phase_3", CapabilityStatus.OUT_OF_SCOPE, "bank_statement", "MT940 statements"),
    FormatCapability(InputFormat.CAMT053, (".camt.053.xml",), ("application/xml",), "phase_3", CapabilityStatus.OUT_OF_SCOPE, "bank_statement", "CAMT.053 statements"),
    FormatCapability(InputFormat.PARQUET, (".parquet",), ("application/vnd.apache.parquet",), "phase_3", CapabilityStatus.OUT_OF_SCOPE, "parquet", "Internal analytical storage"),
)

CAPABILITIES: dict[InputFormat, FormatCapability] = {
    item.format_id: item for item in _CAPABILITIES
}


def all_capabilities() -> tuple[FormatCapability, ...]:
    """Return capabilities in stable roadmap order."""

    return _CAPABILITIES


def capability_for(format_id: InputFormat | str) -> FormatCapability:
    """Return the capability for a stable format identifier."""

    return CAPABILITIES[InputFormat(format_id)]


def detect_input_format(path: str | PathLike[str]) -> FormatCapability | None:
    """Identify a recognized format from a Linux or Windows path string.

    Content validation remains the responsibility of the selected adapter.
    Compound suffixes are matched before simple suffixes.
    """

    filename = str(path).replace("\\", "/").rsplit("/", 1)[-1].casefold()
    matches = sorted(
        (
            (extension, capability)
            for capability in _CAPABILITIES
            for extension in capability.extensions
            if filename.endswith(extension)
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    return matches[0][1] if matches else None


def require_implemented_format(path: str | PathLike[str]) -> FormatCapability:
    """Return an implemented capability or raise a structured-friendly error."""

    capability = detect_input_format(path)
    if capability is None:
        raise ValueError(f"Unsupported input format: {path}")
    if capability.status is not CapabilityStatus.IMPLEMENTED:
        raise NotImplementedError(
            f"Input format {capability.format_id.value} is {capability.status.value}."
        )
    return capability
