/**
 * ============================================================
 *  前端交互逻辑 v3.0
 *  三层贝叶斯 + localStorage API Key
 * ============================================================
 */

let currentResult = null, currentRecordId = null, riskChart = null;

// ===== localStorage 工具 =====
function getStored(field, sessionOnly) {
    return sessionOnly ? sessionStorage.getItem(field) : localStorage.getItem(field);
}
function setStored(field, value, sessionOnly) {
    if (sessionOnly) sessionStorage.setItem(field, value);
    else localStorage.setItem(field, value);
}
function getTrustDevice() {
    // 默认信任设备（与 admin.html 逻辑一致）
    return localStorage.getItem('trust_device') !== 'false';
}

function getAPIKey() {
    // 优先 localStorage（持久），其次 sessionStorage（本次会话）
    return localStorage.getItem('llm_api_key') || sessionStorage.getItem('llm_api_key') || '';
}
function getEndpoint() { return localStorage.getItem('llm_endpoint') || 'https://api.deepseek.com/v1/chat/completions'; }
function getModel() { return localStorage.getItem('llm_model') || 'deepseek-chat'; }

// ===== sessionStorage 表单记忆 =====
const FORM_FIELDS = ['facility_name','facility_type',
    'material','install_age','water_log','sun_shade',
    'use_freq','user_group','use_intensity',
    'inspect_freq','repair_time','dependency','outage_impact'];
const FORM_GROUPS_KEY = 'form_user_groups';

function saveFormToSession() {
    FORM_FIELDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) sessionStorage.setItem('form_'+id, el.value);
    });
    sessionStorage.setItem(FORM_GROUPS_KEY, JSON.stringify(getCheckedGroups()));
}

function loadFormFromSession() {
    let restored = false;
    FORM_FIELDS.forEach(id => {
        const saved = sessionStorage.getItem('form_'+id);
        const el = document.getElementById(id);
        if (saved && el) { el.value = saved; restored = true; }
    });
    const savedGroups = sessionStorage.getItem(FORM_GROUPS_KEY);
    if (savedGroups) {
        const groups = JSON.parse(savedGroups);
        document.querySelectorAll('#user-groups .checkbox-item').forEach(el => {
            el.classList.toggle('checked', groups.includes(el.dataset.value));
        });
        restored = true;
    }
    return restored;
}

function clearFormMemory() {
    FORM_FIELDS.forEach(id => sessionStorage.removeItem('form_'+id));
    sessionStorage.removeItem(FORM_GROUPS_KEY);
    resetForm();
    showToast('表单已清空');
}

// ===== 文件导入 =====
async function handleFileImport(event) {
    const file = event.target.files[0];
    if (!file) return;
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!['.csv','.xlsx'].includes(ext)) {
        showToast('仅支持 .csv 或 .xlsx 文件','error');
        event.target.value = ''; return;
    }

    const preview = document.getElementById('import-preview');
    preview.innerHTML = '<span style="font-size:12px;color:var(--text-secondary);">⏳ 解析中...</span>';

    const formData = new FormData();
    formData.append('file', file);
    try {
        const resp = await fetch('/api/import/parse', {method:'POST', body: formData});
        const data = await resp.json();
        if (!data.success) {
            preview.innerHTML = `<span style="color:var(--danger);font-size:12px;">❌ ${data.error}</span>`;
            event.target.value = ''; return;
        }

        const rows = data.rows;
        if (rows.length === 1) {
            // 单行：直接填充表单
            fillFormFromRow(rows[0]);
            preview.innerHTML = `<span style="color:var(--success);font-size:12px;">✅ 已填充 1 条记录。请检查后点击"开始评估"。</span>`;
        } else {
            // 多行：显示选择器
            let html = `<span style="color:var(--success);font-size:12px;">✅ 解析到 ${data.count} 条记录：</span>
                <select class="form-select" id="import-select" onchange="fillFormFromImported(this.value)" style="width:auto;display:inline-block;margin-left:8px;">
                <option value="">-- 选择一条填充 --</option>`;
            rows.forEach((r,i) => {
                const label = r.facility_name || r.facility_type || `第${i+1}条`;
                html += `<option value="${i}">${label}</option>`;
            });
            html += '</select>';
            // 存储数据
            window._importedRows = rows;
            preview.innerHTML = html;
        }
    } catch(err) {
        preview.innerHTML = `<span style="color:var(--danger);font-size:12px;">网络错误: ${err.message}</span>`;
    }
    event.target.value = '';
}

