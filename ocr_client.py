"""
OCR Client for Text Detection in Images
"""

import easyocr
import re
from logger_config import setup_logger

logger = setup_logger("OCR")


# ==================================================
# OCR Client
# ==================================================


class OCRClient:
    """이미지 텍스트 감지 클라이언트 (한글/영문, 숫자 필터링)"""

    def __init__(self, languages=["ko", "en"], gpu=True):
        logger.info(f"Initializing OCR Client with languages: {languages}")
        self.reader = easyocr.Reader(languages, gpu=gpu)
        logger.info("OCR Client initialized")

    @staticmethod
    def is_valid_text(text):
        """텍스트에 한글 또는 영어가 포함되어 있는지 확인"""
        text_stripped = text.strip()
        if not text_stripped:
            return False
        # 한글(가-힣) 또는 영어(a-zA-Z)가 하나라도 포함되어 있는지 확인
        return bool(re.search(r'[가-힣a-zA-Z]', text_stripped))

    def detect_text(self, image_path, probability_threshold=0.65, text_only=True):
        """이미지에서 텍스트 감지"""
        try:
            results = self.reader.readtext(image_path)

            detections = []
            filtered_count = 0

            for bbox, text, prob in results:
                if prob < probability_threshold:
                    continue

                if text_only:
                    if self.is_valid_text(text):
                        detections.append(
                            {"text": text, "probability": prob, "bbox": bbox}
                        )
                    else:
                        filtered_count += 1
                        logger.debug(
                            f"Filtered (no valid text): '{text}' (prob: {prob:.2f})"
                        )
                else:
                    detections.append({"text": text, "probability": prob, "bbox": bbox})

            has_text = len(detections) > 0

            if has_text:
                logger.info(f"Text detected: {len(detections)} item(s)")
                for det in detections:
                    logger.info(f"  '{det['text']}' (prob: {det['probability']:.2f})")
            else:
                logger.info(f"No text detected above threshold {probability_threshold}")

            return {
                "has_text": has_text,
                "detections": detections,
                "filtered_count": filtered_count,
            }

        except Exception as e:
            logger.error(f"OCR detection failed: {e}")
            raise e

    def check_text_free(self, image_path, probability_threshold=0.65):
        """이미지에 텍스트가 없는지 확인"""
        result = self.detect_text(image_path, probability_threshold, text_only=True)
        return not result["has_text"]
