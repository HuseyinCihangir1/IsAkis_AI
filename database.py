import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_NAME = "flowagent.db"


def get_connection(db_path: str = DB_NAME) -> sqlite3.Connection:
    """
    Python'ın yerleşik sqlite3 kütüphanesini kullanarak veritabanı bağlantısı oluşturur.
    Satırları sözlük benzeri erişilebilir kılmak için row_factory = sqlite3.Row ayarlanır.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Yabancı anahtar (Foreign Key) kısıtlamalarını aktif et
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str = DB_NAME) -> None:
    """
    FlowAgent projesi için gerekli tabloları otomatik oluşturur:
    - purchases: Satın alma talepleri ana tablosu (tedarikçi, tutar, durum, onaylayan, notlar vb.)
    - purchase_items: Talep kalemleri (açıklama, miktar, birim fiyat vb.)
    - workflow_logs: Görev akışı aşamalarının denetim kayıtları
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 1. Satın Alma Talepleri (Purchases) Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dosya_adi TEXT,
            tedarikci TEXT NOT NULL,
            vergi_no TEXT,
            tutar REAL NOT NULL,
            para_birimi TEXT DEFAULT 'TRY',
            talep_turu TEXT,
            politika_uygun_mu INTEGER DEFAULT 1,  -- 1: Uygun, 0: Limit Aşımı/Uygun Değil
            durum TEXT DEFAULT 'BEKLEMEDE',        -- BEKLEMEDE, ONAYLANDI, REDDEDILDI, REVIZYON
            onaylayan TEXT,
            onay_tarihi TEXT,
            yonetici_notu TEXT,
            olusturulma_tarihi TEXT NOT NULL,
            ek_veriler_json TEXT                   -- RAG ve Tool Calling yanıtlarını içeren tam JSON
        );
    """)

    # 2. Kalemler (Purchase Items) Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchase_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_id INTEGER NOT NULL,
            aciklama TEXT NOT NULL,
            miktar REAL,
            birim TEXT,
            birim_fiyat REAL,
            toplam_fiyat REAL,
            FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE
        );
    """)

    # 3. İş Akışı Zaman & Denetim Logları Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_id INTEGER,
            adim_no INTEGER,
            adim_adi TEXT NOT NULL,
            baslangic_zamani TEXT,
            bitis_zamani TEXT,
            durum TEXT,
            detay TEXT,
            FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE
        );
    """)

    conn.commit()
    conn.close()


def add_request(
    tedarikci: str,
    tutar: float,
    dosya_adi: Optional[str] = None,
    vergi_no: Optional[str] = None,
    para_birimi: str = "TRY",
    talep_turu: Optional[str] = "Genel",
    politika_uygun_mu: bool = True,
    durum: str = "BEKLEMEDE",
    onaylayan: Optional[str] = None,
    yonetici_notu: Optional[str] = None,
    kalemler: Optional[List[Dict[str, Any]]] = None,
    ek_veriler: Optional[Dict[str, Any]] = None,
    workflow_loglari: Optional[List[Any]] = None,
    db_path: str = DB_NAME
) -> int:
    """
    Veritabanına yeni bir satın alma talebi (purchase) kaydı ekler.
    Varsa ilişkili kalemleri ve workflow loglarını da kaydeder.
    
    Returns:
        int: Oluşturulan talebin ID numarası.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    simdi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    onay_tarihi = simdi if durum in ["ONAYLANDI", "REDDEDILDI"] else None
    ek_json = json.dumps(ek_veriler, ensure_ascii=False) if ek_veriler else None

    cursor.execute("""
        INSERT INTO purchases (
            dosya_adi, tedarikci, vergi_no, tutar, para_birimi,
            talep_turu, politika_uygun_mu, durum, onaylayan,
            onay_tarihi, yonetici_notu, olusturulma_tarihi, ek_veriler_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        dosya_adi,
        tedarikci,
        vergi_no,
        tutar,
        para_birimi,
        talep_turu,
        1 if politika_uygun_mu else 0,
        durum,
        onaylayan,
        onay_tarihi,
        yonetici_notu,
        simdi,
        ek_json
    ))

    purchase_id = cursor.lastrowid

    # Kalemleri ekle
    if kalemler:
        for k in kalemler:
            cursor.execute("""
                INSERT INTO purchase_items (
                    purchase_id, aciklama, miktar, birim, birim_fiyat, toplam_fiyat
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                purchase_id,
                k.get("aciklama", ""),
                k.get("miktar"),
                k.get("birim"),
                k.get("birim_fiyat"),
                k.get("toplam_fiyat")
            ))

    # Workflow loglarını ekle
    if workflow_loglari:
        for w in workflow_loglari:
            # Pydantic veya Dict kontrolü
            adim_no = getattr(w, "adim_no", None) or (w.get("adim_no") if isinstance(w, dict) else None)
            adim_adi = getattr(w, "adim_adi", None) or (w.get("adim_adi") if isinstance(w, dict) else "")
            baslangic = getattr(w, "baslangic_zamani", None) or (w.get("baslangic_zamani") if isinstance(w, dict) else "")
            bitis = getattr(w, "bitis_zamani", None) or (w.get("bitis_zamani") if isinstance(w, dict) else "")
            durumu = getattr(w, "durum", None) or (w.get("durum") if isinstance(w, dict) else "")
            detay = getattr(w, "detay", None) or (w.get("detay") if isinstance(w, dict) else "")

            cursor.execute("""
                INSERT INTO workflow_logs (
                    purchase_id, adim_no, adim_adi, baslangic_zamani, bitis_zamani, durum, detay
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (purchase_id, adim_no, adim_adi, baslangic, bitis, durumu, detay))

    conn.commit()
    conn.close()
    return purchase_id


def get_requests(limit: int = 50, durum: Optional[str] = None, db_path: str = DB_NAME) -> List[Dict[str, Any]]:
    """
    Veritabanındaki tüm satın alma kayıtlarını en yeniden en eskiye listeler.
    İsteğe bağlı olarak durum (BEKLEMEDE, ONAYLANDI, REDDEDILDI) filtresi alır.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    if durum:
        cursor.execute("SELECT * FROM purchases WHERE durum = ? ORDER BY id DESC LIMIT ?", (durum, limit))
    else:
        cursor.execute("SELECT * FROM purchases ORDER BY id DESC LIMIT ?", (limit,))

    rows = cursor.fetchall()
    sonuclar = [dict(r) for r in rows]
    conn.close()
    return sonuclar


def update_request_status(
    purchase_id: int,
    durum: str,
    yonetici_notu: Optional[str] = None,
    onaylayan: str = "Yetkili Kullanıcı",
    db_path: str = DB_NAME
) -> bool:
    """
    Mevcut bir satın alma talebinin durumunu (ONAYLANDI / REDDEDILDI) günceller.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    onay_tarihi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE purchases
        SET durum = ?, yonetici_notu = ?, onaylayan = ?, onay_tarihi = ?
        WHERE id = ?
    """, (durum, yonetici_notu, onaylayan, onay_tarihi, purchase_id))

    degisen_sayi = cursor.rowcount
    conn.commit()
    conn.close()
    return degisen_sayi > 0


