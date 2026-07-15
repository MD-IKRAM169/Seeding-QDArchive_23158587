from __future__ import annotations

from pathlib import Path
import sqlite3
from textwrap import wrap

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CLASSIFICATION_DB = (
    PROJECT_ROOT / "23158587-sq26-classification.db"
)

EXPORT_DIR = PROJECT_ROOT / "exports"

OUTPUT_PDF = (
    EXPORT_DIR
    / "23158587-sq26-classification-report.pdf"
)

PAGE_SIZE = landscape(A4)

PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE

LEFT_MARGIN = 1.5 * cm
RIGHT_MARGIN = 1.5 * cm
TOP_MARGIN = 1.5 * cm
BOTTOM_MARGIN = 1.5 * cm

def safe_text(
    value: object | None,
) -> str:
    """
    Convert values to clean printable text.
    """

    if value is None:
        return ""

    return str(value).strip()


def repository_name(
    repository_id: object,
) -> str:
    """
    Convert repository IDs to readable labels.
    """

    mapping = {
        1: "QDR",
        2: "CESSDA",
        "1": "QDR",
        "2": "CESSDA",
    }

    return mapping.get(
        repository_id,
        f"Repository {repository_id}",
    )


def print_header(
    title: str,
) -> None:
    """
    Print terminal section header.
    """

    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def get_repository_project_type_groups(
    conn: sqlite3.Connection,
) -> list[tuple[object, str]]:
    """
    Return every repository/project-type combination
    containing project-level classification results.

    Only QDA_PROJECT and QD_PROJECT are included.
    """

    rows = conn.execute(
        """
        SELECT DISTINCT
            p.repository_id,
            p.type

        FROM projects AS p

        JOIN project_classifications AS pc
            ON pc.project_id = p.id

        WHERE p.type IN (
            'QDA_PROJECT',
            'QD_PROJECT'
        )

        ORDER BY
            p.repository_id,
            CASE p.type
                WHEN 'QDA_PROJECT' THEN 1
                WHEN 'QD_PROJECT' THEN 2
                ELSE 3
            END
        """
    ).fetchall()

    return [
        (
            repository_id,
            safe_text(project_type),
        )
        for (
            repository_id,
            project_type,
        ) in rows
    ]


def get_all_project_type_counts(
    conn: sqlite3.Connection,
    repository_id: object,
) -> list[tuple[str, int]]:
    """
    Return all project-type counts for one repository.
    """

    rows = conn.execute(
        """
        SELECT
            type,
            COUNT(*)

        FROM projects

        WHERE repository_id = ?

        GROUP BY type

        ORDER BY
            CASE type
                WHEN 'QDA_PROJECT' THEN 1
                WHEN 'QD_PROJECT' THEN 2
                WHEN 'OTHER_PROJECT' THEN 3
                WHEN 'NOT_A_PROJECT' THEN 4
                ELSE 5
            END
        """,
        (repository_id,),
    ).fetchall()

    return [
        (
            safe_text(project_type),
            int(count),
        )
        for (
            project_type,
            count,
        ) in rows
    ]


def get_class_distribution(
    conn: sqlite3.Connection,
    repository_id: object,
    project_type: str,
) -> list[tuple[str, str, int]]:
    """
    Return project-level primary class distribution
    for one repository/project-type combination.
    """

    rows = conn.execute(
        """
        SELECT
            pc.primary_class,
            pc.primary_title,
            COUNT(*) AS class_count

        FROM project_classifications AS pc

        JOIN projects AS p
            ON p.id = pc.project_id

        WHERE
            p.repository_id = ?
            AND p.type = ?

        GROUP BY
            pc.primary_class,
            pc.primary_title

        ORDER BY
            class_count DESC,
            pc.primary_class
        """,
        (
            repository_id,
            project_type,
        ),
    ).fetchall()

    return [
        (
            safe_text(code),
            safe_text(title),
            int(count),
        )
        for (
            code,
            title,
            count,
        ) in rows
    ]


