// ==============================================================================
// Scholar Studio - Client Architecture
// Zero AI Slop, Pure Vanilla JS, High Integrity Pedagogical UI
// ==============================================================================

const API_BASE = "/api/v1";

const state = {
  workspaces: [],
  currentWorkspace: null,
  activeWorkspaceId: null, // Guard against stale async leaks
  sources: [],
  selectedSourceIds: new Set(),
  currentDeck: null,
  userAnswers: {},
  chatHistory: [],
  chatSessions: [],
  activeSessionId: null,
  savedGuides: [],
  activeMobilePanel: "studio",

  // Duplicate request guards
  isQuerying: false,
  isGeneratingQuiz: false,
  isSubmittingQuiz: false,
  isSynthesizingGuide: false,
  isUploading: false,
  isCreatingNote: false,
  isCreatingWorkspace: false
};

// ==============================================================================
// Initialization
// ==============================================================================
document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  await loadSystemInfo();
  await loadWorkspaces();
});

async function loadSystemInfo() {
  try {
    const res = await fetch(`${API_BASE}/system`);
    if (res.ok) {
      const data = await res.json();
      const el = document.getElementById("modelIndicator");
      if (el) el.textContent = `${data.provider} / ${data.model.split("/").pop()}`;
    }
  } catch (err) {
    console.error("Failed to load system info:", err);
  }
}

function setupEventListeners() {
  // Workspace select
  document.getElementById("workspaceSelect").addEventListener("change", (e) => {
    switchWorkspace(e.target.value);
  });

  // Modals
  document.getElementById("btnNewWorkspace").addEventListener("click", () => {
    document.getElementById("workspaceModal").classList.add("active");
  });
  document.getElementById("btnSubmitNewWorkspace").addEventListener("click", handleCreateWorkspace);

  document.getElementById("btnUploadModal").addEventListener("click", () => {
    document.getElementById("uploadModal").classList.add("active");
  });
  document.getElementById("btnSubmitUpload").addEventListener("click", handleUploadFile);

  document.getElementById("btnTextModal").addEventListener("click", () => {
    document.getElementById("textModal").classList.add("active");
  });
  document.getElementById("btnSubmitNote").addEventListener("click", handleCreateTextNote);

  // Sources selection toggle
  document.getElementById("toggleSelectAllSources").addEventListener("click", toggleSelectAllSources);

  // Grounded Chat
  document.getElementById("btnSendQuery").addEventListener("click", handleSendQuery);
  document.getElementById("queryInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendQuery();
    }
  });
  document.getElementById("btnClearChat").addEventListener("click", () => {
    createChatSession();
  });
  document.getElementById("chatSessionSelect").addEventListener("change", e => loadChatSession(e.target.value));
  document.getElementById("btnRenameChat").addEventListener("click", renameChatSession);
  document.getElementById("btnDeleteChat").addEventListener("click", deleteChatSession);
  document.getElementById("savedGuideSelect").addEventListener("change", e => loadSavedGuide(e.target.value));
  document.getElementById("btnDeleteGuide").addEventListener("click", deleteSavedGuide);

  // Quiz Arena
  document.getElementById("btnGenerateQuiz").addEventListener("click", handleGenerateQuiz);

  // Study Guide
  document.getElementById("btnSynthesizeGuide").addEventListener("click", handleSynthesizeGuide);

  // Export Study Pack
  document.getElementById("btnExportNotes").addEventListener("click", handleExportStudyPack);

  // Mastery Tabs (Right Column: Quiz / Guide / Analytics)
  document.querySelectorAll(".mastery-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".mastery-tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      const tab = btn.dataset.tab;
      document.getElementById("tabContentQuiz").style.display = tab === "quiz" ? "block" : "none";
      document.getElementById("tabContentGuide").style.display = tab === "guide" ? "block" : "none";
      document.getElementById("tabContentMastery").style.display = tab === "mastery" ? "block" : "none";

      if (tab === "mastery") {
        loadMasteryAnalytics();
      }
    });
  });

  // Mobile Panel Navigation (Sources / Studio / Mastery)
  document.querySelectorAll(".mobile-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const panel = btn.dataset.panel;
      switchMobilePanel(panel);
    });
  });
}

function switchMobilePanel(panelName) {
  state.activeMobilePanel = panelName;
  document.querySelectorAll(".mobile-tab-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.panel === panelName);
  });

  const sourcesCol = document.querySelector(".column-sources");
  const studioCol = document.querySelector(".column-studio");
  const masteryCol = document.querySelector(".column-mastery");

  if (sourcesCol) sourcesCol.classList.toggle("mobile-active", panelName === "sources");
  if (studioCol) studioCol.classList.toggle("mobile-active", panelName === "studio");
  if (masteryCol) masteryCol.classList.toggle("mobile-active", panelName === "mastery");
}

// ==============================================================================
// Workspaces Management
// ==============================================================================
async function loadWorkspaces() {
  try {
    const res = await fetch(`${API_BASE}/workspaces`);
    const data = await res.json();
    state.workspaces = data;

    const select = document.getElementById("workspaceSelect");
    select.innerHTML = "";

    if (state.workspaces.length === 0) {
      const defaultWs = await fetch(`${API_BASE}/workspaces`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: "General Study Notebook",
          description: "Default workspace for notes and source documents"
        })
      }).then((r) => r.json());
      state.workspaces = [defaultWs];
    }

    state.workspaces.forEach((ws) => {
      const opt = document.createElement("option");
      opt.value = ws.id;
      opt.textContent = ws.title;
      select.appendChild(opt);
    });

    await switchWorkspace(state.workspaces[0].id);
  } catch (err) {
    console.error("Failed to load workspaces:", err);
  }
}

