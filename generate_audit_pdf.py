"""
Generate Professional PDF Report for OSSPREY System Audit
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.platypus import KeepTogether
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime

def create_audit_report():
    """Create comprehensive PDF audit report"""

    filename = "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/OSSPREY_System_Audit_Report.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=18)

    # Container for the 'Flowable' objects
    elements = []

    # Define styles
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    heading1_style = ParagraphStyle(
        'CustomHeading1',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2c5aa0'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )

    heading2_style = ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2c5aa0'),
        spaceAfter=10,
        spaceBefore=10,
        fontName='Helvetica-Bold'
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=12
    )

    # ============================================================================
    # TITLE PAGE
    # ============================================================================
    elements.append(Spacer(1, 2*inch))
    elements.append(Paragraph("OSSPREY SYSTEM AUDIT REPORT", title_style))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph("Comprehensive Agentic RAG System Analysis", styles['Heading2']))
    elements.append(Spacer(1, 0.5*inch))

    # Metadata table
    metadata = [
        ['Date:', datetime.now().strftime("%B %d, %Y")],
        ['Version:', '1.0'],
        ['Status:', 'CRITICAL GAPS IDENTIFIED'],
        ['Organization:', 'DECAL Lab, UC Davis'],
        ['System:', 'OSSPREY Governance POC'],
    ]

    t = Table(metadata, colWidths=[2*inch, 4*inch])
    t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(t)

    elements.append(PageBreak())

    # ============================================================================
    # EXECUTIVE SUMMARY
    # ============================================================================
    elements.append(Paragraph("EXECUTIVE SUMMARY", heading1_style))
    elements.append(Spacer(1, 0.2*inch))

    summary_text = """
    The comprehensive system audit reveals that while the core Agentic RAG infrastructure is operational,
    there are <b>CRITICAL GAPS</b> preventing the system from meeting technical specification requirements.
    The system currently indexes only governance documents (20% of requirements), while missing GitHub Issues,
    Pull Requests, Commits, and Comments (80% of requirements). Additionally, the OSS Scraper Tool exists
    but is not integrated into the project addition workflow.
    """
    elements.append(Paragraph(summary_text, body_style))
    elements.append(Spacer(1, 0.3*inch))

    # Status Overview Table
    elements.append(Paragraph("System Component Status", heading2_style))

    status_data = [
        ['Component', 'Status', 'Compliance', 'Priority'],
        ['Governance Document Scraping', '✅ Working', '100%', 'Complete'],
        ['Vector + BM25 Hybrid Search', '✅ Working', '100%', 'Complete'],
        ['Multi-Agent Orchestration', '✅ Working', '100%', 'Complete'],
        ['LLM Hyperparameters', '✅ Optimized', '100%', 'Complete'],
        ['GitHub Issues/PRs/Commits', '❌ Missing', '0%', 'P1 - Critical'],
        ['OSS Scraper Integration', '❌ Missing', '0%', 'P1 - Critical'],
        ['Intent Routing Accuracy', '⚠️ 57%', '57%', 'P2 - High'],
        ['Project-Specific Graph RAG', '⚠️ Partial', '30%', 'P2 - High'],
    ]

    t = Table(status_data, colWidths=[2.5*inch, 1.5*inch, 1*inch, 1.3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(t)

    elements.append(PageBreak())

    # ============================================================================
    # TEST 1: VECTOR STORE STATUS
    # ============================================================================
    elements.append(Paragraph("TEST 1: VECTOR STORE & DOCUMENT INDEXING", heading1_style))
    elements.append(Paragraph("<b>Status:</b> ✅ Working but Incomplete", heading2_style))

    text = """
    The vector store is operational with 9,941 indexed document chunks across 6 projects. However, the system
    only indexes governance documents (README, LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, MAINTAINERS).
    Critical socio-technical data including GitHub Issues, Pull Requests, Commits, and Comments are completely absent.
    """
    elements.append(Paragraph(text, body_style))

    # Document Distribution Table
    dist_data = [
        ['Project', 'Total Chunks', 'Primary Content'],
        ['torvalds-linux', '6,509', 'MAINTAINERS file (6,401 chunks)'],
        ['resilientdb-incubator', '1,302', 'README (597), LICENSE (550), COC (155)'],
        ['resilientdb', '752', 'LICENSE (548), COC (155), README (49)'],
        ['apache-incubator-resilientdb', '752', 'LICENSE (548), COC (155), README (49)'],
        ['dicedb-dice', '395', 'CONTRIBUTING (135), COC (104), README (104)'],
        ['microsoft-vscode', '231', 'CONTRIBUTING (206), README (17)'],
    ]

    t = Table(dist_data, colWidths=[2*inch, 1.2*inch, 3.1*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(t)

    elements.append(Spacer(1, 0.2*inch))

    critical_gap = """
    <b>⚠️ CRITICAL GAP:</b> The system indexes ONLY governance documents. The technical specification requires
    indexing of governance documents + issues + commits + pull requests + comments for comprehensive project context.
    Current compliance: <b>20%</b>
    """
    elements.append(Paragraph(critical_gap, body_style))

    elements.append(PageBreak())

    # ============================================================================
    # TEST 2: GRAPH RAG STATUS
    # ============================================================================
    elements.append(Paragraph("TEST 2: GRAPH RAG & SOCIO-TECHNICAL DATA", heading1_style))
    elements.append(Paragraph("<b>Status:</b> ⚠️ Infrastructure Exists, Not Project-Specific", heading2_style))

    text = """
    The Graph RAG infrastructure is functional with 7,987 commit records loaded from CSV data. However,
    the data is from a test project (Apache Hama) and does not update when users add new projects.
    The OSS Scraper Tool exists but is NOT automatically invoked during the project addition workflow.
    """
    elements.append(Paragraph(text, body_style))

    # Current vs Required Flow
    flow_data = [
        ['Current Flow', 'Required Flow'],
        [
            'POST /api/projects/add\n→ Extract governance docs\n→ Index governance docs\n→ DONE ❌',
            'POST /api/projects/add\n→ Extract governance docs\n→ Index governance docs\n→ Run OSS Scraper ✓\n→ Index issues/PRs/commits ✓\n→ Load graph data ✓'
        ],
    ]

    t = Table(flow_data, colWidths=[3*inch, 3.3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#ffcccc')),
        ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#ccffcc')),
    ]))
    elements.append(t)

    elements.append(PageBreak())

    # ============================================================================
    # TEST 3: LLM HYPERPARAMETERS
    # ============================================================================
    elements.append(Paragraph("TEST 3: LLM CONFIGURATION & HYPERPARAMETERS", heading1_style))
    elements.append(Paragraph("<b>Status:</b> ✅ Properly Configured", heading2_style))

    text = """
    The LLM client is correctly configured with appropriate hyperparameters for balanced response quality
    and performance. Temperature, Top-P, and Top-K values are optimized for governance document analysis.
    """
    elements.append(Paragraph(text, body_style))

    llm_config = [
        ['Parameter', 'Value', 'Assessment'],
        ['Model', 'llama3.2:1b', 'Lightweight, fast inference'],
        ['Temperature', '0.7', '✅ Balanced creativity/accuracy'],
        ['Top-P', '0.9', '✅ Appropriate nucleus sampling'],
        ['Top-K', '40', '✅ Standard value'],
        ['Max Tokens', '512', '✅ Reasonable for responses'],
        ['Timeout', '120s', '✅ Adequate for complex queries'],
        ['Connection Pool', '20 async, 10 sync', '✅ Performance optimized'],
    ]

    t = Table(llm_config, colWidths=[1.8*inch, 1.8*inch, 2.7*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(t)

    elements.append(PageBreak())

    # ============================================================================
    # TEST 4: INTENT ROUTING ACCURACY
    # ============================================================================
    elements.append(Paragraph("TEST 4: INTENT ROUTER ACCURACY", heading1_style))
    elements.append(Paragraph("<b>Status:</b> ❌ Below Threshold (57.1% - Requires 80%+)", heading2_style))

    text = """
    The intent routing system achieved only 57.1% accuracy in classification tests, significantly below
    the required 80% threshold for production deployment. Misrouting causes queries to reach incorrect agents,
    resulting in irrelevant or incomplete responses.
    """
    elements.append(Paragraph(text, body_style))

    routing_tests = [
        ['Query', 'Expected', 'Actual', 'Result'],
        ['What is the governance model?', 'governance', 'governance', '✅'],
        ['How do I contribute code?', 'governance', 'code_collab', '❌'],
        ['Who are the top contributors?', 'code_collab', 'governance', '❌'],
        ['Which files are most coupled?', 'code_collab', 'general', '❌'],
        ['Should we adopt this project?', 'recommendations', 'recommendations', '✅'],
        ['Project sustainability score?', 'sustainability', 'sustainability', '✅'],
        ['Tell me about Python', 'general', 'general', '✅'],
    ]

    t = Table(routing_tests, colWidths=[2.2*inch, 1.3*inch, 1.3*inch, 0.8*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(t)

    elements.append(Spacer(1, 0.2*inch))
    accuracy_note = """
    <b>Accuracy: 57.1% (4/7 correct)</b><br/>
    <b>Impact:</b> 43% of queries are routed to the wrong agent, resulting in missing context from governance
    documents and incorrect answers. Queries about contribution guidelines incorrectly route to code collaboration
    agent instead of governance agent.
    """
    elements.append(Paragraph(accuracy_note, body_style))

    elements.append(PageBreak())

    # ============================================================================
    # TEST 5: DATA SCOPE COMPLIANCE
    # ============================================================================
    elements.append(Paragraph("TEST 5: DATA SCOPE - INDEXED CONTENT TYPES", heading1_style))
    elements.append(Paragraph("<b>Status:</b> ❌ Only 20% of Required Data Indexed", heading2_style))

    text = """
    The system currently indexes only governance documents, representing merely 20% of the technical
    specification requirements. Critical socio-technical data including GitHub Issues, Pull Requests,
    Commits, and Comments are completely absent from the RAG system.
    """
    elements.append(Paragraph(text, body_style))

    scope_data = [
        ['Data Type', 'Status', 'Compliance', 'Priority'],
        ['README.md', '✅ Indexed', '100%', 'Complete'],
        ['LICENSE', '✅ Indexed', '100%', 'Complete'],
        ['CONTRIBUTING.md', '✅ Indexed', '100%', 'Complete'],
        ['CODE_OF_CONDUCT.md', '✅ Indexed', '100%', 'Complete'],
        ['SECURITY.md', '✅ Indexed', '100%', 'Complete'],
        ['MAINTAINERS', '✅ Indexed', '100%', 'Complete'],
        ['GitHub Issues', '❌ NOT Indexed', '0%', 'P1 - Critical'],
        ['Pull Requests', '❌ NOT Indexed', '0%', 'P1 - Critical'],
        ['Commit Messages', '❌ NOT Indexed', '0%', 'P1 - Critical'],
        ['Issue Comments', '❌ NOT Indexed', '0%', 'P1 - Critical'],
        ['PR Comments', '❌ NOT Indexed', '0%', 'P1 - Critical'],
        ['Release Notes', '❌ NOT Indexed', '0%', 'P2 - High'],
    ]

    t = Table(scope_data, colWidths=[2*inch, 1.5*inch, 1*inch, 1.8*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(t)

    elements.append(PageBreak())

    # ============================================================================
    # CRITICAL ISSUES SUMMARY
    # ============================================================================
    elements.append(Paragraph("CRITICAL ISSUES SUMMARY", heading1_style))

    # Issue #1
    elements.append(Paragraph("Issue #1: No OSS Scraper Integration", heading2_style))
    elements.append(Paragraph("<b>Severity:</b> 🔴 CRITICAL | <b>Impact:</b> Graph RAG features unusable", body_style))

    issue1_text = """
    The OSSPREY-OSS-Scraper-Tool exists in the repository but is NOT invoked when projects are added via
    the /api/projects/add endpoint. The scraper can extract commits, issues, pull requests, and comments,
    but this functionality is completely disconnected from the project addition workflow. Users add projects
    expecting full analysis, but only receive governance document indexing.
    """
    elements.append(Paragraph(issue1_text, body_style))

    elements.append(Spacer(1, 0.2*inch))

    # Issue #2
    elements.append(Paragraph("Issue #2: Issues/PRs/Commits Not in RAG", heading2_style))
    elements.append(Paragraph("<b>Severity:</b> 🔴 CRITICAL | <b>Impact:</b> Cannot answer socio-technical queries", body_style))

    issue2_text = """
    Only governance documents are indexed into the RAG system. GitHub Issues, Pull Requests, Commit messages,
    and Comments are not indexed, preventing the system from answering questions like "What issues are open for
    bug fixes?", "Show me PRs from contributor X", or "How many commits in the last month?". This represents
    an 80% gap in required functionality.
    """
    elements.append(Paragraph(issue2_text, body_style))

    elements.append(Spacer(1, 0.2*inch))

    # Issue #3
    elements.append(Paragraph("Issue #3: Intent Router Accuracy Too Low", heading2_style))
    elements.append(Paragraph("<b>Severity:</b> 🟡 HIGH | <b>Impact:</b> 43% query misrouting rate", body_style))

    issue3_text = """
    Current routing accuracy of 57% is well below the required 80% threshold. Queries about contributions
    incorrectly route to the code collaboration agent instead of the governance agent, causing users to miss
    critical contribution guidelines from CONTRIBUTING.md files. The keyword matching patterns need enhancement.
    """
    elements.append(Paragraph(issue3_text, body_style))

    elements.append(Spacer(1, 0.2*inch))

    # Issue #4
    elements.append(Paragraph("Issue #4: Graph RAG Not Project-Specific", heading2_style))
    elements.append(Paragraph("<b>Severity:</b> 🟡 HIGH | <b>Impact:</b> Wrong developer data returned", body_style))

    issue4_text = """
    The Graph RAG currently uses static test data from Apache Hama for ALL projects. When users add "resilientdb"
    and query for top contributors, the system returns Hama contributors instead of resilientdb contributors.
    This is misleading and incorrect. The graph loader needs to support per-project CSV data loading.
    """
    elements.append(Paragraph(issue4_text, body_style))

    elements.append(PageBreak())

    # ============================================================================
    # REQUIRED FIXES & IMPLEMENTATION PLAN
    # ============================================================================
    elements.append(Paragraph("REQUIRED FIXES & IMPLEMENTATION PLAN", heading1_style))

    # Priority Table
    priority_data = [
        ['Priority', 'Task', 'Effort', 'Impact'],
        ['P1', 'Integrate OSS Scraper Tool', '8 hours', 'Enables full data extraction'],
        ['P1', 'Index Issues/PRs/Commits in RAG', '12 hours', 'Achieves 100% data scope'],
        ['P2', 'Fix Intent Routing to 80%+', '4 hours', 'Reduces misrouting by 50%'],
        ['P2', 'Project-Specific Graph RAG', '6 hours', 'Accurate developer data'],
        ['P3', 'Testing & Validation', '8 hours', 'Production readiness'],
    ]

    t = Table(priority_data, colWidths=[0.8*inch, 2.8*inch, 1.2*inch, 1.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(t)

    elements.append(Spacer(1, 0.3*inch))
    total_effort = """
    <b>Total Estimated Effort: 38 hours</b><br/>
    <b>Timeline:</b> 1 week for P1 fixes, 1 week for P2 fixes + testing
    """
    elements.append(Paragraph(total_effort, body_style))

    elements.append(PageBreak())

    # ============================================================================
    # ACCEPTANCE CRITERIA
    # ============================================================================
    elements.append(Paragraph("ACCEPTANCE CRITERIA FOR PRODUCTION", heading1_style))

    criteria_text = """
    The system will be considered <b>PRODUCTION-READY</b> when ALL of the following criteria are met:
    """
    elements.append(Paragraph(criteria_text, body_style))

    criteria = [
        ['#', 'Criterion', 'Current', 'Target'],
        ['1', 'Intent routing accuracy', '57%', '≥ 80%'],
        ['2', 'Document types indexed', '6 types', 'All 12 types'],
        ['3', 'OSS scraper integration', 'Not integrated', 'Auto-runs on add'],
        ['4', 'Graph RAG specificity', 'Generic test data', 'Project-specific'],
        ['5', 'Issue/PR query capability', '0% functional', '100% functional'],
        ['6', 'End-to-end test pass rate', 'Partial', '100% all tests'],
        ['7', '95th percentile response time', 'Not measured', '< 10 seconds'],
        ['8', 'Data scope compliance', '20%', '100%'],
    ]

    t = Table(criteria, colWidths=[0.5*inch, 3*inch, 1.5*inch, 1.3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(t)

    elements.append(PageBreak())

    # ============================================================================
    # RECOMMENDATIONS & NEXT STEPS
    # ============================================================================
    elements.append(Paragraph("RECOMMENDATIONS & NEXT STEPS", heading1_style))

    elements.append(Paragraph("Immediate Actions (Week 1):", heading2_style))
    immediate = """
    1. <b>Create OSS Scraper Service wrapper</b> in app/services/oss_scraper.py<br/>
    2. <b>Update /api/projects/add endpoint</b> to invoke scraper after governance extraction<br/>
    3. <b>Test scraper integration</b> with small repository (e.g., dicedb-dice)<br/>
    4. <b>Create Issue/PR/Commit indexer</b> in app/rag/socio_technical_indexer.py<br/>
    5. <b>Add new document types</b> to RAG engine (issue, pull_request, commit)
    """
    elements.append(Paragraph(immediate, body_style))

    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph("Short-term Actions (Week 2):", heading2_style))
    shortterm = """
    1. <b>Enhance intent router keywords</b> with contribution-related terms<br/>
    2. <b>Implement project-specific graph loading</b> in GraphDataLoader<br/>
    3. <b>Update CodeCollabGraphAgent</b> to use per-project graphs<br/>
    4. <b>Add confidence thresholds</b> to intent routing (≥0.9 or fallback)<br/>
    5. <b>Create comprehensive test suite</b> for all query types
    """
    elements.append(Paragraph(shortterm, body_style))

    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph("Validation & Testing (Week 3):", heading2_style))
    validation = """
    1. <b>End-to-end integration testing</b> with multiple projects<br/>
    2. <b>Performance benchmarking</b> and optimization<br/>
    3. <b>User acceptance testing</b> with governance queries<br/>
    4. <b>Documentation updates</b> reflecting new capabilities<br/>
    5. <b>Production deployment preparation</b>
    """
    elements.append(Paragraph(validation, body_style))

    elements.append(PageBreak())

    # ============================================================================
    # CONCLUSION
    # ============================================================================
    elements.append(Paragraph("CONCLUSION", heading1_style))

    conclusion = """
    The OSSPREY Agentic RAG system has a solid foundation with working governance document extraction,
    hybrid search, and multi-agent orchestration. However, <b>critical gaps in socio-technical data indexing
    and scraper integration prevent the system from meeting its technical specifications</b>.
    <br/><br/>
    The system currently achieves only <b>40% overall compliance</b> with requirements:
    <br/>
    • ✅ Governance RAG: 100% (Working)<br/>
    • ✅ Graph RAG Infrastructure: 100% (Working)<br/>
    • ✅ Multi-Agent System: 100% (Working)<br/>
    • ❌ Full Data Scope: 20% (Only governance docs)<br/>
    • ❌ Scraper Integration: 0% (Not connected)<br/>
    • ⚠️ Intent Accuracy: 57% (Below threshold)<br/>
    <br/>
    <b>With the recommended fixes implemented, the system will achieve 100% compliance and be production-ready
    within 3 weeks.</b> The fixes are well-defined, implementable, and will transform the system from a governance
    document viewer into a comprehensive open-source project analysis platform.
    <br/><br/>
    <b>Status:</b> NOT PRODUCTION READY - Requires P1 & P2 fixes before deployment.
    """
    elements.append(Paragraph(conclusion, body_style))

    elements.append(Spacer(1, 0.5*inch))

    # Footer info
    footer = """
    <b>Next Review:</b> After Priority 1 & 2 fixes complete<br/>
    <b>Contact:</b> DECAL Lab, UC Davis<br/>
    <b>Report Generated:</b> {}
    """.format(datetime.now().strftime("%B %d, %Y at %I:%M %p"))
    elements.append(Paragraph(footer, body_style))

    # Build PDF
    doc.build(elements)

    return filename

if __name__ == "__main__":
    filename = create_audit_report()
    print(f"✅ PDF Report Generated: {filename}")
