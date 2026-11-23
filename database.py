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
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str = DB_NAME) -> None:
    """
    FlowAgent projesi için gerekli tabloları otomatik oluşturur:
    - purchases: Satın alma talepleri ana tablosu
    - purchase_items: Talep kalemleri
    - workflow_logs: Görev akışı aşamalarının denetim kayıtları
    - tender_analyses: İhale & RFP şartname analizleri ve teklif kayıtları
    - arge_evaluations: 5746 / 4691 Teknokent & TÜBİTAK Ar-Ge ve teşvik uygunluk değerlendirmeleri
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
            ek_veriler_json TEXT
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

    # 4. İhale & RFP Şartname Analizleri Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tender_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ihale_basligi TEXT NOT NULL,
            kurum_adi TEXT,
            tahmini_butce TEXT,
            genel_uyum_skoru INTEGER,
            kriter_sayisi INTEGER,
            uyum_matrisi_json TEXT,
            eksikler_json TEXT,
            teklif_taslagi TEXT,
            tarih TEXT NOT NULL
        );
    """)

    # 5. Teknokent 5746 / 4691 & TÜBİTAK Ar-Ge Harcama Uygunluk Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS arge_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            talep_id INTEGER,
            tedarikci TEXT,
            tutar REAL,
            kategori TEXT,
            arge_kapsaminda_mi INTEGER DEFAULT 1,
            muafiyet_orani INTEGER,
            tahmini_vergi_avantaji REAL,
            tubitak_butce_kodu TEXT,
            teknokent_gerekce TEXT,
            denetim_notu TEXT,
            tarih TEXT NOT NULL
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

    if workflow_loglari:
        for w in workflow_loglari:
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


def add_tender_analysis(
    ihale_basligi: str,
    kurum_adi: str,
    tahmini_butce: str,
    genel_uyum_skoru: int,
    kriter_sayisi: int,
    uyum_matrisi: List[Dict[str, Any]],
    eksikler: List[str],
    teklif_taslagi: str,
    db_path: str = DB_NAME
) -> int:
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    simdi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO tender_analyses (
            ihale_basligi, kurum_adi, tahmini_butce, genel_uyum_skoru,
            kriter_sayisi, uyum_matrisi_json, eksikler_json, teklif_taslagi, tarih
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ihale_basligi,
        kurum_adi,
        tahmini_butce,
        genel_uyum_skoru,
        kriter_sayisi,
        json.dumps(uyum_matrisi, ensure_ascii=False),
        json.dumps(eksikler, ensure_ascii=False),
        teklif_taslagi,
        simdi
    ))
    t_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return t_id


def get_tender_analyses(limit: int = 30, db_path: str = DB_NAME) -> List[Dict[str, Any]]:
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tender_analyses ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    sonuclar = [dict(r) for r in rows]
    conn.close()
    return sonuclar


def add_arge_evaluation(
    talep_id: Optional[int],
    tedarikci: str,
    tutar: float,
    kategori: str,
    arge_kapsaminda_mi: bool,
    muafiyet_orani: int,
    tahmini_vergi_avantaji: float,
    tubitak_butce_kodu: str,
    teknokent_gerekce: str,
    denetim_notu: str,
    db_path: str = DB_NAME
) -> int:
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    simdi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO arge_evaluations (
            talep_id, tedarikci, tutar, kategori, arge_kapsaminda_mi,
            muafiyet_orani, tahmini_vergi_avantaji, tubitak_butce_kodu,
            teknokent_gerekce, denetim_notu, tarih
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        talep_id,
        tedarikci,
        tutar,
        kategori,
        1 if arge_kapsaminda_mi else 0,
        muafiyet_orani,
        tahmini_vergi_avantaji,
        tubitak_butce_kodu,
        teknokent_gerekce,
        denetim_notu,
        simdi
    ))
    arge_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return arge_id


def get_arge_evaluations(limit: int = 50, db_path: str = DB_NAME) -> List[Dict[str, Any]]:
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM arge_evaluations ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    sonuclar = [dict(r) for r in rows]
    conn.close()
    return sonuclar
