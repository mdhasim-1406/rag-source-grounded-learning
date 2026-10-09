from pathlib import Path
import json
import re
import pytest
from playwright.sync_api import sync_playwright, expect

BASE_URL = "http://127.0.0.1:8000"
QA_OUT = Path(__file__).parent / "qa-artifacts"
QA_OUT.mkdir(exist_ok=True)

MOCK_WORKSPACE_1 = {"id": "ws-1", "title": "Operating Systems", "description": "OS Notes", "created_at": "2026-10-08T00:00:00"}
MOCK_WORKSPACE_2 = {"id": "ws-2", "title": "Distributed Systems", "description": "DS Notes", "created_at": "2026-10-08T00:00:00"}

MOCK_SOURCES = [
    {
        "id": "src-1",
        "workspace_id": "ws-1",
        "title": "Virtual Memory.pdf",
        "source_type": "pdf",
        "chunk_count": 8,
        "created_at": "2026-10-08T00:00:00"
    },
    {
        "id": "src-2",
        "workspace_id": "ws-1",
        "title": "Process Scheduling.txt",
        "source_type": "note",
        "chunk_count": 4,
        "created_at": "2026-10-08T00:00:00"
    }
]

MOCK_DECK_MULTI = {
    "id": "deck-multi",
    "workspace_id": "ws-1",
    "title": "OS Multi-Select Diagnostic",
    "difficulty": "medium",
    "total_questions": 1,
    "created_at": "2026-10-08T00:00:00",
    "questions": [
        {
            "id": "q-multi-1",
            "type": "multi_select",
            "question": "Which of the following are valid page replacement algorithms?",
            "options": ["FIFO", "Round Robin", "LRU", "Dijkstra Shortest Path"],
            "correct_answer": [0, 2],
            "explanation": "FIFO and LRU are page replacement algorithms. Round Robin is CPU scheduling.",
            "citation": {
                "source_id": "src-1",
                "source_title": "Virtual Memory.pdf",
                "page_number": 3,
                "quote": "Common page replacement strategies include FIFO, Optimal, and LRU."
            },
            "concept_tag": "Virtual Memory",
            "bloom_level": "understand"
        }
    ]
}

MOCK_DECK_FLASHCARD = {
    "id": "deck-flash",
    "workspace_id": "ws-1",
    "title": "OS Flashcard Deck",
    "difficulty": "easy",
    "total_questions": 1,
    "created_at": "2026-10-08T00:00:00",
    "questions": [
        {
            "id": "q-flash-1",
            "type": "flashcard",
            "question": "Define Thrashing in operating systems.",
            "options": [],
            "correct_answer": "A state where the CPU spends more time paging than executing instructions.",
            "explanation": "Thrashing occurs when high multiprogramming causes excessive page faults.",
            "citation": {
                "source_id": "src-1",
                "source_title": "Virtual Memory.pdf",
                "page_number": 5,
                "quote": "When total working set exceeds physical frames, thrashing occurs."
            },
            "concept_tag": "Thrashing",
            "bloom_level": "recall"
        }
    ]
}


@pytest.fixture(scope="module")
def browser_instance():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


def setup_mock_routes(page, initial_deck=None):
    """Sets up standard API routes mocking for deterministic testing."""
    page.route("**/api/v1/system", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps({"provider": "OmniRoute", "model": "gemini-3.8-flash"})
    ))
    page.route("**/api/v1/workspaces", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps([MOCK_WORKSPACE_1, MOCK_WORKSPACE_2])
    ))
    page.route("**/api/v1/sources/ws-1", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(MOCK_SOURCES)
    ))
    page.route("**/api/v1/sources/ws-2", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps([])
    ))
    page.route("**/api/v1/quizzes/workspace/ws-1", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps([initial_deck] if initial_deck else [])
    ))
    page.route("**/api/v1/quizzes/workspace/ws-2", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps([])
    ))
    page.route("**/api/v1/quizzes/mastery/*", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps({"workspace_id": "ws-1", "overall_mastery": 80, "concepts": []})
    ))