def get_project_count(
    conn: sqlite3.Connection,
    repository_id: object,
    project_type: str,
) -> int:
    """
    Return number of classified projects in one distribution.
    """

    return int(
        conn.execute(
            """
            SELECT COUNT(*)

            FROM project_classifications AS pc

            JOIN projects AS p
                ON p.id = pc.project_id

            WHERE
                p.repository_id = ?
                AND p.type = ?
            """,
            (
                repository_id,
                project_type,
            ),
        ).fetchone()[0]
    )


def get_confidence_counts(
    conn: sqlite3.Connection,
    repository_id: object,
    project_type: str,
) -> dict[str, int]:
    """
    Return confidence counts for one repository/project type.
    """

    rows = conn.execute(
        """
        SELECT
            pc.confidence,
            COUNT(*)

        FROM project_classifications AS pc

        JOIN projects AS p
            ON p.id = pc.project_id

        WHERE
            p.repository_id = ?
            AND p.type = ?

        GROUP BY pc.confidence
        """,
        (
            repository_id,
            project_type,
        ),
    ).fetchall()

    return {
        safe_text(confidence): int(count)
        for confidence, count in rows
    }


def build_styles():
    """
    Create PDF paragraph styles.
    """

    styles = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),

        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),

        "heading1": ParagraphStyle(
            "Heading1Custom",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            spaceBefore=4,
            spaceAfter=10,
        ),

        "heading2": ParagraphStyle(
            "Heading2Custom",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            spaceBefore=8,
            spaceAfter=6,
        ),

        "body": ParagraphStyle(
            "BodyCustom",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            alignment=TA_LEFT,
            spaceAfter=6,
        ),

        "table_header": ParagraphStyle(
            "TableHeader",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
        ),

        "table_body": ParagraphStyle(
            "TableBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            alignment=TA_LEFT,
        ),
    }


def create_bar_chart(
    distribution: list[tuple[str, str, int]],
) -> Drawing:
    """
    Create vector bar chart with:
    - full class names
    - counts above bars
    """

    if not distribution:

        drawing = Drawing(
            24 * cm,
            8 * cm,
        )

        drawing.add(
            String(
                12 * cm,
                4 * cm,
                "No classified projects available.",
                textAnchor="middle",
                fontName="Helvetica",
                fontSize=11,
            )
        )

        return drawing

    labels = []

    counts = []

    for (
        code,
        title,
        count,
    ) in distribution:

        full_name = (
            f"{code} - {title}"
        )

        wrapped = wrap(
            full_name,
            width=24,
        )

        labels.append(
            "\n".join(
                wrapped[:4]
            )
        )

        counts.append(count)

    chart_width = 24.5 * cm
    chart_height = 12.5 * cm

    drawing = Drawing(
        chart_width,
        chart_height,
    )

    chart = VerticalBarChart()

    chart.x = 1.7 * cm
    chart.y = 4.5 * cm

    chart.width = 21.5 * cm
    chart.height = 6.5 * cm

    chart.data = [
        counts
    ]

    chart.categoryAxis.categoryNames = (
        labels
    )

    chart.categoryAxis.labels.fontName = (
        "Helvetica"
    )

    chart.categoryAxis.labels.fontSize = 6

    chart.categoryAxis.labels.angle = 35

    chart.categoryAxis.labels.boxAnchor = "ne"

    chart.valueAxis.valueMin = 0

    max_count = max(counts)

    chart.valueAxis.valueMax = (
        max_count
        + max(
            1,
            int(max_count * 0.20),
        )
    )

    chart.valueAxis.valueStep = max(
        1,
        int(
            chart.valueAxis.valueMax
            / 6
        ),
    )

    chart.valueAxis.labels.fontName = (
        "Helvetica"
    )

    chart.valueAxis.labels.fontSize = 7

    chart.bars[0].fillColor = (
        colors.HexColor("#4472C4")
    )

    chart.bars[0].strokeColor = (
        colors.HexColor("#2F5597")
    )

    drawing.add(chart)

    slot_width = (
        chart.width
        / len(counts)
    )

    max_axis = (
        chart.valueAxis.valueMax
    )

    for index, count in enumerate(
        counts
    ):

        x_position = (
            chart.x
            + slot_width * index
            + slot_width / 2
        )

        y_position = (
            chart.y
            + (
                count / max_axis
            )
            * chart.height
            + 5
        )

        drawing.add(
            String(
                x_position,
                y_position,
                str(count),
                textAnchor="middle",
                fontName="Helvetica-Bold",
                fontSize=8,
            )
        )

    return drawing


