"""
ComfyUI Client for AI Image Generation
"""

import requests
import json
import uuid
import time
import os
import random
import glob
from logger_config import setup_logger
from enum import Enum
from dotenv import load_dotenv

logger = setup_logger("CFY")

load_dotenv()

# ===================================================================
# 1. 단일 소스(Single Source of Truth)가 될 Theme Enum 정의
# (str, Enum)을 상속하면 Theme.MONET == "monet" 처럼 문자열과 비교 가능
# ===================================================================
class Theme(str, Enum):
    """모든 섬 테마 상수를 정의합니다."""

    # art
    DANSAEKHWA = "dansaekhwa"
    MONET = "monet"
    VANGOGH = "vangogh"
    POLLOCK = "pollock"
    ORIGAMI = "origami"
    KLIMT = "klimt"

    # nature
    AUTUMN = "autumn"
    WINTER = "winter"
    CAMELLIA = "camellia"
    CHERRY = "cherry"
    HYDRAGEA = "hydragea"
    CANOLA = "canola"

    # taste
    CONSTELLATION = "constellation"
    SUMUK = "sumuk"
    ENTERTAINMENT = "entertainment"
    LANDSCAPE = "landscape"
    WAVE = "wave"
    FANTASY = "fantasy"

    # heritage
    KIMHONGDO = "kimhongdo"
    SINYUNBOK = "sinyunbok"
    JASU = "jasu"
    BAEKJA = "baekja"
    TRADITIONAL = "traditional"
    JAGE = "jage"
# ===================================================================
# 2. Enum을 참조하는 카테고리 매핑
# ===================================================================
CATEGORY_MAPPING = {
    "art": [
        Theme.DANSAEKHWA,
        Theme.MONET,
        Theme.VANGOGH,
        Theme.POLLOCK,
        Theme.ORIGAMI,
        Theme.KLIMT
    ],
    "nature": [
        Theme.AUTUMN,
        Theme.WINTER,
        Theme.CAMELLIA,
        Theme.CHERRY,
        Theme.HYDRAGEA,
        Theme.CANOLA
    ],
    "taste": [
        Theme.CONSTELLATION,
        Theme.SUMUK,
        Theme.ENTERTAINMENT,
        Theme.LANDSCAPE,
        Theme.WAVE,
        Theme.FANTASY
    ],
    "heritage": [
        Theme.KIMHONGDO,
        Theme.SINYUNBOK,
        Theme.JASU,
        Theme.BAEKJA,
        Theme.TRADITIONAL,
        Theme.JAGE
    ],
}
# ===================================================================
# 3. Enum을 참조하는 섬별 블랙리스트 (오름차순 정렬)
# ===================================================================
ISLAND_CATEGORY_BLACKLIST = {
    10: [Theme.KIMHONGDO],
    12: [Theme.TRADITIONAL],
    13: [Theme.WAVE],
    17: [Theme.WAVE],
    23: [Theme.KIMHONGDO],
    27: [Theme.WAVE],
    39: [Theme.CANOLA],
    41: [Theme.KLIMT],
    46: [Theme.SINYUNBOK],
    71: [Theme.CANOLA],
    84: [
        # art (6개)
        Theme.DANSAEKHWA, Theme.MONET, Theme.VANGOGH,
        Theme.POLLOCK, Theme.ORIGAMI, Theme.KLIMT,
        # nature (6개)
        Theme.AUTUMN, Theme.WINTER, Theme.CAMELLIA,
        Theme.CHERRY, Theme.HYDRAGEA, Theme.CANOLA,
        # taste (6개)
        Theme.CONSTELLATION, Theme.SUMUK, Theme.ENTERTAINMENT,
        Theme.LANDSCAPE, Theme.WAVE, Theme.FANTASY,
        # heritage (6개)
        Theme.KIMHONGDO, Theme.SINYUNBOK, Theme.JASU,
        Theme.BAEKJA, Theme.TRADITIONAL, Theme.JAGE
    ],
    85: [Theme.BAEKJA],
    86: [Theme.BAEKJA],
    91: [Theme.SINYUNBOK],
    97: [Theme.BAEKJA, Theme.KIMHONGDO],
    100: [Theme.BAEKJA],
    105: [Theme.KIMHONGDO],
    106: [Theme.KIMHONGDO],
    111: [Theme.JAGE, Theme.KIMHONGDO],
    120: [Theme.KIMHONGDO],
    125: [Theme.KLIMT, Theme.KIMHONGDO],
    133: [Theme.KLIMT],
    144: [Theme.KIMHONGDO],
    145: [Theme.KIMHONGDO],
    146: [Theme.KIMHONGDO],
    148: [Theme.KIMHONGDO],
    157: [Theme.KIMHONGDO],
    159: [Theme.BAEKJA],
    167: [Theme.WAVE],
    207: [Theme.JAGE, Theme.SINYUNBOK],
    213: [Theme.MONET, Theme.KIMHONGDO],
    218: [Theme.JASU],
    238: [Theme.CANOLA],
    241: [Theme.ENTERTAINMENT, Theme.CANOLA],
    243 : [Theme.JASU],
    257 : [Theme.JASU],
    279: [Theme.CHERRY],
    281: [Theme.KIMHONGDO],
    283: [Theme.FANTASY],
    284: [Theme.POLLOCK],
    296 : [Theme.JASU],
    302 : [Theme.JASU],
    304: [Theme.KIMHONGDO],
    311: [Theme.VANGOGH],
    317: [Theme.LANDSCAPE],
    322: [Theme.BAEKJA],
    323: [Theme.CANOLA],
    335: [Theme.HYDRAGEA],
    337: [Theme.CHERRY, Theme.KIMHONGDO, Theme.WAVE],
    338: [Theme.KIMHONGDO],
    353: [Theme.KIMHONGDO]
}
# Theme Enum 아래에 추가
# ===================================================================
# 4. 특수 이미지 폴더를 사용하는 카테고리
# ===================================================================
OUTLINE_CATEGORIES = {Theme.CONSTELLATION}
SKETCH_CATEGORIES = {Theme.BAEKJA, Theme.TRADITIONAL, Theme.JAGE}

