/**
 * ============================================================
 *  维护优先级排序页 v1.0
 *  设施管理 + 批量评估 + 排名展示 + 导出
 * ============================================================
 */

let facilityList = [];           // 用户添加的设施 [{facility_type, facility_name, ...}]
let rankingResults = [];        // 后端返回的排序结果
let rankingFiltered = [];       // 当前筛选后的结果

const FACILITY_TYPES = window.FACILITY_TYPES_JS || [];

const FIELD_OPTS = {
    material:['木质','金属','塑料'],
    install_age:['<3年','3-8年','>8年'],
    water_log:['低','中','高'],
    sun_shade:['暴晒','有遮'],
    use_freq:['低','中','高'],
    user_group:['成人','老人','儿童'],
    use_intensity:['静坐','健身','攀爬'],
    inspect_freq:['每周','每月','每季'],
    repair_time:['<3天','3-14天','>14天'],
    dependency:['低','中','高'],
    outage_impact:['轻微','中等','严重'],
};

// ===== 设施类型默认值 =====
const DEFAULTS = {
    '长椅':   {material:'木质',install_age:'3-8年',water_log:'中',sun_shade:'有遮',use_freq:'高',user_group:'老人',use_intensity:'静坐',inspect_freq:'每月',repair_time:'3-14天',dependency:'中',outage_impact:'中等',user_groups:['老人','成年人']},
    '儿童滑梯':{material:'塑料',install_age:'3-8年',water_log:'中',sun_shade:'暴晒',use_freq:'高',user_group:'儿童',use_intensity:'攀爬',inspect_freq:'每月',repair_time:'3-14天',dependency:'高',outage_impact:'严重',user_groups:['儿童']},
    '健身器材':{material:'金属',install_age:'3-8年',water_log:'低',sun_shade:'有遮',use_freq:'中',user_group:'老人',use_intensity:'健身',inspect_freq:'每月',repair_time:'3-14天',dependency:'高',outage_impact:'严重',user_groups:['老人','成年人']},
    '晾衣架': {material:'金属',install_age:'3-8年',water_log:'高',sun_shade:'暴晒',use_freq:'中',user_group:'成人',use_intensity:'静坐',inspect_freq:'每季',repair_time:'>14天',dependency:'低',outage_impact:'轻微',user_groups:['租户','老人']},
    '凉亭':   {material:'木质',install_age:'<3年',water_log:'低',sun_shade:'有遮',use_freq:'低',user_group:'老人',use_intensity:'静坐',inspect_freq:'每周',repair_time:'<3天',dependency:'低',outage_impact:'轻微',user_groups:['老人','成年人']},
    '护栏':   {material:'金属',install_age:'3-8年',water_log:'低',sun_shade:'暴晒',use_freq:'低',user_group:'儿童',use_intensity:'静坐',inspect_freq:'每月',repair_time:'3-14天',dependency:'高',outage_impact:'严重',user_groups:['儿童','成年人']},
    '乒乓球桌':{material:'金属',install_age:'>8年',water_log:'高',sun_shade:'暴晒',use_freq:'高',user_group:'成人',use_intensity:'健身',inspect_freq:'每季',repair_time:'>14天',dependency:'中',outage_impact:'中等',user_groups:['成年人','儿童']},
    '信息公告栏':{material:'金属',install_age:'<3年',water_log:'低',sun_shade:'有遮',use_freq:'低',user_group:'成人',use_intensity:'静坐',inspect_freq:'每周',repair_time:'<3天',dependency:'低',outage_impact:'轻微',user_groups:['成年人','租户']},
    '无障碍坡道':{material:'金属',install_age:'>8年',water_log:'中',sun_shade:'暴晒',use_freq:'中',user_group:'老人',use_intensity:'静坐',inspect_freq:'每月',repair_time:'3-14天',dependency:'高',outage_impact:'严重',user_groups:['行动不便者','老人']},
    '减速带':  {material:'金属',install_age:'>8年',water_log:'低',sun_shade:'暴晒',use_freq:'高',user_group:'成人',use_intensity:'静坐',inspect_freq:'每季',repair_time:'>14天',dependency:'低',outage_impact:'中等',user_groups:['成年人','儿童']},
    '路灯':    {material:'金属',install_age:'>8年',water_log:'低',sun_shade:'暴晒',use_freq:'高',user_group:'老人',use_intensity:'静坐',inspect_freq:'每月',repair_time:'3-14天',dependency:'高',outage_impact:'严重',user_groups:['老人','行动不便者']},
    '可拆卸路牌':{material:'金属',install_age:'3-8年',water_log:'低',sun_shade:'有遮',use_freq:'低',user_group:'成人',use_intensity:'静坐',inspect_freq:'每季',repair_time:'>14天',dependency:'低',outage_impact:'轻微',user_groups:['成年人','租户']},
    '遮阳棚':  {material:'塑料',install_age:'3-8年',water_log:'中',sun_shade:'暴晒',use_freq:'中',user_group:'老人',use_intensity:'静坐',inspect_freq:'每月',repair_time:'3-14天',dependency:'中',outage_impact:'中等',user_groups:['老人','成年人']},
};

