/**
 * ============================================================
 *  动态轮换页 v1.0
 *  同类型设施导入 → BN评估 → 生成循环轮换方案
 * ============================================================
 */

let rotationSites = [];       // 已导入/添加的同类型设施列表
let parsedRowsCache = [];     // 解析后的全部行（用于类型筛选回传）
let rotationPlan = null;      // 后端返回的轮换方案

const FIELD_OPTS = {
    material:['木质','金属','塑料'],
    install_age:['<3年','3-8年','>8年'],
    water_log:['低','中','高'],
    sun_shade:['暴晒','有遮'],
    use_freq:['低','中','高'],
    user_group:['成人','老人','儿童'],
    use_intensity:['静坐','摇晃','冲击'],
    inspect_freq:['每周','每月','每季'],
    repair_time:['<3天','3-14天','>14天'],
    dependency:['低','中','高'],
    outage_impact:['轻微','中等','严重'],
    replaceable:['可替换','不可替换'],
    same_type_nearby:['近(<50m)','中(50-200m)','远(>200m)'],
};
const HEALTH_OPTS = ['1','2','3','4','5'];

function onTypeChange() {
    // 切换类型时清空已有数据
    if (rotationSites.length > 0) {
        if (!confirm('切换类型将清空当前点位数据，确定吗？')) {
            const type = rotationSites[0]?.facility_type || '';
            document.getElementById('rotation-facility-type').value = type;
            return;
        }
        rotationSites = [];
        renderSitesTable();
    }
}

// ===== CSV/XLSX 导入 =====
async function handleRotationImport(event) {
    const file = event.target.files[0];
    if (!file) return;
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!['.csv','.xlsx'].includes(ext)) { showToast('仅支持 .csv 或 .xlsx 文件','error'); event.target.value=''; return; }

    const status = document.getElementById('import-status');
    status.innerHTML = '<span style="color:var(--text-secondary);">⏳ 解析中...</span>';

    const fd = new FormData(); fd.append('file', file);
    try {
        const resp = await fetch('/api/rotation/import', {method:'POST', body: fd});
        const data = await resp.json();
        if (!data.success) { status.innerHTML = `<span style="color:var(--danger);">❌ ${data.error}</span>`; event.target.value=''; return; }

        parsedRowsCache = data.rows;

        if (data.invalid_rows && data.invalid_rows.length > 0) {
            const msg = data.invalid_rows.map(r => `第${r.index}行「${r.name}」：${r.issues.join('、')}`).join('<br>');
            status.innerHTML = `<span style="color:var(--warning);">⚠️ 解析完成（${data.count}条），发现以下问题：<br>${msg}</span>`;
        } else {
            status.innerHTML = `<span style="color:var(--success);">✅ 解析完成（${data.count}条记录）</span>`;
        }

        if (data.multi_type) {
            // 多类型 → 弹窗让用户选
            showTypeSelectModal(data.types);
        } else if (data.types.length === 1) {
            // 单一类型 → 直接导入
            await importFilteredType(data.types[0]);
        }
    } catch(err) {
        status.innerHTML = `<span style="color:var(--danger);">网络错误: ${err.message}</span>`;
    }
    event.target.value = '';
}

function showTypeSelectModal(types) {
    const modal = document.getElementById('type-select-modal');
    document.getElementById('type-select-body').innerHTML =
        `检测到 ${types.length} 种设施类型：<strong>${types.join('、')}</strong><br>请选择要导入轮换方案的类型：`;
    document.getElementById('type-select-actions').innerHTML =
        types.map(t => `<button class="btn btn-primary btn-sm" onclick="selectTypeAndClose('${escapeJs(t)}')">${t}</button>`).join('')
        + `<button class="btn btn-secondary btn-sm" onclick="document.getElementById('type-select-modal').style.display='none'">取消</button>`;
    modal.style.display = 'flex';
}

function selectTypeAndClose(type) {
    document.getElementById('type-select-modal').style.display = 'none';
    importFilteredType(type);
}

