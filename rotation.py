"""
============================================================
 动态轮换引擎 v1.0
 基于 BN 的 exposure + usage 因子，生成同类型设施循环轮换方案
 不修改 BN 结构——仅复用现有推理结果
============================================================
"""

# 材质退化系数（基于 材料曲线/ 文献数据）
# 数值含义：该材质在单位时间内消耗有效寿命的速率（相对值）
MATERIAL_WEAR_FACTOR = {
    "木质": 1.5,   # 最快（UV + 水协同）
    "金属": 1.0,   # 基准
    "塑料": 1.2,   # UV 脆化（无稳定剂更差，此处取商业级含炭黑）
}

# 曝光等级 → 年退化速率基数（基于文献的经验值）
EXPOSURE_RATE = {
    "低暴露": 0.03,   # 有遮+干燥 → 极慢
    "中暴露": 0.08,   # 中等
    "高暴露": 0.15,   # 暴晒+潮湿 → 快
}

# 使用负荷 → 消耗加速因子
USAGE_LOAD_FACTOR = {
    "低负荷": 0.7,
    "中负荷": 1.0,
    "高负荷": 1.5,
}

# 健康度 → 剩余寿命估算（年），假设总设计寿命约 10 年
HEALTH_REMAINING_YEARS = {
    1: 9.0,    # 完好
    2: 7.0,    # 轻微磨损
    3: 5.0,    # 中等磨损
    4: 2.5,    # 严重磨损
    5: 0.5,    # 濒临报废
}


def _degradation_pressure(exposure_label, usage_label, material):
    """
    计算单个点位的年退化压力（消耗速率）。
    数值越高 → 设施在这个点位老得越快 → 应该优先把新设施放这，
    把旧设施挪走休养。

    退化压力 = 材质系数 × exposure 退化速率 × usage 加速因子
    """
    mat = MATERIAL_WEAR_FACTOR.get(material, 1.0)
    exp_rate = EXPOSURE_RATE.get(exposure_label, 0.08)
    use_factor = USAGE_LOAD_FACTOR.get(usage_label, 1.0)
    return round(mat * exp_rate * use_factor, 4)


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
      sites: [{facility_name, material, exposure, usage, current_health, same_type_nearby}]
      T_min: 最短可接受轮换间隔（月），用户设定，默认 3

    返回:
      {
        cycle: ["A","B","C","D"],       # 轮换顺序（沿退化压力降序）
        segments: [                       # 每段详情
          {from:"A", to:"B", interval_months:8, reason:"..."},
          ...
        ],
        lifespan_gain_pct: 28.5,          # 预计寿命延长
        explanation: "...",               # 可读解释
      }

    算法逻辑：
      1. 计算每个点位的退化压力
      2. 按压力降序排列 → 形成循环路径（高压 → 低压 → 高压）
         - 设施沿压力递减方向流动：新设施去高压点，旧设施来低压点休养
      3. 每段轮换间隔 = max(T_min, 两个点位预期寿命差 / 2)
         - 预期寿命 = 当前健康度映射的剩余年数 / 该点位退化压力
      4. 寿命延长 = (轮换后集群均匀老化寿命 − 不轮换寿命) / 不轮换寿命
    """
    if len(sites) < 2:
        return {
            "success": False,
            "error": "至少需要 2 个同类型设施才能生成轮换方案",
        }

    # ---- Step 1: 计算退化压力 ----
    for s in sites:
        s["_pressure"] = _degradation_pressure(
            s.get("exposure", "中暴露"),
            s.get("usage", "中负荷"),
            s.get("material", "金属"),
        )
        s["_health"] = int(s.get("current_health", 3))
        s["_remaining"] = _site_remaining_years(s["_health"], s["_pressure"])

    # ---- Step 2: 按退化压力降序排列 ----
    sorted_sites = sorted(sites, key=lambda s: s["_pressure"], reverse=True)

    # ---- Step 3: 计算轮换路径 ----
    n = len(sorted_sites)
    segments = []
    for i in range(n):
        from_site = sorted_sites[i]
        to_site = sorted_sites[(i + 1) % n]  # 循环：最后一个回到第一个

        # 轮换间隔：取 T_min 和 理论最优（两点寿命中值）的最大值
        theoretical = round(
            (from_site["_remaining"] + to_site["_remaining"]) / 4, 1
        )
        interval_months = max(T_min, theoretical)

        pressure_diff = round(from_site["_pressure"] - to_site["_pressure"], 4)
        if pressure_diff > 0.01:
            reason = (
                f"「{from_site['facility_name']}」退化压力({from_site['_pressure']:.3f}) "
                f"高于「{to_site['facility_name']}」({to_site['_pressure']:.3f})，"
                f"建议每 {interval_months:.0f} 个月将设施从高压点位移至低压点位"
            )
        else:
            reason = (
                f"两点退化压力相近，按 T_min={T_min} 个月轮换以均匀磨损"
            )

        segments.append({
            "from": from_site["facility_name"],
            "to": to_site["facility_name"],
            "from_pressure": from_site["_pressure"],
            "to_pressure": to_site["_pressure"],
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