// ===== 页面初始化 =====
document.addEventListener('DOMContentLoaded', () => {
    // 从 URL 参数读取 IPA 跳转过来的类型
    const params = new URLSearchParams(window.location.search);
    const types = params.get('types');
    if (types) {
        const typeList = types.split(',').map(t => t.trim()).filter(t => t);
        typeList.forEach(t => {
            if (DEFAULTS[t]) {
                const d = DEFAULTS[t];
                facilityList.push({
                    facility_type: t, facility_name: t,
                    material: d.material, install_age: d.install_age,
                    water_log: d.water_log, sun_shade: d.sun_shade,
                    use_freq: d.use_freq, user_group: d.user_group,
                    use_intensity: d.use_intensity, inspect_freq: d.inspect_freq,
                    repair_time: d.repair_time, dependency: d.dependency,
                    outage_impact: d.outage_impact, user_groups: [...d.user_groups],
                });
            }
        });
        renderFacilityList();
        showToast(`已从 IPA 导入 ${typeList.length} 种设施类型，请核对后点击评估`);
    }
});

// ===== 手动添加 =====
function addManualRow(type='', name='') {
    if (!type) {
        // 提供下拉选择
        const types = Object.keys(DEFAULTS);
        const options = types.map(t => `<option value="${t}">${t}</option>`).join('');
        const html = `<div class="ipa-row" style="margin-bottom:8px;padding:12px;">
            <select id="new-facility-type" class="form-select" style="width:auto;min-width:120px;" onchange="onNewTypeChange()">
                <option value="">-- 选择类型 --</option>${options}</select>
            <input type="text" id="new-facility-name" class="form-input" style="width:auto;min-width:150px;" placeholder="设施名称（如：中心广场长椅）">
            <button class="btn btn-primary btn-sm" onclick="confirmAdd()">确认添加</button>
            <button class="btn btn-sm btn-secondary" onclick="this.closest('.ipa-row').remove()">取消</button>
            <div id="new-defaults-preview" style="font-size:11px;color:var(--text-muted);margin-top:4px;width:100%;"></div>
        </div>`;
        const list = document.getElementById('facility-list');
        list.insertAdjacentHTML('beforeend', html);
        document.getElementById('facility-list-card').hidden = false;
        document.getElementById('ranking-empty').style.display = 'none';
        return;
    }
    // 直接添加
    const d = DEFAULTS[type] || DEFAULTS['长椅'];
    facilityList.push({
        facility_type: type, facility_name: name || type,
        material: d.material, install_age: d.install_age,
        water_log: d.water_log, sun_shade: d.sun_shade,
        use_freq: d.use_freq, user_group: d.user_group,
        use_intensity: d.use_intensity, inspect_freq: d.inspect_freq,
        repair_time: d.repair_time, dependency: d.dependency,
        outage_impact: d.outage_impact, user_groups: [...d.user_groups],
    });
    renderFacilityList();
}