async function switchWorkspace(wsId) {
  const targetWs = state.workspaces.find((w) => w.id === wsId);
  if (!targetWs) return;

  state.currentWorkspace = targetWs;
  state.activeWorkspaceId = wsId;
  const currentToken = wsId;

  const select = document.getElementById("workspaceSelect");
  if (select) select.value = wsId;

  // 1. Clear chat stream
  resetChatStream(targetWs.title);

  // 2. Reset mastery tab to default (quiz)
  document.querySelectorAll(".mastery-tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === "quiz"));
  const quizTab = document.getElementById("tabContentQuiz");
  const guideTab = document.getElementById("tabContentGuide");
  const masteryTab = document.getElementById("tabContentMastery");
  if (quizTab) quizTab.style.display = "block";
  if (guideTab) guideTab.style.display = "none";
  if (masteryTab) masteryTab.style.display = "none";

  // 3. Clear quiz arena and answers
  state.currentDeck = null;
  state.userAnswers = {};
  renderEmptyQuizArena();

  // 4. Clear study guide
  renderEmptyStudyGuide();

  // 5. Clear mastery analytics
  renderEmptyMasteryAnalytics();

  // 5. Load sources
  await loadSources(wsId);
  if (state.activeWorkspaceId !== currentToken) return; // Discard if stale

  // 6. Load persisted quiz decks
  await loadQuizDecks(wsId);
  await loadChatSessions(wsId);
  await loadSavedGuides(wsId);
}

async function handleCreateWorkspace() {
  if (state.isCreatingWorkspace) return;
  const title = document.getElementById("newWorkspaceTitle").value.trim();
  const desc = document.getElementById("newWorkspaceDesc").value.trim();
  if (!title) return alert("Please enter a notebook title.");

  state.isCreatingWorkspace = true;
  const submitBtn = document.getElementById("btnSubmitNewWorkspace");
  if (submitBtn) submitBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/workspaces`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, description: desc })
    });
    if (!res.ok) throw new Error(await res.text());

    const ws = await res.json();
    state.workspaces.unshift(ws);

    const select = document.getElementById("workspaceSelect");
    const opt = document.createElement("option");
    opt.value = ws.id;
    opt.textContent = ws.title;
    select.prepend(opt);

    document.getElementById("workspaceModal").classList.remove("active");
    document.getElementById("newWorkspaceTitle").value = "";
    document.getElementById("newWorkspaceDesc").value = "";
    await switchWorkspace(ws.id);
  } catch (err) {
    alert("Failed to create workspace: " + err.message);
  } finally {
    state.isCreatingWorkspace = false;
    if (submitBtn) submitBtn.disabled = false;
  }
}

// ==============================================================================
// Source Operations (PDF, Text Notes, Chunks)
// ==============================================================================
async function loadSources(wsId) {
  const currentToken = wsId;
  try {
    const res = await fetch(`${API_BASE}/sources/${wsId}`);
    if (!res.ok) throw new Error(await res.text());
    const sources = await res.json();

    if (state.activeWorkspaceId !== currentToken) return;

    state.sources = sources;
    restoreSelectedSources(wsId, sources);
    renderSourcesList();
  } catch (err) {
    console.error("Failed to load sources:", err);
  }
}

function renderSourcesList() {
  const container = document.getElementById("sourcesList");
  const countBadge = document.getElementById("sourcesCountBadge");
  const chunksBadge = document.getElementById("totalChunksBadge");
  const activeBadge = document.getElementById("activeSourcesIndicator");
  const toggleLink = document.getElementById("toggleSelectAllSources");

  countBadge.textContent = String(state.sources.length);
  const totalChunks = state.sources.reduce((acc, s) => acc + (s.chunk_count || 0), 0);
  chunksBadge.textContent = `${totalChunks} chunks indexed`;
  activeBadge.textContent = `${state.selectedSourceIds.size} of ${state.sources.length} active`;

  if (toggleLink) {
    if (state.sources.length > 0 && state.selectedSourceIds.size === state.sources.length) {
      toggleLink.textContent = "Deselect all";
    } else {
      toggleLink.textContent = "Select all";
    }
  }

  container.replaceChildren();

  if (state.sources.length === 0) {
    const emptyDiv = document.createElement("div");
    emptyDiv.style.textAlign = "center";
    emptyDiv.style.color = "var(--ink-muted)";
    emptyDiv.style.padding = "40px 10px";
    emptyDiv.style.fontSize = "13px";
    emptyDiv.innerHTML = "No sources added yet.<br>Upload a PDF or paste text to begin.";
    container.appendChild(emptyDiv);
    return;
  }

  state.sources.forEach((src) => {
    const isSelected = state.selectedSourceIds.has(src.id);
    const item = document.createElement("div");
    item.className = `source-item ${isSelected ? "selected" : ""}`;

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "source-checkbox";
    checkbox.checked = isSelected;
    checkbox.addEventListener("change", (e) => {
      if (e.target.checked) {
        state.selectedSourceIds.add(src.id);
        persistSelectedSources();
        item.classList.add("selected");
      } else {
        state.selectedSourceIds.delete(src.id);
        persistSelectedSources();
        item.classList.remove("selected");
      }
      activeBadge.textContent = `${state.selectedSourceIds.size} of ${state.sources.length} active`;
      if (toggleLink) {
        toggleLink.textContent =
          state.selectedSourceIds.size === state.sources.length ? "Deselect all" : "Select all";
      }
    });

    const info = document.createElement("div");
    info.className = "source-info";

    const titleText = document.createElement("div");
    titleText.className = "source-title-text";
    titleText.title = src.title;
    titleText.textContent = src.title;

    const meta = document.createElement("div");
    meta.className = "source-meta";

    const chip = document.createElement("span");
    chip.className = `chip-tag ${src.source_type === "pdf" ? "chip-pdf" : "chip-note"}`;
    chip.textContent = src.source_type.toUpperCase();

    const chunksCount = document.createElement("span");
    chunksCount.className = "source-chunks-count";
    chunksCount.textContent = `${src.chunk_count} chunks`;

    meta.appendChild(chip);
    meta.appendChild(chunksCount);
    info.appendChild(titleText);
    info.appendChild(meta);

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "btn btn-ghost";
    deleteBtn.dataset.delete = src.id;
    deleteBtn.style.padding = "2px 5px";
    deleteBtn.style.fontSize = "11px";
    deleteBtn.title = "Delete Source";
    deleteBtn.textContent = "✕";
    deleteBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (confirm(`Remove source "${src.title}"?`)) {
        await deleteSource(src.id);
      }
    });

    item.appendChild(checkbox);
    item.appendChild(info);
    item.appendChild(deleteBtn);
    container.appendChild(item);
  });
}

function toggleSelectAllSources() {
  if (state.sources.length === 0) return;
  if (state.selectedSourceIds.size === state.sources.length) {
    state.selectedSourceIds.clear();
    persistSelectedSources();
  } else {
    state.selectedSourceIds = new Set(state.sources.map((s) => s.id));
    persistSelectedSources();
  }
  renderSourcesList();
}

async function handleUploadFile() {
  if (state.isUploading) return;
  const fileInput = document.getElementById("fileUploadInput");
  if (!fileInput.files || fileInput.files.length === 0) {
    return alert("Please select a file to upload.");
  }
  if (!state.currentWorkspace) {
    return alert("No active workspace selected.");
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);
  formData.append("workspace_id", state.currentWorkspace.id);

  const btn = document.getElementById("btnSubmitUpload");
  btn.disabled = true;
  btn.textContent = "Ingesting & Chunking...";
  state.isUploading = true;

  try {
    const res = await fetch(`${API_BASE}/sources/upload`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) throw new Error(await res.text());

    document.getElementById("uploadModal").classList.remove("active");
    fileInput.value = "";
    await loadSources(state.currentWorkspace.id);
  } catch (err) {
    alert("Upload failed: " + err.message);
  } finally {
    state.isUploading = false;
    btn.disabled = false;
    btn.textContent = "Ingest & Index";
  }
}

async function handleCreateTextNote() {
  if (state.isCreatingNote) return;
  const title = document.getElementById("noteTitleInput").value.trim();
  const content = document.getElementById("noteContentInput").value.trim();
  if (!title || !content) return alert("Please enter both title and content.");
  if (!state.currentWorkspace) return alert("No active workspace selected.");

  const btn = document.getElementById("btnSubmitNote");
  btn.disabled = true;
  btn.textContent = "Processing...";
  state.isCreatingNote = true;

  try {
    const res = await fetch(`${API_BASE}/sources/text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace_id: state.currentWorkspace.id,
        title,
        content,
        source_type: "note"
      })
    });
    if (!res.ok) throw new Error(await res.text());

    document.getElementById("textModal").classList.remove("active");
    document.getElementById("noteTitleInput").value = "";
    document.getElementById("noteContentInput").value = "";
    await loadSources(state.currentWorkspace.id);
  } catch (err) {
    alert("Note creation failed: " + err.message);
  } finally {
    state.isCreatingNote = false;
    btn.disabled = false;
    btn.textContent = "Save & Chunk";
  }
}

