# -*- coding: utf-8 -*-
"""把 AI 生成的 19 张 PNG 封面转换为 JPG，并写回课程 11-29 的 cover_url。"""
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
GEN = Path(r"C:\Users\Lenovo\WorkBuddy\2026-10-23-22-37-16\gen-covers")
UPLOAD = ROOT / "uploads" / "courses"

sys.path.insert(0, str(ROOT))
from app.database import Base, SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402,F401
from app.models import Course  # noqa: E402
from app.schema_migrate import ensure_schema  # noqa: E402

# 课程 ID -> (目标文件名, 源 PNG 路径)
MAPPING = {
    11: ("copd-diet.jpg", GEN / "Dark_navy_blue_background__glo_2026-10-27T14-11-24.png"),
    12: ("copd-exercise.jpg", GEN / "gen2/Dark_navy_blue_background__glo_2026-10-27T14-12-16.png"),
    13: ("copd-vaccine-prevent.jpg", GEN / "Dark_navy_blue_background__glo_2026-10-27T14-11-21.png"),
    14: ("copd-mind-sleep.jpg", GEN / "Dark_navy_blue_background__glo_2026-10-27T14-11-26.png"),
    15: ("copd-pft.jpg", GEN / "Dark_navy_blue_background__glo_2026-10-27T14-11-30.png"),
    16: ("copd-comorbid.jpg", GEN / "gen2/Dark_navy_blue_background__glo_2026-10-27T14-12-12.png"),
    17: ("copd-visit.jpg", GEN / "gen2/Dark_navy_blue_background__glo_2026-10-27T14-12-17.png"),
    18: ("copd-palliative.jpg", GEN / "gen2/Dark_navy_blue_background__glo_2026-10-27T14-12-14.png"),
    19: ("copd-niv.jpg", GEN / "gen2/Dark_navy_blue_background__glo_2026-10-27T14-12-18.png"),
    20: ("copd-travel.jpg", GEN / "gen3/Dark_navy_blue_background__glo_2026-10-27T14-12-47.png"),
    21: ("copd-home-env.jpg", GEN / "gen3/Dark_navy_blue_background__glo_2026-10-27T14-12-48.png"),
    22: ("copd-quit-science.jpg", GEN / "gen4/Dark_navy_blue_background__glo_2026-10-27T14-13-32.png"),
    23: ("copd-clear.jpg", GEN / "gen3/Dark_navy_blue_background__glo_2026-10-27T14-12-45.png"),
    24: ("copd-device.jpg", GEN / "gen3/Dark_navy_blue_background__glo_2026-10-27T14-12-46.png"),
    25: ("copd-family.jpg", GEN / "gen4/Dark_navy_blue_background__glo_2026-10-27T14-13-31.png"),
    26: ("copd-tcm.jpg", GEN / "gen4/Dark_navy_blue_background__glo_2026-10-27T14-13-34.png"),
    27: ("copd-myth.jpg", GEN / "gen4/Dark_navy_blue_background__glo_2026-10-27T14-13-33.png"),
    28: ("copd-scale.jpg", GEN / "gen5/Dark_navy_blue_background__glo_2026-10-27T14-14-19.png"),
    29: ("copd-plan.jpg", GEN / "gen4/Dark_navy_blue_background__glo_2026-10-27T14-13-27.png"),
}


def convert(src: Path, dst: Path) -> None:
    img = Image.open(src).convert("RGB")
    w, h = img.size
    # 裁掉底部 7%（去除右下角水印），再缩放到 960 宽
    img = img.crop((0, 0, w, int(h * 0.93)))
    target_w = 960
    target_h = round(img.height * target_w / img.width)
    img = img.resize((target_w, target_h), Image.LANCZOS)
    img.save(dst, "JPEG", quality=86, optimize=True)


def main() -> None:
    UPLOAD.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    try:
        for cid, (fname, src) in MAPPING.items():
            if not src.exists():
                print(f"!! 缺少源文件: {src}")
                continue
            dst = UPLOAD / fname
            convert(src, dst)
            c = db.query(Course).filter(Course.id == cid).first()
            if c and (c.cover_url or "").endswith(".svg"):
                c.cover_url = f"/uploads/courses/{fname}"
                print(f"{cid}\t{c.name}\t-> {fname}")
            elif c:
                print(f"  (跳过 DB 更新, 当前 cover={c.cover_url}) {cid} {c.name}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
