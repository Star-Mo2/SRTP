"""
============================================================
 老旧小区适老化设施维护优先级评估 —— 贝叶斯网络模型
 福州大学 SRTP 创新训练项目
============================================================

【文件说明】
 本文件是论文方法演示的简化版本，包含：
   第一部分：贝叶斯网络构建 → 预测设施的「故障中断风险」
   第二部分：社会影响权重计算 → 综合得出「维护优先级」

 ⚠ 注意：本文件使用 2 层简化模型（4 中间因子 → 1 目标风险），
 仅用于论文局部方法演示和独立测试。
 Web 应用实际使用的引擎是 engine.py（3 层模型：11 叶子 → 4 中间 → 1 风险），
 两者结构不同，请勿混淆或以本文件为准。

【运行方式】
 方式1（推荐）：在 PyCharm 中打开此文件，右键 → Run 'bayesian_network'
 方式2：在终端中执行 → python bayesian_network.py

【依赖库】
 pip install pgmpy pandas
"""

import itertools
from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination
import pandas as pd

# ============================================================
#  第一部分：构建贝叶斯网络
# ============================================================

print("=" * 60)
print("  老旧小区适老化设施维护优先级评估系统")
print("  基于贝叶斯网络 + 社会影响权重")
print("=" * 60)

# ----- 1.1 定义网络结构 -----
# 箭头方向：父节点 → 子节点（原因 → 结果）
# 四个父节点（可观测的原因）→ 一个子节点（故障风险，需要推断）

model = DiscreteBayesianNetwork([
    ("exposure",      "failure_risk"),   # 设施老化暴露 → 故障风险
    ("usage",         "failure_risk"),   # 使用负荷     → 故障风险
    ("maintenance",   "failure_risk"),   # 维护滞后     → 故障风险
    ("social_impact", "failure_risk"),   # 社会影响因素 → 故障风险
])

# ----- 1.2 定义各节点的可能取值（离散化） -----
# 每个节点的状态，对应论文表3的离散化方案

# 设施老化暴露（综合了材料、安装年龄、日照、积水等因素）
exposure_states = ["低暴露", "中暴露", "高暴露"]

# 使用负荷（综合了使用频率、使用强度、主要群体）
usage_states = ["低负荷", "中负荷", "高负荷"]

# 维护滞后（综合了维护响应时间、巡检频率）
maintenance_states = ["维护良好", "维护一般", "维护滞后"]

# 社会影响因素（群体依赖程度、停用后影响等级等）
social_states = ["低影响", "中影响", "高影响"]

# 故障中断风险（我们想推断的目标！）
risk_states = ["低风险", "中风险", "高风险"]

# ----- 1.3 定义条件概率表（CPT） -----
# 这一步是贝叶斯网络的核心：定义"在父节点各种组合下，子节点的概率"
# 现阶段使用「专家经验」赋值（论文中提到的 CPT 初始值来源）
# 后续收集到实地数据后，可以替换为数据驱动的概率

# --- 父节点1: 设施老化暴露（先验概率,即没有父节点时的初始信念）---
cpd_exposure = TabularCPD(
    variable="exposure",
    variable_card=3,   # 3种状态
    values=[
        [0.30],  # 低暴露: 30% 的设施属于此类
        [0.40],  # 中暴露: 40%
        [0.30],  # 高暴露: 30%
    ],
    state_names={"exposure": exposure_states},
)

# --- 父节点2: 使用负荷 ---
cpd_usage = TabularCPD(
    variable="usage",
    variable_card=3,
    values=[
        [0.25],  # 低负荷
        [0.45],  # 中负荷
        [0.30],  # 高负荷
    ],
    state_names={"usage": usage_states},
)

# --- 父节点3: 维护滞后 ---
cpd_maintenance = TabularCPD(
    variable="maintenance",
    variable_card=3,
    values=[
        [0.20],  # 维护良好
        [0.45],  # 维护一般
        [0.35],  # 维护滞后
    ],
    state_names={"maintenance": maintenance_states},
)

# --- 父节点4: 社会影响因素 ---
cpd_social = TabularCPD(
    variable="social_impact",
    variable_card=3,
    values=[
        [0.35],  # 低影响
        [0.40],  # 中影响
        [0.25],  # 高影响
    ],
    state_names={"social_impact": social_states},
)

# --- 子节点: 故障中断风险（核心CPT！）---
# 这个表有 3×3×3×3 = 81 行，每一行定义了在特定父节点组合下的风险概率
# 逻辑：暴露高 + 负荷高 + 维护差 + 环境差 → 大概率高风险
#       暴露低 + 负荷低 + 维护好 + 环境好 → 大概率低风险