async function importFilteredType(type) {
    const status = document.getElementById('import-status');
    status.innerHTML = '<span style="color:var(--text-secondary);">⏳ 导入中...</span>';

    try {
        const resp = await fetch('/api/rotation/import-filtered', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({rows: parsedRowsCache, selected_type: type}),
        });
        const data = await resp.json();
        if (!data.success) { status.innerHTML = `<span style="color:var(--danger);">❌ ${data.error}</span>`; return; }

        // 同步设施类型
        document.getElementById('rotation-facility-type').value = type;

        // 用导入结果重置列表
        rotationSites = data.rows.map(r => ({
            facility_name: r.facility_name || r.facility_type || '未命名',
            facility_type: type,
            material: r.material || '金属',
            install_age: r.install_age || '3-8年',
            water_log: r.water_log || '中',
            sun_shade: r.sun_shade || '有遮',
            use_freq: r.use_freq || '中',
            user_group: r.user_group || '成人',
            use_intensity: r.use_intensity || '静坐',
            inspect_freq: r.inspect_freq || '每月',
            repair_time: r.repair_time || '3-14天',
            replaceable: r.replaceable || '可替换',
            dependency: r.dependency || '中',
            outage_impact: r.outage_impact || '中等',
            same_type_nearby: r.same_type_nearby || '',
            current_health: r.current_health || '3',
            user_groups: r.user_groups ? r.user_groups.split(',').map(s=>s.trim()) : ['老人'],
        }));

        renderSitesTable();

        let msg = `✅ 已导入 ${data.count} 个「${type}」点位。`;
        if (data.warnings && data.warnings.length > 0) {
            const wmsgs = data.warnings.flatMap(w => w.flags).join('；');
            msg += `<br><span style="color:var(--warning);">⚠️ ${wmsgs}</span>`;
        }
        status.innerHTML = msg;
    } catch(err) {
        status.innerHTML = `<span style="color:var(--danger);">网络错误: ${err.message}</span>`;
    }
}

// ===== 手动添加点位 =====
function addManualSite() {
    const type = document.getElementById('rotation-facility-type').value;
    if (!type) { showToast('请先选择设施类型', 'error'); return; }

    const idx = rotationSites.length;
    rotationSites.push({
        facility_name: `${type}-${idx+1}`,
        facility_type: type,
        material: '金属', install_age: '3-8年', water_log: '中', sun_shade: '有遮',
        use_freq: '中', user_group: '成人', use_intensity: '静坐',
        inspect_freq: '每月', repair_time: '3-14天',
        dependency: '中', outage_impact: '中等',
        same_type_nearby: '', current_health: '3',
        user_groups: ['老人'],
    });
    renderSitesTable();
}

function removeSite(idx) {
    rotationSites.splice(idx, 1);
    renderSitesTable();
}

// ===== 渲染点位可编辑表格 =====
function renderSitesTable() {
    const tbody = document.getElementById('sites-tbody');
    const card = document.getElementById('sites-card');

    if (rotationSites.length === 0) {
        card.style.display = 'none';
        tbody.innerHTML = '';
        return;
    }
    card.style.display = '';
    document.getElementById('plan-card').style.display = 'none';

    const fields = [
        {key:'facility_name', label:'名称', type:'text'},
        {key:'material', label:'材料', type:'select', opts:FIELD_OPTS.material},
        {key:'install_age', label:'安装年限', type:'select', opts:FIELD_OPTS.install_age},
        {key:'water_log', label:'积水', type:'select', opts:FIELD_OPTS.water_log},
        {key:'sun_shade', label:'遮阴', type:'select', opts:FIELD_OPTS.sun_shade},
        {key:'use_freq', label:'使用频率', type:'select', opts:FIELD_OPTS.use_freq},
        {key:'user_group', label:'主要群体', type:'select', opts:FIELD_OPTS.user_group},
        {key:'use_intensity', label:'使用强度', type:'select', opts:FIELD_OPTS.use_intensity},
        {key:'inspect_freq', label:'巡检', type:'select', opts:FIELD_OPTS.inspect_freq},
        {key:'repair_time', label:'维修响应', type:'select', opts:FIELD_OPTS.repair_time},
        {key:'replaceable', label:'可替换模块', type:'select', opts:FIELD_OPTS.replaceable},
        {key:'dependency', label:'依赖度', type:'select', opts:FIELD_OPTS.dependency},
        {key:'outage_impact', label:'停用影响', type:'select', opts:FIELD_OPTS.outage_impact},
        {key:'same_type_nearby', label:'周边同类设施', type:'select', opts:FIELD_OPTS.same_type_nearby},
        {key:'current_health', label:'健康度(1-5)', type:'select', opts:HEALTH_OPTS},
    ];

    tbody.innerHTML = rotationSites.map((s, idx) => {
        return `<tr>
            ${fields.map(f => {
                if (f.key === 'facility_name') {
                    return `<td><input type="text" class="form-input" style="min-width:100px;font-size:12px;padding:4px 6px;" value="${escapeHtml(s[f.key]||'')}" onchange="rotationSites[${idx}].${f.key}=this.value"></td>`;
                }
                const cur = s[f.key] || '';
                return `<td><select class="form-select" style="font-size:12px;padding:4px 6px;min-width:80px;" onchange="rotationSites[${idx}].${f.key}=this.value">
                    <option value="">--</option>
                    ${f.opts.map(o=>`<option value="${o}" ${cur===o?'selected':''}>${o}</option>`).join('')}
                </select></td>`;
            }).join('')}
            <td><button class="btn btn-danger btn-sm" onclick="removeSite(${idx})">✕</button></td>
        </tr>`;
    }).join('');
}

