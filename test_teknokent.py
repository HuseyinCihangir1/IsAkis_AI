"""
FlowAgent Teknokent Start-up ve İhale Yetenekleri Doğrulama Testi
"""
import os
import database
from utils import (
    SatinAlmaTalebi,
    SatinAlmaKalemi,
    arge_harcama_uygunlugu_degerlendir,
    tedarikci_kapsamli_risk_analizi,
    ihale_sartname_ve_teklif_analizi,
    DEFAULT_MODEL
)

def run_teknokent_tests():
    print("=" * 65)
    print("🚀 FLOWAGENT TEKNOKENT START-UP ENTEGRASYON TESTİ")
    print("=" * 65)

    test_db = "test_teknokent.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    # 1. Veritabanı ve Şema Genişletme Testi
    print("\n[Test 1] Veritabanı Yeni Tablolar (tender_analyses, arge_evaluations)...")
    database.init_db(test_db)
    conn = database.get_connection(test_db)
    cursor = conn.cursor()
    tablolar = [t["name"] for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    print(f" -> Veritabanındaki Tablolar: {tablolar}")
    assert "tender_analyses" in tablolar, "tender_analyses tablosu eksik!"
    assert "arge_evaluations" in tablolar, "arge_evaluations tablosu eksik!"
    conn.close()
    print(" ✅ Test 1 Başarılı: Tüm kurumsal tablolar oluşturuldu.")

    # 2. 5746 / 4691 Teknokent & TÜBİTAK Teşvik Uygunluk Testi
    print("\n[Test 2] Ar-Ge Harcama Uygunluk Motoru (GPU Sunucu Alımı)...")
    talep_gpu = SatinAlmaTalebi(
        tedarikci_adi="Mega Nova Cloud Ltd.",
        toplam_tutar=150000.0,
        para_birimi="TRY",
        talep_turu="Donanım / Sunucu",
        kalemler=[SatinAlmaKalemi(aciklama="2 Adet AI GPU Sunucu Kabini", miktar=2, birim="Adet", birim_fiyat=75000.0, toplam_fiyat=150000.0)]
    )
    arge_sonuc = arge_harcama_uygunlugu_degerlendir(talep_gpu)
    print(f" -> Ar-Ge Kapsamında mı: {arge_sonuc.arge_kapsaminda_mi}")
    print(f" -> TÜBİTAK Bütçe Kodu: {arge_sonuc.tubitak_butce_kodu}")
    print(f" -> Muafiyet Oranı: %{arge_sonuc.muafiyet_orani_yuzde}")
    print(f" -> Tahmini Vergi Tasarrufu: {arge_sonuc.tahmini_vergi_avantaji:,.2f} TRY")
    assert arge_sonuc.arge_kapsaminda_mi is True
    assert arge_sonuc.tahmini_vergi_avantaji > 0
    print(" ✅ Test 2 Başarılı: Teknokent mevzuat motoru doğru vergi avantajı hesapladı.")

    # 3. Tedarikçi Risk Analizi Testi
    print("\n[Test 3] Tedarikçi Risk ve Güven Puanlama Testi...")
    risk_sonuc = tedarikci_kapsamli_risk_analizi("Mega Nova Cloud Ltd.", 150000.0)
    print(f" -> Risk Seviyesi: {risk_sonuc.risk_seviyesi} (Skor: {risk_sonuc.skor}/100)")
    print(f" -> Tavsiye Edilen Ödeme Şartı: {risk_sonuc.tavsiye_edilen_odeme_sartlari}")
    assert risk_sonuc.skor > 0
    print(" ✅ Test 3 Başarılı: Tedarikçi risk skoru ve vade önerisi üretildi.")

    # 4. İhale Analizi ve Veritabanı Kalıcılığı Testi
    print("\n[Test 4] İhale Analizi ve DB Kayıt Testi...")
    sartname = (
        "SAVUNMA SANAYİİ VE SİBER GÜVENLİK TEKNİK ŞARTNAMESİ\n"
        "1. ISO 27001 ve CMMI Seviye 3 sertifikası zorunludur.\n"
        "2. Kubernetes mikroservis kümeleme ve TLS 1.3 şifreleme sağlanacaktır.\n"
        "3. En az 2 PMP sertifikalı proje yöneticisi bulunmalıdır."
    )
    ihale_rap = ihale_sartname_ve_teklif_analizi(sartname, dosya_adi="savunma_sartname.txt", model=DEFAULT_MODEL)
    print(f" -> İhale: {ihale_rap.ihale_basligi}")
    print(f" -> Uyum Skoru: %{ihale_rap.genel_uyum_skoru}")
    print(f" -> Uyum Maddeleri Sayısı: {len(ihale_rap.uyum_matrisi)}")

    t_id = database.add_tender_analysis(
        ihale_basligi=ihale_rap.ihale_basligi,
        kurum_adi=ihale_rap.kurum_adi or "İlgili Kurum",
        tahmini_butce=ihale_rap.tahmini_butce or "Bütçe Belirtilmedi",
        genel_uyum_skoru=ihale_rap.genel_uyum_skoru,
        kriter_sayisi=len(ihale_rap.uyum_matrisi),
        uyum_matrisi=[m.model_dump() for m in ihale_rap.uyum_matrisi],
        eksikler=ihale_rap.eksik_ve_riskler,
        teklif_taslagi=ihale_rap.teklif_taslagi,
        db_path=test_db
    )
    print(f" -> İhale Analizi Veritabanına Kaydedildi. Kayıt ID: {t_id}")
    assert t_id > 0
    ih_kayitlar = database.get_tender_analyses(db_path=test_db)
    assert len(ih_kayitlar) >= 1
    print(" ✅ Test 4 Başarılı: İhale analizi ve teklif taslağı kalıcı olarak kaydedildi.")

    # Temizlik
    if os.path.exists(test_db):
        os.remove(test_db)

    print("\n" + "=" * 65)
    print("🎉 TEKNOKENT START-UP ENTEGRASYON TESTLERİNİN TÜMÜ GEÇTİ!")
    print("=" * 65)

if __name__ == "__main__":
    run_teknokent_tests()