function onNewTypeChange() {
    const type = document.getElementById('new-facility-type').value;
    const preview = document.getElementById('new-defaults-preview');
    if (!type || !DEFAULTS[type]) { preview.textContent = ''; return; }
    const d = DEFAULTS[type];
    preview.textContent = `默认填充：${d.material} | ${d.install_age} | 积水${d.water_log} | ${d.sun_shade} | 频率${d.use_freq} | ${d.user_group} | ${d.use_intensity} | 巡检${d.inspect_freq} | 响应${d.repair_time} | 依赖${d.dependency} | 停用影响${d.outage_impact} | 群体[${d.user_groups.join(',')}]`;
}

function confirmAdd() {
    const type = document.getElementById('new-facility-type').value;
    const name = document.getElementById('new-facility-name').value;
    if (!type) { showToast('请选择设施类型', 'error'); return; }
    addManualRow(type, name || type);
    // 移除添加行
    const row = document.querySelector('#facility-list .ipa-row:last-child');
    if (row) row.remove();
    renderFacilityList();
}

// ===== 渲染设施列表（可展开编辑） =====
function renderFacilityList() {
    const container = document.getElementById('facility-list');
    const card = document.getElementById('facility-list-card');
    const empty = document.getElementById('ranking-empty');
    const countEl = document.getElementById('facility-count');
    const submitBtn = document.getElementById('ranking-submit-btn');

    if (facilityList.length === 0) {
        card.hidden = true;
        empty.style.display = '';
        countEl.textContent = '';
        submitBtn.disabled = true;
        return;
    }
    card.hidden = false;
    empty.style.display = 'none';
    countEl.textContent = `共 ${facilityList.length} 个设施`;
    submitBtn.disabled = false;

    const FIELD_LABELS = {
        material:'材料',install_age:'安装年龄',water_log:'积水',sun_shade:'遮阴',
        use_freq:'使用频率',user_group:'主要群体',use_intensity:'使用强度',
        inspect_freq:'巡检',repair_time:'响应',dependency:'依赖度',outage_impact:'停用影响',
    };

    let html = '';
    facilityList.forEach((f, idx) => {
        // 检查该设施是否有无效字段
        const invalidFields = {};
        let hasInvalid = false;
        for (const key of Object.keys(FIELD_OPTS)) {
            const val = f[key] || '';
            if (val && !FIELD_OPTS[key].includes(val)) {
                invalidFields[key] = true;
                hasInvalid = true;
            }
        }

        // 构建摘要行（编辑后会由 onchange 动态更新）
        const summaryId = `summary-${idx}`;
        html += `<details class="field-group" style="margin-bottom:8px;">
            <summary class="field-group-title" style="display:flex;justify-content:space-between;align-items:center;">
                <span>${hasInvalid?'<span style="color:var(--danger);font-weight:700;" title="存在无效值">⚠️ </span>':''}🏷️ ${escapeHtml(f.facility_name || f.facility_type)}</span>
                <span id="${summaryId}" style="font-size:11px;color:var(--text-muted);font-weight:normal;">${f.facility_type} | ${f.material} | ${f.install_age}</span>
                <button class="btn btn-sm btn-danger" style="margin-left:8px;" onclick="event.preventDefault();removeFacility(${idx})">✕</button>
            </summary>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;margin-top:8px;padding-top:8px;border-top:1px solid var(--border-light);">
                <div><label style="font-size:11px;color:var(--text-secondary);">设施名称</label>
                    <input type="text" class="form-input" style="font-size:12px;padding:4px 8px;" value="${escapeHtml(f.facility_name||'')}" onchange="facilityList[${idx}].facility_name=this.value;document.getElementById('${summaryId}').textContent=this.value"></div>`;
        for (const [key, label] of Object.entries(FIELD_LABELS)) {
            const opts = FIELD_OPTS[key];
            const curVal = f[key] || '';
            const inv = invalidFields[key];
            html += `<div><label style="font-size:11px;color:var(--text-secondary);">${label}${inv?' <span style=\"color:var(--danger);\" title=\"无效值\">⚠️</span>':''}</label>
                <select class="form-select" style="font-size:12px;padding:4px 8px;" onchange="facilityList[${idx}].${key}=this.value;updateFacilitySummary(${idx},'${summaryId}')">
                    ${opts.map(o=>`<option value="${o}" ${curVal===o?'selected':''}>${o}</option>`).join('')}
                </select></div>`;
        }
        html += '</div></details>';
    });
    container.innerHTML = html;
}

