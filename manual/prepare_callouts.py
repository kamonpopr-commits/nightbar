"""Read actual rendered image bounds so editable arrows align exactly."""
from pathlib import Path
import json
import pdfplumber
from build_reference_manual import CHAPTERS
from figure_callouts import CALLOUTS

root=Path(__file__).resolve().parents[1]
manifest=[]
with pdfplumber.open(root/'output/pdf/JUPITER_User_Manual.pdf') as pdf:
    index=5
    for _,topics in CHAPTERS:
        for title,screen,*_ in topics:
            if screen in CALLOUTS:
                images=pdf.pages[index].images
                assert len(images)==1,(index+1,screen,len(images))
                image=images[0]
                manifest.append(dict(screen=screen,page=index+1,x=image['x0'],y=image['top'],width=image['width'],height=image['height'],points=CALLOUTS[screen]))
            index+=1
(root/'tmp/manual/callouts.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
print('Figures:',len(manifest),'Callouts:',sum(len(m['points']) for m in manifest))