def build_failure_cpt():
    """
    根据专家经验构建故障风险的条件概率表。

    打分逻辑（可调整）：
      - 暴露:     低=0, 中=1, 高=2
      - 负荷:     低=0, 中=1, 高=2
      - 维护:    良好=0, 一般=1, 滞后=2
      - 社会影响: 低=0, 中=1, 高=2
      - 总分 = 暴露 + 负荷 + 维护 + 社会影响（范围 0~8）
      - 0-2分 → 大概率低风险
      - 3-5分 → 大概率中风险
      - 6-8分 → 大概率高风险

    注意：这里四个因子等权重相加。论文中通过「因子权重」
    在最终层实现差异化加权（见 engine.py 的 DEFAULT_WEIGHTS）。
    """
    # 生成所有 81 种父节点组合
    parents = list(itertools.product(
        range(3),  # exposure      0,1,2
        range(3),  # usage         0,1,2
        range(3),  # maintenance   0,1,2
        range(3),  # social_impact 0,1,2
    ))

    low_risk_probs = []
    med_risk_probs = []
    high_risk_probs = []

    for (e, u, m, s) in parents:
        score = e + u + m + s  # 0 ~ 8
        if score <= 2:
            # 低风险主导
            low, med, high = 0.70, 0.25, 0.05
        elif score <= 3:
            low, med, high = 0.50, 0.40, 0.10
        elif score <= 5:
            low, med, high = 0.15, 0.60, 0.25
        elif score <= 6:
            low, med, high = 0.05, 0.40, 0.55
        else:  # score >= 7
            low, med, high = 0.03, 0.22, 0.75
        low_risk_probs.append(low)
        med_risk_probs.append(med)
        high_risk_probs.append(high)

    return [low_risk_probs, med_risk_probs, high_risk_probs]

cpd_failure = TabularCPD(
    variable="failure_risk",
    variable_card=3,
    values=build_failure_cpt(),
    evidence=["exposure", "usage", "maintenance", "social_impact"],
    evidence_card=[3, 3, 3, 3],
    state_names={
        "failure_risk": risk_states,
        "exposure": exposure_states,
        "usage": usage_states,
        "maintenance": maintenance_states,
        "social_impact": social_states,
    },
)

# ----- 1.4 将CPT添加到模型中 -----
model.add_cpds(cpd_exposure, cpd_usage, cpd_maintenance, cpd_social, cpd_failure)

# ----- 1.5 验证模型 -----
assert model.check_model(), "模型结构或CPT定义有误，请检查！"
print("\n[OK] 贝叶斯网络模型验证通过！\n")
print("网络结构：", [str(edge) for edge in model.edges()])

# ----- 1.6 创建推理引擎 -----
inference = VariableElimination(model)


# ============================================================
#  第二部分：设施维护优先级评估
# ============================================================

print("\n" + "=" * 60)
print("  设施样本评估")
print("=" * 60)

# ----- 2.1 定义社会影响权重 -----
# 对应论文5.3节的"硬性约束 + 弹性权重"双层框架
#
# 第一层（硬约束）：涉及安全/卫生 → 自动最高优先级
# 第二层（弹性权重）：日常设施 → 综合"使用依赖性 D"和"环境美学性 E"

def calculate_social_weight(facility_type, user_groups):
    """
    计算社会影响权重。

    参数:
      facility_type: 设施类型（如"儿童滑梯""健身器材""长椅""花坛"）
      user_groups:   主要使用群体列表（如["老人","儿童"]）

    返回:
      weight: 社会影响权重 (0~1 之间，越高越需要优先维护)
      tier:   权重层级说明
    """
    # ---- 第一层：硬性约束 ----
    # 涉及人身安全的设施 → 自动最高权重
    SAFETY_CRITICAL = ["儿童滑梯", "儿童攀爬架", "健身器材", "盲道",
                       "无障碍坡道", "护栏", "路灯"]
    # 涉及公共卫生的设施 → 自动最高权重
    SANITATION_CRITICAL = ["垃圾桶", "公厕", "排水设施"]

    if facility_type in SAFETY_CRITICAL:
        return 1.0, "硬约束-安全类"
    if facility_type in SANITATION_CRITICAL:
        return 0.95, "硬约束-卫生类"

    # ---- 第二层：弹性权重 ----
    # α = 使用依赖性权重（默认 0.6）
    # β = 环境美学权重（默认 0.4）
    ALPHA = 0.6  # 使用依赖性
    BETA = 0.4   # 环境美学性

    # 使用依赖性分数 D：看谁在用、多依赖
    dependency_score = 0.0
    if "老人" in user_groups:
        dependency_score += 0.5  # 老人对休憩设施依赖高
    if "儿童" in user_groups:
        dependency_score += 0.4  # 儿童对游乐设施依赖高
    if "成年人" in user_groups:
        dependency_score += 0.2
    if "行动不便者" in user_groups:
        dependency_score += 0.6
    if "租户" in user_groups:
        dependency_score += 0.2

    # 设施类型对应的环境美学分数 E
    aesthetic_scores = {
        "长椅":       0.3,   # 功能为主
        "凉亭":       0.7,   # 观赏性强
        "花坛":       0.8,   # 纯观赏
        "健身器材":   0.4,   # 功能为主
        "乒乓球桌":   0.3,   # 功能为主
        "晾衣架":     0.1,   # 纯功能
        "信息公告栏": 0.2,   # 功能为主
    }
    aesthetic_score = aesthetic_scores.get(facility_type, 0.4)

    weight = ALPHA * min(dependency_score, 1.0) + BETA * aesthetic_score
    return round(weight, 2), "弹性权重"


