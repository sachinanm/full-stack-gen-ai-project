import os
import shutil

base_path = r"c:\Users\sachi\OneDrive\Documents\full stack gen ai project"

dirs = [
    "app", "app/api", "app/services", "app/core", 
    "data", "data/uploads", "data/chroma_db",
    "static/css", "static/js"
]

for d in dirs:
    os.makedirs(os.path.join(base_path, d), exist_ok=True)

for d in ["app", "app/api", "app/services", "app/core"]:
    open(os.path.join(base_path, d, "__init__.py"), "w").close()

if os.path.exists(os.path.join(base_path, "static", "style.css")):
    shutil.move(os.path.join(base_path, "static", "style.css"), os.path.join(base_path, "static", "css", "style.css"))
if os.path.exists(os.path.join(base_path, "static", "script.js")):
    shutil.move(os.path.join(base_path, "static", "script.js"), os.path.join(base_path, "static", "js", "script.js"))

for src, dst in [("uploads", "data/uploads"), ("chroma_db", "data/chroma_db")]:
    src_path = os.path.join(base_path, src)
    dst_path = os.path.join(base_path, dst)
    if os.path.exists(src_path) and src_path != dst_path:
        for item in os.listdir(src_path):
            s = os.path.join(src_path, item)
            d = os.path.join(dst_path, item)
            if not os.path.exists(d):
                shutil.move(s, d)
        try:
            os.rmdir(src_path)
        except Exception:
            pass

for old_file in ["server.py", "rag_engine.py", "main.py"]:
    of_path = os.path.join(base_path, old_file)
    if os.path.exists(of_path):
        os.remove(of_path)