async function deleteSource(sourceId) {
  try {
    await fetch(`${API_BASE}/sources/${sourceId}`, { method: "DELETE" });
    if (state.currentWorkspace) {
      await loadSources(state.currentWorkspace.id);
    }
  } catch (err) {
    alert("Delete failed: " + err.message);
  }
}

// ==============================================================================
// Studio Grounded Chat & Verifiable Citations (XSS Safe)
// ==============================================================================
function resetChatStream(workspaceTitle) {
  const chatStream = document.getElementById("chatStream");
  if (!chatStream) return;
  chatStream.replaceChildren();

  const card = document.createElement("div");
  card.className = "message-card message-assistant";
  card.style.marginTop = "20px";

  const body = document.createElement("div");
  body.className = "assistant-body";
  body.style.fontFamily = "var(--font-serif)";
  body.style.fontSize = "16px";
  body.style.color = "var(--ink-secondary)";

  const welcomeText = workspaceTitle
    ? `Welcome to Scholar Studio. You are currently in notebook: "${workspaceTitle}". Upload lecture slides, papers, or textbook chapters in the Sources panel.`
    : "Welcome to Scholar Studio. Upload your lecture slides, academic papers, or textbook chapters in the Sources panel on the left.";

  body.textContent = welcomeText;
  card.appendChild(body);
  chatStream.appendChild(card);
}

async function handleSendQuery() {
  if (state.isQuerying) return;
  const input = document.getElementById("queryInput");
  const query = input.value.trim();
  if (!query) return;

  if (state.sources.length === 0) {
    return alert("Please upload at least one source document before asking questions.");
  }

  // Guard: Scope [] empty selection must show error, not silently use all sources
  if (state.selectedSourceIds.size === 0) {
    const chatStream = document.getElementById("chatStream");
    const errCard = document.createElement("div");
    errCard.className = "message-card message-assistant";

    const errBody = document.createElement("div");
    errBody.className = "assistant-body";
    errBody.style.color = "var(--accent-rose)";
    errBody.textContent = "No sources selected. Please select at least one source in the Sources panel.";

    errCard.appendChild(errBody);
    chatStream.appendChild(errCard);
    chatStream.scrollTop = chatStream.scrollHeight;
    return;
  }

  if (!state.activeSessionId) {
    showPersistenceError("Start conversation", new Error("Create a new chat before sending a message."));
    return;
  }
  input.value = "";
  const chatStream = document.getElementById("chatStream");

  // Render user message safely
  const userCard = document.createElement("div");
  userCard.className = "message-card message-user";
  userCard.textContent = query;
  chatStream.appendChild(userCard);

  // Render assistant placeholder safely
  const assistantCard = document.createElement("div");
  assistantCard.className = "message-card message-assistant";

  const placeholderBody = document.createElement("div");
  placeholderBody.className = "assistant-body";
  placeholderBody.style.fontFamily = "var(--font-serif)";
  placeholderBody.style.fontSize = "15.5px";
  placeholderBody.style.color = "var(--ink-secondary)";
  placeholderBody.textContent = "Synthesizing source-grounded response...";

  assistantCard.appendChild(placeholderBody);
  chatStream.appendChild(assistantCard);
  chatStream.scrollTop = chatStream.scrollHeight;

  const btn = document.getElementById("btnSendQuery");
  btn.disabled = true;
  state.isQuerying = true;
  const targetWsId = state.currentWorkspace ? state.currentWorkspace.id : null;

  try {
    if (!state.activeWorkspaceId || !state.activeSessionId) {
      // A conversation must be explicitly available before sending; never silently create or switch sessions here.
      if (!state.activeSessionId) {
        const body=assistantCard.querySelector('.assistant-body');
        if(body) body.textContent='Create a new chat before sending a message.';
      }
      return;
    }
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace_id: targetWsId,
        query,
        source_ids: Array.from(state.selectedSourceIds),
        session_id: state.activeSessionId
      })
    });

    if (state.activeWorkspaceId !== targetWsId) {
      // Discard stale async response from another workspace
      return;
    }

    if (!res.ok) {
      let errorMsg = "Query failed";
      try {
        const errData = await res.json();
        errorMsg = errData.detail || errorMsg;
      } catch {
        errorMsg = await res.text();
      }
      throw new Error(errorMsg);
    }

    const data = await res.json();
    if (state.activeWorkspaceId !== targetWsId) return;

    if (data.session_id && data.session_id !== state.activeSessionId) return;
    renderAssistantResponse(assistantCard, data.answer, data.citations);
  } catch (err) {
    if (state.activeWorkspaceId !== targetWsId) return;
    const body = assistantCard.querySelector(".assistant-body");
    if (body) {
      body.style.color = "var(--accent-rose)";
      body.textContent = `Error: ${err.message}`;
    }
  } finally {
    state.isQuerying = false;
    btn.disabled = false;
    chatStream.scrollTop = chatStream.scrollHeight;
  }
}