function removeFacility(idx) {
    facilityList.splice(idx, 1);
    renderFacilityList();
}

function clearAllFacilities() {
    if (!confirm('确定清空全部设施吗？')) return;
    facilityList = [];
    rankingResults = [];
    renderFacilityList();
    document.getElementById('ranking-result-card').hidden = true;
    document.getElementById('filter-bar').hidden = true;
    document.getElementById('ranking-empty').style.display = '';
    document.getElementById('ranking-tbody').innerHTML = '';
}

// ===== CSV/Excel 导入 =====
async function handleRankingImport(event) {
    const file = event.target.files[0];
    if (!file) return;
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!['.csv','.xlsx'].includes(ext)) { showToast('仅支持 .csv 或 .xlsx 文件','error'); event.target.value=''; return; }

    const preview = document.getElementById('import-preview');
    preview.innerHTML = '<span style="color:var(--text-secondary);">⏳ 解析中...</span>';

    const fd = new FormData(); fd.append('file', file);
    try {
        const resp = await fetch('/api/import/parse', {method:'POST', body: fd});
        const data = await resp.json();
        if (!data.success) { preview.innerHTML = `<span style="color:var(--danger);">❌ ${data.error}</span>`; event.target.value=''; return; }

        // 将解析的行加入 facilityList（保留原始值，无效值将在评估时拦截报错）
        let added = 0, invalidCount = 0;
        data.rows.forEach(row => {
            const type = row.facility_type || '';
            const base = DEFAULTS[type] || {material:'金属',install_age:'3-8年',water_log:'中',sun_shade:'有遮',use_freq:'中',user_group:'成人',use_intensity:'静坐',inspect_freq:'每月',repair_time:'3-14天',dependency:'中',outage_impact:'中等',user_groups:['老人']};
            const fields = {};
            for (const key of Object.keys(FIELD_OPTS)) {
                const raw = row[key] || '';
                fields[key] = raw || base[key];
                if (raw && FIELD_OPTS[key] && !FIELD_OPTS[key].includes(raw)) invalidCount++;
            }
            facilityList.push({
                facility_type: type || '长椅',
                facility_name: row.facility_name || row.facility_type || `设施-${facilityList.length+1}`,
                ...fields,
                user_groups: (row.user_groups ? row.user_groups.split(',').map(s=>s.trim()) : [...base.user_groups]),
            });
            added++;
        });
        renderFacilityList();
        const warnMsg = invalidCount > 0 ? ` ⚠️ 检测到 ${invalidCount} 处无效值，请展开核对后修改，否则评估时将报错。` : '';
        preview.innerHTML = `<span style="color:${invalidCount>0?'var(--warning)':'var(--success)'};">${invalidCount>0?'⚠️':'✅'} 已导入 ${added} 条记录。${warnMsg}</span>`;
    } catch(err) { preview.innerHTML = `<span style="color:var(--danger);">网络错误: ${err.message}</span>`; }
    event.target.value = '';
}

