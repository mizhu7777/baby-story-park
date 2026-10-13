#!/usr/bin/env python3
"""用 Agnes AI (agnes-image-2.1-flash) 图生图生成 5 个故事共 25 张场景插画。

用法（PowerShell）：
  $env:AGNES_API_KEY="sk-..."                 # 从环境变量读取，绝不写进源码
  python tools/agnes_generate.py --story 1    # 只生成第 1 个故事
  python tools/agnes_generate.py              # 生成全部 5 个故事

参考图（作为图生图的风格 / 角色 / 分镜参考，不裁剪、不复用其像素）：
  reference-materials/配图/五个故事总览.png
  reference-materials/配图/0N_<故事>_封面配图.png
  reference-materials/配图/0N_<故事>_完整分镜.png

原始生成结果（PNG）保存在 tools/.cache/raw/，转换后的 WebP 写入
public/images/stories/story-0N/page-0M.webp
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT.parent / "reference-materials" / "配图"
CACHE = ROOT / "tools" / ".cache" / "raw"
PROVENANCE = ROOT / "tools" / ".cache" / "provenance.json"
OUT = ROOT / "public" / "images" / "stories"

# 实测：当前 AGNES_API_KEY 只对国内节点 api.agnes-ai.cn 有效，
# 国际节点 apihub.agnes-ai.com 会返回 401 Invalid token，所以不要在两者间切换。
BASE_URL = os.environ.get("AGNES_BASE_URL", "https://api.agnes-ai.cn/v1").rstrip("/")
# 实测 agnes-image-2.0-flash 返回「无可用渠道（distributor）」，目前只有 2.1 可用。
MODELS = [m for m in [os.environ.get("AGNES_IMAGE_MODEL", ""), "agnes-image-2.1-flash"] if m]
API_KEY = os.environ.get("AGNES_API_KEY", "")

# 1024x768 = 4:3 横向构图，两个边长都是 16 的倍数，符合接口要求。
SIZE = "1024x768"

# ---------------------------------------------------------------- 通用画风约束
STYLE = (
    "warm soft children's picture-book illustration, Pixar-like 3D render, "
    "soft rounded shapes, bright cheerful saturated colours that are never harsh, "
    "gentle warm lighting, sunny daylight, clean simple composition with one clear "
    "main subject, shallow depth of field with a softly blurred background, "
    "cute chubby child-friendly proportions, large expressive friendly eyes, "
    "high detail, 4:3 landscape composition, wide safe margins"
)

NEGATIVE = (
    "no text, no letters, no words, no numbers, no title, no caption, no subtitle, "
    "no watermark, no signature, no logo, no user interface, no speech bubble, "
    "no comic panel grid, no split screen, no collage, no borders, no frame, "
    "no duplicated characters, no deformed face, no extra limbs"
)
# ---------------------------------------------------------------- 角色一致性约束
CHARACTERS = {
    "story-01": (
        "Main character: one small WHITE rabbit with long upright ears whose inner ears are soft pink, "
        "fluffy white fur, round face, big dark friendly eyes, rosy pink cheeks, no clothes, "
        "wearing one small tan canvas backpack on its back. "
        "Secondary character: one small reddish-orange squirrel with a big fluffy curled tail, "
        "cream coloured belly and muzzle, dark round eyes."
    ),
    "story-02": (
        "Main character: one small round CHUBBY BROWN BEAR CUB with soft brown fur, "
        "a lighter cream coloured muzzle and belly patch, small round ears, big dark eyes, rosy cheeks. "
        "Secondary characters: the same bear cub's mother (a larger, slightly lighter brown bear) "
        "and one gentle brown bear dentist in a clean white coat."
    ),
    "story-03": (
        "Main character: one small GREY AND WHITE KITTEN with a white face, chest and paws, "
        "soft grey patches on the head, back and tail, big round dark eyes, pink inner ears, "
        "pink nose, small pink collar. "
        "KEY PROP: one bright RED BALLOON on a thin string, clearly visible in the scene. "
        "Secondary character: one kind friendly adult animal helper holding a long pole."
    ),
    "story-04": (
        "Main character: one small YELLOW DUCKLING with soft fluffy yellow feathers, "
        "a bright ORANGE beak, round body, big dark eyes. "
        "Secondary character: the MAMA DUCK, a larger WHITE adult duck with the same orange beak, "
        "always staying right next to the duckling."
    ),
    "story-05": (
        "Main character: one small BROWN-ORANGE SQUIRREL with soft orange-brown fur, "
        "a cream coloured belly and muzzle, tall pointed ears, big dark eyes, "
        "and a very fluffy big curled tail. "
        "Secondary character: the squirrel's mother, a larger lighter brown-orange squirrel "
        "with the same fluffy tail."
    ),
    "story-06": (
        "Main character: one small MONKEY with soft warm brown fur, a cream coloured face and belly, "
        "a pale pink face area, large round dark eyes, rosy cheeks, and a long curled tail. "
        "The monkey wears ONE simple pastel yellow t-shirt and matching shorts, no shoes. "
        "Secondary character: the monkey's mother, a larger brown monkey with the same colouring, "
        "wearing a soft blue dress."
    ),
    "story-07": (
        "Main character: one small PUPPY with soft golden-tan fur, floppy ears, "
        "a cream coloured muzzle and chest, big dark round eyes, and a short wagging tail. "
        "The puppy wears a small blue collar. "
        "Secondary character: one small WHITE RABBIT with long upright ears whose inner ears are pink, "
        "wearing a tiny green dress."
    ),
    "story-08": (
        "Main character: one small HEDGEHOG with soft brown spines over its back, "
        "a cream coloured soft face and belly, a small dark nose, big round dark eyes. "
        "The hedgehog wears striped pyjamas. "
        "Secondary character: the hedgehog's mother, a slightly larger hedgehog with the same colouring."
    ),
    "story-09": (
        "Main character: one small DEER FAWN with soft light-brown fur covered in small white spots, "
        "small antlers, a cream coloured muzzle, large gentle dark eyes, and short hooves. "
        "Secondary character: the fawn's mother, a larger doe deer with the same spotted coat."
    ),
    "story-10": (
        "Main character: one small WHITE LAMB with soft curly wool, a pink face and small pink ears, "
        "big dark round eyes. The lamb wears a small red scarf. "
        "This scene contains ONLY the lamb. It is a quiet scene with a single character."
    ),
}

# ---------------------------------------------------------------- 25 个场景
SCENES = {
    "story-01": [
        "Scene 1: a small white rabbit wearing a tan backpack has just walked into a sunny spring forest meadow "
        "full of green grass, white daisies and leafy trees. The rabbit stands alone in the middle of the meadow, "
        "looking around with a slightly shy and uncertain smile because it does not know anybody here. "
        "The rabbit is the clear main subject, shown full body.",
        "Scene 2: in the same sunny spring meadow, the little white rabbit stands a little behind a big leafy tree, "
        "watching a small reddish-orange squirrel that is gathering pinecones on the ground under another tree. "
        "The rabbit looks hesitant and a bit shy, half hiding behind the tree trunk. Both characters visible.",
        "Scene 3: the little white rabbit has gathered courage and is now standing in front of the squirrel, "
        "leaning slightly forward with a warm open smile, one paw raised in a friendly greeting, "
        "as if politely saying hello and asking to play together. The squirrel looks up at the rabbit, "
        "surprised but friendly. Sunny meadow background.",
        "Scene 4: the little white rabbit and the squirrel are happily playing together on the meadow, "
        "collecting pinecones into a little pile and sharing pinecones with other friendly small forest animals "
        "such as a brown bear cub and a small blue bird. Everyone is smiling, a warm joyful group scene.",
        "Scene 5: at golden sunset in the same meadow, the little white rabbit with its tan backpack is laughing "
        "happily together with its new friends, the squirrel, the bear cub and the bird. "
        "Warm orange evening light, big smiling faces, a happy ending feeling.",
    ],
    "story-02": [
        "Scene 1: inside a cosy warm kitchen, the little brown bear cub sits happily at a small table "
        "with a slice of strawberry cake and a plate of cookies in front of it. The cub is smiling with delight "
        "and holding a cookie. Soft daylight through a window, the cub is the clear main subject.",
        "Scene 2: at night in a cosy bedroom, the little brown bear cub lies in a small bed under a blue blanket, "
        "holding one cheek with its paw and frowning because its tooth hurts. A bedside lamp gives soft warm light, "
        "the cub's face clearly shows toothache.",
        "Scene 3: in a bright friendly dental clinic, the mother bear stands behind the little brown bear cub "
        "and gently holds its paw to comfort it. A kind brown bear dentist in a clean white coat smiles warmly "
        "while examining the cub's teeth. Clean soft-coloured clinic room, no scary instruments, no fear.",
        "Scene 4: in a cosy bathroom, the mother bear stands beside the little brown bear cub at a white sink, "
        "helping it brush its teeth. The cub holds a toothbrush with white foam around its mouth and smiles, "
        "the mother bear smiles too. A small mirror and tidy towels in the background.",
        "Scene 5: on a sunny morning in a bright tidy living room, the little brown bear cub smiles proudly "
        "with its mouth open to show clean white sparkling teeth, and raises one paw in a happy thumbs-up gesture. "
        "Its mother bear stands beside it smiling too. "
        "IMPORTANT: there is NO cake, NO cookies and NO sweets anywhere in this scene — it is about healthy clean teeth.",
    ],
    "story-03": [
        "Scene 1: in a sunny garden with green hedges, a wooden fence and blooming flowers, "
        "the little grey and white kitten walks happily along a garden path while holding "
        "a bright red balloon on a thin string. The kitten looks delighted and the red balloon "
        "floats above its head. The red balloon must be clearly visible.",
        "Scene 2: a gust of wind blows through the sunny garden. The kitten's balloon string has slipped "
        "from its paw and the bright red balloon is floating up high towards the branch of a big leafy tree. "
        "The kitten looks up with worried eyes and a surprised open mouth. "
        "IMPORTANT: the kitten is standing safely on the ground, it is NOT climbing the tree.",
        "Scene 3: under the same big tree in the sunny garden, the little grey and white kitten stands safely "
        "on the ground looking up at the bright red balloon stuck on a high branch. The kitten looks worried "
        "but calm and thoughtful, both front paws held together. "
        "IMPORTANT: the kitten must NOT climb the tree and must stay on the ground beside the trunk.",
        "Scene 4: in the sunny garden, the little grey and white kitten stands beside a kind adult ANIMAL helper "
        "— a tall friendly grown-up grey cat in overalls. The helper holds a long pole with a small net on the end "
        "and gently lowers the bright red balloon down from the tree branch. The kitten watches happily and reaches "
        "out its paws. "
        "IMPORTANT: the helper must be an animal, never a human person. "
        "The red balloon must be clearly visible.",
        "Scene 5: in the sunny garden, the little grey and white kitten happily holds the bright red balloon "
        "again in its paw and smiles a big grateful smile at the kind helper standing beside it. "
        "Colourful flowers around, warm and safe happy ending.",
    ],
    "story-04": [
        "Scene 1: beside a calm sparkling pond on a sunny spring day, the little yellow duckling stands "
        "safely on the grassy bank and looks down at the bright blue water with wide curious eyes, "
        "wanting to swim. Reeds and water lilies around the pond, the duckling is the clear main subject.",
        "Scene 2: at the edge of a shallow safe part of the pond, the white mama duck stands in the shallow water "
        "right next to the little yellow duckling, calmly reassuring it with a gentle smile. "
        "Both are in calm shallow water only, sunny day, calm reassuring scene.",
        "Scene 3: in the shallow sunny pond water, the little yellow duckling puts its small orange feet "
        "into the water and paddles them gently, looking slightly nervous with a small uncertain expression. "
        "The white mama duck swims right beside it, staying very close and cheering it on. "
        "Only shallow water, the mama duck is always touching the duckling.",
        "Scene 4: in the sunny pond, the little yellow duckling swims forward more confidently and steadily, "
        "leaving small splashes behind it, and happily flaps its little wings. "
        "The white mama duck swims right next to it. Water lilies and gentle ripples, happy progress scene.",
        "Scene 5: in the sunny pond on a happy day, the little yellow duckling smiles happily in the water "
        "with the white mama duck swimming calmly right beside it. Bright blue sky, green lily pads and "
        "white water lilies. A warm, safe and joyful scene.",
    ],
    "story-05": [
        "Scene 1: in a bright and cosy children's playroom, toys are scattered everywhere on a soft rug: "
        "colourful wooden building blocks, a small red toy car, a teddy bear and a ball. "
        "The little brown-orange squirrel stands in the middle of the messy toys, happily playing, "
        "looking cheerful and carefree.",
        "Scene 2: in the same playroom, the little brown-orange squirrel looks worried and searches anxiously "
        "among the messy scattered toys, turning a block over and looking under things, because it cannot find "
        "its favourite little toy car. A small worried frown on its face.",
        "Scene 3: in the playroom, the larger lighter brown-orange mother squirrel stands beside the little squirrel. "
        "Two open storage baskets, one blue and one green, are on the floor. The mother squirrel gently points "
        "at the baskets and explains how to sort the toys, while the little squirrel listens and smiles. "
        "Both squirrels are clearly visible.",
        "Scene 4: in the playroom, the little brown-orange squirrel carefully puts the toys back into the open "
        "baskets one by one: building blocks into one basket and the toy car into the other. "
        "The room is now much tidier, the squirrel looks happy and focused, soft warm light.",
        "Scene 5: in the sunny tidy playroom the next morning, a warm sunbeam falls across the room. "
        "The little brown-orange squirrel happily finds its favourite red toy car inside its basket "
        "and lifts it up with a big delighted smile. Neat shelves and tidy baskets in the background, "
        "a bright and satisfying happy ending.",
    ],
    "story-06": [
        "Scene 1: in a sunny warm bedroom in the early morning, the little brown monkey has just woken up "
        "and is standing beside a small bed, looking at a pastel yellow t-shirt and shorts that are "
        "crumpled on a chair. It looks eager and a little determined.",
        "Scene 2: the little brown monkey is pulling the pastel yellow t-shirt over its head, "
        "with its face coming out through the collar and both small arms sticking out of the sleeves. "
        "The monkey looks pleased with itself. Bright bedroom with soft morning light.",
        "Scene 3: the little brown monkey is standing on one leg trying to pull up its shorts, "
        "wobbling unsteadily with a surprised open-mouth expression as it almost falls over. "
        "A humorous, clumsy and clearly harmless moment.",
        "Scene 4: in a sunny bedroom, the little brown monkey sits on a small stool and calmly pulls its "
        "shorts on one leg at a time. The larger monkey mother in a soft blue dress kneels beside it, "
        "smiling and cheering it on. Both are calm and happy.",
        "Scene 5: in the sunny bedroom, the little brown monkey stands proudly wearing its pastel yellow "
        "t-shirt and matching shorts, arms spread wide and smiling. The mother monkey in the blue dress "
        "stands beside it smiling warmly. A bright proud happy morning.",
    ],
    "story-07": [
        "Scene 1: in a sunny green park lawn, the little golden-tan puppy runs happily and accidentally "
        "knocks over a small tower of colourful building blocks. The blocks are scattered on the grass. "
        "The puppy looks surprised by what it has done.",
        "Scene 2: beside the fallen blocks, the little white rabbit in a tiny green dress looks a bit sad, "
        "while the golden-tan puppy stands in front of her looking guilty with lowered head and ears. "
        "Sad but gentle mood, nothing scary.",
        "Scene 3: in the park, the little golden-tan puppy bows its head low with a sorry expression, "
        "while beside it both paws are picking up the colourful blocks to rebuild the tower. "
        "The puppy is helping to fix the mistake.",
        "Scene 4: in the sunny park, the little white rabbit smiles warmly at the little golden-tan puppy, "
        "and the rebuilt block tower stands between them. The rabbit looks happy and forgiving. "
        "A warm friendly moment.",
        "Scene 5: in a sunny park meadow, the little golden-tan puppy happily runs along with several new "
        "friends — the white rabbit, a brown bear cub and a blue bird. Everyone smiles together. "
        "A joyful friendship happy ending.",
    ],
    "story-08": [
        "Scene 1: in a cosy living room at night, the little brown hedgehog in striped pyjamas stands in "
        "front of a glowing television, watching happily and refusing to leave. The room is dark except "
        "for the TV glow. A cosy late-night scene.",
        "Scene 2: in the same cosy living room, the slightly larger mother hedgehog stands gently beside "
        "the little hedgehog and points kindly toward the bedroom doorway. The little hedgehog still looks "
        "at the TV. Warm gentle lighting.",
        "Scene 3: the next morning in a bright bedroom, the little brown hedgehog sits up in bed but looks "
        "very sleepy and tired, with droopy eyes and a big yawn. Daylight streams through the window "
        "showing it is already late.",
        "Scene 4: in the evening of a warm cosy bedroom, the mother hedgehog sits on the edge of the bed "
        "reading a small picture book to the little hedgehog, who is now tucked under a blue blanket "
        "looking interested and ready to sleep.",
        "Scene 5: on a bright sunny morning, the little brown hedgehog is happily running around a green "
        "garden looking energetic and cheerful, with the mother hedgehog smiling nearby. "
        "Full of energy, a healthy happy ending.",
    ],
    "story-09": [
        "Scene 1: at a sunny dining table, the little spotted deer fawn sits in front of a plate holding "
        "green vegetables, an orange carrot and yellow corn. The fawn is happily reaching only for the "
        "carrot and pushing the green vegetables aside. A warm kitchen setting.",
        "Scene 2: at the dining table, the little spotted deer fawn has pushed the green vegetables to "
        "the far side of the plate with one hoof and is turning its head away from them, "
        "looking fussy about the vegetables. The mother deer is not in this frame.",
        "Scene 3: at the sunny dining table, the mother doe deer with the same spotted coat stands beside "
        "the little fawn and gently encourages it, while the fawn looks at the vegetables "
        "with a curious but unsure expression.",
        "Scene 4: at the dining table, the little spotted deer fawn has its eyes closed and is "
        "trying a small bite of green vegetables, with a curious 'surprised' expression as it starts "
        "to notice the vegetables are a little sweet.",
        "Scene 5: outdoors on a sunny green meadow, the little spotted deer fawn runs joyfully and fast "
        "with the mother doe deer running happily beside it. Both look strong, healthy and full of energy. "
        "Bright open sky, a lively happy ending.",
    ],
    "story-10": [
        "Scene 1: a crowded outdoor market square with colourful stalls. The one small white lamb in a red "
        "scarf stands ALONE on a cobblestone path, looking back over its shoulder with a worried expression, "
        "unable to find its mother. The lamb is the only character in focus. "
        "The market shoppers behind are blurred, out-of-focus cartoon ANIMAL shapes in the far background.",
        "Scene 2: a quiet corner of the market square. The one small white lamb in a red scarf sits down "
        "calmly on a wooden bench on its own, looking a little anxious but obedient, remembering what its "
        "mother said. The lamb is the only character. Background shoppers stay blurred and far away.",
        "Scene 3: a quieter corner of the market square beside one big leafy tree. The one small white lamb "
        "in a red scarf stands calmly and waits in one single spot on the grass, looking a little anxious "
        "but staying put. The lamb is the only character in the picture.",
        "Scene 4: beside the big tree stands a kind brown bear POLICE OFFICER in a navy blue uniform with a "
        "badge and a police cap. He gently holds the little white lamb's paw and walks with it. "
        "The lamb looks relieved and safe. These two are the only characters in the foreground.",
        "Scene 5: in the sunlit market square, the little white lamb in a red scarf happily hugs its MOTHER "
        "SHEEP, a larger white sheep wearing a yellow dress. The two of them hold each other and smile with "
        "relief. A brown bear police officer in a navy uniform stands beside them watching them smile. "
        "Only these three characters are in the picture.",
    ],
}

STORY_REFS = {
    "story-01": ("01_小兔子第一次交朋友_封面配图.png", "01_小兔子第一次交朋友_完整分镜.png"),
    "story-02": ("02_小熊学会自己刷牙_封面配图.png", "02_小熊学会自己刷牙_完整分镜.png"),
    "story-03": ("03_小猫咪找回红气球_封面配图.png", "03_小猫咪找回红气球_完整分镜.png"),
    "story-04": ("04_小鸭子学游泳_封面配图.png", "04_小鸭子学游泳_完整分镜.png"),
    "story-05": ("05_小松鼠整理玩具_封面配图.png", "05_小松鼠整理玩具_完整分镜.png"),
    # story-06 ~ story-10 是新增故事，素材包里没有对应的封面/分镜，
    # 因此只用「五个故事总览.png」作为整体画风参考，保证与前 5 个故事观感统一。
}
OVERVIEW = "五个故事总览.png"


def data_uri(path: Path, max_side: int = 1024) -> str:
    """把本地参考图缩放后转成 Data URI，供 extra_body.image 使用。"""
    with Image.open(path) as im:
        im = im.convert("RGB")
        if max(im.size) > max_side:
            scale = max_side / max(im.size)
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def build_prompt(story_id: str, scene: str, use_refs: bool) -> str:
    ref_line = (
        "The reference image is a STYLE SAMPLE ONLY. Take from it ONLY the colour palette, the warm lighting "
        "and the 3D rendering look. NEVER reproduce its layout, its panel arrangement, its borders or its text — "
        "reference images made of many small pictures sometimes tempt the model into copying that collage, "
        "which is forbidden here."
        if use_refs
        else "Follow the style and character description above very strictly."
    )
    return (
        "Create ONE single standalone children's story illustration of the scene described below.\n\n"
        f"STYLE: {STYLE}\n\n"
        f"CHARACTER DESIGN (must stay exactly the same in every image of this story): {CHARACTERS[story_id]}\n\n"
        f"SCENE: {scene}\n\n"
        "IMPORTANT RULES:\n"
        "- The ENTIRE picture must be ONE single continuous scene filling the frame from edge to edge.\n"
        "- Absolutely NO panel borders, NO grids, NO comic strips, NO inset thumbnails, "
        "NO side images, NO multiple small pictures of the same characters.\n"
        f"- {ref_line}\n"
        "- EVERY character in the scene is a cartoon ANIMAL, never a human being, and no other species "
        "than the ones described above may appear. Mothers, fathers, dentists, police officers and helpers "
        "are all animals of the same species as the main character.\n"
        "- Exactly ONE background, ONE setting, ONE moment in time.\n"
        "- Keep the main character large, centred and clearly readable for a 4-year-old.\n"
        f"- {NEGATIVE}."
    )


def _request(model: str, prompt: str, images: list[str] | None):
    payload = {"model": model, "prompt": prompt, "size": SIZE}
    if images:
        payload["extra_body"] = {"image": images, "response_format": "b64_json"}
    req = urllib.request.Request(
        f"{BASE_URL}/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    item = body["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        with urllib.request.urlopen(item["url"], timeout=300) as r:
            return r.read()
    raise ValueError(f"response has no image: {json.dumps(body)[:300]}")


def try_img2img(prompt: str, images: list[str], tries: int, wait_s: int) -> bytes:
    """尝试图生图。通道繁忙时会立刻返回 503，这里只做有限次尝试。"""
    last = ""
    for i in range(1, tries + 1):
        try:
            return _request(MODELS[0], prompt, images)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:120]}"
            if e.code not in (408, 429, 500, 502, 503, 504):
                break
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        if i < tries:
            time.sleep(wait_s)
    raise RuntimeError(last or "img2img unavailable")


def t2i(prompt: str, retries: int = 12) -> bytes:
    """文生图。通道目前可用，退避重试以应对偶发拥堵。"""
    last = ""
    for i in range(1, retries + 1):
        try:
            return _request(MODELS[0], prompt, None)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:120]}"
            if e.code not in (408, 429, 500, 502, 503, 504):
                break
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        time.sleep(min(10 * i, 60) + random.uniform(0, 8))
    raise RuntimeError(f"t2i failed: {last}")


def load_provenance() -> dict:
    if PROVENANCE.exists():
        return json.loads(PROVENANCE.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", type=int, action="append", help="1-5, repeatable; default all")
    ap.add_argument("--page", type=int, action="append", help="1-5, repeatable; 只重做指定页（需配合 --force）")
    ap.add_argument("--force", action="store_true", help="regenerate even if the file exists")
    ap.add_argument(
        "--mode",
        choices=["auto", "img2img", "t2i"],
        default="auto",
        help="auto: 先试图生图，通道不可用则回退文生图；img2img: 只用参考图；t2i: 只用文生图",
    )
    args = ap.parse_args()

    if not API_KEY:
        print("AGNES_API_KEY is not set. Set it in the environment first.", file=sys.stderr)
        return 2

    # 用 :02d 补零，10 号故事才是 story-10 而不是 story-010
    targets = [f"story-{n:02d}" for n in (args.story or [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])]
    CACHE.mkdir(parents=True, exist_ok=True)
    overview = data_uri(REFS / OVERVIEW)
    prov = load_provenance()
    ok = fail = 0

    for story_id in targets:
        pair = STORY_REFS.get(story_id)
        refs = [overview]
        if pair:
            refs += [data_uri(REFS / pair[0]), data_uri(REFS / pair[1])]
        print(f"\n=== {story_id} ===  (参考图 {len(refs)} 张)", flush=True)
        for idx, scene in enumerate(SCENES[story_id], start=1):
            name = f"page-{idx:02d}"
            webp = OUT / story_id / f"{name}.webp"
            raw = CACHE / story_id / f"{name}.png"
            targeted = args.page is not None and idx not in args.page
            if targeted:
                continue
            if webp.exists() and webp.stat().st_size > 0 and not args.force:
                print(f"  - {name}: exists ({prov.get(f'{story_id}/{name}', '?')}), skip", flush=True)
                continue

            used = None
            print(f"  > {name}: generating...", flush=True)
            if args.mode in ("auto", "img2img"):
                try:
                    png = try_img2img(build_prompt(story_id, scene, True), refs, tries=4, wait_s=20)
                    used = "img2img"
                except Exception as e:  # noqa: BLE001
                    if args.mode == "img2img":
                        print(f"  x {name}: FAILED img2img: {e}", flush=True)
                        fail += 1
                        continue
                    print(f"    ~ img2img 不可用（{str(e)[:60]}），改用文生图", flush=True)

            if used is None:
                try:
                    png = t2i(build_prompt(story_id, scene, False))
                    used = "t2i"
                except Exception as e:  # noqa: BLE001 - 单张失败不中断整批
                    print(f"  x {name}: FAILED {e}", flush=True)
                    fail += 1
                    continue

            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(png)
            with Image.open(io.BytesIO(png)) as im:
                im = im.convert("RGB")
                webp.parent.mkdir(parents=True, exist_ok=True)
                im.save(webp, "WEBP", quality=82, method=6)
                size = im.size
            prov[f"{story_id}/{name}"] = used
            PROVENANCE.write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  + {name}: [{used}] {size[0]}x{size[1]} -> {webp.stat().st_size // 1024} KB", flush=True)
            ok += 1
            time.sleep(3)  # 1K 图片限流 20/min

    print(f"\ndone: {ok} generated, {fail} failed")
    by_mode: dict[str, int] = {}
    for v in prov.values():
        by_mode[v] = by_mode.get(v, 0) + 1
    print(f"provenance: {by_mode}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