function renderAssistantResponse(card, answerText, citations = []) {
  const body = card.querySelector(".assistant-body");
  if (!body) return;
  body.replaceChildren();
  card.querySelectorAll('.citations-tray').forEach(el => el.remove());

  // Parse [1], [2] citation bracket patterns without innerHTML injection (Strict XSS safety)
  const citationRegex = /\[(\d+)\]/g;
  let lastIndex = 0;
  let match;

  const fragment = document.createDocumentFragment();

  while ((match = citationRegex.exec(answerText)) !== null) {
    if (match.index > lastIndex) {
      fragment.appendChild(document.createTextNode(answerText.substring(lastIndex, match.index)));
    }

    const citeNum = parseInt(match[1], 10);
    const cite = citations.find((c) => c.citation_index === citeNum);

    const pillBtn = document.createElement("button");
    pillBtn.className = "citation-pill";
    pillBtn.dataset.citeIdx = String(citeNum);
    pillBtn.title = cite ? cite.source_title : `Source ${citeNum}`;
    pillBtn.textContent = `[${citeNum}]`;
    pillBtn.addEventListener("click", () => {
      if (cite) openCitationModal(cite);
    });

    fragment.appendChild(pillBtn);
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < answerText.length) {
    fragment.appendChild(document.createTextNode(answerText.substring(lastIndex)));
  }

  body.appendChild(fragment);

  // Render Citations Tray below answer (Safe DOM)
  if (citations && citations.length > 0) {
    const tray = document.createElement("div");
    tray.className = "citations-tray";

    citations.forEach((cite) => {
      const pill = document.createElement("div");
      pill.className = "citation-card-ref";

      const strong = document.createElement("strong");
      strong.textContent = `[${cite.citation_index}] `;

      const text = document.createTextNode(`${cite.source_title} (p. ${cite.page_number})`);
      pill.appendChild(strong);
      pill.appendChild(text);

      pill.addEventListener("click", () => openCitationModal(cite));
      tray.appendChild(pill);
    });

    card.appendChild(tray);
  }
}

function openCitationModal(cite) {
  document.getElementById("modalCitationPill").textContent = `Citation [${cite.citation_index}]`;
  document.getElementById("modalCitationSource").textContent = cite.source_title;
  document.getElementById("modalCitationPage").textContent = `Page / Offset: ${cite.page_number}`;
  document.getElementById("modalCitationQuote").textContent = `"${cite.quote}"`;
  document.getElementById("citationModal").classList.add("active");
}

// ==============================================================================
// Active Recall Quiz Arena (Pedagogical Engine & Interaction)
// ==============================================================================
function renderEmptyQuizArena() {
  const container = document.getElementById("quizArenaContainer");
  if (!container) return;
  container.replaceChildren();

  const emptyDiv = document.createElement("div");
  emptyDiv.style.textAlign = "center";
  emptyDiv.style.color = "var(--ink-muted)";
  emptyDiv.style.padding = "40px 10px";
  emptyDiv.style.fontSize = "13px";
  emptyDiv.innerHTML = "No quiz loaded.<br>Click \"Generate Grounded Quiz\" above to create source-verified questions.";
  container.appendChild(emptyDiv);
}