// ===== 批量评估 =====
async function runRanking() {
    if (facilityList.length === 0) { showToast('请先添加设施', 'error'); return; }

    // 评估前校验：逐设施逐字段检查，无效值报错并列出合法选项
    const errors = [];
    facilityList.forEach((f, idx) => {
        for (const key of Object.keys(FIELD_OPTS)) {
            const val = f[key] || '';
            const opts = FIELD_OPTS[key];
            if (val && !opts.includes(val)) {
                errors.push(`设施 #${idx+1}「${f.facility_name||f.facility_type}」：${validOptionsHint(key)}（当前值："${val}"）`);
            }
        }
    });
    if (errors.length > 0) {
        const msg = errors.length <= 3 ? errors.join('<br>') : errors.slice(0,3).join('<br>') + `<br>…… 还有 ${errors.length-3} 处错误`;
        showToast(msg, 'error');
        return;
    }

    const btn = document.getElementById('ranking-submit-btn');
    btn.disabled = true; btn.textContent = '⏳ 评估中...';

    try {
        const resp = await fetch('/api/ranking/evaluate', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({facilities: facilityList}),
        });
        // 先读文本，便于调试
        const text = await resp.text();
        let data;
        try { data = JSON.parse(text); }
        catch (parseErr) {
            showToast('服务器返回异常 (HTTP ' + resp.status + '): ' + text.slice(0, 200), 'error');
            console.error('Ranking API response:', text);
            btn.disabled = false; btn.textContent = '🔍 开始评估排序'; return;
        }
        if (!data.success) { showToast(data.error || '评估失败', 'error'); btn.disabled=false; btn.textContent='🔍 开始评估排序'; return; }

        rankingResults = data.results;
        applyFilter();
        document.getElementById('ranking-result-card').hidden = false;
        document.getElementById('filter-bar').hidden = false;
        document.getElementById('ranking-empty').style.display = 'none';
        showToast(`评估完成！共 ${data.count} 个设施`);

        // 检测是否有同类型设施 ≥2 个 → 提示轮换
        checkRotationHint(data.results);
    } catch(err) { showToast('网络错误: '+err.message, 'error'); console.error(err); }
    finally { btn.disabled = false; btn.textContent = '🔍 开始评估排序'; }
}

// ===== 筛选 =====
function applyFilter() {
    const filter = document.getElementById('ranking-priority-filter').value;
    rankingFiltered = filter ? rankingResults.filter(r => r.priority_level === filter) : [...rankingResults];
    renderRankingTable(rankingFiltered);
}

// ===== 渲染排名表 =====
function renderRankingTable(results) {
    const tbody = document.getElementById('ranking-tbody');
    const rc = {'高风险':'stat-risk-high','中风险':'stat-risk-med','低风险':'stat-risk-low'};
    const bm = {'[!!!] 最高优先':'badge-highest','[!!]  高度优先':'badge-high','[*]   一般关注':'badge-normal','[ ]   定期巡检即可':'badge-low'};
    const riskBorder = {'高风险':'ranking-row-high','中风险':'ranking-row-med','低风险':'ranking-row-low'};

    if (results.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:40px;color:var(--text-muted);">无匹配结果</td></tr>`;
        return;
    }

    tbody.innerHTML = results.map(r => {
        // 构建跳转 URL 参数
        const params = r._params || {};
        const urlParams = new URLSearchParams();
        urlParams.set('facility_name', r.facility_name || '');
        urlParams.set('facility_type', r.facility_type || '');
        for (const [k, v] of Object.entries(params)) {
            urlParams.set(k, v || '');
        }
        urlParams.set('user_groups', (r.user_groups||[]).join(','));

        return `<tr class="${riskBorder[r.risk_level]||''}">
            <td><strong>${r.rank}</strong></td>
            <td><strong>${escapeHtml(r.facility_name)}</strong></td>
            <td>${r.facility_type}</td>
            <td><span class="${rc[r.risk_level]||''}" style="font-weight:600;">${r.risk_level}</span></td>
            <td>${r.risk_score.toFixed(2)}</td>
            <td>${r.social_weight}</td>
            <td><strong>${r.priority_score.toFixed(2)}</strong></td>
            <td><span class="priority-badge ${bm[r.priority_level]||'badge-normal'}">${r.priority_level}</span></td>
            <td style="font-size:12px;color:var(--text-secondary);">${r.key_factors}</td>
            <td><a href="/diagnose?${urlParams.toString()}" class="btn btn-sm btn-primary" target="_blank">🔍 诊断</a></td>
        </tr>`;
    }).join('');

    // 统计
    const high = results.filter(r=>r.priority_level==='[!!!] 最高优先').length;
    document.getElementById('facility-count').textContent =
        `共 ${results.length} 个设施（最高优先: ${high}）`;
}

