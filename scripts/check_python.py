import py_compile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
files=list((root/"scripts").glob("*.py"))+list((root/"src/analysis").glob("*.py"))
for i,p in enumerate(files):
 py_compile.compile(str(p),cfile=str(root/f"work/python-cache/check-{i}.pyc"),doraise=True)
print(f"Python syntax OK: {len(files)} files")