def create_project_type_table(
    counts: list[tuple[str, int]],
    styles,
) -> Table:
    """
    Create project-type count table.
    """

    data = [
        [
            Paragraph(
                "Project type",
                styles["table_header"],
            ),
            Paragraph(
                "Count",
                styles["table_header"],
            ),
        ]
    ]

    for (
        project_type,
        count,
    ) in counts:

        data.append(
            [
                Paragraph(
                    project_type,
                    styles["table_body"],
                ),
                Paragraph(
                    str(count),
                    styles["table_body"],
                ),
            ]
        )

    table = Table(
        data,
        colWidths=[
            6 * cm,
            3 * cm,
        ],
        repeatRows=1,
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#D9EAF7"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#808080"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "ALIGN",
                    (1, 1),
                    (1, -1),
                    "CENTER",
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        colors.HexColor("#F7F9FB"),
                    ],
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    return table


def create_top20_table(
    distribution: list[tuple[str, str, int]],
    styles,
) -> Table:
    """
    Create top-20 ranked ISIC class table.
    """

    data = [
        [
            Paragraph(
                "Rank",
                styles["table_header"],
            ),
            Paragraph(
                "ISIC division",
                styles["table_header"],
            ),
            Paragraph(
                "Full class name",
                styles["table_header"],
            ),
            Paragraph(
                "Count",
                styles["table_header"],
            ),
        ]
    ]

    for rank, (
        code,
        title,
        count,
    ) in enumerate(
        distribution[:20],
        start=1,
    ):

        data.append(
            [
                Paragraph(
                    str(rank),
                    styles["table_body"],
                ),
                Paragraph(
                    code,
                    styles["table_body"],
                ),
                Paragraph(
                    title,
                    styles["table_body"],
                ),
                Paragraph(
                    str(count),
                    styles["table_body"],
                ),
            ]
        )

    table = Table(
        data,
        colWidths=[
            1.4 * cm,
            2.4 * cm,
            15.5 * cm,
            2 * cm,
        ],
        repeatRows=1,
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#D9EAF7"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#808080"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "ALIGN",
                    (0, 1),
                    (1, -1),
                    "CENTER",
                ),
                (
                    "ALIGN",
                    (3, 1),
                    (3, -1),
                    "CENTER",
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        colors.HexColor("#F7F9FB"),
                    ],
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    return table

def create_comments(
    repo_label: str,
    project_type: str,
    classified_projects: int,
    distribution: list[tuple[str, str, int]],
    confidence_counts: dict[str, int],
) -> list[str]:
    """
    Create factual comments for one distribution.
    """

    comments = []

    comments.append(
        (
            f"This distribution contains "
            f"{classified_projects} classified "
            f"{project_type} project(s) from {repo_label}."
        )
    )

    if distribution:

        (
            top_code,
            top_title,
            top_count,
        ) = distribution[0]

        share = (
            100.0
            * top_count
            / classified_projects
            if classified_projects
            else 0
        )

        comments.append(
            (
                f"The most frequent primary class is "
                f"{top_code} - {top_title}, with "
                f"{top_count} project(s), representing "
                f"approximately {share:.1f}% of this distribution."
            )
        )

        comments.append(
            (
                f"The distribution contains "
                f"{len(distribution)} distinct primary "
                f"ISIC Rev. 5 division class(es)."
            )
        )

    high = confidence_counts.get(
        "HIGH",
        0,
    )

    medium = confidence_counts.get(
        "MEDIUM",
        0,
    )

    low = confidence_counts.get(
        "LOW",
        0,
    )

    comments.append(
        (
            f"Project-level classification confidence is "
            f"{high} HIGH, {medium} MEDIUM, and {low} LOW. "
            f"LOW-confidence results should be interpreted cautiously "
            f"because available metadata or file content may be limited."
        )
    )

    return comments