def test_multiselect_interaction_and_submission(browser_instance):
    """Tests multi_select question type: toggle options, submit multiple selections, check feedback."""
    page = browser_instance.new_page(viewport={"width": 1400, "height": 900})
    submitted_payload = []

    def handle_submit(route):
        data = json.loads(route.request.post_data)
        submitted_payload.append(data)
        feedback = [
            {
                "question_id": "q-multi-1",
                "is_correct": True,
                "score": 1.0,
                "user_answer": [0, 2],
                "correct_answer": [0, 2],
                "explanation": "Correct page replacement algorithms.",
                "citation": MOCK_DECK_MULTI["questions"][0]["citation"],
                "concept_tag": "Virtual Memory",
                "evaluator_feedback": ""
            }
        ]
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "deck_id": "deck-multi",
                "total_score": 1.0,
                "total_questions": 1,
                "percentage": 100.0,
                "concept_breakdown": {},
                "feedback": feedback
            })
        )

    setup_mock_routes(page, initial_deck=MOCK_DECK_MULTI)
    page.route("**/api/v1/quizzes/submit", handle_submit)

    page.goto(BASE_URL, wait_until="networkidle")

    # Verify multi-select question rendered
    qbox = page.locator("#qbox-q-multi-1")
    expect(qbox).to_be_visible()

    options = qbox.locator(".quiz-option")
    expect(options).to_have_count(4)

    # Click FIFO (index 0) and LRU (index 2)
    options.nth(0).click()
    expect(options.nth(0)).to_have_class(re.compile(r"selected"))

    options.nth(2).click()
    expect(options.nth(2)).to_have_class(re.compile(r"selected"))
    expect(options.nth(0)).to_have_class(re.compile(r"selected"))

    # Also test deselecting by clicking again
    options.nth(1).click()
    expect(options.nth(1)).to_have_class(re.compile(r"selected"))
    options.nth(1).click()
    expect(options.nth(1)).not_to_have_class(re.compile(r"selected"))

    # Submit quiz
    page.get_by_role("button", name=re.compile(r"Submit & Verify", re.I)).click()

    assert len(submitted_payload) == 1
    subs = submitted_payload[0]["submissions"]
    assert subs[0]["question_id"] == "q-multi-1"
    # answer must be list of selected indices [0, 2]
    assert sorted(subs[0]["answer"]) == [0, 2]

    # Verify feedback visible
    expect(qbox.locator(".explanation-card")).to_be_visible()
    expect(qbox.locator(".citation-anchor-box")).to_be_visible()
    page.screenshot(path=str(QA_OUT / "qa-fixture-multiselect.png"))
    page.close()


def test_flashcard_reveal_no_auto_grade_requires_explicit_rating(browser_instance):
    """Tests flashcard: reveal must not auto-grade; require explicit recall self-rating."""
    page = browser_instance.new_page(viewport={"width": 1400, "height": 900})
    submitted_payload = []

    def handle_submit(route):
        data = json.loads(route.request.post_data)
        submitted_payload.append(data)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "deck_id": "deck-flash",
                "total_score": 0.0,
                "total_questions": 1,
                "percentage": 0.0,
                "concept_breakdown": {},
                "feedback": [
                    {
                        "question_id": "q-flash-1",
                        "is_correct": False,
                        "score": 0.0,
                        "user_answer": 0,
                        "correct_answer": MOCK_DECK_FLASHCARD["questions"][0]["correct_answer"],
                        "explanation": "Needs review.",
                        "citation": MOCK_DECK_FLASHCARD["questions"][0]["citation"],
                        "concept_tag": "Thrashing",
                        "evaluator_feedback": ""
                    }
                ]
            })
        )

    setup_mock_routes(page, initial_deck=MOCK_DECK_FLASHCARD)
    page.route("**/api/v1/quizzes/submit", handle_submit)

    page.goto(BASE_URL, wait_until="networkidle")

    qbox = page.locator("#qbox-q-flash-1")
    expect(qbox).to_be_visible()

    flip_btn = qbox.locator("#btn-flip-q-flash-1")
    reveal_div = qbox.locator("#flashcard-reveal-q-flash-1")

    expect(flip_btn).to_be_visible()
    expect(reveal_div).to_be_hidden()

    # Click reveal
    flip_btn.click()
    expect(reveal_div).to_be_visible()

    # Self-rating buttons must be present
    needs_practice_btn = qbox.locator(".self-rate-btn[data-rate='0']")
    mastered_btn = qbox.locator(".self-rate-btn[data-rate='1']")
    expect(needs_practice_btn).to_be_visible()
    expect(mastered_btn).to_be_visible()

    # Explicitly click "Needs Practice" (0)
    needs_practice_btn.click()
    expect(needs_practice_btn).to_have_class(re.compile(r"active|selected"))

    page.get_by_role("button", name=re.compile(r"Submit & Verify", re.I)).click()

    assert len(submitted_payload) == 1
    subs = submitted_payload[0]["submissions"]
    assert subs[0]["question_id"] == "q-flash-1"
    assert subs[0]["answer"] == 0

    page.screenshot(path=str(QA_OUT / "qa-fixture-flashcard.png"))
    page.close()


