"""
Flask AI Server for Island Image Generation
- 스케치 이미지 분석 및 매칭
- AI 기반 이미지 생성
- Firebase Storage/Firestore 연동
"""

import os
import csv
import time
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from rich.logging import RichHandler  # 추가

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, storage

from island_retriever import IslandRetriever
from comfyui_client import ComfyUIClient

# from ocr_client import OCRClient
from logger_config import setup_logger
import base64

load_dotenv()


# ==================================================
# 로깅 설정
# ==================================================

LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)

logger = setup_logger("SVR")

# 파일 핸들러는 별도로 추가
file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "server.log"),
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)


# ==================================================
# 환경 변수 및 경로 설정
# ==================================================

# 프로젝트 기준 디렉터리 (현재 파일 기준)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _abs_path(val):
    """Convert env value to absolute path relative to BASE_DIR when not already absolute."""
    if not val:
        return None
    val = str(val).strip()
    if os.path.isabs(val):
        return os.path.normpath(val)
    return os.path.normpath(os.path.join(BASE_DIR, val))


# AI 모델 경로
LORA_MODEL_SAVE_PATH = _abs_path("clip_outline_only.pt")
REAL_ISLAND = _abs_path("ComfyUI\\input\\original")
SKETCH_ISLAND = _abs_path("ComfyUI\\input\\generated_sketches_all")
OUTLINE_ISLAND = _abs_path("ComfyUI\\input\\outline")
KIMHONGDO_PATH = _abs_path("kimhongdo")
OUTPUT_PATH = _abs_path("ComfyUI\\output")

# Firebase 설정
FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS_PATH")
FIREBASE_BUCKET = os.environ.get("FIREBASE_BUCKET")
GENERATED_PATH = os.environ.get("GENERATED_PATH")
FIXED_SKETCH_PATH = os.environ.get("FIXED_SKETCH_PATH")

# 임시 파일 경로
TEMP_DOWNLOAD_DIR = "./temp_sketches"
TIMING_CSV_PATH = os.path.join(LOG_DIR, "timing_log.csv")

os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)


# ==================================================
# CSV 타이밍 로그
# ==================================================
def init_timing_log():
    """타이밍 로그 CSV 파일 초기화"""
    if not os.path.exists(TIMING_CSV_PATH):
        with open(TIMING_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "island_id",
                    "category_input",
                    "category_final",
                    # "selection_type",
                    "generation_time",
                    "total_time",
                    "status",
                ]
            )
        logger.info(f"Timing CSV initialized: {TIMING_CSV_PATH}")


def write_timing_log(
    timestamp,
    island_id,
    category_input,
    category_final,
    # selection_type,
    generation_time,
    total_time,
    status,
):
    """타이밍 정보를 CSV에 기록"""
    try:
        with open(TIMING_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    timestamp,
                    island_id,
                    category_input,
                    category_final,
                    # selection_type,
                    round(generation_time, 2),  # 문자열 포맷팅 제거
                    round(total_time, 2),  # 문자열 포맷팅 제거
                    status,
                ]
            )
    except Exception as e:
        logger.error(f"Failed to write timing log: {e}")


# ==================================================
# 서비스 초기화
# ==================================================


def init_services():
    """Firebase 및 AI 모델 초기화"""

    # Firebase 초기화
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred, {"storageBucket": FIREBASE_BUCKET})
        logger.info("Firebase initialized")

    # IslandRetriever 초기화 (스케치 매칭)
    retriever = IslandRetriever(
        model_save_path=LORA_MODEL_SAVE_PATH, island_folder=SKETCH_ISLAND, batch_size=64
    )
    logger.info(f"IslandRetriever initialized (DB: {SKETCH_ISLAND})")

    # ComfyUI 초기화 (이미지 생성)
    comfyui = ComfyUIClient(
        server_url="http://127.0.0.1:23101",
        output_dir=OUTPUT_PATH,
        kimhongdo_path=KIMHONGDO_PATH,
    )
    logger.info(f"ComfyUI initialized (workflows: {list(comfyui.workflows.keys())})")

    # 미리 모델 로드
    # comfyui.warmup_workflows(island_id=1, island_folder=REAL_ISLAND)

    # OCR 초기화 (텍스트 검출)
    # ocr = OCRClient(languages=["ko", "en"], gpu=True)
    # logger.info("OCR Client initialized")

    return retriever, comfyui
    # return retriever, comfyui, ocr


# ==================================================
# Flask 앱 생성
# ==================================================

app = Flask(__name__)
CORS(app)

# 초기화
init_timing_log()
# island_retriever, comfyui_client, ocr_client = init_services()
island_retriever, comfyui_client = init_services()
db = firestore.client()
storage_client = storage.bucket()


# ==================================================
# API: 스케치 매칭 (/retrieve_island)
# ==================================================


