const $ = (id) => document.getElementById(id);
const labels = {groq:'Fresh answer', exact_cache:'Exact cache hit', semantic_cache:'Semantic cache hit'};
let history = [], busy = false;

function node(tag, className, text) {
  const el = document.createElement(tag); el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check your message and try again.');
  return data;
}
function showError(message) { $('error').textContent = message; $('error').hidden = !message; }
function setBusy(value) {
  busy = value;
  for (const id of ['send','new-chat','clear-cache']) $(id).disabled = value;
  $('messages').setAttribute('aria-busy', String(value));
}
function addMessage(role, text, data) {
  $('welcome').hidden = true;
  const article = node('article', `message ${role}`);
  const heading = node('div', 'message-heading');
  if (role === 'assistant') heading.append(node('span','avatar','✦'));
  heading.append(node('span','',role === 'user' ? 'You' : 'EchoCache'));
  article.append(heading,node('div','bubble',text));
  if (data) {
    const meta = node('div','message-meta');
    meta.append(node('span', `source-badge ${data.source === 'groq' ? '' : 'hit'}`, labels[data.source]));
    meta.append(node('span','',`${data.latency_ms} ms · ${data.tokens_used} tokens`));
    for (const source of data.sources) {
      const button = node('button','source-link',source.replaceAll('-',' '));
      button.addEventListener('click',()=>openPolicies(source)); meta.append(button);
    }
    article.append(meta);
    const details = node('details','diagnostics');
    details.append(node('summary','', 'How this answer was found'),node('p','',data.cache_note));
    if (data.embedding_compared) {
      const score = data.similarity ?? data.nearest_similarity;
      details.append(node('p','diagnostic-values',`pgvector · ${data.candidates_checked} answers compared · ${(data.threshold*100).toFixed(0)}% threshold` + (score === null ? '' : ` · ${(score*100).toFixed(2)}% ${data.similarity === null ? 'closest similarity' : 'match'}`)));
      if (data.matched_prompt) details.append(node('p','',`Saved question: ${data.matched_prompt}`));
      if (data.matched_query && data.matched_query !== data.matched_prompt) details.append(node('p','',`Matched wording: ${data.matched_query}`));
    }
    article.append(details);
  }
  $('messages').append(article);
  return article;
}
async function updateStats() {
  try {
    const data = await api('/api/stats');
    $('stat-hits').textContent = data.cache_hits; $('stat-calls').textContent = data.llm_calls; $('stat-entries').textContent = data.entries;
    $('database-status').replaceChildren(node('i',''),document.createTextNode('PostgreSQL + pgvector'));
    $('database-status').classList.remove('unavailable');
  } catch {
    $('database-status').textContent = 'Database unavailable'; $('database-status').classList.add('unavailable');
  }
}
async function sendMessage(value) {
  const prompt = value.trim(); if (busy || !prompt) return;
  setBusy(true); showError('');
  const user = addMessage('user',prompt);
  const loading = addMessage('assistant','Checking the cache and finding your answer…'); loading.classList.add('loading');
  $('message').value=''; $('message').style.height='auto';
  loading.scrollIntoView({block:'center',behavior:'smooth'});
  try {
    const result = await api('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:prompt,history:history.slice(-12),use_cache:$('use-cache').checked})});
    loading.remove(); const reply = addMessage('assistant',result.answer,result);
    history.push({role:'user',content:prompt},{role:'assistant',content:result.answer});
    reply.scrollIntoView({block:'center',behavior:'smooth'});
  } catch(error) {
    loading.remove(); user.remove(); $('message').value=prompt;
    if (!history.length) $('welcome').hidden=false;
    showError(error.message || 'Could not connect to the server.');
  } finally { setBusy(false); updateStats(); $('message').focus({preventScroll:true}); }
}
function newChat() {
  if(busy) return;
  history=[]; $('messages').replaceChildren(); $('welcome').hidden=false;
  $('message').value=''; $('message').style.height='auto'; showError('');
  window.scrollTo({top:0,behavior:'smooth'}); $('message').focus({preventScroll:true});
}
async function openPolicies(source) {
  try {
    const data=await api('/api/policies'); $('policy-content').replaceChildren();
    for(const [id,content] of Object.entries(data.sections)) {
      const section=node('section',''); section.id=`policy-${id}`;
      section.append(node('h3','',id.replaceAll('-',' ')),node('p','',content)); $('policy-content').append(section);
    }
    $('policy-library').hidden=false; $('open-policies').setAttribute('aria-expanded','true');
    (source ? $(`policy-${source}`) : $('policy-library'))?.scrollIntoView({block:'start',behavior:'smooth'});
  } catch(error) { showError(error.message); }
}
$('chat-form').addEventListener('submit',event=>{event.preventDefault();sendMessage($('message').value);});
$('message').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();sendMessage($('message').value);}});
$('message').addEventListener('input',()=>{$('message').style.height='auto';$('message').style.height=`${Math.min($('message').scrollHeight,150)}px`;});
$('new-chat').addEventListener('click',newChat);
$('open-policies').addEventListener('click',()=>openPolicies());
$('close-policies').addEventListener('click',()=>{$('policy-library').hidden=true;$('open-policies').setAttribute('aria-expanded','false');$('open-policies').focus();});
$('clear-cache').addEventListener('click',async()=>{
  $('clear-cache').disabled=true;
  try{await api('/api/cache',{method:'DELETE'});await updateStats();}
  catch(error){showError(error.message);}
  finally{$('clear-cache').disabled=false;}
});
async function initialize() {
  try {
    const status=await api('/health');
    $('connection').replaceChildren(node('i',''),document.createTextNode(status.configured?'API configured':'API not configured'));
    $('connection').classList.toggle('ready',status.configured);$('connection').classList.toggle('not-configured',!status.configured);
    $('setup-notice').hidden=status.configured;
  }catch{$('connection').textContent='Server unavailable';$('connection').classList.add('not-configured');showError('Start PostgreSQL and the application, then reload.');}
  updateStats();
}
initialize();