function fillFormFromImported(idx) {
    if (!window._importedRows || idx === '') return;
    fillFormFromRow(window._importedRows[parseInt(idx)]);
}

function fillFormFromRow(row) {
    // 工具函数：找匹配选项
    function setSelect(id, value) {
        const el = document.getElementById(id);
        if (!el || !value) return;
        // 精确匹配
        for (const opt of el.options) {
            if (opt.value === value || opt.text === value) { el.value = opt.value; return; }
        }
        // 模糊匹配
        const v = value.toLowerCase().replace(/\s+/g,'');
        for (const opt of el.options) {
            if (opt.value.toLowerCase().replace(/\s+/g,'') === v ||
                opt.text.toLowerCase().replace(/\s+/g,'') === v) { el.value = opt.value; return; }
        }
    }

    const FIELDS = ['facility_type','material','install_age','water_log','sun_shade',
        'use_freq','user_group','use_intensity','inspect_freq','repair_time',
        'dependency','outage_impact'];
    FIELDS.forEach(k => setSelect(k, row[k]));

    if (row.facility_name) document.getElementById('facility_name').value = row.facility_name;
    saveFormToSession();
    showToast('表单已自动填充，请核对后提交');
}

// 页面加载时恢复表单
document.addEventListener('DOMContentLoaded', () => {
    if (loadFormFromSession()) {
        // 如果恢复了设施类型，也应用预设
        const typeEl = document.getElementById('facility_type');
        if (typeEl && typeEl.value && sessionStorage.getItem('form_facility_type')) {
            // 不触发 onTypeChange（会覆盖恢复的值）
        }
    }
});

// 所有表单字段自动保存
document.addEventListener('change', e => {
    if (e.target.closest('#evaluate-form')) saveFormToSession();
});
document.getElementById('facility_name')?.addEventListener('input', saveFormToSession);
document.querySelectorAll('#user-groups .checkbox-item').forEach(el => {
    el.addEventListener('click', () => { setTimeout(saveFormToSession, 50); });
});

// ===== 复选框 =====
document.querySelectorAll('#user-groups .checkbox-item').forEach(el => {
    el.addEventListener('click', function() { this.classList.toggle('checked'); });
});
function getCheckedGroups() {
    return Array.from(document.querySelectorAll('#user-groups .checkbox-item.checked')).map(el => el.dataset.value);
}

// ===== 设施类型快速填充 =====
function onTypeChange() {
    const presets = {
        '长椅': {material:'木质',install_age:'3-8年',water_log:'中',sun_shade:'有遮',
                 use_freq:'高',user_group:'老人',use_intensity:'静坐',
                 inspect_freq:'每月',repair_time:'3-14天',
                 dependency:'中',outage_impact:'中等',groups:['老人','成年人']},
        '儿童滑梯':{material:'塑料',install_age:'3-8年',water_log:'中',sun_shade:'暴晒',
                   use_freq:'高',user_group:'儿童',use_intensity:'攀爬',
                   inspect_freq:'每月',repair_time:'3-14天',
                   dependency:'高',outage_impact:'严重',groups:['儿童']},
        '健身器材':{material:'金属',install_age:'3-8年',water_log:'低',sun_shade:'有遮',
                   use_freq:'中',user_group:'老人',use_intensity:'健身',
                   inspect_freq:'每月',repair_time:'3-14天',
                   dependency:'高',outage_impact:'严重',groups:['老人','成年人']},
        '晾衣架':{material:'金属',install_age:'3-8年',water_log:'高',sun_shade:'暴晒',
                 use_freq:'中',user_group:'成人',use_intensity:'静坐',
                 inspect_freq:'每季',repair_time:'>14天',
                 dependency:'低',outage_impact:'轻微',groups:['租户','老人']},
        '凉亭':{material:'木质',install_age:'<3年',water_log:'低',sun_shade:'有遮',
               use_freq:'低',user_group:'老人',use_intensity:'静坐',
               inspect_freq:'每周',repair_time:'<3天',
               dependency:'低',outage_impact:'轻微',groups:['老人','成年人']},
        '护栏':{material:'金属',install_age:'3-8年',water_log:'低',sun_shade:'暴晒',
               use_freq:'低',user_group:'儿童',use_intensity:'静坐',
               inspect_freq:'每月',repair_time:'3-14天',
               dependency:'高',outage_impact:'严重',groups:['儿童','成年人']},
        '乒乓球桌':{material:'金属',install_age:'>8年',water_log:'高',sun_shade:'暴晒',
                   use_freq:'高',user_group:'成人',use_intensity:'健身',
                   inspect_freq:'每季',repair_time:'>14天',
                   dependency:'中',outage_impact:'中等',groups:['成年人','儿童']},
        '信息公告栏':{material:'金属',install_age:'<3年',water_log:'低',sun_shade:'有遮',
                    use_freq:'低',user_group:'成人',use_intensity:'静坐',
                    inspect_freq:'每周',repair_time:'<3天',
                    dependency:'低',outage_impact:'轻微',groups:['成年人','租户']},
        '无障碍坡道':{material:'金属',install_age:'>8年',water_log:'中',sun_shade:'暴晒',
                     use_freq:'中',user_group:'老人',use_intensity:'静坐',
                     inspect_freq:'每月',repair_time:'3-14天',
                     dependency:'高',outage_impact:'严重',groups:['行动不便者','老人']},
    };
    const type = document.getElementById('facility_type').value;
    if (!presets[type]) return;
    const p = presets[type];
    ['material','install_age','water_log','sun_shade','use_freq','user_group','use_intensity',
     'inspect_freq','repair_time','dependency','outage_impact'].forEach(k => {
        const el = document.getElementById(k);
        if (el) el.value = p[k];
    });
    document.querySelectorAll('#user-groups .checkbox-item').forEach(el => {
        el.classList.toggle('checked', p.groups.includes(el.dataset.value));
    });
}