def draw_page_number(
    canvas,
    document,
) -> None:
    """
    Add footer and page number.
    """

    canvas.saveState()

    canvas.setFont(
        "Helvetica",
        8,
    )

    canvas.drawString(
        LEFT_MARGIN,
        0.8 * cm,
        "Seeding QDArchive - Part 2 Classification",
    )

    canvas.drawRightString(
        PAGE_WIDTH - RIGHT_MARGIN,
        0.8 * cm,
        f"Page {canvas.getPageNumber()}",
    )

    canvas.restoreState()


def build_report(
    conn: sqlite3.Connection,
) -> None:
    """
    Build corrected PDF report.
    """

    EXPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    styles = build_styles()

    frame = Frame(
        LEFT_MARGIN,
        BOTTOM_MARGIN,
        PAGE_WIDTH
        - LEFT_MARGIN
        - RIGHT_MARGIN,
        PAGE_HEIGHT
        - TOP_MARGIN
        - BOTTOM_MARGIN,
        id="normal",
    )

    document = BaseDocTemplate(
        str(OUTPUT_PDF),
        pagesize=PAGE_SIZE,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=(
            "Seeding QDArchive Part 2 "
            "Classification Results Report"
        ),
        author="Md Ikram Tareq",
        subject=(
            "ISIC Rev. 5 classification results "
            "by repository and project type"
        ),
    )

    document.addPageTemplates(
        [
            PageTemplate(
                id="classification_report",
                frames=[frame],
                onPage=draw_page_number,
            )
        ]
    )

    story = []


    story.append(
        Spacer(
            1,
            2.2 * cm,
        )
    )

    story.append(
        Paragraph(
            "Seeding QDArchive",
            styles["title"],
        )
    )

    story.append(
        Paragraph(
            "Part 2 - Classification Results Report",
            styles["heading1"],
        )
    )

    story.append(
        Spacer(
            1,
            0.5 * cm,
        )
    )

    story.append(
        Paragraph(
            "<b>Student:</b> Md Ikram Tareq",
            styles["subtitle"],
        )
    )

    story.append(
        Paragraph(
            "<b>Student ID:</b> 23158587",
            styles["subtitle"],
        )
    )

    story.append(
        Paragraph(
            (
                "<b>Classification taxonomy:</b> "
                "ISIC Rev. 5, division level"
            ),
            styles["subtitle"],
        )
    )

    story.append(
        Paragraph(
            (
                "<b>Repositories:</b> QDR and CESSDA"
            ),
            styles["subtitle"],
        )
    )

    story.append(
        Spacer(
            1,
            1.0 * cm,
        )
    )

    story.append(
        Paragraph(
            (
                "This report summarizes classification results "
                "separately by repository and project type. "
                "For every available QDA_PROJECT or QD_PROJECT distribution, "
                "it provides a vector histogram of primary ISIC Rev. 5 "
                "division classes, a ranked top-20 class table, and "
                "comments on the findings."
            ),
            styles["body"],
        )
    )

    story.append(
        PageBreak()
    )

    groups = (
        get_repository_project_type_groups(
            conn
        )
    )

    current_repository = None

    for group_index, (
        repository_id,
        project_type,
    ) in enumerate(groups):

        repo_label = repository_name(
            repository_id
        )

        # Add repository overview once.
        if repository_id != current_repository:

            if current_repository is not None:
                story.append(
                    PageBreak()
                )

            story.append(
                Paragraph(
                    f"Repository: {repo_label}",
                    styles["heading1"],
                )
            )

            story.append(
                Paragraph(
                    f"Repository ID: {repository_id}",
                    styles["body"],
                )
            )

            story.append(
                Paragraph(
                    "Project-type counts",
                    styles["heading2"],
                )
            )

            story.append(
                create_project_type_table(
                    get_all_project_type_counts(
                        conn,
                        repository_id,
                    ),
                    styles,
                )
            )

            story.append(
                Spacer(
                    1,
                    0.7 * cm,
                )
            )

            current_repository = (
                repository_id
            )

        distribution = get_class_distribution(
            conn,
            repository_id,
            project_type,
        )

        classified_projects = get_project_count(
            conn,
            repository_id,
            project_type,
        )

        confidence_counts = get_confidence_counts(
            conn,
            repository_id,
            project_type,
        )

        story.append(
            Paragraph(
                (
                    f"{repo_label} - "
                    f"{project_type} classification distribution"
                ),
                styles["heading2"],
            )
        )

        story.append(
            Paragraph(
                (
                    f"This distribution contains "
                    f"{classified_projects} classified project(s). "
                    f"The histogram shows project-level primary ISIC Rev. 5 "
                    f"division classes. Full class names are displayed as "
                    f"category labels, and counts appear above the bars."
                ),
                styles["body"],
            )
        )

        story.append(
            create_bar_chart(
                distribution
            )
        )

        story.append(
            PageBreak()
        )

        story.append(
            Paragraph(
                (
                    f"{repo_label} - {project_type} "
                    f"- Top 20 primary classes"
                ),
                styles["heading2"],
            )
        )

        story.append(
            create_top20_table(
                distribution,
                styles,
            )
        )

        story.append(
            Spacer(
                1,
                0.7 * cm,
            )
        )

        story.append(
            Paragraph(
                "Comments on findings",
                styles["heading2"],
            )
        )

        comments = create_comments(
            repo_label=repo_label,
            project_type=project_type,
            classified_projects=(
                classified_projects
            ),
            distribution=distribution,
            confidence_counts=(
                confidence_counts
            ),
        )

        for comment in comments:

            story.append(
                Paragraph(
                    f"- {comment}",
                    styles["body"],
                )
            )

       
        if group_index < len(groups) - 1:

            next_repository_id = (
                groups[
                    group_index + 1
                ][0]
            )

            if (
                next_repository_id
                == repository_id
            ):
                story.append(
                    PageBreak()
                )

    document.build(
        story
    )