async function handleGenerateQuiz() {
  if (state.isGeneratingQuiz) return;

  const arena = document.getElementById("quizArenaContainer");
  if (state.sources.length === 0) {
    arena.replaceChildren();
    const errDiv = document.createElement("div");
    errDiv.style.color = "var(--accent-rose)";
    errDiv.style.textAlign = "center";
    errDiv.style.padding = "30px 10px";
    errDiv.textContent = "Upload documents first before generating a quiz.";
    arena.appendChild(errDiv);
    return;
  }

  // Guard: Scope [] empty selection must show error, not silently all
  if (state.selectedSourceIds.size === 0) {
    arena.replaceChildren();
    const errDiv = document.createElement("div");
    errDiv.style.color = "var(--accent-rose)";
    errDiv.style.textAlign = "center";
    errDiv.style.padding = "30px 10px";
    errDiv.textContent = "No sources selected. Please select at least one source in the Sources panel to generate a quiz.";
    arena.appendChild(errDiv);
    return;
  }

  const difficulty = document.getElementById("quizDifficulty").value;
  const numQuestions = parseInt(document.getElementById("quizCount").value, 10);

  const btn = document.getElementById("btnGenerateQuiz");
  btn.disabled = true;
  btn.textContent = "Generating Grounded Quiz...";
  state.isGeneratingQuiz = true;

  arena.replaceChildren();
  const loadingDiv = document.createElement("div");
  loadingDiv.style.textAlign = "center";
  loadingDiv.style.color = "var(--ink-secondary)";
  loadingDiv.style.padding = "30px 10px";
  loadingDiv.style.fontSize = "13.5px";
  loadingDiv.textContent = "Consulting source chunks and synthesizing grounded questions...";
  arena.appendChild(loadingDiv);

  const targetWsId = state.currentWorkspace ? state.currentWorkspace.id : null;

  try {
    const res = await fetch(`${API_BASE}/quizzes/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace_id: targetWsId,
        source_ids: Array.from(state.selectedSourceIds),
        num_questions: numQuestions,
        difficulty,
        question_types: ["mcq_single", "multi_select", "flashcard"]
      })
    });

    if (state.activeWorkspaceId !== targetWsId) return;

    if (!res.ok) {
      let errDetail = "Quiz generation failed";
      try {
        const errJson = await res.json();
        errDetail = errJson.detail || errDetail;
      } catch {
        errDetail = await res.text();
      }
      throw new Error(errDetail);
    }

    const deck = await res.json();
    if (state.activeWorkspaceId !== targetWsId) return;

    state.currentDeck = deck;
    state.userAnswers = {};
    renderQuizArena(deck);
  } catch (err) {
    if (state.activeWorkspaceId !== targetWsId) return;
    arena.replaceChildren();
    const errDiv = document.createElement("div");
    errDiv.style.color = "var(--accent-rose)";
    errDiv.style.fontSize = "13px";
    errDiv.style.padding = "20px 10px";
    errDiv.textContent = `Quiz generation failed: ${err.message}`;
    arena.appendChild(errDiv);
  } finally {
    state.isGeneratingQuiz = false;
    btn.disabled = false;
    btn.textContent = "Generate Grounded Quiz";
  }
}

async function loadQuizDecks(wsId) {
  const currentToken = wsId;
  try {
    const res = await fetch(`${API_BASE}/quizzes/workspace/${wsId}`);
    if (!res.ok) throw new Error(await res.text());
    const decks = await res.json();

    if (state.activeWorkspaceId !== currentToken) return;

    if (decks && decks.length > 0) {
      state.currentDeck = decks[0];
      state.userAnswers = {};
      renderQuizArena(decks[0]);
    } else {
      state.currentDeck = null;
      state.userAnswers = {};
      renderEmptyQuizArena();
    }
  } catch (err) {
    console.error("Failed to load quiz decks:", err);
  }
}

function renderQuizArena(deck) {
  const container = document.getElementById("quizArenaContainer");
  container.replaceChildren();

  const titleHeader = document.createElement("div");
  titleHeader.style.marginBottom = "14px";

  const deckTitle = document.createElement("div");
  deckTitle.style.fontSize = "14px";
  deckTitle.style.fontWeight = "600";
  deckTitle.style.color = "var(--ink-primary)";
  deckTitle.textContent = deck.title;

  const deckMeta = document.createElement("div");
  deckMeta.style.fontSize = "12px";
  deckMeta.style.color = "var(--ink-muted)";
  const qCount = deck.questions ? deck.questions.length : deck.total_questions;
  deckMeta.textContent = `${qCount} Questions • ${deck.difficulty.toUpperCase()}`;

  titleHeader.appendChild(deckTitle);
  titleHeader.appendChild(deckMeta);
  container.appendChild(titleHeader);

  deck.questions.forEach((q, qIdx) => {
    const qBox = document.createElement("div");
    qBox.className = "question-box";
    qBox.id = `qbox-${q.id}`;

    // Meta header
    const qMeta = document.createElement("div");
    qMeta.className = "question-meta";

    const bloomSpan = document.createElement("span");
    bloomSpan.className = "question-bloom";
    bloomSpan.textContent = q.bloom_level;

    const conceptSpan = document.createElement("span");
    conceptSpan.className = "question-concept";
    conceptSpan.textContent = q.concept_tag || "General";

    qMeta.appendChild(bloomSpan);
    qMeta.appendChild(conceptSpan);
    qBox.appendChild(qMeta);

    // Question text
    const qText = document.createElement("div");
    qText.className = "question-text";
    const typeLabel = q.type === "multi_select" ? " (Select all that apply)" : "";
    qText.textContent = `${qIdx + 1}. ${q.question}${typeLabel}`;
    qBox.appendChild(qText);

    // Options group
    const optionsGroup = document.createElement("div");
    optionsGroup.className = "options-group";

    if (q.type === "mcq_single" || q.type === "multi_select") {
      q.options.forEach((opt, optIdx) => {
        const optDiv = document.createElement("div");
        optDiv.className = "quiz-option";
        optDiv.dataset.optIdx = String(optIdx);

        const prefix = document.createElement("span");
        prefix.style.fontWeight = "600";
        prefix.style.fontSize = "12px";
        prefix.style.color = "var(--ink-secondary)";
        prefix.style.width = "20px";
        prefix.textContent = `${String.fromCharCode(65 + optIdx)})`;

        const optContent = document.createElement("span");
        optContent.textContent = opt;

        optDiv.appendChild(prefix);
        optDiv.appendChild(optContent);

        // Interaction handlers
        if (q.type === "mcq_single") {
          optDiv.addEventListener("click", () => {
            optionsGroup.querySelectorAll(".quiz-option").forEach((o) => o.classList.remove("selected"));
            optDiv.classList.add("selected");
            state.userAnswers[q.id] = optIdx;
          });
        } else if (q.type === "multi_select") {
          optDiv.addEventListener("click", () => {
            if (!Array.isArray(state.userAnswers[q.id])) {
              state.userAnswers[q.id] = [];
            }
            const currentSelected = new Set(state.userAnswers[q.id]);
            if (currentSelected.has(optIdx)) {
              currentSelected.delete(optIdx);
              optDiv.classList.remove("selected");
            } else {
              currentSelected.add(optIdx);
              optDiv.classList.add("selected");
            }
            state.userAnswers[q.id] = Array.from(currentSelected).sort((a, b) => a - b);
          });
        }

        optionsGroup.appendChild(optDiv);
      });
    } else if (q.type === "flashcard") {
      const flashcardWrap = document.createElement("div");
      flashcardWrap.style.padding = "14px";
      flashcardWrap.style.background = "var(--canvas-bg)";
      flashcardWrap.style.borderRadius = "8px";
      flashcardWrap.style.border = "1px dashed var(--border-medium)";
      flashcardWrap.style.marginBottom = "10px";

      const recallHeader = document.createElement("div");
      recallHeader.style.fontSize = "12px";
      recallHeader.style.fontWeight = "600";
      recallHeader.style.color = "var(--ink-secondary)";
      recallHeader.style.marginBottom = "6px";
      recallHeader.textContent = "RECALL ANSWER:";

      const revealDiv = document.createElement("div");
      revealDiv.id = `flashcard-reveal-${q.id}`;
      revealDiv.style.display = "none";
      revealDiv.style.fontSize = "13.5px";
      revealDiv.style.color = "var(--ink-primary)";
      revealDiv.style.fontFamily = "var(--font-serif)";
      revealDiv.style.marginBottom = "10px";
      revealDiv.textContent = q.correct_answer;

      const flipBtn = document.createElement("button");
      flipBtn.className = "btn btn-secondary";
      flipBtn.id = `btn-flip-${q.id}`;
      flipBtn.style.fontSize = "11.5px";
      flipBtn.style.padding = "4px 10px";
      flipBtn.textContent = "Reveal Answer";

      // Rating container (Only visible after reveal)
      const ratingContainer = document.createElement("div");
      ratingContainer.className = "flashcard-rating-container";
      ratingContainer.id = `flashcard-rating-${q.id}`;
      ratingContainer.style.display = "none";

      const ratingLabel = document.createElement("div");
      ratingLabel.className = "flashcard-rating-label";
      ratingLabel.textContent = "Rate your active recall mastery:";

      const ratingActions = document.createElement("div");
      ratingActions.className = "flashcard-rating-actions";

      const needsPracticeBtn = document.createElement("button");
      needsPracticeBtn.className = "self-rate-btn";
      needsPracticeBtn.dataset.rate = "0";
      needsPracticeBtn.textContent = "Needs Practice";

      const masteredBtn = document.createElement("button");
      masteredBtn.className = "self-rate-btn";
      masteredBtn.dataset.rate = "1";
      masteredBtn.textContent = "Mastered";

      needsPracticeBtn.addEventListener("click", () => {
        needsPracticeBtn.classList.add("active", "selected");
        masteredBtn.classList.remove("active", "selected");
        state.userAnswers[q.id] = 0;
      });

      masteredBtn.addEventListener("click", () => {
        masteredBtn.classList.add("active", "selected");
        needsPracticeBtn.classList.remove("active", "selected");
        state.userAnswers[q.id] = 1;
      });

      ratingActions.appendChild(needsPracticeBtn);
      ratingActions.appendChild(masteredBtn);
      ratingContainer.appendChild(ratingLabel);
      ratingContainer.appendChild(ratingActions);

      flipBtn.addEventListener("click", () => {
        revealDiv.style.display = "block";
        flipBtn.style.display = "none";
        ratingContainer.style.display = "block";
        // Do NOT auto-grade as mastered; user must rate recall explicitly!
      });

      flashcardWrap.appendChild(recallHeader);
      flashcardWrap.appendChild(revealDiv);
      flashcardWrap.appendChild(flipBtn);
      flashcardWrap.appendChild(ratingContainer);
      optionsGroup.appendChild(flashcardWrap);
    }

    qBox.appendChild(optionsGroup);

    // Feedback container
    const feedbackBox = document.createElement("div");
    feedbackBox.id = `feedback-${q.id}`;
    qBox.appendChild(feedbackBox);

    container.appendChild(qBox);
  });

  // Submit Button
  const submitBtn = document.createElement("button");
  submitBtn.className = "btn btn-primary";
  submitBtn.id = "btnSubmitQuizAnswers";
  submitBtn.style.width = "100%";
  submitBtn.style.justifyContent = "center";
  submitBtn.style.padding = "10px 0";
  submitBtn.style.marginTop = "10px";
  submitBtn.textContent = "Submit & Verify Against Sources";
  submitBtn.addEventListener("click", handleEvaluateQuiz);
  container.appendChild(submitBtn);
}

async function handleEvaluateQuiz() {
  if (state.isSubmittingQuiz || !state.currentDeck) return;

  const submissions = Object.entries(state.userAnswers).map(([qid, ans]) => ({
    question_id: qid,
    answer: ans
  }));

  const submitBtn = document.getElementById("btnSubmitQuizAnswers");
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = "Evaluating Grounded Feedback...";
  }
  state.isSubmittingQuiz = true;

  try {
    const res = await fetch(`${API_BASE}/quizzes/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        deck_id: state.currentDeck.id,
        submissions
      })
    });

    if (!res.ok) {
      let errText = "Evaluation failed";
      try {
        const errJson = await res.json();
        errText = errJson.detail || errText;
      } catch {
        errText = await res.text();
      }
      throw new Error(errText);
    }

    const result = await res.json();
    renderQuizResults(result);
  } catch (err) {
    alert("Evaluation error: " + err.message);
  } finally {
    state.isSubmittingQuiz = false;
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Submit & Verify Against Sources";
    }
  }
}