// ===== 重置 =====
function resetForm() {
    document.getElementById('evaluate-form').reset();
    document.querySelectorAll('#user-groups .checkbox-item').forEach(el => el.classList.remove('checked'));
    ['老人','成年人'].forEach(v => {
        const el = document.querySelector(`#user-groups .checkbox-item[data-value="${v}"]`);
        if (el) el.classList.add('checked');
    });
    document.getElementById('result-section').style.display = 'none';
    document.getElementById('empty-state').style.display = '';
    document.getElementById('interpretation-section').style.display = 'none';
    document.getElementById('whatif-panel').style.display = 'none';
    document.getElementById('scenario-panel').style.display = 'none';
    currentResult = null; currentRecordId = null;
    // 重置时也清除 sessionStorage
    FORM_FIELDS.forEach(id => sessionStorage.removeItem('form_'+id));
    sessionStorage.removeItem(FORM_GROUPS_KEY);
}

// ===== 提交 =====
document.getElementById('evaluate-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('submit-btn');
    btn.disabled = true; btn.textContent = '⏳ 评估中...';
    const groups = getCheckedGroups();
    if (!groups.length) { showToast('请至少选择一个使用群体','error'); btn.disabled=false; btn.textContent='🔍 开始评估'; return; }

    const payload = {
        facility_name: document.getElementById('facility_name').value || '未命名设施',
        facility_type: document.getElementById('facility_type').value || '长椅',
        material: document.getElementById('material').value,
        install_age: document.getElementById('install_age').value,
        water_log: document.getElementById('water_log').value,
        sun_shade: document.getElementById('sun_shade').value,
        use_freq: document.getElementById('use_freq').value,
        user_group: document.getElementById('user_group').value,
        use_intensity: document.getElementById('use_intensity').value,
        inspect_freq: document.getElementById('inspect_freq').value,
        repair_time: document.getElementById('repair_time').value,
        dependency: document.getElementById('dependency').value,
        outage_impact: document.getElementById('outage_impact').value,
        user_groups: groups,
    };

    try {
        const resp = await fetch('/api/evaluate', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
        const data = await resp.json();
        if (data.success) {
            currentResult = data.raw; currentRecordId = data.record_id;
            renderResult(data.result, data.raw);
            showToast('评估完成！已保存到历史记录');
        } else showToast('评估失败: '+(data.error||''),'error');
    } catch(err) { showToast('网络错误: '+err.message,'error'); }
    finally { btn.disabled = false; btn.textContent = '🔍 开始评估'; }
});