// ===== 生成轮换方案 =====
async function generateRotationPlan() {
    if (rotationSites.length < 2) { showToast('至少需要 2 个同类型设施', 'error'); return; }

    // 有效性检查
    const errors = [];
    rotationSites.forEach((s, idx) => {
        for (const key of Object.keys(FIELD_OPTS)) {
            const val = s[key] || '';
            if (val && !FIELD_OPTS[key].includes(val)) {
                errors.push(`点位 #${idx+1}「${s.facility_name}」：${key} 值「${val}」无效`);
            }
        }
        const hl = s.current_health || '';
        if (hl && !HEALTH_OPTS.includes(String(hl))) {
            errors.push(`点位 #${idx+1}「${s.facility_name}」：健康度值「${hl}」无效（应填 1-5）`);
        }
    });
    if (errors.length > 0) {
        const msg = errors.slice(0, 4).join('<br>') + (errors.length > 4 ? `<br>还有 ${errors.length-4} 处错误...` : '');
        showToast(msg, 'error');
        return;
    }

    const T_min = parseInt(document.getElementById('rotation-tmin').value) || 3;

    const btn = document.getElementById('generate-btn');
    btn.disabled = true; btn.textContent = '⏳ 计算中...';

    try {
        const resp = await fetch('/api/rotation/plan', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({sites: rotationSites, T_min}),
        });
        const data = await resp.json();
        if (!data.success) { showToast(data.error || '生成失败', 'error'); btn.disabled=false; btn.textContent='🔄 生成轮换方案'; return; }

        rotationPlan = data.plan;
        renderPlan(data.plan);
        document.getElementById('plan-card').style.display = '';
        showToast('轮换方案生成成功！');
    } catch(err) { showToast('网络错误: '+err.message, 'error'); }
    finally { btn.disabled = false; btn.textContent = '🔄 生成轮换方案'; }
}

// ===== 渲染轮换方案 =====
function renderPlan(plan) {
    // 全部压力相近的特殊情况（方案 C）
    if (plan.all_similar) {
        document.getElementById('plan-summary').innerHTML = `
            <div style="text-align:center;padding:20px;">
                <div style="font-size:48px;margin-bottom:12px;">✅</div>
                <div style="font-size:16px;font-weight:600;color:var(--success);">${plan.message}</div>
            </div>`;
        document.getElementById('rotation-diagram').innerHTML = '';
        document.getElementById('plan-segments-tbody').innerHTML = '';
        return;
    }

    // 摘要
    const gainColor = plan.lifespan_gain_pct > 5 ? 'var(--success)' : (plan.lifespan_gain_pct > 0 ? 'var(--warning)' : 'var(--text-secondary)');
    document.getElementById('plan-summary').innerHTML = `
        <div style="margin-bottom:8px;"><strong>轮换类型：</strong>${rotationSites[0]?.facility_type||''} × ${plan.cycle.length} 个点位</div>
        <div><strong>预计寿命延长：</strong><span style="font-size:22px;font-weight:700;color:${gainColor};">${plan.lifespan_gain_pct > 0 ? '+' : ''}${plan.lifespan_gain_pct}%</span></div>
        <div style="font-size:11px;color:var(--text-muted);">不轮换平均剩余: ${plan.avg_remaining_no_rotation} 年 → 轮换后: ${plan.avg_remaining_with_rotation} 年</div>`;

    // SVG 路径图
    renderRotationDiagram(plan);

    // 各段详情表（含压力分解 + 跳过标记）
    const segTbody = document.getElementById('plan-segments-tbody');
    segTbody.innerHTML = plan.segments.map((seg, i) => {
        const fromDetail = `退化压力:${seg.from_pressure?.toFixed(4)||'—'} | exp:${(seg.from_exp_score*100).toFixed(1)}% | use:${(seg.from_use_score*100).toFixed(1)}% | 健康:${seg.from_health}`;
        const toDetail = `退化压力:${seg.to_pressure?.toFixed(4)||'—'} | exp:${(seg.to_exp_score*100).toFixed(1)}% | use:${(seg.to_use_score*100).toFixed(1)}% | 健康:${seg.to_health}`;
        if (seg.skip) {
            return `<tr style="opacity:0.45;background:var(--bg-secondary);">
                <td><strong>#${i+1}</strong></td>
                <td>📍 ${escapeHtml(seg.from)}</td>
                <td>📍 ${escapeHtml(seg.to)}</td>
                <td><span style="font-size:13px;color:var(--text-muted);text-decoration:line-through;">— ⚠️ 跳过</span></td>
                <td style="font-size:11px;max-width:300px;color:var(--text-muted);">${seg.reason}</td>
            </tr>`;
        }
        return `<tr>
            <td><strong>#${i+1}</strong></td>
            <td>📍 ${escapeHtml(seg.from)}<br><span style="font-size:10px;color:var(--text-muted);">${fromDetail}</span></td>
            <td>📍 ${escapeHtml(seg.to)}<br><span style="font-size:10px;color:var(--text-muted);">${toDetail}</span></td>
            <td><strong style="font-size:16px;color:var(--accent);">${seg.interval_months} 个月</strong></td>
            <td style="font-size:12px;max-width:300px;">${seg.reason}</td>
        </tr>`;
    }).join('');
}

