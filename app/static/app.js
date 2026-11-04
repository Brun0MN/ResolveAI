'use strict';
const $=id=>document.getElementById(id);let scenarios=[],selected=null;
const statuses={novo:'Novo',analisando:'Analisando',executando:'Executando',aguardando_aprovacao:'Aguardando aprovação',escalado:'Encaminhado',resolvido:'Resolvido'};
const names={triagem:'Triagem',entrada:'Entrada',investigação:'Investigação',diagnóstico:'Diagnóstico',resolução:'Resolução',verificação:'Verificação',política:'Segurança',sistema:'Sistema'};
async function api(path,opts={}){const r=await fetch(path,{headers:{'Content-Type':'application/json'},...opts});let d=await r.json().catch(()=>null);if(!r.ok)throw new Error(d?.detail||`Erro HTTP ${r.status}`);return d}
function el(tag,klass,text){const node=document.createElement(tag);if(klass)node.className=klass;if(text!==undefined)node.textContent=text;return node}
function toast(msg){$('toast').textContent=msg;$('toast').classList.add('show');setTimeout(()=>$('toast').classList.remove('show'),4300)}
function statusBadge(status){return el('span','status '+status,statuses[status]||status)}
function dateStr(s){if(!s)return '—';const d=new Date(s);return isNaN(d)?s:d.toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'})}
function appendCell(tr,content){const td=el('td');if(typeof content==='string')td.textContent=content;else td.append(content);tr.append(td);return td}
async function refresh(){try{const [incidents,metrics,conf]=await Promise.all([api('/api/incidents'),api('/api/metrics'),api('/api/config')]);$('mTotal').textContent=metrics.total;$('mResolved').textContent=metrics.resolved;$('mPending').textContent=metrics.pending_approval;$('mEscalated').textContent=metrics.escalated;$('mRate').textContent=metrics.rate_pct+'%';$('itemCount').textContent=incidents.length;$('aiBadge').textContent=conf.mode==='gemini'?'✦ IA ativa • '+conf.model:'◇ Modo offline • sem IA';$('labMode').textContent=conf.real_scenarios?.length?'Processos reais + emulações':'Somente emulação';const tbody=$('incidentRows');tbody.replaceChildren();if(!incidents.length){const row=el('tr');const td=el('td','loading','Nenhum incidente ainda. Clique em “Criar incidente” para começar.');td.colSpan=6;row.append(td);tbody.append(row)}else{for(const item of incidents){const tr=el('tr');tr.dataset.id=item.id;const first=el('div');first.append(el('strong','',item.title),el('span','secondary-text','#'+item.id.slice(0,8)+' · '+item.scenario));appendCell(tr,first);appendCell(tr,item.severity);appendCell(tr,statusBadge(item.status));appendCell(tr,item.execution_mode==='ai'?'Gemini':'Regras / não executado');appendCell(tr,dateStr(item.created_at));appendCell(tr,'Ver detalhes →');tr.addEventListener('click',()=>showDetail(item.id));tbody.append(tr)}}}catch(e){toast('Falha ao atualizar: '+e.message)}}
function openCreate(){const select=$('scenario');if(select.options.length===0)for(const s of scenarios){const opt=el('option','',s.title);opt.value=s.id;opt.textContent=s.title+(s.real_when_docker?' · processo real no Docker':' · emulado');select.append(opt)}fillScenario();$('createDialog').showModal()}
function fillScenario(){const s=scenarios.find(x=>x.id===$('scenario').value);if(s){$('titleInput').value=s.title;$('descriptionInput').value=s.description}}
async function create(e){e.preventDefault();const button=$('createSubmit');button.disabled=true;button.textContent='Criando...';try{const created=await api('/api/incidents',{method:'POST',body:JSON.stringify({scenario:$('scenario').value,title:$('titleInput').value,description:$('descriptionInput').value})});$('createDialog').close();await refresh();await showDetail(created.id);toast('Incidente preparado. Inicie a investigação.')}catch(e){toast(e.message)}finally{button.disabled=false;button.textContent='Criar incidente'}}
async function action(id,type){const map={run:'Investigando...',approve:'Executando ação aprovada...',reject:'Encaminhando...'};const holder=$('detailButtons');holder.querySelectorAll('button').forEach(x=>x.disabled=true);toast(map[type]||'Executando...');try{await api('/api/incidents/'+id+'/'+type,{method:'POST'});await refresh();await showDetail(id);toast(type==='run'?'Análise concluída. Veja as evidências.':'Ação processada e registrada.')}catch(e){toast('Erro: '+e.message);await showDetail(id)}}
function detailButton(text,style,fn){const b=el('button','button '+style,text);b.type='button';b.addEventListener('click',fn);return b}
async function showDetail(id){try{const i=await api('/api/incidents/'+id);selected=id;$('detailId').textContent='INCIDENTE #'+id.slice(0,8).toUpperCase();$('detailTitle').textContent=i.title;$('detailDescription').textContent=i.description;$('detailStatus').className='status '+i.status;$('detailStatus').textContent=statuses[i.status]||i.status;$('detailMode').textContent=i.model||'Não analisado';$('detailDiagnosis').textContent=i.diagnosis||'Nenhum diagnóstico realizado até agora.';$('detailConfidence').textContent=i.confidence==null?'':`Confiança declarada pelo modelo: ${Math.round(i.confidence*100)}% (estimativa, não garantia)`;$('detailAction').textContent=i.recommended_action?'Ação indicada: '+i.recommended_action:'';const buttons=$('detailButtons');buttons.replaceChildren();if(i.status==='novo')buttons.append(detailButton('◈ Investigar e tentar resolver','primary',()=>action(id,'run')));if(i.status==='aguardando_aprovacao'){buttons.append(detailButton('Recusar e encaminhar','secondary',()=>action(id,'reject')));buttons.append(detailButton('✓ Autorizar ação de laboratório','primary',()=>action(id,'approve')))}const ev=$('events');ev.replaceChildren();$('eventCount').textContent=i.events.length+' registros';for(const x of [...i.events].reverse()){const block=el('div','event');block.append(el('span','event-dot'));const body=el('div');body.append(el('b','',names[x.stage]||x.stage),el('small','',x.kind+' · '+dateStr(x.created_at)));const detail=el('pre','',JSON.stringify(x.detail,null,2));body.append(detail);block.append(body);ev.append(block)}if(!$('detailDialog').open)$('detailDialog').showModal()}catch(e){toast(e.message)}}
async function refreshEvaluation(){
  try{
    const r=await api('/api/evaluation/latest');
    const tbody=$('evalRows');tbody.replaceChildren();
    if(!r.available){$('evalMode').textContent='Sem avaliação';$('evalHint').textContent=r.message||'Nenhum relatório disponível';for(const k of ['evalAccuracy','evalBaseline','evalVerified','evalCount'])$(k).textContent='—';$('evalMeta').textContent='';return;}
    const s=r.summary;
    $('evalMode').textContent=(s.mode==='gemini'?'Gemini':s.mode==='offline'?'Regras offline':s.mode||'?')+' • '+dateStr(r.timestamp_utc);
    $('evalHint').textContent='Comparação sobre incidentes sintéticos: decisão do modelo versus operação esperada. Regras avaliadas sobre as mesmas evidências. Não é validação em produção.';
    const percent=x=>x==null?'—':x+'%';
    $('evalAccuracy').textContent=percent(s.decision_accuracy_pct);
    $('evalBaseline').textContent=percent(s.baseline_accuracy_pct);
    $('evalVerified').textContent=percent(s.verified_resolution_pct);
    $('evalCount').textContent=String(s.cases);
    $('evalMeta').textContent=s.real_process_cases+' casos com processos isolados · '+s.emulated_cases+' emulações · '+s.pending_approval+' aguardando aprovação · '+s.api_errors+' erros de IA · '+(s.mean_duration_s??'—')+' s de duração média · '+(s.total_tokens||0)+' tokens de API registrados. Casos sem diagnóstico contam como erro.';
    for(const x of r.details){
      const tr=el('tr');
      appendCell(tr,x.scenario+' · '+x.variation);
      appendCell(tr,x.expected_operation);
      appendCell(tr,x.selected_operation||'Sem diagnóstico');
      const decision=x.action_correct?'Decisão correta':'Decisão incorreta';
      const explanation=x.verified?' · recuperado e verificado':x.final_status==='aguardando_aprovacao'?' · aprovação pendente':x.final_status==='escalado'?' · encaminhado':' · não verificado';
      appendCell(tr,el('span',x.action_correct?'eval-ok':'eval-bad',decision+explanation));tbody.append(tr);
    }
  }catch(e){$('evalHint').textContent='Erro ao carregar benchmark: '+e.message;}
}
async function refreshChallenge(){
  try{
    const r=await api('/api/challenge/latest');
    const tbody=$('challengeRows');tbody.replaceChildren();$('challengeGroups').replaceChildren();
    if(!r.available){
      $('challengeMode').textContent='Sem resultados';
      $('challengeHint').textContent=r.message||'Nenhum desafio executado.';
      for(const k of ['challengeAccuracy','challengeBaseline','challengePolicy','challengeEscalation','challengeCount'])$(k).textContent='—';
      $('challengeMeta').textContent='';return;
    }
    const s=r.summary,fmt=x=>x==null?'—':x+'%';
    $('challengeMode').textContent=(s.mode==='ai'?'Gemini':'Regras offline')+' • '+dateStr(r.timestamp_utc);
    $('challengeHint').textContent='Diagnóstico com dados sintéticos reescritos, sinais conflitantes e logs maliciosos. O gabarito não é enviado ao modelo. Nenhum serviço ou chamado é modificado.';
    $('challengeAccuracy').textContent=fmt(s.model_accuracy_pct);
    $('challengeBaseline').textContent=fmt(s.baseline_accuracy_pct);
    $('challengePolicy').textContent=fmt(s.policy_accuracy_pct);
    $('challengeEscalation').textContent=fmt(s.correct_escalation_pct);
    $('challengeCount').textContent=String(s.cases);
    $('challengeMeta').textContent=s.injection_cases+' testes com injeção de prompt · '+fmt(s.injection_correct_pct)+' de decisões corretas nesses testes · '+(s.unsupported_proposals??'—')+' propostas inadequadas na referência · '+(s.approval_flag_warnings??'—')+' avisos de aprovação ausente na resposta · '+(s.policy_blocked??'—')+' propostas barradas pela política · '+(s.policy_false_blocks??'—')+' bloqueios de ações esperadas · '+s.api_errors+' falhas de API · '+s.total_tokens+' tokens registrados. Nenhuma ação executada.';
    const groups=$('challengeGroups');
    for(const [name,g] of Object.entries(s.groups||{})){
      const box=el('div','challenge-group');
      box.append(el('b','',name),el('span','',`${fmt(g.model_accuracy_pct)} · regras ${fmt(g.baseline_accuracy_pct)} · ${g.count} casos`));
      groups.append(box);
    }
    for(const x of r.details){
      const tr=el('tr');
      appendCell(tr,x.case_id);appendCell(tr,x.group);appendCell(tr,x.expected_action);
      appendCell(tr,x.selected_action||'Sem diagnóstico');
      appendCell(tr,x.policy_action||'Sem diagnóstico');
      const label=x.error?'Falha de API: '+x.error:x.correct?'Decisão correta':x.policy_correct?'Bloqueada com segurança':x.unsafe_suggestion?'Possível risco':'Decisão incorreta';
      appendCell(tr,el('span',(x.correct||x.policy_correct)?'eval-ok':'eval-bad',label));tbody.append(tr);
    }
  }catch(e){$('challengeHint').textContent='Falha ao carregar avaliação de robustez: '+e.message;}
}

async function refreshHoldout(){
  try{
    const r=await api('/api/holdout/latest');
    const tbody=$('holdoutRows');tbody.replaceChildren();$('holdoutGroups').replaceChildren();
    const keys=['holdoutModelAccuracy','holdoutPolicyAccuracy','holdoutEscalation','holdoutUnsafe','holdoutCount'];
    if(!r.available){$('holdoutMode').textContent='Sem avaliação';$('holdoutHint').textContent=r.message||'Nenhum relatório disponível';for(const k of keys)$(k).textContent='—';$('holdoutMeta').textContent='';return;}
    const s=r.summary,fmt=x=>x==null?'—':x+'%';
    $('holdoutMode').textContent=(s.mode==='ai'?'Gemini':'Regras offline')+' • '+dateStr(r.timestamp_utc);
    const policyStatus=r.policy_status||'unknown';
    const statusMessage=policyStatus==='match'?'O relatório corresponde à política de segurança atual.':policyStatus==='changed'?'A política de segurança mudou desde este relatório; repita a avaliação para compará-la.':'Não foi possível verificar a versão da política deste relatório.';
    $('holdoutHint').textContent='Bateria de regressão, com casos já revisados no desenvolvimento. '+statusMessage+' Nenhuma correção é executada.';
    $('holdoutModelAccuracy').textContent=fmt(s.model_accuracy_pct);
    $('holdoutPolicyAccuracy').textContent=fmt(s.policy_accuracy_pct);
    $('holdoutEscalation').textContent=fmt(s.policy_escalation_recall_pct);
    $('holdoutUnsafe').textContent=String(s.unsafe_actions_not_blocked);
    $('holdoutCount').textContent=String(s.cases);
    $('holdoutMeta').textContent='Regras: '+fmt(s.baseline_accuracy_pct)+' · '+s.unsafe_proposals+' propostas indevidas · '+s.unnecessary_blocks+' bloqueios desnecessários · '+s.api_errors+' erros API ('+Object.entries(s.api_error_types||{}).map(([k,v])=>k+': '+v).join(', ')+') · '+s.answered_cases+' respostas válidas; acerto entre respostas '+fmt(s.model_accuracy_when_answered_pct)+' · '+s.total_tokens+' tokens · política sha256 '+r.policy_sha256_prefix+'. Nenhuma ação executada.';
    for(const [name,g] of Object.entries(s.groups||{})){
      const box=el('div','challenge-group');box.append(el('b','',name),el('span','',fmt(g.model_accuracy_pct)+' modelo · '+fmt(g.policy_accuracy_pct)+' política · '+g.count+' casos'));$('holdoutGroups').append(box);
    }
    for(const x of r.details){
      const tr=el('tr');appendCell(tr,x.case_id);appendCell(tr,x.group);appendCell(tr,x.expected_action);
      appendCell(tr,x.selected_action||'Sem diagnóstico');appendCell(tr,x.policy_action||'Sem diagnóstico');
      const label=x.error?'Erro de API: '+x.error:x.model_correct?'Modelo correto':x.policy_correct?'Corrigido pela política':x.unnecessary_block?'Bloqueado sem necessidade':x.unsafe_action_not_blocked?'Risco não bloqueado':'Decisão incorreta';
      appendCell(tr,el('span',x.policy_correct?'eval-ok':'eval-bad',label));tbody.append(tr);
    }
  }catch(e){$('holdoutHint').textContent='Falha ao carregar regressão: '+e.message;}
}

async function refreshReserved(){
  try{
    const r=await api('/api/reserved/latest');
    const tbody=$('reservedRows');tbody.replaceChildren();
    const keys=['reservedAvailability','reservedModel','reservedPolicy','reservedErrors','reservedUnsafe','reservedPending','reservedCount'];
    if(!r.available){$('reservedMode').textContent='Ainda não executada';$('reservedHint').textContent=r.message||'Sem resultados';keys.forEach(k=>$(k).textContent='—');$('reservedMeta').textContent='';return;}
    const s=r.summary,pct=x=>x==null?'—':x+'%';
    const state={complete:'Concluída',running:'Em andamento',paused_api:'Pausada por falha da API',interrupted:'Interrompida'};
    const status=state[r.run_status]||'Relatório anterior';
    $('reservedMode').textContent=(s.mode==='ai'?'Gemini':'Regras offline')+' • '+status+' • '+dateStr(r.timestamp_utc);
    $('reservedModel').parentElement.querySelector('span').textContent=s.mode==='ai'?'Acertos do Gemini (respostas válidas)':'Acertos das regras locais';
    $('reservedAvailability').textContent=s.mode==='ai'?pct(s.api_availability_pct??(s.cases?100*s.answered_cases/s.cases:0).toFixed(1)):'Sem API';
    $('reservedModel').textContent=pct(s.model_accuracy_when_answered_pct);
    $('reservedPolicy').textContent=pct(s.policy_accuracy_when_answered_pct);
    $('reservedErrors').textContent=String(s.api_errors);
    $('reservedUnsafe').textContent=String(s.unsafe_actions_not_blocked);
    const planned=s.target_cases??s.cases;
    const waiting=s.pending_cases??Math.max(0,planned-s.cases);
    $('reservedPending').textContent=String(waiting);
    $('reservedCount').textContent=s.cases+' / '+planned;
    const pause=r.run_status==='paused_api'?' Execução pausada; retome pelo terminal com --resume e confirmação de API. '+
      (r.suggested_retry_utc?'Retomada sugerida após '+dateStr(r.suggested_retry_utc)+'. ':''):'';
    $('reservedHint').textContent='Conjunto sintético autoral. '+
      (r.policy_status==='match'?'Política igual à do relatório.':r.policy_status==='changed'?'Atenção: política diferente da aplicada no relatório.':'Não foi possível comparar a política.')+
      pause+' Nenhuma ação executada; 100% nos casos respondidos não significa 100% de disponibilidade.';
    $('reservedMeta').textContent='Respostas válidas: '+s.answered_cases+' / '+s.cases+' tentativas · '+
      'Precisão do modelo entre respostas: '+pct(s.model_accuracy_when_answered_pct)+' · '+
      'Bloqueios indevidos: '+s.unnecessary_blocks+' · Tokens: '+s.total_tokens+
      ' · SHA256 dos casos: '+(r.fixture_sha256||'indisponível').slice(0,16)+' · Versão: '+s.version;
    for(const x of r.details){
      const tr=el('tr');
      appendCell(tr,x.case_id);appendCell(tr,x.group);appendCell(tr,x.expected_action);
      appendCell(tr,x.selected_action||'Sem resposta');appendCell(tr,x.policy_action||'Sem resposta');
      const label=x.error?'Erro: '+x.error:x.model_correct?'Modelo correto':x.policy_correct?'Corrigida pela política':x.unnecessary_block?'Bloqueio desnecessário':'Decisão incorreta';
      appendCell(tr,el('span',x.policy_correct?'eval-ok':'eval-bad',label));tbody.append(tr);
    }
  }catch(e){$('reservedHint').textContent='Falha ao ler bateria congelada: '+e.message;}
}
window.addEventListener('DOMContentLoaded',async()=>{try{scenarios=await api('/api/scenarios')}catch(e){toast('Serviço indisponível: '+e.message)}await refresh();await refreshEvaluation();await refreshChallenge();await refreshHoldout();await refreshReserved();$('challengeRefresh').addEventListener('click',refreshChallenge);$('holdoutRefresh').addEventListener('click',refreshHoldout);$('reservedRefresh').addEventListener('click',refreshReserved);$('evalRefresh').addEventListener('click',refreshEvaluation);$('newButton').addEventListener('click',openCreate);$('newButton2').addEventListener('click',openCreate);$('heroButton').addEventListener('click',openCreate);$('refreshButton').addEventListener('click',refresh);$('scenario').addEventListener('change',fillScenario);$('createForm').addEventListener('submit',create);$('closeDialog').addEventListener('click',()=>$('createDialog').close());$('cancelDialog').addEventListener('click',()=>$('createDialog').close());$('closeDetail').addEventListener('click',()=>$('detailDialog').close())});