@app.route("/retrieve_island", methods=["GET"])
def retrieve_island():
    """
    스케치 이미지 분석 및 매칭 섬 ID 반환

    처리 과정:
    1. Firebase Storage에서 스케치 다운로드
    2. OCR로 텍스트 검출 (텍스트가 있으면 에러 반환)
    3. AI 모델로 가장 유사한 섬 ID 찾기

    Returns:
        200: {"status": "success", "island_id": int, "similarity": float}
        400: 텍스트 검출 시
        500: 처리 실패 시
    """
    temp_sketch_path = None

    try:
        # 1. 스케치 다운로드
        blob = storage_client.blob(FIXED_SKETCH_PATH)
        temp_sketch_path = os.path.join(TEMP_DOWNLOAD_DIR, "temp_sketch.png")
        blob.download_to_filename(temp_sketch_path)
        logger.info(f"Sketch downloaded from {FIXED_SKETCH_PATH}")

        # # 2. OCR 텍스트 검출
        # logger.info("Checking for text in sketch...")
        # ocr_result = ocr_client.detect_text(
        #     temp_sketch_path, probability_threshold=0.65, text_only=True
        # )

        # if ocr_result["has_text"]:
        #     detected_texts = [det["text"] for det in ocr_result["detections"]]
        #     logger.warning(f"Text detected: {detected_texts}")
        #     return (
        #         jsonify(
        #             {
        #                 "status": "error",
        #                 "message": "Text detected in image. Please draw without text.",
        #             }
        #         ),
        #         400,
        #     )

        # logger.info("No text detected, proceeding with retrieval")

        # 3. AI 매칭
        top_results = island_retriever.retrieve_island(temp_sketch_path, topk=1)
        if not top_results:
            logger.error("AI retrieval failed")
            return jsonify({"status": "error", "message": "AI retrieval failed"}), 500

        matched_filename = top_results[0]["filename"]
        matched_island_id = int(matched_filename.split("_")[-1].split(".")[0])

        logger.info(
            f"Matched Island ID: {matched_island_id} "
            f"(similarity: {top_results[0]['similarity']:.3f})"
        )

        return (
            jsonify(
                {
                    "status": "success",
                    "island_id": matched_island_id,
                    "similarity": top_results[0]["similarity"],
                }
            ),
            200,
        )

    except Exception as e:
        logger.exception(f"Island retrieval failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        # 임시 파일 정리
        if temp_sketch_path and os.path.exists(temp_sketch_path):
            os.remove(temp_sketch_path)


# ==================================================
# API: 이미지 생성 (/generate_image)
# ==================================================


@app.route("/generate_image", methods=["POST"])
def generate_image():
    """
    AI 이미지 생성 및 업로드

    처리 과정:
    1. 요청 데이터 파싱 (island_id, category)
    2. 카테고리 매핑 (대분류 → 세부 카테고리 랜덤 선택)
    3. ComfyUI로 이미지 생성
    4. Firebase Storage 업로드
    5. Firestore 메타데이터 업데이트
    6. 타이밍 로그 기록

    Request Body:
        {
            "sketch_json": {
                "drawingData": {
                    "island_id": int,
                    "category": str  # 대분류 또는 세부 카테고리
                }
            }
        }

    Returns:
        200: {"status": "success", "island_id": int}
        500: 처리 실패 시
    """
    start_time = time.time()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 로그용 변수 초기화
    island_id = category_input = category_final = None
    # selection_type = "UNKNOWN"
    generation_time = 0.0
    status = "error"

    try:
        # 1. 요청 파싱
        data = request.get_json() or {}
        sketch_json = data.get("sketch_json", {})
        drawing_data = sketch_json.get("drawingData", {})

        island_id = drawing_data.get("island_id")
        main_category = drawing_data.get("category", "taste")  # 대주제만 받음

        if island_id is None:
            raise Exception({"message": "island_id is required", "code": 400})

        logger.info(f"Request: Island {island_id}, Main Category '{main_category}'")

        # 4. AI 이미지 생성
        logger.info("Starting AI image generation...")
        gen_start = time.time()
        img_content, img_filename, selected_category = (
            comfyui_client.generate_island_image(
                island_id=island_id,
                main_category=main_category,
                real_island_path=REAL_ISLAND,
                outline_island_path=OUTLINE_ISLAND,
                sketch_island_path=SKETCH_ISLAND,
            )
        )

        generation_time = time.time() - gen_start

        if not img_content:
            logger.error("AI generation failed")
            raise Exception({"message": "AI generation failed", "code": 500})

        # 5. Firebase Storage 업로드
        generated_blob = storage_client.blob(GENERATED_PATH)
        generated_blob.upload_from_string(img_content, content_type="image/png")
        logger.info(f"Image uploaded to {GENERATED_PATH}")

        sketch_json["drawingData"]["category"] = selected_category

        # 6. Firestore 메타데이터 업데이트
        update_data = {
            "matched_island_id": island_id,
            "matched_filename": f"{island_id:03d}.png",
            "updated_at": firestore.SERVER_TIMESTAMP,
            "sketch_json": sketch_json,
        }

        db.collection("config").document("current_task").set(update_data, merge=True)
        logger.info("Firestore updated")

        # 7. 타이밍 로그 기록
        total_time = time.time() - start_time
        status = "success"
        logger.info(
            f"TIMING | Generation: {generation_time:.2f}s | Total: {total_time:.2f}s"
        )

        write_timing_log(
            timestamp,
            island_id,
            main_category,
            selected_category,
            # selection_type,
            generation_time,
            total_time,
            status,
        )

        return (
            jsonify(
                {
                    "status": "success",
                    "island_id": island_id,
                    "generated_image": base64.b64encode(img_content).decode("utf-8"),
                }
            ),
            200,
        )
    except Exception as e:
        total_time = time.time() - start_time
        logger.exception(f"Generation failed after {total_time:.2f}s: {e}")

        write_timing_log(
            timestamp,
            island_id,
            category_input,
            category_final,
            # selection_type,
            generation_time,
            total_time,
            "error",
        )

        # 에러 객체에서 message와 code 추출
        error_obj = (
            e.args[0]
            if isinstance(e.args[0], dict)
            else {"message": str(e), "code": 500}
        )
        return (
            jsonify({"status": "error", "message": error_obj["message"]}),
            error_obj["code"],
        )


# ==================================================
# 서버 실행
# ==================================================

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Flask AI Server Starting...")
    logger.info(f"Storage Path: {FIXED_SKETCH_PATH}")
    logger.info(f"Port: 23100")
    logger.info("=" * 50)

    app.run(host="0.0.0.0", port=23100, debug=False)
