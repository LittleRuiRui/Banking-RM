const labels={cet1_ratio_pct:'CET1',capital_adequacy_ratio_pct:'BIS Capital',npl_ratio_pct:'NPL',roe_pct:'ROE',roa_pct:'ROA',gmt_programme_usd_bn:'GMTN',uscp_programme_usd_bn:'USCP',ecp_programme_usd_bn:'ECP',ratings_detected:'Ratings'};
const formats={cet1_ratio_pct:v=>`${v.toFixed(2)}%`,capital_adequacy_ratio_pct:v=>`${v.toFixed(2)}%`,npl_ratio_pct:v=>`${v.toFixed(2)}%`,roe_pct:v=>`${v.toFixed(2)}%`,roa_pct:v=>`${v.toFixed(2)}%`,gmt_programme_usd_bn:v=>`US$${v}bn`,uscp_programme_usd_bn:v=>`US$${v}bn`,ecp_programme_usd_bn:v=>`US$${v}bn`,ratings_detected:v=>v.join(' / ')};
const discovery=[
['Funding pipeline','How are you thinking about benchmark issuance versus opportunistic/private placements over the next 12–18 months?'],
['Refinancing','Which parts of the maturity profile are taking most attention over the next year or so?'],
['Rates impact','Has the current long-end USD rate environment changed tenor or timing?'],
['ASEAN pipeline','Are you seeing more Korean corporate financing activity in the US, or is Southeast Asia becoming more active?'],
['Partner banks','Where is international-bank participation most useful in KDB-led financings?'],
['Wallet criteria','For recent offshore transactions, what mattered most when selecting banking partners?']
];

function safe(v){return v===undefined||v===null||v===''?'n/a':v}
function metricValue(key,v){if(v===null||v===undefined)return 'n/a'; return (formats[key]||String)(v)}
function openMetric(snapshot,key){
  const ev=snapshot.metric_evidence?.[key]||{}; const src=snapshot.metric_sources?.[key]||{};
  const value=metricValue(key,snapshot.metrics?.[key]);
  document.querySelector('#dialog-body').innerHTML=`<h2>${labels[key]||key}: ${value}</h2><div class="prov-grid"><b>Source</b><span>${safe(ev.source_name||src.name)}</span><b>Period</b><span>${safe(ev.reporting_period||src.reporting_period)}</span><b>Page</b><span>${safe(ev.page)}</span><b>Section</b><span>${safe(ev.section)}</span><b>Method</b><span>${safe(ev.method||src.method||'direct extraction')}</span></div><div class="snippet">${safe(ev.evidence_snippet)}</div>`;
  document.querySelector('#metric-dialog').showModal();
}

async function load(){
  const res=await fetch('data/kdb_public_snapshot.json',{cache:'no-store'}); if(!res.ok)throw new Error(`Data load failed: ${res.status}`); const s=await res.json();
  document.querySelector('#client-title').textContent=s.client||'Korea Development Bank';
  document.querySelector('#generated-at').textContent=`Generated ${new Date(s.generated_at).toLocaleString()}`;
  const q=s.data_quality||{};
  document.querySelector('#quality').innerHTML=`<span class="score">Reliability ${safe(q.reliability_score_out_of_10)}/10</span><span class="score">Coverage ${safe(q.coverage_pct)}%</span>`;
  const ratings=s.metrics?.ratings_detected||[];
  document.querySelector('#credit-view').textContent=`Sovereign-linked credit; ${ratings.length?ratings.join(' / '):'ratings unavailable'}.`;

  const keys=['cet1_ratio_pct','capital_adequacy_ratio_pct','npl_ratio_pct','roe_pct','roa_pct','gmt_programme_usd_bn','uscp_programme_usd_bn','ecp_programme_usd_bn','ratings_detected'];
  const box=document.querySelector('#metrics'); box.innerHTML='';
  keys.forEach(key=>{const el=document.createElement('article'); el.className='metric'; const v=s.metrics?.[key]; const source=s.metric_sources?.[key]?.name||s.metric_evidence?.[key]?.source_name||'Verified source'; el.innerHTML=`<div class="label">${labels[key]}</div><div class="value">${metricValue(key,v)}</div><div class="source">${source}</div>`; el.onclick=()=>openMetric(s,key); box.appendChild(el)});

  document.querySelector('#questions').innerHTML=discovery.map(([a,b])=>`<article class="question"><strong>${a}</strong><p>${b}</p></article>`).join('');
  const flags=s.consistency_flags||[];
  document.querySelector('#warnings').innerHTML=flags.length?flags.map(f=>`<div class="warning"><strong>${safe(f.check)}</strong><br>${safe(f.detail)}</div>`).join(''):`<div class="warning good">No unresolved cross-metric consistency warnings in this snapshot.</div>`;
}

document.querySelector('#dialog-close').onclick=()=>document.querySelector('#metric-dialog').close();
document.querySelector('#refresh-btn').onclick=()=>load().catch(showError);
function showError(err){document.querySelector('#credit-view').textContent='Could not load current snapshot';document.querySelector('#warnings').innerHTML=`<div class="warning">${err.message}</div>`}
load().catch(showError);
if('serviceWorker' in navigator){navigator.serviceWorker.register('sw.js').catch(()=>{})}
