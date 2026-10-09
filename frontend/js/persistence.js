// Durable chat and guide UI; all user-authored content is rendered as text.
const activeSessionKey = ws => `scholar.activeSession.${ws}`;
async function persistenceJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error((await response.text()) || `Request failed (${response.status})`);
  return response.status === 204 ? null : response.json();
}
function workspaceUrl(path, ws = state.activeWorkspaceId) { return `${API_BASE}${path}?workspace_id=${encodeURIComponent(ws)}`; }
function renderSessionOptions() {
  const select = document.getElementById('chatSessionSelect'); if (!select) return;
  select.replaceChildren();
  state.chatSessions.forEach(s => { const o=document.createElement('option'); o.value=s.id; o.textContent=s.title || 'Untitled chat'; select.append(o); });
  select.value = state.activeSessionId || '';
}
function selectedSourcesKey(ws) { return `scholar.selectedSources.${ws}`; }
function persistSelectedSources() {
  const ws=state.activeWorkspaceId; if (!ws) return;
  localStorage.setItem(selectedSourcesKey(ws), JSON.stringify([...state.selectedSourceIds]));
}
function restoreSelectedSources(ws, sources) {
  let saved=[];
  try { saved=JSON.parse(localStorage.getItem(selectedSourcesKey(ws)) || '[]'); } catch {}
  const available=new Set(sources.map(s=>s.id));
  state.selectedSourceIds=new Set(saved.filter(id=>available.has(id)));
  if (!localStorage.getItem(selectedSourcesKey(ws))) state.selectedSourceIds=new Set(available);
  persistSelectedSources();
}
async function loadChatSessions(ws) {
  try {
    const sessions = await persistenceJson(workspaceUrl('/chat/sessions', ws));
    if (state.activeWorkspaceId !== ws) return;
    state.chatSessions=sessions; renderSessionOptions();
    const remembered=localStorage.getItem(activeSessionKey(ws));
    const selected=sessions.find(s=>s.id===remembered) || sessions[0];
    if (selected) { state.activeSessionId=selected.id; await loadChatSession(selected.id); }
    else { state.activeSessionId=null; localStorage.removeItem(activeSessionKey(ws)); resetChatStream(state.currentWorkspace?.title); }
  } catch(e) { if (state.activeWorkspaceId===ws) showPersistenceError('Chat history',e); }
}
async function loadChatSession(id) {
  const ws=state.activeWorkspaceId; if (!id || !ws) return;
  const requestToken=Symbol(); state.chatLoadToken=requestToken;
  try {
    const data=await persistenceJson(workspaceUrl(`/chat/sessions/${encodeURIComponent(id)}`,ws));
    if (state.activeWorkspaceId!==ws || state.chatLoadToken!==requestToken || state.activeSessionId && state.activeSessionId!==id) return;
    state.activeSessionId=data.session.id; localStorage.setItem(activeSessionKey(ws), data.session.id); renderSessionOptions();
    const stream=document.getElementById('chatStream'); stream.replaceChildren();
    (data.messages||[]).forEach(m=>{
      if (m.role==='user') { const c=document.createElement('div'); c.className='message-card message-user'; c.textContent=m.content; stream.append(c); }
      else { const c=document.createElement('div'); c.className='message-card message-assistant'; const b=document.createElement('div'); b.className='assistant-body'; c.append(b); stream.append(c); renderAssistantResponse(c,m.content,m.citations||[]); }
    });
    if (!data.messages?.length) resetChatStream(state.currentWorkspace?.title);
    stream.scrollTop=stream.scrollHeight;
  } catch(e) { if(state.activeWorkspaceId===ws && state.chatLoadToken===requestToken) showPersistenceError('Conversation',e); }
}
async function createChatSession() {
  const ws=state.activeWorkspaceId; if(!ws)return;
  try {
    const session=await persistenceJson(`${API_BASE}/chat/sessions`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({workspace_id:ws,title:'New chat'})});
    if(state.activeWorkspaceId!==ws)return;
    state.chatSessions.unshift(session); state.activeSessionId=session.id; localStorage.setItem(activeSessionKey(ws),session.id); renderSessionOptions(); resetChatStream(state.currentWorkspace?.title);
  } catch(e){showPersistenceError('New chat',e);}
}
async function renameChatSession() {
  const s=state.chatSessions.find(x=>x.id===state.activeSessionId); if(!s)return;
  const title=prompt('Conversation name',s.title); if(title===null || !title.trim())return;
  try {const updated=await persistenceJson(workspaceUrl(`/chat/sessions/${encodeURIComponent(s.id)}`),{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:title.trim()})}); state.chatSessions=state.chatSessions.map(x=>x.id===s.id?updated:x);renderSessionOptions();} catch(e){showPersistenceError('Rename',e);}
}
async function deleteChatSession(){const s=state.chatSessions.find(x=>x.id===state.activeSessionId);if(!s||!confirm(`Delete “${s.title}” and its messages?`))return;const ws=state.activeWorkspaceId;try{await persistenceJson(workspaceUrl(`/chat/sessions/${encodeURIComponent(s.id)}`,ws),{method:'DELETE'});state.chatSessions=state.chatSessions.filter(x=>x.id!==s.id);state.activeSessionId=null;localStorage.removeItem(activeSessionKey(ws));renderSessionOptions();if(state.chatSessions.length)await loadChatSession(state.chatSessions[0].id);else resetChatStream(state.currentWorkspace?.title);}catch(e){showPersistenceError('Delete conversation',e);}}
function renderGuideOptions(){const sel=document.getElementById('savedGuideSelect');sel.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent='Saved study guides';sel.append(empty);state.savedGuides.forEach(g=>{const o=document.createElement('option');o.value=g.id;o.textContent=g.title;sel.append(o);});}
async function loadSavedGuides(ws){try{const guides=await persistenceJson(workspaceUrl('/study/guides',ws));if(state.activeWorkspaceId!==ws)return;state.savedGuides=guides;renderGuideOptions();const remembered=localStorage.getItem(`scholar.activeGuide.${ws}`);const selected=guides.find(g=>g.id===remembered);if(selected){document.getElementById('savedGuideSelect').value=selected.id;await loadSavedGuide(selected.id);}else if(remembered)localStorage.removeItem(`scholar.activeGuide.${ws}`);}catch(e){if(state.activeWorkspaceId===ws)showPersistenceError('Saved guides',e);}}
async function loadSavedGuide(id){if(!id)return;const ws=state.activeWorkspaceId;const token=Symbol();state.guideLoadToken=token;try{const g=await persistenceJson(workspaceUrl(`/study/guides/${encodeURIComponent(id)}`,ws));if(state.activeWorkspaceId===ws&&state.guideLoadToken===token){localStorage.setItem(`scholar.activeGuide.${ws}`,id);renderStudyGuide(g);}}catch(e){if(state.activeWorkspaceId===ws&&state.guideLoadToken===token)showPersistenceError('Study guide',e);}}
async function deleteSavedGuide(){const id=document.getElementById('savedGuideSelect').value;if(!id||!confirm('Delete this saved study guide?'))return;const ws=state.activeWorkspaceId;try{await persistenceJson(workspaceUrl(`/study/guides/${encodeURIComponent(id)}`,ws),{method:'DELETE'});state.savedGuides=state.savedGuides.filter(g=>g.id!==id);localStorage.removeItem(`scholar.activeGuide.${ws}`);renderGuideOptions();renderEmptyStudyGuide();}catch(e){showPersistenceError('Delete guide',e);}}
function showPersistenceError(action,error){const stream=document.getElementById('chatStream');if(!stream)return;const note=document.createElement('div');note.className='message-card message-assistant';note.style.color='var(--accent-rose)';note.textContent=`${action} failed: ${error.message}`;stream.append(note);}
