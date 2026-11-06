import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = "audit_log.db"

def init_db():
    """Veritabanı tablosunu ve şemasını oluşturur."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS talep_denetim_kayitlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            islem_zamani TEXT NOT NULL,
            dosya_adi TEXT,
            tedarikci_adi TEXT,
            toplam_tutar REAL,
            para_birimi TEXT,
            talep_turu TEXT,
            politika_uygun_mu INTEGER,
            karar TEXT NOT NULL,
            yonetici_notu TEXT,
            tam_rapor_json TEXT
        )
    """)
    conn.commit()
    conn.close()

def kayit_ekle(
    dosya_adi: str,
    tedarikci_adi: str,
    toplam_tutar: float,
    para_birimi: str,
    talep_turu: str,
    politika_uygun_mu: bool,
    karar: str,
    yonetici_notu: str,
    tam_rapor_json: str
) -> int:
    """Verilen onay/ret kararını ve akış detayını veritabanına ekler."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    simdi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO talep_denetim_kayitlari (
            islem_zamani, dosya_adi, tedarikci_adi, toplam_tutar, para_birimi,
            talep_turu, politika_uygun_mu, karar, yonetici_notu, tam_rapor_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        simdi,
        dosya_adi,
        tedarikci_adi,
        toplam_tutar,
        para_birimi,
        talep_turu,
        1 if politika_uygun_mu else 0,
        karar,
        yonetici_notu,
        tam_rapor_json
    ))
    kayit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return kayit_id

def tum_kayitlari_getir() -> List[Dict[str, Any]]:
    """Tüm geçmiş kararları liste olarak döndürür."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM talep_denetim_kayitlari ORDER BY id DESC")
    rows = cursor.fetchall()
    kayitlar = [dict(r) for r in rows]
    conn.close()
    return kayitlar