// ===== 渲染结果 =====
function renderResult(result, raw) {
    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('result-section').style.display = '';
    document.getElementById('interpretation-section').style.display = 'none';
    document.getElementById('whatif-panel').style.display = 'none';
    document.getElementById('scenario-panel').style.display = 'none';

    const rc = {'高风险':'stat-risk-high','中风险':'stat-risk-med','低风险':'stat-risk-low'};
    const bm = {'[!!!] 最高优先':'badge-highest','[!!]  高度优先':'badge-high','[*]   一般关注':'badge-normal','[ ]   定期巡检即可':'badge-low'};

    document.getElementById('result-stats').innerHTML = `
        <div class="result-stat"><div class="stat-value ${rc[result.risk_level]}">${result.risk_level}</div><div class="stat-label">故障风险等级</div></div>
        <div class="result-stat"><div class="stat-value stat-accent">${result.risk_score}</div><div class="stat-label">风险得分 / 3.0</div></div>
        <div class="result-stat"><div class="stat-value stat-accent">${result.social_weight}</div><div class="stat-label">社会影响权重</div></div>
        <div class="result-stat"><div class="stat-value stat-accent">${result.priority_score}</div><div class="stat-label">综合优先级得分</div></div>`;

    // 中间因子推断结果
    if (result.mid_probs) {
        let midHtml = '<div style="font-size:12px;color:var(--text-secondary);text-align:center;margin:8px 0;">';
        const names = {exposure_prob:'退化暴露',usage_prob:'使用负荷',maintenance_prob:'治理状态',social_prob:'正义修正'};
        for (const [k,v] of Object.entries(result.mid_probs)) {
            const dominant = Object.entries(v).sort((a,b)=>b[1]-a[1])[0];
            midHtml += `<span style="margin:0 8px;">${names[k]}: <b>${dominant[0]}</b>(${(dominant[1]*100).toFixed(0)}%)</span>`;
        }
        midHtml += '</div>';
        document.getElementById('mid-probs').innerHTML = midHtml;
    }

    document.getElementById('result-priority').innerHTML = `
        <span class="priority-badge ${bm[result.priority_level]||'badge-normal'}" style="font-size:16px;padding:8px 20px;">${result.priority_level}</span>`;
    renderChart(result.prob_low_val, result.prob_med_val, result.prob_high_val);
}

function renderChart(pl,pm,ph) {
    const ctx = document.getElementById('riskChart').getContext('2d');
    if (riskChart) riskChart.destroy();
    riskChart = new Chart(ctx,{type:'bar',
        data:{labels:['低风险','中风险','高风险'],datasets:[{data:[pl*100,pm*100,ph*100],backgroundColor:['#8BAA7D','#D4A853','#C4655A'],borderRadius:6,borderSkipped:false}]},
        options:{responsive:true,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,max:100,ticks:{callback:v=>v+'%'}}}}});
}

