"""
============================================================
 贝叶斯网络推理引擎 v3.1 — 三层分层结构
 12个观测节点 → 4个中间因子 → 1个目标风险
 v3.1: 新增 replaceable（是否可替换模块）+ use_intensity 取值改为静坐/摇晃/冲击
============================================================
"""
import itertools
from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination

# ===== 第一层：12 个可观测叶子节点 =====
MATERIAL       = ["木质","金属","塑料"]
INSTALL_AGE    = ["<3年","3-8年",">8年"]
WATER_LOG      = ["低","中","高"]
SUN_SHADE      = ["暴晒","有遮"]
USE_FREQ       = ["低","中","高"]
USER_GROUP     = ["成人","老人","儿童"]
USE_INTENSITY  = ["静坐","摇晃","冲击"]
INSPECT_FREQ   = ["每周","每月","每季"]
REPAIR_TIME    = ["<3天","3-14天",">14天"]
DEPENDENCY     = ["低","中","高"]
OUTAGE_IMPACT  = ["轻微","中等","严重"]
REPLACEABLE    = ["可替换","不可替换"]

# ===== 第二层：4 个中间因子节点（与旧版兼容） =====
EXPOSURE       = ["低暴露","中暴露","高暴露"]
USAGE          = ["低负荷","中负荷","高负荷"]
MAINTENANCE    = ["维护良好","维护一般","维护滞后"]
SOCIAL_IMPACT  = ["低影响","中影响","高影响"]

# ===== 第三层：目标 =====
RISK           = ["低风险","中风险","高风险"]

# ===== 默认因子权重 =====
DEFAULT_WEIGHTS = {
    "exposure":      1.0,
    "usage":         1.0,
    "maintenance":   1.0,
    "social_impact": 1.0,
}

# ===== 中间节点评分映射 =====
def _score_cpt(parents_combo, score_func, out_states, normalize_max):
    """通用：对父节点组合计算加权分数 → 映射到输出状态的概率分布"""
    low_p, med_p, high_p = [], [], []
    for combo in parents_combo:
        raw = score_func(combo)
        score = min(8, 8 * raw / normalize_max) if normalize_max > 0 else 0
        if score <= 2:      l,m,h = 0.70,0.25,0.05
        elif score <= 3:    l,m,h = 0.50,0.40,0.10
        elif score <= 5:    l,m,h = 0.15,0.60,0.25
        elif score <= 6:    l,m,h = 0.05,0.40,0.55
        else:               l,m,h = 0.03,0.22,0.75
        low_p.append(l); med_p.append(m); high_p.append(h)
    return [low_p, med_p, high_p]


