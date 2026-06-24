"""
============================================================
 动态轮换引擎 v1.2
 基于 BN 的 exposure + usage 连续概率分布，生成同类型设施循环轮换方案
 v1.1: 用概率期望替代离散标签 → 解决同分排序失效问题
 v1.2: 压力相近的点位自动跳过 → 避免无效轮换浪费人力
============================================================
"""

# 材质退化系数（基于 材料曲线/ 文献数据）
MATERIAL_WEAR_FACTOR = {
    "木质": 1.5,
    "金属": 1.0,
    "塑料": 1.2,
}

# 曝光退化速率范围（经验值，对应低暴露→高暴露）
EXPOSURE_RATE_MIN = 0.03   # 低暴露
EXPOSURE_RATE_MAX = 0.15   # 高暴露

# 使用负荷加速因子范围
USAGE_FACTOR_MIN = 0.7     # 低负荷
USAGE_FACTOR_MAX = 1.5     # 高负荷

# 退化压力相似度阈值：两个点位压力相对差 < 15% 视为可跳过轮换
PRESSURE_DIFF_THRESHOLD = 0.15

# 健康度 → 剩余寿命估算（年）
HEALTH_REMAINING_YEARS = {
    1: 9.0, 2: 7.0, 3: 5.0, 4: 2.5, 5: 0.5,
}


def _deg_pressure_from_probs(exposure_probs, usage_probs, material):
    """
    从 BN 中间因子的连续概率分布计算退化压力。
    不再使用离散标签（argmax），而是用概率加权期望值，
    保证即使输入差异微小，输出也会有所区分。

    exposure_score: 0(全低) ~ 1(全高)，连续值
    usage_score:    0(全低) ~ 1(全高)，连续值
    """
    # exposure 概率期望（低暴露→0, 中暴露→0.5, 高暴露→1）
    exp_score = (
        0.0 * exposure_probs.get("低暴露", 0.33) +
        0.5 * exposure_probs.get("中暴露", 0.33) +
        1.0 * exposure_probs.get("高暴露", 0.33)
    )
    # usage 概率期望
    use_score = (
        0.0 * usage_probs.get("低负荷", 0.33) +
        0.5 * usage_probs.get("中负荷", 0.33) +
        1.0 * usage_probs.get("高负荷", 0.33)
    )
    # 材质系数
    mat = MATERIAL_WEAR_FACTOR.get(material, 1.0)
    # 插值到实际退化速率范围
    exp_rate = EXPOSURE_RATE_MIN + exp_score * (EXPOSURE_RATE_MAX - EXPOSURE_RATE_MIN)
    use_factor = USAGE_FACTOR_MIN + use_score * (USAGE_FACTOR_MAX - USAGE_FACTOR_MIN)

    pressure = round(mat * exp_rate * use_factor, 5)
    return {
        "pressure": pressure,
        "exp_score": round(exp_score, 4),
        "use_score": round(use_score, 4),
        "exp_rate": round(exp_rate, 5),
        "use_factor": round(use_factor, 4),
    }


def _site_remaining_years(health, pressure):
    """
    在给定退化压力下，该设施还能撑多少年。
    健康度 → 基准剩余寿命 → 除以退化压力。
    """
    base = HEALTH_REMAINING_YEARS.get(health, 5.0)
    if pressure <= 0:
        return base
    return round(base / pressure, 1)