def test_empty_scope_shows_error_not_silently_all(browser_instance):
    """Tests empty scope []: deselecting all sources shows error and does not send requests."""
    page = browser_instance.new_page(viewport={"width": 1400, "height": 900})
    api_requests = []

    def record_request(route):
        api_requests.append(route.request.url)
        route.abort()

    setup_mock_routes(page)
    page.route("**/api/v1/chat", record_request)
    page.route("**/api/v1/quizzes/generate", record_request)
    page.route("**/api/v1/study/guide", record_request)

    page.goto(BASE_URL, wait_until="networkidle")

    # Deselect all sources using toggle
    toggle_link = page.locator("#toggleSelectAllSources")
    toggle_link.click()

    # Verify active sources count is 0
    expect(page.locator("#activeSourcesIndicator")).to_contain_text("0 of 2 active")

    # 1. Attempt Inquiry
    page.locator("#queryInput").fill("What is virtual memory?")
    page.locator("#btnSendQuery").click()

    # Must show error and NOT call /api/v1/chat
    assert not any("/api/v1/chat" in u for u in api_requests)
    expect(page.locator("#chatStream")).to_contain_text("No sources selected")

    # 2. Attempt Quiz Generation
    page.locator("#btnGenerateQuiz").click()
    assert not any("/api/v1/quizzes/generate" in u for u in api_requests)
    expect(page.locator("#quizArenaContainer")).to_contain_text("No sources selected")

    # 3. Attempt Study Guide Synthesis
    page.locator("[data-tab='guide']").click()
    page.locator("#btnSynthesizeGuide").click()
    assert not any("/api/v1/study/guide" in u for u in api_requests)
    expect(page.locator("#studyGuideContent")).to_contain_text("No sources selected")

    page.screenshot(path=str(QA_OUT / "qa-fixture-empty-scope.png"))
    page.close()


def test_xss_sanitization(browser_instance):
    """Tests XSS prevention: user input and LLM output must be rendered safely with no script execution."""
    page = browser_instance.new_page(viewport={"width": 1400, "height": 900})

    setup_mock_routes(page)
    page.route("**/api/v1/chat", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps({
            "answer": 'Here is an answer with <img src="x" onerror="window.__xss_fired=1"> and <script>window.__xss_fired=2</script> citing [1].',
            "citations": [
                {
                    "citation_index": 1,
                    "source_id": "src-1",
                    "source_title": "Virtual Memory.pdf",
                    "page_number": 2,
                    "quote": "Safe quote"
                }
            ],
            "retrieval_count": 1
        })
    ))

    page.goto(BASE_URL, wait_until="networkidle")
    page.locator("#queryInput").fill("<script>window.__xss_fired=3</script> Hello")
    page.locator("#btnSendQuery").click()

    # Wait for response card
    expect(page.locator(".citation-pill")).to_be_visible()

    # Check XSS flag in window
    xss_fired = page.evaluate("() => window.__xss_fired")
    assert xss_fired is None, f"XSS executed! Flag value: {xss_fired}"

    # Verify citation pill button works and opens modal
    page.locator(".citation-pill").click()
    expect(page.locator("#citationModal")).to_have_class(re.compile(r"active"))
    expect(page.locator("#modalCitationSource")).to_have_text("Virtual Memory.pdf")

    page.close()


def test_notebook_switching_clears_state(browser_instance):
    """Tests notebook switching clears chat, quiz, guide, and analytics state."""
    page = browser_instance.new_page(viewport={"width": 1400, "height": 900})

    setup_mock_routes(page, initial_deck=MOCK_DECK_MULTI)

    page.goto(BASE_URL, wait_until="networkidle")

    # In workspace 1, quiz is loaded
    expect(page.locator("#qbox-q-multi-1")).to_be_visible()

    # Switch to workspace 2 (which has no quiz, no sources)
    page.locator("#workspaceSelect").select_option("ws-2")

    # Quiz arena must be empty, not showing old workspace questions
    expect(page.locator("#qbox-q-multi-1")).not_to_be_visible()
    expect(page.locator("#quizArenaContainer")).to_contain_text("No quiz loaded")

    # Sources must be empty
    expect(page.locator("#sourcesCountBadge")).to_have_text("0")

    page.close()