class BNFacilityEngine:
    """三层贝叶斯网络推理引擎"""

    def __init__(self, factor_weights=None):
        self.factor_weights = factor_weights or dict(DEFAULT_WEIGHTS)
        self._rebuild()

    def _rebuild(self):
        self.model = self._build_model()
        self.inference = VariableElimination(self.model)

    def set_weights(self, weights):
        for k in DEFAULT_WEIGHTS:
            if k in weights: self.factor_weights[k] = float(weights[k])
        self._rebuild()

    # ================================================================
    #  构建三层贝叶斯网络
    # ================================================================

    def _build_model(self):
        """三层结构：11个叶子 → 4个中间因子 → 1个目标"""
        model = DiscreteBayesianNetwork([
            # 第二层 → 第三层
            ("exposure",      "failure_risk"),
            ("usage",         "failure_risk"),
            ("maintenance",   "failure_risk"),
            ("social_impact", "failure_risk"),
            # 第一层 → 第二层
            ("material",    "exposure"),
            ("install_age", "exposure"),
            ("water_log",   "exposure"),
            ("sun_shade",   "exposure"),
            ("use_freq",    "usage"),
            ("user_group",  "usage"),
            ("use_intensity","usage"),
            ("inspect_freq","maintenance"),
            ("repair_time", "maintenance"),
            ("replaceable", "maintenance"),
            ("dependency",    "social_impact"),
            ("outage_impact","social_impact"),
        ])

        # ---- 第一层：叶子节点先验概率 ----
        def leaf_cpd(var, states, probs):
            return TabularCPD(var, len(states), [[p] for p in probs], state_names={var: states})

        model.add_cpds(
            leaf_cpd("material",       MATERIAL,       [0.30,0.40,0.30]),
            leaf_cpd("install_age",    INSTALL_AGE,    [0.25,0.45,0.30]),
            leaf_cpd("water_log",      WATER_LOG,      [0.30,0.40,0.30]),
            leaf_cpd("sun_shade",      SUN_SHADE,      [0.50,0.50]),
            leaf_cpd("use_freq",       USE_FREQ,       [0.25,0.45,0.30]),
            leaf_cpd("user_group",     USER_GROUP,     [0.35,0.40,0.25]),
            leaf_cpd("use_intensity",  USE_INTENSITY,  [0.45,0.35,0.20]),
            leaf_cpd("inspect_freq",   INSPECT_FREQ,   [0.20,0.45,0.35]),
            leaf_cpd("repair_time",    REPAIR_TIME,    [0.20,0.45,0.35]),
            leaf_cpd("dependency",     DEPENDENCY,     [0.30,0.40,0.30]),
            leaf_cpd("outage_impact",  OUTAGE_IMPACT,  [0.30,0.40,0.30]),
            leaf_cpd("replaceable",   REPLACEABLE,    [0.50,0.50]),
        )

        # ---- 第二层：中间因子 CPT（用评分函数生成）----
        # exposure: 4 parents, 3*3*3*2=54 combos, max_raw=2+2+2+2=8
        exp_parents = list(itertools.product(range(3),range(3),range(3),range(2)))
        def exp_score(combo): # material, install_age, water_log, sun_shade
            mat_map={0:1.0,1:0.0,2:0.5}; age_map={0:0.0,1:1.0,2:2.0}
            wat_map={0:0.0,1:1.0,2:2.0}; sun_map={0:2.0,1:0.0}
            return (mat_map[combo[0]]+age_map[combo[1]]+wat_map[combo[2]]+sun_map[combo[3]])
        model.add_cpds(TabularCPD("exposure",3, _score_cpt(exp_parents,exp_score,EXPOSURE,8),
            evidence=["material","install_age","water_log","sun_shade"],
            evidence_card=[3,3,3,2],
            state_names={"exposure":EXPOSURE,"material":MATERIAL,"install_age":INSTALL_AGE,
                         "water_log":WATER_LOG,"sun_shade":SUN_SHADE}))

        # usage: 3 parents, 3*3*3=27 combos, max_raw=2+2+2=6
        use_parents = list(itertools.product(range(3),range(3),range(3)))
        def use_score(combo): # use_freq, user_group, use_intensity
            freq_map={0:0.0,1:1.0,2:2.0}; grp_map={0:0.0,1:1.0,2:2.0}; int_map={0:0.0,1:1.0,2:2.0}
            return freq_map[combo[0]]+grp_map[combo[1]]+int_map[combo[2]]
        model.add_cpds(TabularCPD("usage",3, _score_cpt(use_parents,use_score,USAGE,6),
            evidence=["use_freq","user_group","use_intensity"], evidence_card=[3,3,3],
            state_names={"usage":USAGE,"use_freq":USE_FREQ,"user_group":USER_GROUP,
                         "use_intensity":USE_INTENSITY}))

        # maintenance: 3 parents, 2*3*3=18 combos, max_raw=0/1（可/不可替换）+2+2=5
        maint_parents = list(itertools.product(range(2),range(3),range(3)))
        def maint_score(combo): # replaceable, inspect_freq, repair_time
            rep_mod={0:0.0,1:1.0}; ins_map={0:0.0,1:1.0,2:2.0}; rep_map={0:0.0,1:1.0,2:2.0}
            return rep_mod[combo[0]]+ins_map[combo[1]]+rep_map[combo[2]]
        model.add_cpds(TabularCPD("maintenance",3, _score_cpt(maint_parents,maint_score,MAINTENANCE,5),
            evidence=["replaceable","inspect_freq","repair_time"], evidence_card=[2,3,3],
            state_names={"maintenance":MAINTENANCE,"replaceable":REPLACEABLE,
                         "inspect_freq":INSPECT_FREQ,"repair_time":REPAIR_TIME}))

        # social_impact: 2 parents, 3*3=9 combos, max_raw=2+2=4
        soc_parents = list(itertools.product(range(3),range(3)))
        def soc_score(combo): # dependency, outage_impact
            dep_map={0:0.0,1:1.0,2:2.0}; out_map={0:0.0,1:1.0,2:2.0}
            return dep_map[combo[0]]+out_map[combo[1]]
        model.add_cpds(TabularCPD("social_impact",3, _score_cpt(soc_parents,soc_score,SOCIAL_IMPACT,4),
            evidence=["dependency","outage_impact"], evidence_card=[3,3],
            state_names={"social_impact":SOCIAL_IMPACT,"dependency":DEPENDENCY,
                         "outage_impact":OUTAGE_IMPACT}))

        # ---- 第三层：故障风险 CPT（加权四个中间因子）----
        final_parents = list(itertools.product(range(3),range(3),range(3),range(3)))
        w = self.factor_weights
        tw = w["exposure"]+w["usage"]+w["maintenance"]+w["social_impact"]
        final_low,final_med,final_high = [],[],[]
        for (e,u,m,s) in final_parents:
            raw = w["exposure"]*e + w["usage"]*u + w["maintenance"]*m + w["social_impact"]*s
            score = 8*raw/(2*tw) if tw>0 else 0
            if score<=2:     l,m_,h = 0.70,0.25,0.05
            elif score<=3:   l,m_,h = 0.50,0.40,0.10
            elif score<=5:   l,m_,h = 0.15,0.60,0.25
            elif score<=6:   l,m_,h = 0.05,0.40,0.55
            else:            l,m_,h = 0.03,0.22,0.75
            final_low.append(l); final_med.append(m_); final_high.append(h)

        model.add_cpds(TabularCPD("failure_risk",3, [final_low,final_med,final_high],
            evidence=["exposure","usage","maintenance","social_impact"],
            evidence_card=[3,3,3,3],
            state_names={"failure_risk":RISK,"exposure":EXPOSURE,"usage":USAGE,
                         "maintenance":MAINTENANCE,"social_impact":SOCIAL_IMPACT}))

        assert model.check_model(), "模型验证失败！"
        return model

    # ================================================================
    #  评估接口（11 个观测变量）
    # ================================================================

    def evaluate(self, material, install_age, water_log, sun_shade,
                 use_freq, user_group, use_intensity,
                 inspect_freq, repair_time,
                 dependency, outage_impact,
                 facility_type, user_groups, facility_name="", replaceable="可替换"):
        """用 12 个观测变量进行贝叶斯推理（直接联合推理，保留完整概率信息）"""

        evidence = {
            "material":material, "install_age":install_age,
            "water_log":water_log, "sun_shade":sun_shade,
            "use_freq":use_freq, "user_group":user_group,
            "use_intensity":use_intensity,
            "inspect_freq":inspect_freq, "repair_time":repair_time,
            "replaceable":replaceable,
            "dependency":dependency, "outage_impact":outage_impact,
        }

        # ============================================================
        # 核心改进：直接从叶子节点查询 failure_risk
        # pgmpy 的变量消元会自动对中间因子求和，保留完整不确定性
        # 不再使用 argmax 硬赋值（旧方法会丢失概率信息）
        # ============================================================
        risk_q = self.inference.query(variables=["failure_risk"], evidence=evidence)
        pl, pm, ph = round(risk_q.values[0], 4), round(risk_q.values[1], 4), round(risk_q.values[2], 4)
        risk_score = 1 * pl + 2 * pm + 3 * ph

        if ph > 0.4:
            risk_level = "高风险"
        elif pm > 0.5:
            risk_level = "中风险"
        else:
            risk_level = "低风险"

        # ---- 中间因子概率分布（仅供展示，不参与最终计算）----
        exp_q = self.inference.query(variables=["exposure"], evidence=evidence)
        usage_q = self.inference.query(variables=["usage"], evidence=evidence)
        maint_q = self.inference.query(variables=["maintenance"], evidence=evidence)
        soc_q = self.inference.query(variables=["social_impact"], evidence=evidence)

        # 取最大概率的状态作为"标签"（仅用于前端展示摘要）
        exp_val = EXPOSURE[exp_q.values.argmax()]
        use_val = USAGE[usage_q.values.argmax()]
        maint_val = MAINTENANCE[maint_q.values.argmax()]
        soc_val = SOCIAL_IMPACT[soc_q.values.argmax()]

        # 社会影响权重（双层框架）
        social_weight, weight_tier = self._calc_social_weight(facility_type, user_groups)
        priority_score = round(risk_score * social_weight, 2)

        if priority_score >= 2.5:
            priority_level = "[!!!] 最高优先"
        elif priority_score >= 1.8:
            priority_level = "[!!]  高度优先"
        elif priority_score >= 1.2:
            priority_level = "[*]   一般关注"
        else:
            priority_level = "[ ]   定期巡检即可"

        mid_probs = {
            "exposure_prob": {"低暴露": round(exp_q.values[0], 3), "中暴露": round(exp_q.values[1], 3), "高暴露": round(exp_q.values[2], 3)},
            "usage_prob": {"低负荷": round(usage_q.values[0], 3), "中负荷": round(usage_q.values[1], 3), "高负荷": round(usage_q.values[2], 3)},
            "maintenance_prob": {"维护良好": round(maint_q.values[0], 3), "维护一般": round(maint_q.values[1], 3), "维护滞后": round(maint_q.values[2], 3)},
            "social_prob": {"低影响": round(soc_q.values[0], 3), "中影响": round(soc_q.values[1], 3), "高影响": round(soc_q.values[2], 3)},
        }

        return {
            "facility_name": facility_name, "facility_type": facility_type,
            # 11 个原始输入
            "material": material, "install_age": install_age, "water_log": water_log, "sun_shade": sun_shade,
            "use_freq": use_freq, "user_group": user_group, "use_intensity": use_intensity,
            "inspect_freq": inspect_freq, "repair_time": repair_time,
            "replaceable": replaceable,
            "dependency": dependency, "outage_impact": outage_impact,
            # 中间因子标签（仅展示用）
            "exposure": exp_val, "usage": use_val, "maintenance": maint_val, "social_impact": soc_val,
            # 中间因子完整概率分布
            "mid_probs": mid_probs,
            # 最终结果（基于直接联合推理）
            "user_groups": user_groups,
            "risk_level": risk_level, "risk_score": round(risk_score, 2),
            "prob_low": pl, "prob_med": pm, "prob_high": ph,
            "social_weight": social_weight, "weight_tier": weight_tier,
            "priority_score": priority_score, "priority_level": priority_level,
        }

    def _calc_social_weight(self, facility_type, user_groups):
        """双层社会影响权重（外部乘数）"""
        SAFETY=["儿童滑梯","儿童攀爬架","健身器材","盲道","无障碍坡道","护栏","路灯","减速带"]
        SANITATION=["垃圾桶","公厕","排水设施"]
        if facility_type in SAFETY: return 1.0,"硬约束-安全类"
        if facility_type in SANITATION: return 0.95,"硬约束-卫生类"
        ALPHA,BETA=0.6,0.4; dep=0.0
        if "老人" in user_groups: dep+=0.5
        if "儿童" in user_groups: dep+=0.4
        if "成年人" in user_groups: dep+=0.2
        if "行动不便者" in user_groups: dep+=0.6
        if "租户" in user_groups: dep+=0.2
        aesthetic={"长椅":0.3,"凉亭":0.7,"花坛":0.8,"健身器材":0.4,"乒乓球桌":0.3,"晾衣架":0.1,"信息公告栏":0.2}.get(facility_type,0.4)
        return round(ALPHA*min(dep,1.0)+BETA*aesthetic,2),"弹性权重"

    # ================================================================
    #  CPT 规则 + 因子影响
    # ================================================================

    def get_factor_influence(self):
        """各因子边际影响：直接操作中间因子，固定其他为中等。
        同时返回当前权重占比，以便区分"边际效应"和"权重贡献"。
        """
        baseline = {"exposure":"中暴露","usage":"中负荷",
                    "maintenance":"维护一般","social_impact":"中影响"}

        configs = [
            ("exposure", EXPOSURE, "设施退化暴露",
             "日照、雨水、材料老化对设施的侵蚀"),
            ("usage", USAGE, "使用负荷",
             "使用频率和强度，高负荷加速部件磨损"),
            ("maintenance", MAINTENANCE, "治理滞后",
             "物业响应速度与巡检频率，滞后积累故障"),
            ("social_impact", SOCIAL_IMPACT, "正义修正因子",
             "群体依赖程度与停用影响等级"),
        ]

        tw = sum(self.factor_weights.values())

        influences = {}
        for var, states, name, desc in configs:
            vi = []
            for st in states:
                ev = {**baseline, var: st}
                q = self.inference.query(variables=["failure_risk"], evidence=ev)
                vi.append({"state":st, "prob_low":round(q.values[0],3),
                           "prob_med":round(q.values[1],3), "prob_high":round(q.values[2],3)})
            diff = round(vi[-1]["prob_high"] - vi[0]["prob_high"], 3)
            w = self.factor_weights.get(var, 1.0)
            weight_pct = round(w / tw, 3) if tw > 0 else 0.25
            influences[var] = {
                "name":name, "description":desc, "states":vi,
                "lowest":vi[0]["prob_high"], "highest":vi[-1]["prob_high"],
                "diff":diff, "weight_pct": weight_pct,
                "weight_raw": w,
                "interpretation":f"从{states[0]}到{states[-1]}，高风险概率增加{diff:.0%}（当前权重占比 {weight_pct:.0%}）",
            }
        return influences

    def what_if(self, current_evidence, change_var, new_value):
        """单变量 What-if"""
        before = self.inference.query(variables=["failure_risk"], evidence=current_evidence)
        after_ev = {**current_evidence, change_var: new_value}
        after = self.inference.query(variables=["failure_risk"], evidence=after_ev)
        return {
            "change_var":change_var,"old_value":current_evidence.get(change_var,""),"new_value":new_value,
            "before":{"prob_low":round(before.values[0],3),"prob_med":round(before.values[1],3),"prob_high":round(before.values[2],3)},
            "after":{"prob_low":round(after.values[0],3),"prob_med":round(after.values[1],3),"prob_high":round(after.values[2],3)},
        }

    def compare_scenarios(self, material, install_age, water_log, sun_shade,
                          use_freq, user_group, use_intensity,
                          inspect_freq, repair_time,
                          dependency, outage_impact,
                          facility_type, user_groups, facility_name="", replaceable="可替换"):
        """三种维护情景对比"""
        scenarios = {
            "A":{"label":"现状被动维修","desc":"故障发生后才响应","inspect_freq":"每季","repair_time":">14天","cost":"低(短期)→高(长期)"},
            "B":{"label":"定期预防维护","desc":"固定周期巡检","inspect_freq":"每月","repair_time":"3-14天","cost":"中等(周期性)"},
            "C":{"label":"动态调配维护","desc":"基于BN优先处理高风险","inspect_freq":"每周","repair_time":"<3天","cost":"中高(精准投入)"},
        }
        results = {}
        for key,sc in scenarios.items():
            r = self.evaluate(material,install_age,water_log,sun_shade,
                              use_freq,user_group,use_intensity,
                              sc["inspect_freq"],sc["repair_time"],
                              dependency,outage_impact,
                              facility_type,user_groups,facility_name,replaceable)
            results[key] = {**sc,"result":r}
        return results

    def get_network_graph(self):
        """返回三层网络结构数据供前端 SVG"""
        influences = self.get_factor_influence()

        nodes = [
            # 第一层：11 个叶子
            {"id":"material","layer":1,"label":"材料类型","states":MATERIAL,"group":"exposure"},
            {"id":"install_age","layer":1,"label":"安装年龄","states":INSTALL_AGE,"group":"exposure"},
            {"id":"water_log","layer":1,"label":"积水风险","states":WATER_LOG,"group":"exposure"},
            {"id":"sun_shade","layer":1,"label":"遮阴情况","states":SUN_SHADE,"group":"exposure"},
            {"id":"use_freq","layer":1,"label":"使用频率","states":USE_FREQ,"group":"usage"},
            {"id":"user_group","layer":1,"label":"主要群体","states":USER_GROUP,"group":"usage"},
            {"id":"use_intensity","layer":1,"label":"使用强度","states":USE_INTENSITY,"group":"usage"},
            {"id":"inspect_freq","layer":1,"label":"巡检频率","states":INSPECT_FREQ,"group":"maintenance"},
            {"id":"repair_time","layer":1,"label":"维修响应","states":REPAIR_TIME,"group":"maintenance"},
            {"id":"replaceable","layer":1,"label":"是否可替换模块","states":REPLACEABLE,"group":"maintenance"},
            {"id":"dependency","layer":1,"label":"群体依赖度","states":DEPENDENCY,"group":"social"},
            {"id":"outage_impact","layer":1,"label":"停用后影响等级","states":OUTAGE_IMPACT,"group":"social"},
            # 第二层：4 个中间因子
            {"id":"exposure","layer":2,"label":"设施退化暴露","states":EXPOSURE,"group":"exposure"},
            {"id":"usage","layer":2,"label":"使用负荷","states":USAGE,"group":"usage"},
            {"id":"maintenance","layer":2,"label":"治理滞后","states":MAINTENANCE,"group":"maintenance"},
            {"id":"social_impact","layer":2,"label":"正义修正因子","states":SOCIAL_IMPACT,"group":"social"},
            # 第三层：目标
            {"id":"failure_risk","layer":3,"label":"故障中断风险","states":RISK,"group":"target"},
            {"id":"priority","layer":4,"label":"维护优先级","states":["最高优先","高度优先","一般关注","定期巡检"],"group":"target"},
        ]

        edges = [
            {"from":"material","to":"exposure"},{"from":"install_age","to":"exposure"},
            {"from":"water_log","to":"exposure"},{"from":"sun_shade","to":"exposure"},
            {"from":"use_freq","to":"usage"},{"from":"user_group","to":"usage"},
            {"from":"use_intensity","to":"usage"},
            {"from":"inspect_freq","to":"maintenance"},{"from":"repair_time","to":"maintenance"},
            {"from":"replaceable","to":"maintenance"},
            {"from":"dependency","to":"social_impact"},{"from":"outage_impact","to":"social_impact"},
            {"from":"exposure","to":"failure_risk"},{"from":"usage","to":"failure_risk"},
            {"from":"maintenance","to":"failure_risk"},{"from":"social_impact","to":"failure_risk"},
            {"from":"failure_risk","to":"priority"},
        ]

        # 代表性规则示例
        sample_rules = {
            "高风险倾向": [
                {"desc":"木质+>8年+积水+暴晒 → 高暴露；高频+老人+攀爬 → 高负荷；每季巡检+>14天响应 → 维护滞后；高依赖+非无障碍 → 高影响 → 高风险~75%"},
                {"desc":"塑料+>8年+高积水+暴晒 → 高暴露；高频+儿童+攀爬 → 高负荷；每季+>14天 → 维护滞后；高依赖 → 高影响 → 高风险~75%"},
            ],
            "中风险倾向": [
                {"desc":"金属+3-8年+中积水+有遮 → 中暴露；中频+成人+健身 → 中负荷；每月+3-14天 → 维护一般；中依赖 → 中影响 → 中风险~60%"},
                {"desc":"木质+3-8年+低积水+有遮 → 中暴露；中频+老人+静坐 → 中负荷；每周+3-14天 → 维护一般；中依赖 → 中影响 → 中风险~60%"},
            ],
            "低风险倾向": [
                {"desc":"金属+<3年+低积水+有遮 → 低暴露；低频+成人+静坐 → 低负荷；每周+<3天 → 维护良好；低依赖+无障碍 → 低影响 → 低风险~70%"},
                {"desc":"塑料+<3年+低积水+有遮 → 低暴露；低频+成人+静坐 → 低负荷；每周+<3天 → 维护良好；低依赖 → 低影响 → 低风险~70%"},
            ],
        }

        return {"nodes":nodes,"edges":edges,
                "influences":{k:{"name":v["name"],"diff":v["diff"],"interpretation":v["interpretation"],
                                    "weight_pct":v.get("weight_pct",0.25),"weight_raw":v.get("weight_raw",1.0),
                                    "description":v.get("description","")} for k,v in influences.items()},
                "sample_rules":sample_rules}

    @staticmethod
    def ipa_analyze(facilities_scores):
        """简易 IPA 分析"""
        if not facilities_scores: return {"error":"无数据"}
        imps=[f["importance"] for f in facilities_scores]
        perfs=[f["performance"] for f in facilities_scores]
        imp_mean=sum(imps)/len(imps); perf_mean=sum(perfs)/len(perfs)
        quads={"I":[],"II":[],"III":[],"IV":[]}
        for f in facilities_scores:
            imp,perf=f["importance"],f["performance"]
            q = "II" if imp>=imp_mean and perf<perf_mean else "I" if imp>=imp_mean and perf>=perf_mean else "III" if imp<imp_mean and perf<perf_mean else "IV"
            quads[q].append({**f,"quadrant":q})
        return {"imp_mean":round(imp_mean,2),"perf_mean":round(perf_mean,2),"quadrants":quads,"total":len(facilities_scores),"focus":quads["II"]}

    def get_priors(self):
        """返回当前模型中 11 个叶子节点的先验概率分布（用于校准前后对比）"""
        leaf_vars = [
            ("material", MATERIAL), ("install_age", INSTALL_AGE),
            ("water_log", WATER_LOG), ("sun_shade", SUN_SHADE),
            ("use_freq", USE_FREQ), ("user_group", USER_GROUP),
            ("use_intensity", USE_INTENSITY), ("inspect_freq", INSPECT_FREQ),
            ("repair_time", REPAIR_TIME), ("replaceable", REPLACEABLE),
            ("dependency", DEPENDENCY), ("outage_impact", OUTAGE_IMPACT),
        ]
        import numpy as np
        priors = {}
        for var, states in leaf_vars:
            cpd = self.model.get_cpds(var)
            vals = np.array(cpd.values).flatten()
            priors[var] = {s: round(float(vals[i]), 4) for i, s in enumerate(states)}
        return priors

    # ================================================================
    #  轮换辅助：周边同类设施 → social 推断 + 健康度推断
    # ================================================================

    # 周边同类设施可取的值
    SAME_TYPE_NEARBY = ["近(<50m)", "中(50-200m)", "远(>200m)"]
    # 当前健康度可取的值
    CURRENT_HEALTH = ["1-完好", "2-轻微磨损", "3-中等磨损", "4-严重磨损", "5-濒临报废"]

    @staticmethod
    def infer_social_from_nearby(nearby_value):
        """
        根据「周边同类设施」字段，自动推断 outage_impact 和 dependency。
        不进 BN 结构——这是前置推断器，帮用户自动填两个叶子节点。

        映射逻辑：
          近(<50m)   → 坏了走两步就有替代 → 停用影响轻微，依赖度低/中
          中(50-200m) → 有替代但要走一段     → 停用影响中等，依赖度中
          远(>200m)   → 整个片区可能就这一个  → 停用影响严重，依赖度高
        """
        if nearby_value == "近(<50m)":
            return {"outage_impact": "轻微", "dependency": "低"}
        elif nearby_value == "中(50-200m)":
            return {"outage_impact": "中等", "dependency": "中"}
        elif nearby_value == "远(>200m)":
            return {"outage_impact": "严重", "dependency": "高"}
        return {"outage_impact": None, "dependency": None}

    @staticmethod
    def infer_health_from_age(install_age, material="木质"):
        """
        根据安装年限 + 材质，推断默认健康度（1-5）。
        用户可在前端手动覆盖。

        木质老化快 → 同一年限 +1 级
        金属居中   → 直映射
        塑料最慢   → 同一年限 −1 级（但有 UV 脆化风险，暴晒下需另判）
        """
        base = {"<3年": 1, "3-8年": 3, ">8年": 4}
        adj = {"木质": 1, "金属": 0, "塑料": -1}
        raw = base.get(install_age, 3) + adj.get(material, 0)
        return max(1, min(5, raw))

    LABELS_MAP = {
        "material":       {"states": MATERIAL,       "label": "材料类型"},
        "install_age":    {"states": INSTALL_AGE,    "label": "安装年限"},
        "water_log":      {"states": WATER_LOG,      "label": "积水风险"},
        "sun_shade":      {"states": SUN_SHADE,      "label": "遮阴情况"},
        "use_freq":       {"states": USE_FREQ,       "label": "使用频率"},
        "user_group":     {"states": USER_GROUP,     "label": "主要使用群体"},
        "use_intensity":  {"states": USE_INTENSITY,  "label": "使用强度"},
        "inspect_freq":   {"states": INSPECT_FREQ,   "label": "巡检频率"},
        "repair_time":    {"states": REPAIR_TIME,    "label": "维修响应"},
        "replaceable":    {"states": REPLACEABLE,    "label": "是否可替换模块"},
        "dependency":     {"states": DEPENDENCY,     "label": "群体依赖度"},
        "outage_impact":  {"states": OUTAGE_IMPACT,  "label": "停用影响等级"},
    }

    def calibrate_from_data(self, records):
        """
        从实地观测记录校准模型参数。

        支持三层校准（按数据完备程度自动判断）：

        【第1层：叶子节点先验校准】
          - 需求：≥5 条记录，每条包含 11 个观测字段的值
          - 效果：更新各叶子节点的先验概率分布，使模型反映本小区的
            设施材料构成、使用群体比例等实际分布

        【第2层：中间层 CPT 校准】
          - 需求：≥30 条记录且包含 exposure / usage / maintenance / social_impact
            的标注值（需专家逐设施标注，或由 BN 推断辅助标注）
          - 效果：用频率计数更新中间因子 CPT，替代原有的评分函数

        【第3层：最终风险 CPT 校准】
          - 需求：≥50 条记录且包含 risk_level 的真实观测值（需长期跟踪）
          - 效果：用实际故障数据校准最终层 CPT
          - 当前状态：暂未实现

        局限性说明：
          第1层校准基于拉普拉斯平滑的频率计数，第2层同样使用频率计数
          但受限于样本量，大量父节点组合可能缺乏足够观测。
          这是小样本条件下的务实选择——论文 5.4 节已对此进行说明。
        """
        if len(records) < 5:
            return {
                "success": False,
                "error": "至少需要5条观测记录用于校准",
                "count": len(records),
                "calibration_level": "none",
            }

        # ================================================================
        #  第1层：更新 11 个叶子节点的先验概率
        # ================================================================
        leaf_vars = [
            ("material", MATERIAL), ("install_age", INSTALL_AGE),
            ("water_log", WATER_LOG), ("sun_shade", SUN_SHADE),
            ("use_freq", USE_FREQ), ("user_group", USER_GROUP),
            ("use_intensity", USE_INTENSITY), ("inspect_freq", INSPECT_FREQ),
            ("repair_time", REPAIR_TIME), ("replaceable", REPLACEABLE),
            ("dependency", DEPENDENCY), ("outage_impact", OUTAGE_IMPACT),
        ]
        for var, states in leaf_vars:
            counts = {s: 1 for s in states}  # 拉普拉斯平滑（+1 避免零概率）
            for rec in records:
                if rec.get(var) in counts:
                    counts[rec[var]] += 1
            total = sum(counts.values())
            self.model.add_cpds(
                TabularCPD(var, len(states),
                           [[counts[s] / total] for s in states],
                           state_names={var: states}))

        # 检查中间因子标签和风险标签
        middle_labels_present = all(
            any(rec.get(mid) for rec in records)
            for mid in ["exposure", "usage", "maintenance", "social_impact"]
        )
        risk_labels_present = any(rec.get("risk_level") for rec in records)

        # ================================================================
        #  第2层：中间因子 CPT 校准（频率计数）
        # ================================================================
        level2_done = False
        level2_counts = {}

        # 短写→全称映射（用户可能填"高"而非"高暴露"，填"低"而非"维护良好"）
        SHORT_TO_FULL = {
            "exposure":     {"低":"低暴露","中":"中暴露","高":"高暴露"},
            "usage":        {"低":"低负荷","中":"中负荷","高":"高负荷"},
            "maintenance":  {"低":"维护良好","中":"维护一般","高":"维护滞后",
                             "好":"维护良好","一般":"维护一般","滞后":"维护滞后",
                             "良好":"维护良好"},
            "social_impact":{"低":"低影响","中":"中影响","高":"高影响"},
        }

        # 先对所有记录做中间因子值归一化
        for rec in records:
            for var in ["exposure","usage","maintenance","social_impact"]:
                raw = rec.get(var, "")
                if raw and var in SHORT_TO_FULL:
                    rec[var] = SHORT_TO_FULL[var].get(raw, raw)

        if middle_labels_present and len(records) >= 30:
            # 中间因子结构定义
            middle_factors = [
                ("exposure", EXPOSURE,
                 ["material","install_age","water_log","sun_shade"],
                 [MATERIAL, INSTALL_AGE, WATER_LOG, SUN_SHADE],
                 [3, 3, 3, 2]),
                ("usage", USAGE,
                 ["use_freq","user_group","use_intensity"],
                 [USE_FREQ, USER_GROUP, USE_INTENSITY],
                 [3, 3, 3]),
                ("maintenance", MAINTENANCE,
                 ["replaceable","inspect_freq","repair_time"],
                 [REPLACEABLE, INSPECT_FREQ, REPAIR_TIME],
                 [2, 3, 3]),
                ("social_impact", SOCIAL_IMPACT,
                 ["dependency","outage_impact"],
                 [DEPENDENCY, OUTAGE_IMPACT],
                 [3, 3]),
            ]

            for var, out_states, parent_vars, parent_states, cards in middle_factors:
                # 筛选同时有所有父节点和中间因子标签的记录
                valid_recs = []
                for rec in records:
                    if rec.get(var) in out_states:
                        if all(rec.get(p) in ps for p, ps in zip(parent_vars, parent_states)):
                            valid_recs.append(rec)
                level2_counts[var] = len(valid_recs)

                if len(valid_recs) < 5:
                    continue  # 该因子有效记录不足，跳过

                # 构建状态到索引的映射
                state_idx = [{s: i for i, s in enumerate(st)} for st in parent_states]
                out_idx = {s: i for i, s in enumerate(out_states)}

                # 计算所有父节点组合数
                import numpy as np
                n_cols = int(np.prod(cards))

                # 拉普拉斯平滑计数
                counts_2d = [[1 for _ in range(len(out_states))] for _ in range(n_cols)]

                # 频率计数
                for rec in valid_recs:
                    col = 0
                    stride = 1
                    # pgmpy 列序：最后一个 evidence 变化最快
                    for pi in range(len(parent_vars) - 1, -1, -1):
                        col += state_idx[pi][rec[parent_vars[pi]]] * stride
                        stride *= cards[pi]
                    ei = out_idx[rec[var]]
                    counts_2d[col][ei] += 1

                # 归一化每列
                low_p, med_p, high_p = [], [], []
                for col_counts in counts_2d:
                    total = sum(col_counts)
                    low_p.append(col_counts[0] / total)
                    med_p.append(col_counts[1] / total)
                    high_p.append(col_counts[2] / total)

                # 构建 state_names 映射
                sn_map = {var: out_states}
                for pv, ps in zip(parent_vars, parent_states):
                    sn_map[pv] = ps

                self.model.add_cpds(TabularCPD(
                    var, len(out_states), [low_p, med_p, high_p],
                    evidence=parent_vars, evidence_card=cards,
                    state_names=sn_map))

            level2_done = True

        # 仅更新推理引擎，不重建模型（否则会覆盖校准后的 CPD）
        self.inference = VariableElimination(self.model)

        new_priors = self.get_priors()

        # ================================================================
        #  构建返回消息
        # ================================================================
        message_parts = [f"已使用 {len(records)} 条观测记录更新 11 个叶子节点的先验概率"]

        if level2_done:
            detail = "、".join(
                f"{var}({level2_counts.get(var, 0)}条)" for var in
                ["exposure","usage","maintenance","social_impact"]
            )
            message_parts.append(
                f"第2层中间因子 CPT 已用频率计数校准（{detail}有效记录），替代原有评分函数")
            calibration_level = "level2_middle_cpt"
        elif middle_labels_present:
            if len(records) >= 30:
                message_parts.append(
                    "检测到中间因子标签，但有效组合不足（需每个因子 ≥5 条完整记录），未进行第2层校准")
            else:
                message_parts.append(
                    f"检测到中间因子标签，但数据量不足（当前 {len(records)} 条，需 ≥30 条），未进行第2层校准")
            calibration_level = "level1_prior"
        else:
            message_parts.append("未检测到中间因子标签，仅进行了第1层（先验）校准")
            calibration_level = "level1_prior"

        if risk_labels_present:
            if len(records) >= 50:
                message_parts.append(
                    f"检测到真实风险标签且数据量充足（{len(records)} 条），最终层 CPT 校准将在后续版本开放")
            else:
                message_parts.append(
                    f"检测到真实风险标签，但数据量不足（当前 {len(records)} 条，需 ≥50 条），未进行第3层校准")

        return {
            "success": True,
            "count": len(records),
            "calibration_level": calibration_level,
            "message": "；".join(message_parts),
            "has_middle_labels": middle_labels_present,
            "has_risk_labels": risk_labels_present,
            "new_priors": new_priors,
        }


# ===== 全局单例 =====
_engine = None
def get_engine():
    global _engine
    if _engine is None: _engine = BNFacilityEngine()
    return _engine
def rebuild_engine(weights=None):
    global _engine; _engine = BNFacilityEngine(factor_weights=weights)
    return _engine