# ----- 2.2 定义样本设施 -----
# 模拟 10 个典型设施，对应论文表4的预判

sample_facilities = [
    {
        "id": "F01", "name": "中心广场长椅",
        "type": "长椅",
        "exposure": "高暴露", "usage": "高负荷",
        "maintenance": "维护滞后", "social_impact": "高影响",
        "user_groups": ["老人", "儿童", "成年人"],
    },
    {
        "id": "F02", "name": "儿童滑梯",
        "type": "儿童滑梯",
        "exposure": "高暴露", "usage": "高负荷",
        "maintenance": "维护一般", "social_impact": "高影响",
        "user_groups": ["儿童"],
    },
    {
        "id": "F03", "name": "健身区扭腰器",
        "type": "健身器材",
        "exposure": "中暴露", "usage": "中负荷",
        "maintenance": "维护一般", "social_impact": "中影响",
        "user_groups": ["老人", "成年人"],
    },
    {
        "id": "F04", "name": "北门晾衣架",
        "type": "晾衣架",
        "exposure": "高暴露", "usage": "中负荷",
        "maintenance": "维护滞后", "social_impact": "中影响",
        "user_groups": ["租户", "老人"],
    },
    {
        "id": "F05", "name": "小花园凉亭",
        "type": "凉亭",
        "exposure": "中暴露", "usage": "低负荷",
        "maintenance": "维护良好", "social_impact": "低影响",
        "user_groups": ["老人", "成年人"],
    },
    {
        "id": "F06", "name": "幼儿园旁护栏",
        "type": "护栏",
        "exposure": "中暴露", "usage": "低负荷",
        "maintenance": "维护一般", "social_impact": "高影响",
        "user_groups": ["儿童", "成年人"],
    },
    {
        "id": "F07", "name": "东侧乒乓球桌",
        "type": "乒乓球桌",
        "exposure": "高暴露", "usage": "高负荷",
        "maintenance": "维护滞后", "social_impact": "中影响",
        "user_groups": ["成年人", "儿童"],
    },
    {
        "id": "F08", "name": "花坛休息区座椅",
        "type": "长椅",
        "exposure": "低暴露", "usage": "中负荷",
        "maintenance": "维护良好", "social_impact": "低影响",
        "user_groups": ["老人", "成年人"],
    },
    {
        "id": "F09", "name": "小区入口信息栏",
        "type": "信息公告栏",
        "exposure": "中暴露", "usage": "低负荷",
        "maintenance": "维护良好", "social_impact": "低影响",
        "user_groups": ["成年人", "租户"],
    },
    {
        "id": "F10", "name": "南侧无障碍坡道",
        "type": "无障碍坡道",
        "exposure": "高暴露", "usage": "中负荷",
        "maintenance": "维护一般", "social_impact": "高影响",
        "user_groups": ["行动不便者", "老人"],
    },
]


# ----- 2.3 逐设施评估 -----
results = []