function renderQuizResults(result) {
  // Render feedback in each question card
  result.feedback.forEach((fb) => {
    const fbContainer = document.getElementById(`feedback-${fb.question_id}`);
    const qBox = document.getElementById(`qbox-${fb.question_id}`);
    if (!fbContainer || !qBox) return;

    // Highlight options for mcq_single and multi_select
    const correctAnswers = new Set(
      Array.isArray(fb.correct_answer) ? fb.correct_answer : [fb.correct_answer]
    );
    const userAnswers = new Set(
      Array.isArray(fb.user_answer) ? fb.user_answer : [fb.user_answer]
    );

    qBox.querySelectorAll(".quiz-option").forEach((opt) => {
      const idx = parseInt(opt.dataset.optIdx, 10);
      if (correctAnswers.has(idx)) {
        opt.classList.add("correct-choice");
      } else if (userAnswers.has(idx) && !correctAnswers.has(idx)) {
        opt.classList.add("wrong-choice");
      }
    });

    fbContainer.replaceChildren();

    const explanationCard = document.createElement("div");
    explanationCard.className = "explanation-card";

    const correctnessTitle = document.createElement("div");
    correctnessTitle.style.fontWeight = "600";
    correctnessTitle.style.marginBottom = "4px";
    correctnessTitle.style.color = fb.is_correct ? "var(--accent-emerald)" : "var(--accent-rose)";
    correctnessTitle.textContent = fb.is_correct ? "✓ Correct" : "✗ Needs Review";

    const explanationText = document.createElement("div");
    explanationText.textContent = fb.explanation || "";

    explanationCard.appendChild(correctnessTitle);
    explanationCard.appendChild(explanationText);

    if (fb.citation) {
      const citationBox = document.createElement("div");
      citationBox.className = "citation-anchor-box";

      const strong = document.createElement("strong");
      strong.textContent = "Source Verification: ";

      const quoteSpan = document.createElement("span");
      quoteSpan.textContent = `"${fb.citation.quote}" — `;

      const citeSource = document.createElement("em");
      citeSource.textContent = `${fb.citation.source_title} (p. ${fb.citation.page_number})`;

      citationBox.appendChild(strong);
      citationBox.appendChild(quoteSpan);
      citationBox.appendChild(citeSource);
      explanationCard.appendChild(citationBox);
    }

    fbContainer.appendChild(explanationCard);
  });

  // Render score summary card in container
  const container = document.getElementById("quizArenaContainer");
  let scoreSummary = container.querySelector(".quiz-score-summary");
  if (!scoreSummary) {
    scoreSummary = document.createElement("div");
    scoreSummary.className = "quiz-score-summary";
    container.prepend(scoreSummary);
  }
  scoreSummary.replaceChildren();

  const scoreTitle = document.createElement("div");
  scoreTitle.className = "quiz-score-title";
  scoreTitle.textContent = "DIAGNOSTIC MASTERY SCORE";

  const scoreVal = document.createElement("div");
  scoreVal.className = "quiz-score-value";
  scoreVal.textContent = `${result.total_score} / ${result.total_questions} (${result.percentage}%)`;

  scoreSummary.appendChild(scoreTitle);
  scoreSummary.appendChild(scoreVal);
}

