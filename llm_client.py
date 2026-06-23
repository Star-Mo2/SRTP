"""
============================================================
 LLM API 客户端 v2.0
 API Key 从参数传入（浏览器 localStorage），不存服务器
============================================================
"""
import json, os, requests

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def _load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def get_system_prompt():
    return _load_config().get("system_prompt", "")

def save_system_prompt(prompt):
    config = _load_config(); config["system_prompt"] = prompt; _save_config(config)

def get_admin_password():
    return _load_config()["app"].get("admin_password", "admin123")

def save_admin_password(new_password):
    config = _load_config(); config["app"]["admin_password"] = new_password; _save_config(config)

def get_app_title():
    return _load_config()["app"].get("page_title", "")

def get_knowledge_base():
    return _load_config().get("knowledge_base", "")

def save_knowledge_base(text):
    config = _load_config(); config["knowledge_base"] = text; _save_config(config)


def call_llm(api_key, endpoint, model, system_prompt, user_message, timeout=60):
    """
    调用 LLM API（Key 从参数传入，不从 config.json 读取）。
    使用 OpenAI 兼容的 chat/completions 接口。
    """
    if not api_key:    raise ValueError("API Key 未配置。请在设置页面填入你的 API Key。")
    if not endpoint:   raise ValueError("API Endpoint 未配置。")

    # 拼接知识库到系统提示词后面
    kb = get_knowledge_base()
    if kb:
        full_system = system_prompt + "\n\n【维护策略知识库】\n" + kb
    else:
        full_system = system_prompt

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.7, "max_tokens": 1500,
    }
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"LLM API 返回错误 ({resp.status_code}): {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"]


def test_llm_connection(api_key, endpoint, model):
    """测试 LLM 连接（Key 从参数传入）"""
    try:
        if not api_key: return False, "API Key 未配置"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": [{"role":"user","content":"你好，请回复'连接成功'。"}], "max_tokens":20}
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            return True, "连接成功！" + resp.json()["choices"][0]["message"]["content"]
        return False, f"API 返回错误 ({resp.status_code}): {resp.text[:200]}"
    except Exception as e:
        return False, f"连接失败: {str(e)}"
