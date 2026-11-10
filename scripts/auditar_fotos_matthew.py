#!/usr/bin/env python3
"""Auditoría temporal de imágenes de la fuente original para elegir solo las del artículo."""
import json,re
from pathlib import Path
from urllib.request import Request,urlopen
from bs4 import BeautifulSoup
SOURCE="https://www.pinkbike.com/news/video-matthew-fairbrother-mountain-bikes-in-el-salvador-from-murder-capital-to-mountain-bike-haven.html"
OUTPUT=Path("data/auditoria-matthew-fuente.json")
def main():
    try:
        with urlopen(Request(SOURCE,headers={"User-Agent":"Mozilla/5.0"}),timeout=25) as r:
            html=r.read(4000000).decode("utf-8","replace")
    except Exception as e:
        OUTPUT.write_text(json.dumps({"source":SOURCE,"error":str(e)},ensure_ascii=False,indent=2)+"\\n",encoding="utf-8")
        print("AUDITORIA: fuente inaccesible",type(e).__name__,flush=True)
        return
    soup=BeautifulSoup(html,"html.parser")
    rows=[]
    for tag in soup.find_all(True):
        attrs={k:v for k,v in tag.attrs.items() if k in ("src","data-src","data-full","data-original","srcset","href","style","data-image","data-photo")}
        relevant=[]
        for k,v in attrs.items():
            v=" ".join(v) if isinstance(v,list) else str(v)
            if re.search(r"pinkbike\.org|p\d+pb\d+|\.jpg|\.jpeg|\.webp",v,re.I):
                relevant.append({k:v[:800]})
        if relevant:
            parents=[]
            for parent in list(tag.parents)[:5]:
                if parent.name in ("body","html"):break
                parents.append({"tag":parent.name,"id":parent.get("id"),"class":parent.get("class")})
            rows.append({"tag":tag.name,"attrs":relevant[:4],"parents":parents,"context":tag.parent.get_text(" ",strip=True)[:160] if tag.parent else ""})
    OUTPUT.write_text(json.dumps({"source":SOURCE,"count":len(rows),"rows":rows[:250]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Auditoría html origen:",len(rows),"imagenes candidatas",flush=True)
if __name__=="__main__": main()
