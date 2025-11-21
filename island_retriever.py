"""
Island Retriever using CLIP Model
"""

import os
import torch
import torch.nn.functional as F
import clip
from PIL import Image, ImageOps
from logger_config import setup_logger

logger = setup_logger("RET")


# ==================================================
# 유틸 함수
# ==================================================


def list_images(folder):
    """폴더에서 이미지 파일 목록 반환"""
    exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
    files = [
        os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(exts)
    ]
    files.sort()
    return files


def _to_mono_rgb(pil_img):
    """이미지를 흑백으로 변환 후 RGB로 복원"""
    g = pil_img.convert("L")
    g = ImageOps.autocontrast(g)
    return Image.merge("RGB", (g, g, g))


# ==================================================
# Island Retriever
# ==================================================


class IslandRetriever:
    """CLIP 기반 섬 이미지 검색 시스템"""

    def __init__(self, model_save_path: str, island_folder: str, batch_size: int = 64):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Device: {self.device}")

        # 모델 로드
        self.model, self.preprocess = clip.load(
            "ViT-B/32", device=self.device, jit=False
        )
        if self.device == "cuda":
            self.model = self.model.float()
        self.model.eval()

        # 파인튜닝 가중치 로드
        state = torch.load(model_save_path, map_location=self.device)
        try:
            self.model.load_state_dict(state, strict=True)
        except Exception as e:
            logger.warning(f"Loading with strict=False due to: {e}")
            self.model.load_state_dict(state, strict=False)
        logger.info("Fine-tuned weights loaded")

        # 데이터베이스 임베딩
        self.island_paths = list_images(island_folder)
        assert len(self.island_paths) > 0, f"No images found in: {island_folder}"
        self.island_feats = self._embed_image_paths(self.island_paths, batch_size)
        logger.info(f"Database loaded: {len(self.island_paths)} islands")

    @torch.no_grad()
    def _embed_image_paths(self, paths, batch_size):
        """이미지 경로 목록을 임베딩"""
        feats = []
        for i in range(0, len(paths), batch_size):
            batch_paths = paths[i : i + batch_size]
            imgs = [self.preprocess(Image.open(p).convert("RGB")) for p in batch_paths]
            x = torch.stack(imgs, dim=0).to(self.device)
            z = self.model.encode_image(x)
            z = F.normalize(z.float(), dim=-1, eps=1e-6)
            feats.append(z.cpu())
        return torch.cat(feats, dim=0)

    @torch.no_grad()
    def _embed_single_image(self, img_path: str):
        """단일 이미지를 임베딩"""
        img = _to_mono_rgb(Image.open(img_path))
        x = self.preprocess(img.convert("RGB")).unsqueeze(0).to(self.device)
        z = self.model.encode_image(x)
        z = F.normalize(z.float(), dim=-1, eps=1e-6)
        return z.squeeze(0).cpu()

    def retrieve_island(self, user_image_path: str, topk: int = 5):
        """사용자 스케치 이미지와 유사한 Top-K 섬 검색"""
        query_feat = self._embed_single_image(user_image_path)

        sims = (self.island_feats @ query_feat[:, None]).squeeze(1)
        k = min(topk, sims.shape[0])
        scores, idxs = torch.topk(sims, k=k, largest=True, sorted=True)

        results = []
        for i, (idx, score) in enumerate(zip(idxs.tolist(), scores.tolist())):
            results.append(
                {
                    "rank": i + 1,
                    "path": self.island_paths[idx],
                    "filename": os.path.basename(self.island_paths[idx]),
                    "similarity": float(score),
                }
            )

        return results
