"""Render a report as Markdown.

Deliberately the plainest possible renderer. The PDF service is a separate
component; until it exists, this produces a document a person can read,
review and send, and it is the reference for what the PDF must contain.
"""

from __future__ import annotations

from .model import GeotechnicalReport


def render_markdown(report: GeotechnicalReport) -> str:
    out: list[str] = []
    out.append(f"# GeoFatali — {report.project_name}")
    out.append("")
    out.append(f"**{report.banner}**")
    out.append("")
    out.append(
        f"Revision {report.revision:02d} · generated {report.generated_on} · "
        f"engine v{report.engine_version}"
        + (f" · AI model {report.ai_model}" if report.ai_model else "")
    )
    out.append("")

    for section in report.sections:
        if section.title == "Cover":
            continue
        out.append(f"## {section.title}")
        out.append("")
        if section.absent_reason:
            out.append(f"> Not available. {section.absent_reason}")
            out.append("")
            continue
        if section.body:
            out.append(section.body)
            out.append("")
        for item in section.items:
            out.append(f"- {item}")
        if section.items:
            out.append("")
        if section.table:
            keys = list(section.table[0].keys())
            out.append("| " + " | ".join(str(k) for k in keys) + " |")
            out.append("|" + "|".join(["---"] * len(keys)) + "|")
            for row in section.table:
                cells = [str(row.get(k, "")).replace("\n", " ") for k in keys]
                out.append("| " + " | ".join(cells) + " |")
            out.append("")
        for calc in section.calculations:
            out.append(f"### {calc.calculation_type} — {calc.method}")
            out.append("")
            out.append(
                f"Status **{calc.status.value}** · standard {calc.standard_id} · "
                f"engine v{calc.engine_version}"
                + (f" · {calc.reference}" if calc.reference else "")
            )
            out.append("")
            if calc.results:
                for key, value in calc.results.items():
                    if isinstance(value, (int, float, str, bool)) or value is None:
                        out.append(f"- **{key}**: {value}")
                out.append("")
            if calc.provenance.entries:
                out.append("| parameter | value | unit | source |")
                out.append("|---|---|---|---|")
                for name, m in calc.provenance.entries.items():
                    out.append(f"| {name} | {m.value} | {m.unit} | {m.source.value} |")
                out.append("")
            if len(calc.warnings):
                for warning in calc.warnings:
                    out.append(f"- `{warning.severity.value}` **{warning.code}** — {warning.message}")
                out.append("")
    return "\n".join(out)