// ===== 导出 CSV =====
function exportRankingCSV() {
    const data = rankingFiltered.length > 0 ? rankingFiltered : rankingResults;
    if (data.length === 0) { showToast('暂无数据可导出', 'error'); return; }
    const headers = ['排名','设施名称','类型','风险等级','风险得分','社会权重','优先级得分','优先级等级','关键影响因素'];
    const rows = data.map(r => [r.rank, r.facility_name, r.facility_type, r.risk_level,
        r.risk_score.toFixed(2), r.social_weight, r.priority_score.toFixed(2), r.priority_level, r.key_factors]);
    const csv = '﻿' + headers.join(',') + '\n' + rows.map(r=>r.map(v=>`"${v}"`).join(',')).join('\n');
    const blob = new Blob([csv], {type:'text/csv;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = '维护优先级排序_export.csv';
    a.click(); URL.revokeObjectURL(url);
    showToast('导出成功');
}

// ===== 工具函数 =====
function escapeHtml(text) {
    const d = document.createElement('div'); d.textContent = text || ''; return d.innerHTML;
}

function updateFacilitySummary(idx, summaryId) {
    const f = facilityList[idx];
    if (!f) return;
    const el = document.getElementById(summaryId);
    if (el) el.textContent = `${f.facility_type} | ${f.material} | ${f.install_age}`;
}

// ===== 同类型设施轮换提示 =====
function checkRotationHint(results) {
    // 按 facility_type 分组
    const groups = {};
    results.forEach(r => {
        const ft = r.facility_type || '其他';
        if (!groups[ft]) groups[ft] = [];
        groups[ft].push(r.facility_name);
    });

    // 过滤出 ≥2 个同类型的组
    const rotatable = Object.entries(groups).filter(([, names]) => names.length >= 2);
    if (rotatable.length === 0) return;

    // 排除不适合轮换的类型
    const NON_ROTATABLE = ['护栏','减速带','无障碍坡道','盲道'];
    const filtered = rotatable.filter(([ft]) => !NON_ROTATABLE.includes(ft));
    if (filtered.length === 0) return;

    // 构建提示消息
    const items = filtered.map(([ft, names]) => `${names.length} 个「${ft}」`).join('、');

    const hintBar = document.getElementById('rotation-hint');
    if (hintBar) hintBar.remove();

    const bar = document.createElement('div');
    bar.id = 'rotation-hint';
    bar.style.cssText = 'margin-top:16px;padding:14px 20px;background:var(--accent-light);border:1.5px solid var(--accent);border-radius:var(--radius);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;';
    bar.innerHTML = `
        <span style="font-size:14px;">🔄 检测到 ${items}，共 ${filtered.length} 类同类型设施可参与轮换。是否生成动态轮换方案？</span>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
            ${filtered.map(([ft]) => `<a href="/rotation?type=${encodeURIComponent(ft)}" class="btn btn-primary btn-sm" target="_blank">${ft} →</a>`).join('')}
            <button class="btn btn-secondary btn-sm" onclick="document.getElementById('rotation-hint').remove()">忽略</button>
        </div>`;
    document.getElementById('ranking-result-card').insertAdjacentElement('afterend', bar);
}

/** 列出字段的合法值，用于报错提示 */
function validOptionsHint(key) {
    const opts = FIELD_OPTS[key];
    if (!opts) return '';
    return '请规定' + ({
        material:'材料',install_age:'安装年龄',water_log:'积水风险',sun_shade:'遮阴',
        use_freq:'使用频率',user_group:'主要使用群体',use_intensity:'使用强度',
        inspect_freq:'巡检频率',repair_time:'维修响应',dependency:'群体依赖度',outage_impact:'停用影响等级',
    }[key] || key) + '的数值范围为 ' + opts.map(o => `"${o}"`).join('、');
}
