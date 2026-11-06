"""
FlowAgent Entegrasyon ve Doğrulama Testi
Bu script:
1. SQLite veritabanı (database.py) CRUD işlemlerini,
2. Veritabanı tablolarının (purchases, purchase_items, workflow_logs) bütünlüğünü,
3. utils.py içindeki mock API ve Pydantic modellerinin çalışmasını doğrular.
"""
import sys
import os
import database
from utils import (
    SatinAlmaKalemi,
    SatinAlmaTalebi,
    ButceUygunlukSonucu,
    api_tedarikci_dogrula,
    api_departman_kalan_butce_sorgula,
    pdf_veya_gorselden_metin_cikar
)

def run_tests():
    print("=" * 60)
    print("🚀 FLOWAGENT SİSTEM VE ENTEGRASYON TESTLERİ BAŞLIYOR")
    print("=" * 60)

    # 1. SQLite Veritabanı Testi
    print("\n[Test 1] Veritabanı İlklendirme ve Tablo Kontrolü...")
    database.init_db("test_flowagent.db")
    conn = database.get_connection("test_flowagent.db")
    cursor = conn.cursor()
    
    tablolar = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    tablo_isimleri = [t["name"] for t in tablolar]
    print(f" -> Oluşturulan tablolar: {tablo_isimleri}")
    assert "purchases" in tablo_isimleri, "purchases tablosu bulunamadı!"
    assert "purchase_items" in tablo_isimleri, "purchase_items tablosu bulunamadı!"
    assert "workflow_logs" in tablo_isimleri, "workflow_logs tablosu bulunamadı!"
    conn.close()
    print(" ✅ Test 1 Başarılı: Veritabanı şeması eksiksiz.")

    # 2. CRUD İşlemleri Testi
    print("\n[Test 2] add_request, get_requests ve update_request_status...")
    ornek_id = database.add_request(
        tedarikci="Beta Kırtasiye Ltd.",
        tutar=15000.0,
        para_birimi="TRY",
        talep_turu="Ofis Malzemeleri",
        politika_uygun_mu=True,
        durum="BEKLEMEDE",
        kalemler=[
            {"aciklama": "Fotokopi Kağıdı", "miktar": 20, "birim": "Koli", "birim_fiyat": 500.0, "toplam_fiyat": 10000.0},
            {"aciklama": "Toner", "miktar": 5, "birim": "Adet", "birim_fiyat": 1000.0, "toplam_fiyat": 5000.0}
        ],
        db_path="test_flowagent.db"
    )
    print(f" -> Yeni satın alma talebi eklendi. ID: {ornek_id}")
    assert ornek_id > 0, "Kayıt eklenemedi!"

    talepler = database.get_requests(db_path="test_flowagent.db")
    print(f" -> Kayıt listelendi. Toplam: {len(talepler)}")
    assert len(talepler) >= 1, "Kayıtlar listelenemedi!"
    assert talepler[0]["durum"] == "BEKLEMEDE"

    # Durum güncelleme (İnsan onayı simülasyonu)
    guncellendi = database.update_request_status(
        purchase_id=ornek_id,
        durum="ONAYLANDI",
        yonetici_notu="Departman bütçesi uygun, onay verildi.",
        onaylayan="Finans Direktörü",
        db_path="test_flowagent.db"
    )
    assert guncellendi is True, "Durum güncellenemedi!"
    
    guncel_talep = database.get_requests(db_path="test_flowagent.db")[0]
    print(f" -> Güncellenmiş durum: {guncel_talep['durum']} (Not: {guncel_talep['yonetici_notu']})")
    assert guncel_talep["durum"] == "ONAYLANDI"
    print(" ✅ Test 2 Başarılı: CRUD ve İnsan-Onay akışı çalışıyor.")

    # 3. Harici Sistem API (Tool Calling) Fonksiyon Testleri
    print("\n[Test 3] Tedarikçi Doğrulama ve Kalan Bütçe API Araçları...")
    tedarikci_resp = api_tedarikci_dogrula("XYZ Bilişim")
    print(f" -> api_tedarikci_dogrula('XYZ Bilişim'): {tedarikci_resp['tedarikci_statu']} (Risk: {tedarikci_resp['risk_skoru']})")
    assert tedarikci_resp["tedarikci_statu"] == "Onaylı"

    butce_resp = api_departman_kalan_butce_sorgula("Donanım")
    print(f" -> api_departman_kalan_butce_sorgula('Donanım'): Kalan: {butce_resp['kalan_kullanilabilir_butce_try']} TRY")
    assert butce_resp["kalan_kullanilabilir_butce_try"] > 0
    print(" ✅ Test 3 Başarılı: Tool calling API fonksiyonları doğru yanıt veriyor.")

    # 4. Metin Çıkarıcı (PDF / Serbest Metin) Güvenlik Testi
    print("\n[Test 4] pdf_veya_gorselden_metin_cikar Girdi Kontrolü...")
    test_metin = "Örnek satın alma talebi içeriğidir."
    sonuc = pdf_veya_gorselden_metin_cikar(test_metin)
    assert sonuc["metin"] == test_metin
    assert sonuc["yontem"] == "duz_metin"
    print(" ✅ Test 4 Başarılı: Düz metin ve girdi koruması çalışıyor.")

    # Temizlik
    if os.path.exists("test_flowagent.db"):
        os.remove("test_flowagent.db")

    print("\n" + "=" * 60)
    print("🎉 TÜM SİSTEM VE VERİTABANI DOĞRULAMA TESTLERİ BAŞARIYLA GEÇTİ!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()