class ComfyUIClient:
    def __init__(
            self,
            server_url="http://127.0.0.1:23101",
            workflow_dir="./workflows",
            output_dir=None,
            kimhongdo_path=None
    ):
        self.server_url = server_url
        self.workflow_dir = workflow_dir
        self.kimhongdo_path = kimhongdo_path
        # ComfyUI output 폴더 경로 (기본값)
        if output_dir is None:
            comfyui_root = os.path.dirname(os.path.dirname(workflow_dir))
            self.output_dir = os.path.join(comfyui_root, "ComfyUI", "output")
        else:
            self.output_dir = output_dir
        self.workflows = self._load_workflows()

    def _load_workflows(self):
        """워크플로우 JSON 파일들을 미리 로드합니다."""
        workflows = {}
        if not os.path.exists(self.workflow_dir):
            logger.warning(f"Workflow directory not found: {self.workflow_dir}")
            return workflows

        for filename in os.listdir(self.workflow_dir):
            if filename.endswith(".json"):
                category_name = filename.replace(".json", "")
                filepath = os.path.join(self.workflow_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        workflows[category_name] = json.load(f)
                    logger.info(f"Loaded workflow: {category_name}")
                except Exception as e:
                    logger.error(f"Failed to load {filename}: {e}")

        return workflows

    def delete_previous_outputs(self, pattern="generated_island_*.png"):
        """이전에 생성된 이미지를 삭제합니다."""
        try:
            search_pattern = os.path.join(self.output_dir, pattern)
            old_files = glob.glob(search_pattern)

            for file_path in old_files:
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted old file: {os.path.basename(file_path)}")
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")

            if not old_files:
                logger.info(f"No old files found matching pattern: {pattern}")

        except Exception as e:
            logger.error(f"Failed to clean output directory: {e}")

    def queue_prompt(self, prompt):
        """ComfyUI에 워크플로우를 제출합니다."""
        p = {"prompt": prompt, "client_id": str(uuid.uuid4())}
        data = json.dumps(p).encode("utf-8")
        response = requests.post(f"{self.server_url}/prompt", data=data)
        return response.json()

    def get_image(self, filename, subfolder, folder_type):
        """생성된 이미지를 다운로드합니다."""
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url = f"{self.server_url}/view"
        response = requests.get(url, params=data)
        return response.content

    def get_history(self, prompt_id):
        """워크플로우 실행 결과를 확인합니다."""
        response = requests.get(f"{self.server_url}/history/{prompt_id}")
        return response.json()

    # File: `server/comfyui_client.py`
    def generate_island_image(self, island_id, main_category, real_island_path, outline_island_path,
                              sketch_island_path):
        """
        정해진 워크플로우로 AI 이미지를 생성합니다.
        카테고리에 따라 적절한 이미지 폴더를 자동 선택합니다.

        Args:
            island_id: 섬 번호
            main_category: 대주제 카테고리
            real_island_path: 실사 이미지 폴더 경로
            outline_island_path: 외곽선 이미지 폴더 경로
            sketch_island_path: 스케치 이미지 폴더 경로

        Returns:
            (이미지 바이너리, 파일명) 튜플
        """
        # 0. 대주제인지 세부 주제인지 판별
        is_main_category = main_category in CATEGORY_MAPPING

        if is_main_category:
            # 대주제인 경우: 블랙리스트 필터링 후 랜덤 선택
            sub_categories = CATEGORY_MAPPING[main_category]

            # 1. 블랙리스트 필터링
            blacklist = ISLAND_CATEGORY_BLACKLIST.get(island_id, [])
            available_categories = [cat for cat in sub_categories if cat not in blacklist]

            if not available_categories:
                logger.warning(f"Island {island_id}: All categories blacklisted")
                return None, None, None

            # 2. 랜덤 선택
            category = random.choice(available_categories)
            logger.info(
                f"Island {island_id}: Selected '{category}' from main category '{main_category}' "
                f"({len(available_categories)}/{len(sub_categories)} available)"
            )
        else:
            # 세부 주제인 경우: 직접 사용 (블랙리스트 체크 안 함)
            try:
                category = Theme(main_category)
                logger.info(f"Island {island_id}: Using specific theme '{category}' (no blacklist check)")
            except ValueError:
                logger.error(f"Invalid category: {main_category}")
                return None, None, None

        # ============ 김홍도 테마 특수 처리 ============
        if category == Theme.KIMHONGDO:
            fixed_image_path = os.path.join(self.kimhongdo_path, f"{island_id:03d}.png")

            try:
                with open(fixed_image_path, "rb") as f:
                    img_content = f.read()

                filename = f"kimhongdo_{island_id:03d}.png"
                logger.info(f"Returned fixed KIMHONGDO image: {fixed_image_path}")
                return img_content, filename, category

            except FileNotFoundError:
                logger.error(f"KIMHONGDO fixed image not found: {fixed_image_path}")
                return None, None, None
            except Exception as e:
                logger.error(f"Failed to read KIMHONGDO image: {e}")
                return None, None, None
        # =============================================

        # 3. 카테고리에 따라 이미지 폴더 선택
        if category in OUTLINE_CATEGORIES:
            island_folder = outline_island_path
            folder_type = "outline"
        elif category in SKETCH_CATEGORIES:
            island_folder = sketch_island_path
            folder_type = "sketch"
        else:
            island_folder = real_island_path
            folder_type = "real"

        logger.info(f"Using {folder_type} folder for category '{category}'")

        # 4. 이전 출력 파일 삭제
        self.delete_previous_outputs()

        # 5. 워크플로우 선택
        if category not in self.workflows:
            logger.error(f"Category '{category}' not found")
            return None, None, None

        workflow = self.workflows[category]
        workflow_copy = json.loads(json.dumps(workflow))

        # 6. LoadImage 노드 업데이트
        load_image_found = False
        for node_id, node_data in workflow_copy.items():
            if node_data.get("class_type") == "LoadImage":
                image_filename = f"{island_folder}/{island_id:03d}.png"
                node_data["inputs"]["image"] = image_filename
                logger.info(f"Updated LoadImage: {image_filename}")
                load_image_found = True
                break

        if not load_image_found:
            logger.warning(f"No LoadImage node found")
            return None, None, None

        # 이하 기존 코드(시드 변경, SaveImage 업데이트, 제출, 대기, 다운로드 등)는 동일하게 동작)
        # 7. KSampler 노드들의 시드를 각각 랜덤으로 변경
        ksampler_count = 0
        for node_id, node_data in workflow_copy.items():
            if node_data.get("class_type") == "KSampler":
                # 각 KSampler마다 다른 랜덤 시드 생성
                random_seed = random.randint(0, 999999999999999)
                node_data["inputs"]["seed"] = random_seed
                logger.info(f"Updated KSampler node {node_id} with seed={random_seed}")
                ksampler_count += 1

        if ksampler_count > 0:
            logger.info(f"Updated {ksampler_count} KSampler nodes with different seeds")
        else:
            logger.warning(f"No KSampler nodes found in workflow '{category}'")

        # 8. SaveImage 노드 찾아서 filename_prefix 고정
        save_image_found = False
        for node_id, node_data in workflow_copy.items():
            if node_data.get("class_type") == "SaveImage":
                node_data["inputs"]["filename_prefix"] = "generated_island"

                logger.info(f"Updated SaveImage node {node_id}:")
                logger.info(f"     filename_prefix=generated_island")
                save_image_found = True
                break

        if not save_image_found:
            logger.warning(f"No 'SaveImage' node found in workflow '{category}'")
            return None, None, None

        # 9. 수정된 워크플로우 제출
        try:
            result = self.queue_prompt(workflow_copy)
            prompt_id = result["prompt_id"]
            logger.info(f"Submitted workflow with prompt_id: {prompt_id}")
        except Exception as e:
            logger.error(f"Failed to submit workflow: {e}")
            return None, None, None

        # 10. 생성 완료까지 대기 (타임아웃 시 작업 중단)
        max_wait = 120  # seconds
        elapsed_time = 0
        check_interval = 2

        while True:
            time.sleep(check_interval)
            elapsed_time += check_interval

            # 타임아웃 체크 (60초 초과 시 작업 중단 후 실패 반환)
            if elapsed_time >= max_wait:
                logger.error(f"ComfyUI generation timed out after {elapsed_time}s - interrupting")
                try:
                    # 인터럽트 신호 전송
                    requests.post(f"{self.server_url}/interrupt")
                    logger.info("Sent interrupt signal to ComfyUI")

                except Exception as e:
                    logger.warning(f"Failed to interrupt ComfyUI: {e}")
                return None, None, None

            try:
                history = self.get_history(prompt_id)
                if prompt_id in history:
                    entry = history[prompt_id]
                    status = entry.get("status", {})

                    if status.get("status_str") == "error":
                        error_msgs = status.get("messages", [])
                        logger.error(f"ComfyUI execution failed: {error_msgs}")
                        return None, None, None

                    if status.get("completed", False) or "outputs" in entry:
                        logger.info(f"Image generation completed in {elapsed_time}s")
                        break

                if elapsed_time % 10 == 0:
                    logger.info(f"Waiting for generation... ({elapsed_time}s elapsed)")

            except Exception as e:
                logger.warning(f"Error checking history: {e}")

        # 11. 생성된 이미지 다운로드
        if prompt_id not in history:
            logger.error(f"No history found for prompt_id: {prompt_id}")
            return None, None, None

        entry = history[prompt_id]
        outputs = entry.get("outputs", {})

        if not outputs:
            logger.error(f"No outputs in history")
            return None, None, None

        for node_id in outputs:
            if "images" in outputs[node_id]:
                images = outputs[node_id]["images"]
                if images:
                    img_data = images[0]
                    img_content = self.get_image(
                        img_data["filename"],
                        img_data.get("subfolder", ""),
                        img_data.get("type", "output"),
                    )

                    if img_content and len(img_content) > 0:
                        return img_content, img_data["filename"], category
                    else:
                        logger.error(f"Image download failed or empty file")
                        return None, None, None

        logger.error(f"No valid images found in outputs")
        return None, None, None