for fac in sample_facilities:
    # Step 1: 贝叶斯推理 —— 预测故障中断风险
    query = inference.query(
        variables=["failure_risk"],
        evidence={
            "exposure":      fac["exposure"],
            "usage":         fac["usage"],
            "maintenance":   fac["maintenance"],
            "social_impact": fac["social_impact"],
        },
    )

    # 提取各风险等级的概率
    risk_probs = {
        "低风险": round(query.values[0], 4),
        "中风险": round(query.values[1], 4),
        "高风险": round(query.values[2], 4),
    }

    # 风险得分（用于排序）：低=1, 中=2, 高=3，按概率加权
    risk_score = (
        1 * risk_probs["低风险"] +
        2 * risk_probs["中风险"] +
        3 * risk_probs["高风险"]
    )

    # 判断主要风险等级
    if risk_probs["高风险"] > 0.4:
        risk_level = "高风险"
    elif risk_probs["中风险"] > 0.5:
        risk_level = "中风险"
    else:
        risk_level = "低风险"

    # Step 2: 社会影响权重
    social_weight, weight_tier = calculate_social_weight(
        fac["type"], fac["user_groups"]
    )

    # Step 3: 维护优先级 = 风险得分 × 社会影响权重
    priority_score = round(risk_score * social_weight, 2)

    # 优先级等级
    if priority_score >= 2.5:
        priority_level = "[!!!] 最高优先"
    elif priority_score >= 1.8:
        priority_level = "[!!]  高度优先"
    elif priority_score >= 1.2:
        priority_level = "[*]   一般关注"
    else:
        priority_level = "[ ]   定期巡检即可"

    results.append({
        "设施ID":   fac["id"],
        "设施名称": fac["name"],
        "设施类型": fac["type"],
        "风险等级": risk_level,
        "低风险概率": risk_probs["低风险"],
        "中风险概率": risk_probs["中风险"],
        "高风险概率": risk_probs["高风险"],
        "风险得分":  round(risk_score, 2),
        "社会权重":  social_weight,
        "权重类型":  weight_tier,
        "优先级得分": priority_score,
        "优先级":    priority_level,
    })

# ----- 2.4 输出结果 -----
df = pd.DataFrame(results)
# 按优先级得分降序排列
df = df.sort_values("优先级得分", ascending=False).reset_index(drop=True)

print("\n--- 设施维护优先级评估结果 ---\n")
print(df.to_string(index=False, columns=[
    "设施ID", "设施名称", "风险等级", "风险得分",
    "社会权重", "优先级得分", "优先级"
]))

# ----- 2.5 打印关键设施详情 -----
print("\n" + "=" * 60)
print("  重点设施详细分析")
print("=" * 60)

for _, row in df.iterrows():
    if row["优先级"] in ["[!!!] 最高优先", "[!!]  高度优先"]:
        print(f"\n{'-' * 50}")
        print(f"【{row['设施ID']}】{row['设施名称']}（{row['设施类型']}）")
        print(f"  风险概率分布：低={row['低风险概率']:.2%}  "
              f"中={row['中风险概率']:.2%}  高={row['高风险概率']:.2%}")
        print(f"  风险得分={row['风险得分']}  社会权重={row['社会权重']}  "
              f"优先级得分={row['优先级得分']}")
        print(f"  评估结论：{row['优先级']}")


# ============================================================
#  第三部分：交互式推理（可选）
# ============================================================

print("\n" + "=" * 60)
print("  交互式推理演示")
print("=" * 60)
print("""
现在你可以像医生问诊一样，输入某个设施的情况，
模型会立刻给出它的故障风险预测。

示例输入格式：
  暴露等级: 高暴露
  负荷等级: 高负荷
  维护状态: 维护滞后
  社会影响: 高影响
""")

# 取消下面三行注释即可启用交互模式（在 PyCharm 终端中使用）
# custom_evidence = {
#     "exposure":    input("暴露等级（低暴露/中暴露/高暴露）: ").strip(),
#     "usage":       input("负荷等级（低负荷/中负荷/高负荷）: ").strip(),
#     "maintenance": input("维护状态（维护良好/维护一般/维护滞后）: ").strip(),
#     "social_impact": input("社会影响（低影响/中影响/高影响）: ").strip(),
# }
# if all(v in {"低暴露","中暴露","高暴露","低负荷","中负荷","高负荷",
#              "维护良好","维护一般","维护滞后","低影响","中影响","高影响"}
#        for v in custom_evidence.values()):
#     result = inference.query(variables=["failure_risk"], evidence=custom_evidence)
#     print(f"\n预测结果：低风险={result.values[0]:.1%}  "
#           f"中风险={result.values[1]:.1%}  高风险={result.values[2]:.1%}")


# ============================================================
#  第四部分：模型信息摘要（用于论文）
# ============================================================

print("\n" + "=" * 60)
print("  模型摘要（可用于论文方法部分）")
print("=" * 60)
print(f"""
  模型类型: 离散贝叶斯网络（Discrete Bayesian Network）
  节点数量: {len(model.nodes())} 个
  边数量:   {len(model.edges())} 条
  父节点:   设施老化暴露、使用负荷、维护滞后、社会影响因素
  目标节点: 故障中断风险（高/中/低）
  推理方法: 精确变量消元（Variable Elimination）
  权重框架: 双层社会影响权重（硬约束 + 弹性权重）

  优先级计算: P = R × W
    其中 R = 贝叶斯推断的故障风险期望得分
          W = 社会影响权重（基于设施类型和群体依赖性）
""")

print("=" * 60)
print("  运行完毕！可查看上方结果表格。")
print("  如需调整概率参数，请编辑 build_failure_cpt() 函数。")
print("=" * 60)
