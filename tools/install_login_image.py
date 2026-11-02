from pathlib import Path
import json,shutil
from PIL import Image
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'assets'/'login-image-prompt.json').read_text(encoding='utf8'))
source=Path(data['source']); dest=root/'assets'/'originals'/'login-bar.png'
if not dest.exists(): shutil.copy2(source,dest)
with Image.open(dest) as image:
    image=image.convert('RGB'); image.thumbnail((1440,1440)); image.save(root/'assets'/'login-bar.webp','WEBP',quality=85,method=6)
print('Login background saved.')