def test_mobile_responsive_390px_and_panel_tabs(browser_instance):
    """Tests mobile responsiveness at 390px: no overflow, panel tabs work."""
    page = browser_instance.new_page(viewport={"width": 390, "height": 844})
    setup_mock_routes(page)

    page.goto(BASE_URL, wait_until="networkidle")

    # Assert no horizontal overflow
    scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
    assert scroll_width <= 390, f"Page overflows horizontally at 390px! scrollWidth={scroll_width}"

    # Assert mobile panel tabs are visible
    panel_nav = page.locator("#mobilePanelNav")
    expect(panel_nav).to_be_visible()

    sources_btn = panel_nav.locator("[data-panel='sources']")
    studio_btn = panel_nav.locator("[data-panel='studio']")
    mastery_btn = panel_nav.locator("[data-panel='mastery']")

    # Switch to sources panel
    sources_btn.click()
    expect(page.locator(".column-sources")).to_be_visible()
    expect(page.locator(".column-studio")).to_be_hidden()
    expect(page.locator(".column-mastery")).to_be_hidden()

    # Switch to mastery panel
    mastery_btn.click()
    expect(page.locator(".column-mastery")).to_be_visible()
    expect(page.locator(".column-sources")).to_be_hidden()
    expect(page.locator(".column-studio")).to_be_hidden()

    # Switch to studio panel
    studio_btn.click()
    expect(page.locator(".column-studio")).to_be_visible()
    expect(page.locator(".column-sources")).to_be_hidden()
    expect(page.locator(".column-mastery")).to_be_hidden()

    page.screenshot(path=str(QA_OUT / "qa-fixture-mobile-390px.png"))
    page.close()


def test_no_ui_emoji(browser_instance):
    """Tests that UI buttons and headers do not contain emoji icons."""
    page = browser_instance.new_page(viewport={"width": 1400, "height": 900})
    setup_mock_routes(page)
    page.goto(BASE_URL, wait_until="networkidle")

    btn_text = page.locator("#btnGenerateQuiz").text_content()
    assert "⚡" not in btn_text, f"Emoji ⚡ still found in generate button: '{btn_text}'"

    page.close()


def test_pdf_upload_includes_workspace_id(browser_instance, tmp_path):
    """Tests that PDF upload sends workspace_id in multipart form data."""
    page = browser_instance.new_page(viewport={"width": 1400, "height": 900})
    upload_calls = []

    def handle_upload(route):
        post_data = route.request.post_data_buffer
        # Check text representation of multipart body
        content_type = route.request.headers.get("content-type", "")
        upload_calls.append({
            "content_type": content_type,
            "has_workspace_id": b"workspace_id" in post_data and b"ws-1" in post_data
        })
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "id": "src-uploaded",
                "workspace_id": "ws-1",
                "title": "sample_upload.pdf",
                "source_type": "pdf",
                "chunk_count": 2,
                "created_at": "2026-10-08T00:00:00"
            })
        )

    setup_mock_routes(page)
    page.route("**/api/v1/sources/upload", handle_upload)

    dummy_pdf = tmp_path / "sample_upload.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 sample pdf content")

    page.goto(BASE_URL, wait_until="networkidle")
    page.locator("#btnUploadModal").click()
    page.locator("#fileUploadInput").set_input_files(str(dummy_pdf))
    page.locator("#btnSubmitUpload").click()

    page.wait_for_timeout(500)
    assert len(upload_calls) == 1
    assert upload_calls[0]["has_workspace_id"] is True, "workspace_id was not provided in upload form data"
    page.close()


def test_export_study_pack_download(browser_instance):
    """Tests exporting study pack generates valid JSON download payload."""
    page = browser_instance.new_page(viewport={"width": 1400, "height": 900})
    setup_mock_routes(page, initial_deck=MOCK_DECK_MULTI)

    page.goto(BASE_URL, wait_until="networkidle")

    with page.expect_download() as download_info:
        page.locator("#btnExportNotes").click()

    download = download_info.value
    assert download.suggested_filename.endswith(".json")
    path = download.path()
    content = json.loads(Path(path).read_text())
    assert content["workspace"]["id"] == "ws-1"
    assert content["quizDeck"]["id"] == "deck-multi"
    page.close()