def verify_output() -> None:
    """
    Verify PDF exists and is not empty.
    """

    if not OUTPUT_PDF.exists():

        raise RuntimeError(
            "PDF report was not created."
        )

    size = OUTPUT_PDF.stat().st_size

    if size <= 0:

        raise RuntimeError(
            "PDF report is empty."
        )

    print(
        f"PDF file size: {size} bytes"
    )


def show_summary(
    conn: sqlite3.Connection,
) -> None:
    """
    Print report distribution summary.
    """

    print_header(
        "PDF REPORT DISTRIBUTIONS"
    )

    groups = (
        get_repository_project_type_groups(
            conn
        )
    )

    for (
        repository_id,
        project_type,
    ) in groups:

        repo_label = repository_name(
            repository_id
        )

        distribution = (
            get_class_distribution(
                conn,
                repository_id,
                project_type,
            )
        )

        project_count = (
            get_project_count(
                conn,
                repository_id,
                project_type,
            )
        )

        print(
            f"{repo_label:<8}"
            f" | {project_type:<12}"
            f" | Projects: {project_count}"
            f" | Distinct classes: "
            f"{len(distribution)}"
        )

    print(
        f"\nTotal distributions: "
        f"{len(groups)}"
    )

def main() -> None:
    """
    Main entry point.
    """

    print("=" * 78)

    print(
        "SEEDING QDARCHIVE - "
        "GENERATE CORRECTED CLASSIFICATION PDF REPORT"
    )

    print("=" * 78)

    if not CLASSIFICATION_DB.exists():

        print("\nERROR:")

        print(
            "Classification database not found:"
        )

        print(CLASSIFICATION_DB)

        raise SystemExit(1)

    print(
        "\nClassification database:"
    )

    print(CLASSIFICATION_DB)

    try:

        with sqlite3.connect(
            CLASSIFICATION_DB
        ) as conn:

            build_report(conn)

            verify_output()

            show_summary(conn)

    except (
        sqlite3.Error,
        RuntimeError,
        OSError,
        ValueError,
    ) as error:

        print("\nERROR:")

        print(error)

        raise SystemExit(1) from error

    print("\n" + "=" * 78)

    print("SUCCESS")

    print(
        "Corrected classification PDF report "
        "generated successfully."
    )

    print(
        f"Output file:\n{OUTPUT_PDF}"
    )

    print("=" * 78)


if __name__ == "__main__":
    main()