// ===== SVG 轮换路径图 =====
function renderRotationDiagram(plan) {
    const n = plan.cycle.length;
    if (n < 2) return;

    // 简化的水平流程图
    const cycleNames = [...plan.cycle, plan.cycle[0]]; // 回到起点形成环
    let html = '<div style="display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:0;padding:20px;background:var(--bg-secondary);border-radius:var(--radius);overflow-x:auto;">';

    for (let i = 0; i < cycleNames.length; i++) {
        const isLast = i === cycleNames.length - 1;
        const seg = plan.segments[i % n];
        const name = cycleNames[i];

        // 节点
        const bgColors = ['#C17D53','#D4956B','#D4A853','#8BAA7D','#7BA4B5','#B8A898'];
        const bg = bgColors[i % bgColors.length];
        html += `<div style="text-align:center;flex-shrink:0;">
            <div style="width:80px;height:80px;border-radius:50%;background:${bg};color:#FFF;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;box-shadow:var(--shadow);margin:0 4px;">
                ${escapeHtml(name.length > 6 ? name.slice(0,6)+'…' : name)}
            </div>
            <div style="font-size:10px;color:var(--text-muted);margin-top:4px;">${i < n ? `压力 ${plan.segments[i]?.from_pressure?.toFixed(3)||'—'}` : ''}</div>
            ${i < n ? `<div style="font-size:10px;color:var(--text-muted);">健康度 ${plan.segments[i]?.from_health||'—'}</div>` : ''}
        </div>`;

        // 箭头 + 间隔标注（或跳过）
        if (!isLast) {
            if (seg.skip) {
                html += `<div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;margin:0 4px;opacity:0.4;">
                    <div style="font-size:10px;font-weight:600;color:var(--text-muted);white-space:nowrap;text-decoration:line-through;">跳过</div>
                    <div style="font-size:20px;color:var(--text-muted);">→</div>
                </div>`;
            } else {
                html += `<div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;margin:0 4px;">
                    <div style="font-size:11px;font-weight:600;color:var(--accent);white-space:nowrap;">${seg.interval_months}个月 →</div>
                    <div style="font-size:20px;color:var(--accent);">→</div>
                </div>`;
            }
        }
    }

    html += '</div>';

    // 如果屏幕宽，加文字说明
    html += `<p style="text-align:center;font-size:12px;color:var(--text-secondary);margin-top:12px;">
        循环路径：${plan.cycle.join(' → ')} → ${plan.cycle[0]}（回到起点）
    </p>`;

    document.getElementById('rotation-diagram').innerHTML = html;
}

// ===== 导出 CSV =====
function exportRotationCSV() {
    if (!rotationPlan) { showToast('请先生成轮换方案', 'error'); return; }

    const headers = ['段序','从(高压点位)','从退化压力','从健康度','至(低压点位)','至退化压力','至健康度','建议轮换间隔(月)','预计寿命延长(%)','说明'];
    const rows = rotationPlan.segments.map((seg, i) => [
        i+1, seg.from, seg.from_pressure, seg.from_health,
        seg.to, seg.to_pressure, seg.to_health,
        seg.interval_months, i===0 ? rotationPlan.lifespan_gain_pct : '', seg.reason,
    ]);
    const csv = '﻿' + headers.join(',') + '\n' + rows.map(r=>r.map(v=>`"${v}"`).join(',')).join('\n');
    const blob = new Blob([csv], {type:'text/csv;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `轮换方案_${rotationSites[0]?.facility_type||'未分类'}_export.csv`;
    a.click(); URL.revokeObjectURL(url);
    showToast('导出成功');
}

// ===== 工具函数 =====
function escapeHtml(str) {
    const d = document.createElement('div'); d.textContent = str || ''; return d.innerHTML;
}
function escapeJs(str) {
    return str.replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'\\"');
}