// ===== Markdown 清洗 =====
function stripMarkdown(text) {
    return text.replace(/^#{1,6}\s+/gm,'').replace(/\*\*(.+?)\*\*/g,'$1').replace(/\*(.+?)\*/g,'$1')
        .replace(/^[\*\-]\s+/gm,'  - ').replace(/^>\s+/gm,'').replace(/`{1,3}[^`]*`{1,3}/g,'').replace(/\n{3,}/g,'\n\n');
}

function escapeHtml(text) {
    const d = document.createElement('div'); d.textContent = text; return d.innerHTML.replace(/\n/g,'<br>');
}

// ===== LLM 解读（Key 从浏览器取） =====
async function requestInterpretation() {
    if (!currentRecordId) { showToast('请先完成评估','error'); return; }
    const apiKey = getAPIKey();
    if (!apiKey) { showToast('请先在「设置」页面填写 API Key','error'); return; }

    const section = document.getElementById('interpretation-section');
    const content = document.getElementById('interpretation-content');
    section.style.display = '';
    content.innerHTML = '<div class="interpretation-loading"><div class="spinner"></div><div>AI 正在分析...</div></div>';
    document.getElementById('interpret-btn').disabled = true;

    try {
        const resp = await fetch('/api/llm/interpret', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body:JSON.stringify({record_id:currentRecordId, api_key:apiKey, endpoint:getEndpoint(), model:getModel()}),
        });
        const data = await resp.json();
        if (data.success) {
            content.innerHTML = `<div class="interpretation-box">${escapeHtml(stripMarkdown(data.interpretation))}</div>`;
            showToast('AI 解读完成！');
        } else {
            content.innerHTML = `<div class="interpretation-box" style="color:var(--danger);">${escapeHtml(data.error||'')}</div>`;
        }
    } catch(err) { content.innerHTML = '<div class="interpretation-box" style="color:var(--danger);">网络错误</div>'; }
    finally { document.getElementById('interpret-btn').disabled = false; }
}

// ===== What-if 多变量 =====
async function showWhatIf() {
    if (!currentResult) return;
    const panel = document.getElementById('whatif-panel');
    if (panel.style.display === '') { panel.style.display='none'; return; }

    const vars = [
        {key:'material',label:'材料类型',opts:['木质','金属','塑料']},
        {key:'install_age',label:'安装年龄',opts:['<3年','3-8年','>8年']},
        {key:'water_log',label:'积水风险',opts:['低','中','高']},
        {key:'sun_shade',label:'遮阴情况',opts:['暴晒','有遮']},
        {key:'use_freq',label:'使用频率',opts:['低','中','高']},
        {key:'user_group',label:'主要群体',opts:['成人','老人','儿童']},
        {key:'use_intensity',label:'使用强度',opts:['静坐','健身','攀爬']},
        {key:'inspect_freq',label:'巡检频率',opts:['每周','每月','每季']},
        {key:'repair_time',label:'维修响应',opts:['<3天','3-14天','>14天']},
        {key:'dependency',label:'群体依赖',opts:['低','中','高']},
        {key:'outage_impact',label:'停用后影响',opts:['轻微','中等','严重']},
    ];
    let html = '<h4>🔄 What-if 多变量模拟</h4><p style="font-size:13px;color:var(--text-secondary);margin-bottom:12px;">修改任意多个变量后点击「计算」。(括号内=当前值)</p>';
    vars.forEach(v => {
        const cur = currentResult[v.key] || '';
        html += `<div style="margin-bottom:6px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            <span style="font-weight:600;font-size:12px;min-width:70px;">${v.label}</span>
            <select id="whatif-${v.key}" class="form-select" style="width:auto;font-size:12px;">
                ${v.opts.map(o=>`<option value="${o}" ${o===cur?'selected':''}>${o}</option>`).join('')}</select>
            <span style="font-size:10px;color:var(--text-muted);">(${cur})</span></div>`;
    });
    html += '<button class="btn btn-primary btn-sm" onclick="runMultiWhatIf()" style="margin-top:8px;">🔍 计算此场景</button><div id="whatif-result" style="margin-top:12px;"></div>';
    panel.innerHTML = html; panel.style.display = '';
}

async function runMultiWhatIf() {
    const resultDiv = document.getElementById('whatif-result');
    resultDiv.innerHTML = '<span style="color:var(--text-secondary);">⏳ 计算中...</span>';
    const keys = ['material','install_age','water_log','sun_shade','use_freq','user_group','use_intensity','inspect_freq','repair_time','dependency','outage_impact'];
    const payload = {facility_name: currentResult.facility_name+'（模拟）', facility_type: currentResult.facility_type, user_groups: currentResult.user_groups};
    keys.forEach(k => { payload[k] = document.getElementById('whatif-'+k).value; });
    try {
        const resp = await fetch('/api/evaluate', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
        const data = await resp.json();
        if (data.success) {
            const r = data.result; const old = currentResult.risk_score;
            const delta = (r.risk_score-old).toFixed(2);
            const color = delta>0?'var(--danger)':delta<0?'var(--success)':'inherit';
            const bm = {'[!!!] 最高优先':'badge-highest','[!!]  高度优先':'badge-high','[*]   一般关注':'badge-normal','[ ]   定期巡检即可':'badge-low'};
            resultDiv.innerHTML = `<div class="card" style="margin-top:8px;">
                <div class="result-grid">
                    <div class="result-stat"><div class="stat-value" style="color:${color};">${r.risk_level}</div><div class="stat-label">模拟风险等级</div></div>
                    <div class="result-stat"><div class="stat-value stat-accent">${r.risk_score} <span style="font-size:12px;color:${color};">(${delta>=0?'+':''}${delta})</span></div><div class="stat-label">风险得分</div></div>
                    <div class="result-stat"><div class="stat-value stat-accent">${r.priority_score}</div><div class="stat-label">优先级得分</div></div>
                    <div class="result-stat"><span class="priority-badge ${bm[r.priority_level]||'badge-normal'}">${r.priority_level}</span></div></div>
                <div style="font-size:12px;color:var(--text-secondary);">低${r.prob_low} / 中${r.prob_med} / 高${r.prob_high}</div></div>`;
        } else resultDiv.innerHTML = '<span style="color:var(--danger);">计算失败</span>';
    } catch(err) { resultDiv.innerHTML = '<span style="color:var(--danger);">网络错误</span>'; }
}

// ===== 情景对比 =====
async function showScenario() {
    if (!currentResult) return;
    const panel = document.getElementById('scenario-panel');
    if (panel.style.display === '') { panel.style.display='none'; return; }
    panel.innerHTML = '<div class="interpretation-loading"><div class="spinner"></div><div>计算三种情景...</div></div>';
    panel.style.display = '';

    const keys = ['material','install_age','water_log','sun_shade','use_freq','user_group','use_intensity','inspect_freq','repair_time','dependency','outage_impact'];
    const payload = {facility_type:currentResult.facility_type,user_groups:currentResult.user_groups,facility_name:currentResult.facility_name};
    keys.forEach(k=>{payload[k]=currentResult[k];});

    try {
        const resp = await fetch('/api/scenario/compare', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
        const data = await resp.json();
        if (!data.success) { panel.innerHTML='<div class="card" style="color:var(--danger);">对比失败</div>'; return; }
        const sc = data.scenarios; const colors = {A:'#C4655A',B:'#D4A853',C:'#8BAA7D'};
        let html = '<h4 style="margin-bottom:12px;">📋 三种维护情景对比</h4><div class="scenario-cards">';
        for (const [key,s] of Object.entries(sc)) {
            html += `<div class="scenario-card${key==='C'?' recommended':''}" style="border-top:3px solid ${colors[key]};">
                <h4>情景${key}：${s.label}</h4><div class="scenario-score" style="color:${colors[key]};">${s.result.priority_score}</div>
                <div style="font-size:13px;">优先级 | 风险:${s.result.risk_level}</div>
                <div class="scenario-desc">${s.desc}</div><div style="font-size:11px;color:var(--text-muted);margin-top:4px;">${s.cost}</div></div>`;
        }
        html += '</div>';
        panel.innerHTML = html;
    } catch(err) { panel.innerHTML = '<div class="card" style="color:var(--danger);">网络错误</div>'; }
}

// ===== URL 参数预填充（从排名页跳转过来） =====
function loadFromURLParams() {
    const params = new URLSearchParams(window.location.search);
    const FIELD_KEYS = ['material','install_age','water_log','sun_shade',
        'use_freq','user_group','use_intensity','inspect_freq','repair_time',
        'dependency','outage_impact'];
    let hasParams = false;

    // 1. 先设设施类型（触发 onTypeChange 填好默认值）
    const ftype = params.get('facility_type');
    if (ftype) {
        const el = document.getElementById('facility_type');
        if (el) { el.value = ftype; onTypeChange(); hasParams = true; }
    }

    // 2. 再用 URL 参数覆盖（onTypeChange 的默认值被实际值替换）
    FIELD_KEYS.forEach(key => {
        const val = params.get(key);
        if (val) {
            const el = document.getElementById(key);
            if (el) { el.value = val; hasParams = true; }
        }
    });

    // 设施名称
    const fname = params.get('facility_name');
    if (fname) { document.getElementById('facility_name').value = decodeURIComponent(fname); hasParams = true; }

    // 使用群体（URL 参数覆盖 onTypeChange 的默认勾选）
    const groups = params.get('user_groups');
    if (groups) {
        const groupList = groups.split(',');
        document.querySelectorAll('#user-groups .checkbox-item').forEach(el => {
            el.classList.toggle('checked', groupList.includes(el.dataset.value));
        });
        hasParams = true;
    }

    // 有参数就自动提交评估
    if (hasParams) {
        saveFormToSession();
        document.getElementById('evaluate-form').dispatchEvent(new Event('submit'));
    }
}

// diagnose 页面加载时检查 URL 参数
if (document.getElementById('evaluate-form')) {
    document.addEventListener('DOMContentLoaded', loadFromURLParams);
}
