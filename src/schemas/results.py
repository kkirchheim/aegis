"""Marshmallow schemas for analysis results."""

from marshmallow import Schema, fields


class ArtifactSchema(Schema):
    """Schema for artifact metadata.

    Represents artifacts generated during analysis (documents, files, etc.).
    """

    id = fields.Str(allow_none=True)
    job_id = fields.Str(allow_none=True)
    url = fields.Str(allow_none=True)
    artifact_type = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)


class PluginEvaluationSchema(Schema):
    """Schema for plugin evaluation results.

    Represents the evaluation of a specific plugin of reproducibility
    (e.g., code availability, data availability, methodology clarity).
    """

    plugin_id = fields.Str(allow_none=True)
    name = fields.Str(allow_none=True)
    status = fields.Str(allow_none=True)
    evidence = fields.Str(allow_none=True)
    paper_supports = fields.Bool(allow_none=True)
    code_supports = fields.Bool(allow_none=True)
    conclusion = fields.Str(allow_none=True)


class ExecutionResultSchema(Schema):
    """Schema for execution step results.

    Represents the result of executing a single step in the analysis pipeline.
    """

    step = fields.Str(allow_none=True)
    status = fields.Str(allow_none=True)
    output = fields.Str(allow_none=True)
    error = fields.Str(allow_none=True)


class PaperAnalysisSchema(Schema):
    """Schema for paper analysis results.

    Represents the complete analysis of a research paper, including
    extracted metadata, methodology, dependencies, and citations.
    """

    title = fields.Str(allow_none=True)
    abstract = fields.Str(allow_none=True)
    extracted_text = fields.Str(allow_none=True)
    claimed_results = fields.Dict(allow_none=True)
    methodology = fields.Str(allow_none=True)
    dependencies = fields.Str(allow_none=True)
    dataset_description = fields.Str(allow_none=True)
    citations = fields.List(fields.Dict(), allow_none=True)
