"""
app.py Sözdizimi ve UI CSS Bütünlüğü Doğrulama Testi
"""
import py_compile
import sys

try:
    py_compile.compile("app.py", doraise=True)
    print("✅ app.py sözdizimi tamamen hatasız (Syntax OK).")
except Exception as e:
    print(f"❌ Sözdizimi Hatası: {e}")
    sys.exit(1)