def generate_rotation_plan(sites, T_min=3):
    """
    核心算法：生成同类型设施的循环轮换方案。

    参数:
      sites: [{facility_name, material, exposure_probs, usage_probs, current_health, same_type_nearby}]
      T_min: 最短可接受轮换间隔（月），用户设定，默认 3

    返回:
      {
        cycle: ["A","B","C","D"],
        segments: [{from, to, interval_months, reason}],
        lifespan_gain_pct: 28.5,
        explanation: "...",
      }
    """
    if len(sites) < 2:
        return {"success": False, "error": "至少需要 2 个同类型设施才能生成轮换方案"}

    # ---- Step 1: 计算退化压力（使用连续概率）----
    for s in sites:
        exp_probs = s.get("exposure_probs", {"低暴露": 0.33, "中暴露": 0.33, "高暴露": 0.33})
        use_probs = s.get("usage_probs", {"低负荷": 0.33, "中负荷": 0.33, "高负荷": 0.33})
        result = _deg_pressure_from_probs(exp_probs, use_probs, s.get("material", "金属"))
        s["_pressure"] = result["pressure"]
        s["_exp_score"] = result["exp_score"]
        s["_use_score"] = result["use_score"]
        s["_exp_rate"] = result["exp_rate"]
        s["_use_factor"] = result["use_factor"]
        s["_health"] = int(s.get("current_health", 3))
        s["_remaining"] = _site_remaining_years(s["_health"], s["_pressure"])

    # ---- Step 2: 按退化压力降序排列 ----
    sorted_sites = sorted(sites, key=lambda s: s["_pressure"], reverse=True)
    n = len(sorted_sites)
    max_p = sorted_sites[0]["_pressure"]
    min_p = sorted_sites[-1]["_pressure"]

    # ---- Step 2.1: 全局检查 —— 全是同级点位则无需轮换（方案 C）----
    if max_p > 0 and (max_p - min_p) / max_p < PRESSURE_DIFF_THRESHOLD:
        names = "、".join(s["facility_name"] for s in sorted_sites)
        return {
            "success": True,
            "all_similar": True,
            "message": (
                f"所有 {n} 个点位退化压力接近（最高 {max_p:.4f}，最低 {min_p:.4f}，"
                f"差异仅 {round((max_p-min_p)/max_p*100,1)}% < {round(PRESSURE_DIFF_THRESHOLD*100)}%），"
                f"无需轮换。建议对所有点位定期巡检即可。"
            ),
            "cycle": [],
            "segments": [],
            "lifespan_gain_pct": 0.0,
            "avg_pressure": round(sum(s["_pressure"] for s in sorted_sites) / n, 4),
            "avg_remaining_no_rotation": round(min(s["_remaining"] for s in sorted_sites), 1),
            "avg_remaining_with_rotation": 0.0,
            "explanation": f"「{names}」退化压力处于同一水平，轮换不会产生明显收益，反而增加搬运成本。",
            "T_min": T_min,
        }

    # ---- Step 3: 计算轮换路径（方案 A：相近点位自动跳过）----
    segments = []
    skip_count = 0
    for i in range(n):
        from_site = sorted_sites[i]
        to_site = sorted_sites[(i + 1) % n]

        # 计算相对压力差（用绝对值 + max 防止循环末尾低压→高压时符号逆转）
        denom = max(from_site["_pressure"], to_site["_pressure"], 0.0001)
        rel_diff = abs(from_site["_pressure"] - to_site["_pressure"]) / denom

        if rel_diff < PRESSURE_DIFF_THRESHOLD:
            # 压力相近 → 跳过此段，不安排轮换
            skip_count += 1
            segments.append({
                "from": from_site["facility_name"],
                "to": to_site["facility_name"],
                "from_pressure": from_site["_pressure"],
                "to_pressure": to_site["_pressure"],
                "from_exp_score": from_site["_exp_score"],
                "from_use_score": from_site["_use_score"],
                "to_exp_score": to_site["_exp_score"],
                "to_use_score": to_site["_use_score"],
                "from_health": from_site["_health"],
                "to_health": to_site["_health"],
                "interval_months": None,  # 跳过，不建议轮换
                "skip": True,
                "reason": (
                    f"「{from_site['facility_name']}」与「{to_site['facility_name']}」"
                    f"退化压力接近（差仅 {round(rel_diff*100,1)}% < {round(PRESSURE_DIFF_THRESHOLD*100)}%），"
                    f"建议跳过，无需在此两点位间轮换"
                ),
            })
        else:
            # 压力差异显著 → 安排轮换
            theoretical = round(
                (from_site["_remaining"] + to_site["_remaining"]) / 4, 1
            )
            interval_months = max(T_min, theoretical)

            segments.append({
                "from": from_site["facility_name"],
                "to": to_site["facility_name"],
                "from_pressure": from_site["_pressure"],
                "to_pressure": to_site["_pressure"],
                "from_exp_score": from_site["_exp_score"],
                "from_use_score": from_site["_use_score"],
                "to_exp_score": to_site["_exp_score"],
                "to_use_score": to_site["_use_score"],
                "from_health": from_site["_health"],
                "to_health": to_site["_health"],
                "interval_months": round(interval_months, 1),
                "skip": False,
                "reason": (
                    f"「{from_site['facility_name']}」退化压力({from_site['_pressure']:.4f}) "
                    f"显著高于「{to_site['facility_name']}」({to_site['_pressure']:.4f})，"
                    f"建议每 {interval_months:.0f} 个月轮换一次"
                ),
            })

    # ---- Step 4: 寿命延长估算 ----
    no_rotation_lifespan = min(s["_remaining"] for s in sorted_sites)
    avg_pressure = sum(s["_pressure"] for s in sorted_sites) / n
    rotation_individual = [
        _site_remaining_years(s["_health"], avg_pressure)
        for s in sorted_sites
    ]
    rotation_lifespan = sum(rotation_individual) / n

    if no_rotation_lifespan > 0:
        lifespan_gain_pct = round(
            (rotation_lifespan - no_rotation_lifespan) / no_rotation_lifespan * 100, 1
        )
    else:
        lifespan_gain_pct = 0.0

    # ---- Step 5: 构建解释 ----
    cycle_names = [s["facility_name"] for s in sorted_sites]
    if lifespan_gain_pct > 20:
        gain_desc = f"首次更换时间预计推迟约 {lifespan_gain_pct}%，集群整体使用寿命显著延长"
    elif lifespan_gain_pct > 5:
        gain_desc = f"首次更换时间预计推迟约 {lifespan_gain_pct}%"
    elif lifespan_gain_pct > 0:
        gain_desc = f"首次更换时间略有推迟（+{lifespan_gain_pct}%）"
    elif lifespan_gain_pct > -5:
        gain_desc = "各点位退化压力接近，轮换主要起均匀磨损作用"
    else:
        gain_desc = "注意：当前存在一个或多个严重磨损设施，建议先更换后再启动轮换计划"

    skip_desc = f"其中 {skip_count} 段因压力相近(差<{round(PRESSURE_DIFF_THRESHOLD*100)}%)建议跳过不轮换" if skip_count > 0 else ""

    explanation = (
        f"共 {n} 个同类型设施参与评估。"
        f"轮换路径按退化压力降序排列：{' → '.join(cycle_names)} → {cycle_names[0]}。"
        f"{skip_desc}。"
        f"{gain_desc}。"
        f"最短轮换间隔设为 {T_min} 个月。"
    )

    return {
        "success": True,
        "cycle": cycle_names,
        "segments": segments,
        "lifespan_gain_pct": lifespan_gain_pct,
        "avg_pressure": round(avg_pressure, 4),
        "avg_remaining_no_rotation": round(no_rotation_lifespan, 1),
        "avg_remaining_with_rotation": round(rotation_lifespan, 1),
        "explanation": explanation,
        "T_min": T_min,
    }