// ==============================================================================
// Study Guide Synthesis (Safe DOM & Citations)
// ==============================================================================
function renderEmptyStudyGuide() {
  const content = document.getElementById("studyGuideContent");
  if (!content) return;
  content.replaceChildren();

  const emptyDiv = document.createElement("div");
  emptyDiv.style.textAlign = "center";
  emptyDiv.style.color = "var(--ink-muted)";
  emptyDiv.style.padding = "40px 10px";
  emptyDiv.textContent = "Click \"Synthesize New Guide\" to generate executive summaries, glossaries, and review prompts.";
  content.appendChild(emptyDiv);
}

async function handleSynthesizeGuide() {
  if (state.isSynthesizingGuide) return;
  const content = document.getElementById("studyGuideContent");

  if (state.sources.length === 0) {
    content.replaceChildren();
    const errDiv = document.createElement("div");
    errDiv.style.color = "var(--accent-rose)";
    errDiv.style.textAlign = "center";
    errDiv.style.padding = "20px";
    errDiv.textContent = "Upload sources first to synthesize a study guide.";
    content.appendChild(errDiv);
    return;
  }

  // Guard: Scope [] empty selection must show error, not silently all
  if (state.selectedSourceIds.size === 0) {
    content.replaceChildren();
    const errDiv = document.createElement("div");
    errDiv.style.color = "var(--accent-rose)";
    errDiv.style.textAlign = "center";
    errDiv.style.padding = "20px";
    errDiv.textContent = "No sources selected. Please select at least one source in the Sources panel to synthesize a study guide.";
    content.appendChild(errDiv);
    return;
  }

  const btn = document.getElementById("btnSynthesizeGuide");
  btn.disabled = true;
  btn.textContent = "Synthesizing...";
  state.isSynthesizingGuide = true;

  content.replaceChildren();
  const loadingDiv = document.createElement("div");
  loadingDiv.style.textAlign = "center";
  loadingDiv.style.color = "var(--ink-secondary)";
  loadingDiv.style.padding = "30px 10px";
  loadingDiv.textContent = "Synthesizing academic executive summary and concept glossary...";
  content.appendChild(loadingDiv);

  const targetWsId = state.currentWorkspace ? state.currentWorkspace.id : null;

  try {
    const res = await fetch(`${API_BASE}/study/guide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace_id: targetWsId,
        source_ids: Array.from(state.selectedSourceIds)
      })
    });

    if (state.activeWorkspaceId !== targetWsId) return;

    if (!res.ok) {
      let errText = "Study guide synthesis failed";
      try {
        const errJson = await res.json();
        errText = errJson.detail || errText;
      } catch {
        errText = await res.text();
      }
      throw new Error(errText);
    }

    const guide = await res.json();
    if (state.activeWorkspaceId !== targetWsId) return;

    renderStudyGuide(guide);
    await loadSavedGuides(targetWsId);
  } catch (err) {
    if (state.activeWorkspaceId !== targetWsId) return;
    content.replaceChildren();
    const errDiv = document.createElement("div");
    errDiv.style.color = "var(--accent-rose)";
    errDiv.textContent = `Error: ${err.message}`;
    content.appendChild(errDiv);
  } finally {
    state.isSynthesizingGuide = false;
    btn.disabled = false;
    btn.textContent = "Synthesize New Guide";
  }
}

function renderStudyGuide(guide) {
  const content = document.getElementById("studyGuideContent");
  content.replaceChildren();

  const titleEl = document.createElement("h3");
  titleEl.style.fontSize = "16px";
  titleEl.style.fontWeight = "600";
  titleEl.style.marginBottom = "10px";
  titleEl.style.color = "var(--ink-primary)";
  titleEl.textContent = guide.title;

  const summaryEl = document.createElement("div");
  summaryEl.style.marginBottom = "16px";
  summaryEl.style.fontFamily = "var(--font-serif)";
  summaryEl.style.fontSize = "14.5px";
  summaryEl.style.lineHeight = "1.6";
  summaryEl.style.color = "var(--ink-secondary)";
  summaryEl.textContent = guide.executive_summary;

  content.appendChild(titleEl);
  content.appendChild(summaryEl);

  // Key Concepts
  const conceptsHeader = document.createElement("h4");
  conceptsHeader.style.fontSize = "13.5px";
  conceptsHeader.style.fontWeight = "600";
  conceptsHeader.style.margin = "16px 0 8px 0";
  conceptsHeader.style.color = "var(--ink-primary)";
  conceptsHeader.textContent = "Key Concepts & Terminology";
  content.appendChild(conceptsHeader);

  guide.key_concepts.forEach((kc) => {
    const card = document.createElement("div");
    card.style.marginBottom = "12px";
    card.style.padding = "10px";
    card.style.background = "var(--canvas-bg)";
    card.style.borderRadius = "6px";

    const strong = document.createElement("strong");
    strong.style.color = "var(--accent-indigo)";
    strong.textContent = `${kc.concept}: `;

    const def = document.createTextNode(kc.definition);
    card.appendChild(strong);
    card.appendChild(def);

    if (kc.source_reference) {
      const ref = document.createElement("div");
      ref.style.fontSize = "11.5px";
      ref.style.color = "var(--ink-muted)";
      ref.style.marginTop = "4px";
      ref.textContent = `Ref: ${kc.source_reference}`;
      card.appendChild(ref);
    }

    content.appendChild(card);
  });

  // Core Takeaways
  const takeawaysHeader = document.createElement("h4");
  takeawaysHeader.style.fontSize = "13.5px";
  takeawaysHeader.style.fontWeight = "600";
  takeawaysHeader.style.margin = "16px 0 8px 0";
  takeawaysHeader.style.color = "var(--ink-primary)";
  takeawaysHeader.textContent = "Core Takeaways";
  content.appendChild(takeawaysHeader);

  const takeawaysList = document.createElement("ul");
  takeawaysList.style.paddingLeft = "20px";
  takeawaysList.style.marginBottom = "16px";
  guide.core_takeaways.forEach((t) => {
    const li = document.createElement("li");
    li.style.marginBottom = "6px";
    li.textContent = t;
    takeawaysList.appendChild(li);
  });
  content.appendChild(takeawaysList);

  // Practice Prompts
  const promptsHeader = document.createElement("h4");
  promptsHeader.style.fontSize = "13.5px";
  promptsHeader.style.fontWeight = "600";
  promptsHeader.style.margin = "16px 0 8px 0";
  promptsHeader.style.color = "var(--ink-primary)";
  promptsHeader.textContent = "Practice & Review Prompts";
  content.appendChild(promptsHeader);

  const promptsList = document.createElement("ul");
  promptsList.style.paddingLeft = "20px";
  guide.practice_prompts.forEach((p) => {
    const li = document.createElement("li");
    li.style.marginBottom = "6px";
    li.style.fontStyle = "italic";
    li.textContent = `"${p}"`;
    promptsList.appendChild(li);
  });
  content.appendChild(promptsList);
}

// ==============================================================================
// Concept Mastery Analytics
// ==============================================================================
function renderEmptyMasteryAnalytics() {
  const container = document.getElementById("masteryAnalyticsContainer");
  if (!container) return;
  container.replaceChildren();

  const emptyDiv = document.createElement("div");
  emptyDiv.style.textAlign = "center";
  emptyDiv.style.color = "var(--ink-muted)";
  emptyDiv.style.padding = "40px 10px";
  emptyDiv.style.fontSize = "13px";
  emptyDiv.innerHTML = "Take quizzes to populate your concept mastery radar.";
  container.appendChild(emptyDiv);
}

async function loadMasteryAnalytics() {
  if (!state.currentWorkspace) return;
  const targetWsId = state.currentWorkspace.id;
  const container = document.getElementById("masteryAnalyticsContainer");

  container.replaceChildren();
  const loadingDiv = document.createElement("div");
  loadingDiv.style.textAlign = "center";
  loadingDiv.style.color = "var(--ink-muted)";
  loadingDiv.style.padding = "20px";
  loadingDiv.textContent = "Loading mastery stats...";
  container.appendChild(loadingDiv);

  try {
    const res = await fetch(`${API_BASE}/quizzes/mastery/${targetWsId}`);
    if (state.activeWorkspaceId !== targetWsId) return;

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    if (state.activeWorkspaceId !== targetWsId) return;

    container.replaceChildren();

    if (!data.concepts || data.concepts.length === 0) {
      renderEmptyMasteryAnalytics();
      return;
    }

    const overallCard = document.createElement("div");
    overallCard.style.marginBottom = "16px";
    overallCard.style.padding = "14px";
    overallCard.style.background = "var(--canvas-bg)";
    overallCard.style.borderRadius = "8px";
    overallCard.style.textAlign = "center";

    const overallLabel = document.createElement("div");
    overallLabel.style.fontSize = "12px";
    overallLabel.style.color = "var(--ink-secondary)";
    overallLabel.style.marginBottom = "4px";
    overallLabel.textContent = "OVERALL NOTEBOOK MASTERY";

    const overallScore = document.createElement("div");
    overallScore.style.fontSize = "28px";
    overallScore.style.fontWeight = "700";
    overallScore.style.color = "var(--ink-primary)";
    overallScore.textContent = `${data.overall_mastery}%`;

    overallCard.appendChild(overallLabel);
    overallCard.appendChild(overallScore);
    container.appendChild(overallCard);

    data.concepts.forEach((c) => {
      const pct = c.mastery_level;
      const barColor =
        pct >= 80 ? "var(--accent-emerald)" : pct >= 50 ? "var(--accent-indigo)" : "var(--accent-rose)";

      const card = document.createElement("div");
      card.style.background = "var(--surface-white)";
      card.style.border = "1px solid var(--border-subtle)";
      card.style.borderRadius = "8px";
      card.style.padding = "12px";
      card.style.marginBottom = "10px";

      const topRow = document.createElement("div");
      topRow.style.display = "flex";
      topRow.style.justifyContent = "space-between";
      topRow.style.alignItems = "center";
      topRow.style.marginBottom = "6px";

      const tagSpan = document.createElement("span");
      tagSpan.style.fontSize = "13px";
      tagSpan.style.fontWeight = "600";
      tagSpan.style.color = "var(--ink-primary)";
      tagSpan.textContent = c.concept_tag;

      const pctSpan = document.createElement("span");
      pctSpan.style.fontSize = "12px";
      pctSpan.style.fontWeight = "600";
      pctSpan.style.color = barColor;
      pctSpan.textContent = `${pct}%`;

      topRow.appendChild(tagSpan);
      topRow.appendChild(pctSpan);

      const barTrack = document.createElement("div");
      barTrack.style.height = "6px";
      barTrack.style.background = "var(--surface-alt)";
      barTrack.style.borderRadius = "3px";
      barTrack.style.overflow = "hidden";
      barTrack.style.marginBottom = "6px";

      const barFill = document.createElement("div");
      barFill.style.width = `${pct}%`;
      barFill.style.height = "100%";
      barFill.style.background = barColor;
      barTrack.appendChild(barFill);

      const attemptsMeta = document.createElement("div");
      attemptsMeta.style.fontSize = "11px";
      attemptsMeta.style.color = "var(--ink-muted)";
      attemptsMeta.textContent = `${c.correct_attempts} / ${c.total_attempts} questions correct`;

      card.appendChild(topRow);
      card.appendChild(barTrack);
      card.appendChild(attemptsMeta);
      container.appendChild(card);
    });
  } catch (err) {
    if (state.activeWorkspaceId !== targetWsId) return;
    container.replaceChildren();
    const errDiv = document.createElement("div");
    errDiv.style.color = "var(--accent-rose)";
    errDiv.textContent = `Failed to load mastery data: ${err.message}`;
    container.appendChild(errDiv);
  }
}

// ==============================================================================
// Export Study Pack
// ==============================================================================
function handleExportStudyPack() {
  if (!state.currentWorkspace) return;
  const exportPayload = {
    workspace: state.currentWorkspace,
    sources: state.sources,
    quizDeck: state.currentDeck,
    exported_at: new Date().toISOString()
  };

  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportPayload, null, 2));
  const dlAnchor = document.createElement("a");
  dlAnchor.setAttribute("href", dataStr);
  dlAnchor.setAttribute("download", `${state.currentWorkspace.title.replace(/\s+/g, "_")}_study_pack.json`);
  dlAnchor.click();
}
