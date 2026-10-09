from pathlib import Path
import json
import re
from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).parent / "artifacts"
OUT.mkdir(exist_ok=True)
errors = []
console_errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    response = page.goto(BASE, wait_until="networkidle", timeout=30000)
    assert response and response.status == 200, "App root failed to load"
    expect(page.get_by_text("Scholar Studio", exact=True)).to_be_visible()
    expect(page.get_by_text("Studio Inquiry")).to_be_visible()
    expect(page.get_by_text("Active Recall Quiz")).to_be_visible()
    page.screenshot(path=str(OUT / "scholar-studio-initial.png"), full_page=True)
    print("PASS: app loads and primary UI panels render")

    page.get_by_role("button", name="+ New Notebook").click()
    page.locator("#newWorkspaceTitle").fill("Playwright Acceptance Notebook")
    page.locator("#newWorkspaceDesc").fill("Live acceptance test")
    page.get_by_role("button", name="Create", exact=True).click()
    expect(page.locator("#workspaceSelect")).not_to_be_empty(timeout=10000)
    workspace_id = page.locator("#workspaceSelect").input_value()
    print("PASS: notebook creation through UI", workspace_id)

    page.get_by_role("button", name="+ Note").click()
    page.locator("#noteTitleInput").fill("Transformer Fundamentals")
    page.locator("#noteContentInput").fill(
        "The Transformer uses self-attention to compute representations without recurrence. "
        "Multi-Head Attention concatenates multiple attention heads and applies an output projection. "
        "Positional encodings are added to token embeddings so the model can use sequence order. "
        "Sine and cosine functions with different frequencies encode positions."
    )
    page.get_by_role("button", name="Save & Chunk").click()
    expect(page.get_by_text("Transformer Fundamentals", exact=True)).to_be_visible(timeout=15000)
    expect(page.get_by_text("1 chunks", exact=True)).to_be_visible()
    print("PASS: source note ingested and chunked through UI")

    page.get_by_role("button", name=re.compile(r"Generate Grounded Quiz")).click()
    expect(page.locator("#quizArenaContainer .question-box").first).to_be_visible(timeout=120000)
    questions = page.locator("#quizArenaContainer .question-box")
    count = questions.count()
    assert count >= 1, "Quiz endpoint returned no questions"
    expect(questions.first.locator(".question-text")).not_to_be_empty()
    print(f"PASS: live quiz generation produced {count} question(s)")
    page.screenshot(path=str(OUT / "quiz-generated.png"), full_page=True)

    options = questions.first.locator(".quiz-option")
    assert options.count() >= 2, "Generated question has fewer than two options"
    options.first.click()
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Submit & Verify Against Sources").click()
    expect(questions.first.locator(".explanation-card")).to_be_visible(timeout=15000)
    expect(questions.first.locator(".citation-anchor-box")).to_be_visible()
    print("PASS: quiz answer submission shows explanation and source quote")

    page.get_by_role("button", name="Study Guide").click()
    page.get_by_role("button", name="Synthesize New Guide").click()
    expect(page.locator("#studyGuideContent h3")).to_be_visible(timeout=120000)
    print("PASS: live study guide generation works")
    page.screenshot(path=str(OUT / "study-guide.png"), full_page=True)

    podcast_ui = page.get_by_text("Podcast", exact=False).count()
    api_paths = page.request.get(f"{BASE}/openapi.json").json().get("paths", {})
    podcast_api = [path for path in api_paths if "podcast" in path.lower() or "audio" in path.lower()]
    assert podcast_ui == 0 and not podcast_api, "Podcast feature unexpectedly exists; inspect implementation"
    print("NOT IMPLEMENTED: no podcast/audio overview UI or API endpoint is present")

    result = {
        "workspace_id": workspace_id,
        "generated_quiz_questions": count,
        "podcast_ui_matches": podcast_ui,
        "podcast_api_routes": podcast_api,
        "page_errors": errors,
        "console_errors": console_errors,
    }
    (OUT / "playwright-results.json").write_text(json.dumps(result, indent=2))
    assert not errors, f"Browser JavaScript errors: {errors}"
    print("RESULT:", json.dumps(result, indent=2))
    browser.close()