# ---------------------------------------------------------
# Örnek Kullanım Kodu (Test Bloğu)
# ---------------------------------------------------------
if __name__ == "__main__":
    print("--- FlowAgent SQLite Veritabanı Testi Başlıyor ---")
    
    # 1. Veritabanını ve tabloları ilklendir
    init_db()
    print("1. init_db() calisti ve tablolar olusturuldu.")

    # 2. Yeni talep ekleme testi (add_request)
    ornek_id = add_request(
        dosya_adi="ornek_fatura.pdf",
        tedarikci="XYZ Bilişim Teknolojileri A.Ş.",
        vergi_no="9876543210",
        tutar=125000.0,
        para_birimi="TRY",
        talep_turu="Donanım Alımı",
        politika_uygun_mu=False,
        durum="BEKLEMEDE",
        yonetici_notu="Bütçe komitesi incelemesinde",
        kalemler=[
            {"aciklama": "AI GPU Sunucu", "miktar": 2, "birim": "Adet", "birim_fiyat": 50000.0, "toplam_fiyat": 100000.0},
            {"aciklama": "Monitör", "miktar": 5, "birim": "Adet", "birim_fiyat": 5000.0, "toplam_fiyat": 25000.0}
        ]
    )
    print(f"2. Yeni talep eklendi. Olusan Kayit ID: {ornek_id}")

    # 3. Tüm kayıtları listeleme testi (get_requests)
    kayitlar = get_requests()
    print(f"3. get_requests() calisti. Toplam kayit sayisi: {len(kayitlar)}")
    for k in kayitlar:
        print(f"   -> ID: {k['id']} | Tedarikci: {k['tedarikci']} | Tutar: {k['tutar']} {k['para_birimi']} | Durum: {k['durum']}")

