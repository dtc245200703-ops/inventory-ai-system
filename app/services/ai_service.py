import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types


# =========================================================
# LOAD .ENV
# =========================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")
GEMINI_THINKING_LEVEL = os.getenv(
    "GEMINI_THINKING_LEVEL",
    "high"
)


# =========================================================
# PROMPTS
# =========================================================

BASE_DIR = Path(__file__).resolve().parents[2]
PROMPT_DIR = BASE_DIR / "prompts"


def load_prompt(filename: str) -> str:
    prompt_path = PROMPT_DIR / filename

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy prompt: {prompt_path}"
        )

    return prompt_path.read_text(
        encoding="utf-8"
    )


# =========================================================
# GEMINI CLIENT
# =========================================================

def get_client():
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "Chưa cấu hình GEMINI_API_KEY trong file .env"
        )

    if not GEMINI_MODEL:
        raise RuntimeError(
            "Chưa cấu hình GEMINI_MODEL trong file .env"
        )

    return genai.Client(
        api_key=GEMINI_API_KEY
    )


# =========================================================
# HÀM GỌI GEMINI CHUNG
# =========================================================

def generate_ai_text(
    system_prompt: str,
    data: Any
) -> str:

    client = get_client()

    data_json = json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
        default=str
    )

    user_prompt = f"""
DỮ LIỆU KHO DO HỆ THỐNG CUNG CẤP:

{data_json}

Hãy phân tích dữ liệu trên theo đúng yêu cầu.

QUY TẮC BẮT BUỘC:
- Không tự tạo số liệu.
- Không suy đoán số liệu không được cung cấp.
- Không thay đổi dữ liệu kho.
- Nếu thiếu dữ liệu phải nói rõ.
- Trả lời bằng tiếng Việt.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            thinking_config=types.ThinkingConfig(
                thinking_level=GEMINI_THINKING_LEVEL
            )
        )
    )

    if not response.text:
        raise RuntimeError(
            "Gemini không trả về nội dung."
        )

    return response.text.strip()


# =========================================================
# AI SINH BÁO CÁO KHO
# =========================================================

def generate_inventory_report(data):

    if not data:
        return "Không có dữ liệu tồn kho để tạo báo cáo."

    prompt = load_prompt(
        "inventory_report.txt"
    )

    return generate_ai_text(
        prompt,
        data
    )


# =========================================================
# AI GỢI Ý NHẬP HÀNG
# =========================================================

def generate_restock_suggestion(data):

    if not data:
        return "Không có dữ liệu để gợi ý nhập hàng."

    prompt = load_prompt(
        "restock_suggestion.txt"
    )

    return generate_ai_text(
        prompt,
        data
    )


# =========================================================
# AI PHÂN TÍCH BẤT THƯỜNG
# =========================================================

def generate_anomaly_summary(data):

    if not data:
        return "Không có dữ liệu để phân tích biến động."

    prompt = load_prompt(
        "inventory_anomaly.txt"
    )

    return generate_ai_text(
        prompt,
        data
    )