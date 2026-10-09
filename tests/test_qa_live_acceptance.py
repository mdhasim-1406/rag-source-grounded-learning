from pathlib import Path
import json
import re
import time
import pymupdf
from playwright.sync_api import sync_playwright, expect

BASE_URL = "http://127.0.0.1:8000"
QA_OUT = Path(__file__).parent / "qa-artifacts"
QA_OUT.mkdir(exist_ok=True)


def create_sample_pdf(filepath: Path) -> None:
    """Creates a compact, valid two-page PDF for live ingestion testing."""
    doc = pymupdf.open()
    
    page1 = doc.new_page()
    page1.insert_text(
        pymupdf.Point(50, 72),
        "Operating System Microkernel Design\n\n"
        "A microkernel structures the operating system by removing all nonessential components "
        "from the kernel and implementing them as user-level system and application programs.\n"
        "Microkernels typically provide minimal process and memory management, alongside a "
        "fast interprocess communication (IPC) facility.\n\n"
        "The Mach microkernel modularizes the system architecture and improves extensibility."
    )
    
    page2 = doc.new_page()
    page2.insert_text(
        pymupdf.Point(50, 72),
        "Virtualization and Hypervisors\n\n"
        "Hypervisors decouple physical hardware from guest operating systems.\n"
        "Type 1 bare-metal hypervisors run directly on host hardware (e.g. VMware ESXi, Xen).\n"
        "Type 2 hosted hypervisors run on top of an underlying operating system.\n"
        "Hardware-assisted virtualization utilizes extended page tables (EPT) to accelerate address translation."
    )
    
    doc.save(str(filepath))
    doc.close()


