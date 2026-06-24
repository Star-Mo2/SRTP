"""
============================================================
 动态轮换引擎 v1.1
 基于 BN 的 exposure + usage 连续概率分布，生成同类型设施循环轮换方案
 v1.1: 用概率期望替代离散标签 → 解决同分排序失效问题
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

    # ---- Step 3: 计算轮换路径 ----
    n = len(sorted_sites)
    segments = []
    for i in range(n):
        from_site = sorted_sites[i]
        to_site = sorted_sites[(i + 1) % n]

        theoretical = round(
            (from_site["_remaining"] + to_site["_remaining"]) / 4, 1
        )
        interval_months = max(T_min, theoretical)

        pressure_diff = round(from_site["_pressure"] - to_site["_pressure"], 5)
        if pressure_diff > 0.001:
            reason = (
                f"「{from_site['facility_name']}」退化压力({from_site['_pressure']:.4f}) "
                f"高于「{to_site['facility_name']}」({to_site['_pressure']:.4f})，"
                f"每 {interval_months:.0f} 个月将设施轮换至低压点位，减缓磨损积累"
            )
        else:
            reason = (
                f"两点退化压力接近(差仅{abs(pressure_diff):.4f})，"
                f"按 T_min={T_min} 个月轮换以均匀磨损"
            )

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
            "reason": reason,
        })

    # ---- Step 4: 寿命延长估算 ----
    # 不轮换：第一个设施在自己点位撑到报废的时间（触发首次更换）
    no_rotation_lifespan = min(s["_remaining"] for s in sorted_sites)

    # 轮换后：所有设施均匀分担退化压力，同时耗尽
    avg_pressure = sum(s["_pressure"] for s in sorted_sites) / n
    # 每个设施在平均压力下的剩余寿命
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

    explanation = (
        f"共 {n} 个同类型设施参与轮换。"
        f"轮换路径按退化压力降序排列：{' → '.join(cycle_names)} → {cycle_names[0]}。"
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