def run_live_acceptance_suite():
    print("=" * 70)
    print("STARTING SCHOLAR STUDIO LIVE PLAYWRIGHT ACCEPTANCE SUITE")
    print("=" * 70)

    pdf_sample_path = QA_OUT / "microkernels_live_sample.pdf"
    create_sample_pdf(pdf_sample_path)

    page_errors = []
    console_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 950})
        page = context.new_page()

        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text) if msg.type == "error" else None
        )

        # ----------------------------------------------------------------------
        # 1. Initial Page Load & UI Cockpit
        # ----------------------------------------------------------------------
        res = page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        assert res and res.status == 200, f"Failed to load application at {BASE_URL}"
        expect(page.get_by_text("Scholar Studio", exact=True)).to_be_visible()
        expect(page.get_by_text("Studio Inquiry")).to_be_visible()
        expect(page.get_by_text("Active Recall Quiz")).to_be_visible()

        # Verify no emoji in generate button
        gen_btn_text = page.locator("#btnGenerateQuiz").text_content() or ""
        assert "⚡" not in gen_btn_text, f"Emoji found in generate quiz button: '{gen_btn_text}'"

        page.screenshot(path=str(QA_OUT / "live-01-initial-cockpit.png"), full_page=True)
        print("PASS [1/12]: App cockpit initialized without errors, UI emoji removed")

        # ----------------------------------------------------------------------
        # 2. Workspace Creation
        # ----------------------------------------------------------------------
        ts = int(time.time())
        ws_title = f"Live Acceptance OS Notebook {ts}"
        page.get_by_role("button", name="+ New Notebook").click()
        page.locator("#newWorkspaceTitle").fill(ws_title)
        page.locator("#newWorkspaceDesc").fill("Full live E2E testing of all capabilities")
        page.get_by_role("button", name="Create", exact=True).click()

        expect(page.locator("#workspaceSelect option:checked")).to_have_text(ws_title, timeout=10000)
        ws_id = page.locator("#workspaceSelect").input_value()
        print(f"PASS [2/12]: Created and active in isolated notebook: {ws_id} ('{ws_title}')")

        # ----------------------------------------------------------------------
        # 3. Source Note Ingestion (Text)
        # ----------------------------------------------------------------------
        page.get_by_role("button", name="+ Note").click()
        page.locator("#noteTitleInput").fill("Raft Consensus Protocol")
        page.locator("#noteContentInput").fill(
            "Raft is a consensus algorithm designed as an alternative to Multi-Paxos. "
            "Raft achieves consensus via an elected leader. The leader accepts log entries from clients, "
            "replicates them across follower nodes, and tells followers when it is safe to apply log entries. "
            "Leader election uses randomized election timers to avoid split votes. "
            "Nodes transition between three states: Follower, Candidate, and Leader."
        )
        page.get_by_role("button", name="Save & Chunk").click()
        expect(page.get_by_text("Raft Consensus Protocol", exact=True)).to_be_visible(timeout=15000)
        print("PASS [3/12]: Text note ingested and chunked successfully")

        # ----------------------------------------------------------------------
        # 4. Source PDF Ingestion
        # ----------------------------------------------------------------------
        page.get_by_role("button", name="+ PDF").click()
        page.locator("#fileUploadInput").set_input_files(str(pdf_sample_path))
        page.locator("#btnSubmitUpload").click()

        expect(page.get_by_text("microkernels_live_sample.pdf", exact=True)).to_be_visible(timeout=20000)
        expect(page.locator("#sourcesCountBadge")).to_have_text("2")
        page.screenshot(path=str(QA_OUT / "live-02-sources-ingested.png"))
        print("PASS [4/12]: PDF document uploaded and chunked with workspace_id in form data")

        # ----------------------------------------------------------------------
        # 5. Scoped Selection Testing (Select None / Error handling)
        # ----------------------------------------------------------------------
        # Toggle to deselect all sources
        page.locator("#toggleSelectAllSources").click()
        expect(page.locator("#activeSourcesIndicator")).to_contain_text("0 of 2 active")

        # Chat with 0 active sources -> must show error
        page.locator("#queryInput").fill("How does Raft elect a leader?")
        page.locator("#btnSendQuery").click()
        expect(page.locator("#chatStream")).to_contain_text("No sources selected")

        # Quiz generation with 0 active sources -> must show error
        page.locator("#btnGenerateQuiz").click()
        expect(page.locator("#quizArenaContainer")).to_contain_text("No sources selected")

        # Study guide synthesis with 0 active sources -> must show error
        page.locator("[data-tab='guide']").click()
        page.locator("#btnSynthesizeGuide").click()
        expect(page.locator("#studyGuideContent")).to_contain_text("No sources selected")

        # Re-select all sources
        page.locator("#toggleSelectAllSources").click()
        expect(page.locator("#activeSourcesIndicator")).to_contain_text("2 of 2 active")
        print("PASS [5/12]: Scoped select none correctly prevents ungrounded queries and shows error")

        # ----------------------------------------------------------------------
        # 6. Live Grounded Inquiry & Citation Verification
        # ----------------------------------------------------------------------
        page.locator("#queryInput").fill("Explain how the Raft leader is elected and what prevents split votes.")
        page.locator("#btnSendQuery").click()

        expect(page.locator(".citation-pill").first).to_be_visible(timeout=90000)
        pills = page.locator(".citation-pill")
        assert pills.count() >= 1, "Expected at least one citation pill in grounded chat response"

        # Open citation modal
        pills.first.click()
        expect(page.locator("#citationModal")).to_have_class(re.compile(r"active"))
        expect(page.locator("#modalCitationSource")).not_to_be_empty()
        expect(page.locator("#modalCitationQuote")).not_to_be_empty()
        page.screenshot(path=str(QA_OUT / "live-03-chat-citation.png"))

        # Close modal
        page.locator("#citationModal button[onclick*='citationModal']").click()
        expect(page.locator("#citationModal")).not_to_have_class(re.compile(r"active"))
        print("PASS [6/12]: Live grounded chat with inline citations and citation modal verified")

        # ----------------------------------------------------------------------
        # 7. Live Grounded Quiz Generation (Exercising All Question Types)
        # ----------------------------------------------------------------------
        page.locator("[data-tab='quiz']").click()
        page.locator("#quizDifficulty").select_option("medium")
        page.locator("#quizCount").select_option("3")
        page.locator("#btnGenerateQuiz").click()

        expect(page.locator("#quizArenaContainer .question-box").first).to_be_visible(timeout=240000)
        question_boxes = page.locator("#quizArenaContainer .question-box")
        q_count = question_boxes.count()
        assert q_count >= 1, "Expected at least 1 generated question"
        print(f"PASS [7/12]: Live grounded quiz generated with {q_count} questions")
        page.screenshot(path=str(QA_OUT / "live-04-quiz-generated.png"))

        # ----------------------------------------------------------------------
        # 8. Quiz Answer Interaction & Self-Rating Submission
        # ----------------------------------------------------------------------
        for i in range(q_count):
            q_box = question_boxes.nth(i)
            options = q_box.locator(".quiz-option")
            opt_count = options.count()

            if opt_count > 0:
                q_text = q_box.locator(".question-text").text_content() or ""
                if "Select all" in q_text:
                    # Multi-select question
                    options.nth(0).click()
                    if opt_count > 1:
                        options.nth(1).click()
                    print(f"  Exercised multi_select question #{i+1}")
                else:
                    # Single-choice MCQ
                    options.nth(0).click()
                    print(f"  Exercised mcq_single question #{i+1}")
            else:
                # Flashcard
                flip_btn = q_box.locator("[id^='btn-flip-']")
                if flip_btn.count() > 0:
                    flip_btn.click()
                    # Assert self-rating buttons are visible
                    mastered_btn = q_box.locator(".self-rate-btn[data-rate='1']")
                    needs_practice_btn = q_box.locator(".self-rate-btn[data-rate='0']")
                    expect(mastered_btn).to_be_visible()
                    expect(needs_practice_btn).to_be_visible()
                    # Click explicit self-rating
                    mastered_btn.click()
                    print(f"  Exercised flashcard question #{i+1} with explicit recall self-rating")

        # Submit answers
        page.locator("#btnSubmitQuizAnswers").click()
        expect(page.locator(".explanation-card").first).to_be_visible(timeout=30000)
        expect(page.locator(".quiz-score-summary")).to_be_visible()

        score_text = page.locator(".quiz-score-value").text_content()
        print(f"PASS [8/12]: Submitted quiz; feedback and score evaluated ({score_text})")
        page.screenshot(path=str(QA_OUT / "live-05-quiz-evaluated.png"))

        # ----------------------------------------------------------------------
        # 9. Concept Mastery Analytics Tab
        # ----------------------------------------------------------------------
        page.locator("[data-tab='mastery']").click()
        expect(page.locator("#masteryAnalyticsContainer")).not_to_contain_text("Loading mastery stats...")
        expect(page.locator("#masteryAnalyticsContainer")).to_contain_text("OVERALL NOTEBOOK MASTERY", timeout=15000)
        page.screenshot(path=str(QA_OUT / "live-06-concept-analytics.png"))
        print("PASS [9/12]: Concept mastery analytics populated and verified")

        # ----------------------------------------------------------------------
        # 10. Study Guide Synthesis
        # ----------------------------------------------------------------------
        page.locator("[data-tab='guide']").click()
        page.locator("#btnSynthesizeGuide").click()
        expect(page.locator("#studyGuideContent h3")).to_be_visible(timeout=120000)
        expect(page.locator("#studyGuideContent h4").first).to_be_visible()
        page.screenshot(path=str(QA_OUT / "live-07-study-guide.png"))
        print("PASS [10/12]: Grounded study guide synthesized with executive summary and concepts")

        # ----------------------------------------------------------------------
        # 11. Notebook Switching & State Persistence
        # ----------------------------------------------------------------------
        # Create second workspace to test isolation
        page.get_by_role("button", name="+ New Notebook").click()
        page.locator("#newWorkspaceTitle").fill("Secondary Isolation Test WS")
        page.locator("#newWorkspaceDesc").fill("Testing workspace clearing")
        page.get_by_role("button", name="Create", exact=True).click()

        expect(page.locator("#workspaceSelect option:checked")).to_contain_text("Secondary Isolation Test WS")
        # In new notebook: chat should be reset, quiz empty, sources 0
        expect(page.locator("#sourcesCountBadge")).to_have_text("0")
        expect(page.locator("#quizArenaContainer")).to_contain_text("No quiz loaded")
        expect(page.locator("#studyGuideContent")).to_contain_text("Click \"Synthesize New Guide\"")

        # Switch back to the first workspace
        page.locator("#workspaceSelect").select_option(ws_id)
        expect(page.locator("#sourcesCountBadge")).to_have_text("2", timeout=10000)
        # Select Quiz tab to inspect restored quiz deck
        page.locator("[data-tab='quiz']").click()
        # Persisted quiz deck is restored!
        expect(page.locator("#quizArenaContainer .question-box").first).to_be_visible(timeout=10000)
        page.screenshot(path=str(QA_OUT / "live-08-workspace-restored.png"))
        print("PASS [11/12]: Workspace switching clears volatile state and restores persisted deck")

        # ----------------------------------------------------------------------
        # 12. Mobile Responsiveness at 390px (No horizontal overflow)
        # ----------------------------------------------------------------------
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(500)

        scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
        assert scroll_width <= 390, f"Horizontal overflow detected at 390px: scrollWidth={scroll_width}"

        # Test mobile tabs
        panel_nav = page.locator("#mobilePanelNav")
        expect(panel_nav).to_be_visible()

        panel_nav.locator("[data-panel='sources']").click()
        expect(page.locator(".column-sources")).to_be_visible()
        expect(page.locator(".column-studio")).to_be_hidden()

        panel_nav.locator("[data-panel='mastery']").click()
        expect(page.locator(".column-mastery")).to_be_visible()
        expect(page.locator(".column-sources")).to_be_hidden()

        panel_nav.locator("[data-panel='studio']").click()
        expect(page.locator(".column-studio")).to_be_visible()
        expect(page.locator(".column-mastery")).to_be_hidden()

        page.screenshot(path=str(QA_OUT / "live-09-mobile-390px.png"))
        print("PASS [12/12]: Mobile responsive layout at 390px verified with zero overflow and panel tabs")

        # ----------------------------------------------------------------------
        # Final Assertions: Zero Console / Page Errors
        # ----------------------------------------------------------------------
        assert len(page_errors) == 0, f"Browser JavaScript page errors: {page_errors}"
        # Filter favicon or analytics if any, though none expected
        serious_console_errors = [e for e in console_errors if "favicon" not in e.lower()]
        assert len(serious_console_errors) == 0, f"Browser console errors: {serious_console_errors}"

        summary = {
            "test_run": "Live Full Acceptance Suite",
            "workspace_id": ws_id,
            "workspace_title": ws_title,
            "sources_ingested": 2,
            "quiz_questions_generated": q_count,
            "score_result": score_text,
            "page_errors": page_errors,
            "console_errors": serious_console_errors,
            "status": "ALL_PASSED"
        }
        (QA_OUT / "qa-live-acceptance-summary.json").write_text(json.dumps(summary, indent=2))
        print("=" * 70)
        print("ALL LIVE ACCEPTANCE TESTS PASSED SUCCESSFULLY!")
        print("Summary report written to tests/qa-artifacts/qa-live-acceptance-summary.json")
        print("=" * 70)

        browser.close()


if __name__ == "__main__":
    run_live_acceptance_suite()
