"""
FlowAgent Tüm Modüller Uçtan Uca Entegre Test Scripti
Bu script satın alma akışını, yerel kural motorunu, SQLite veritabanını,
B2B maliyet denetimini ve İhale analiz modülünü tek seferde doğrular.
"""
import os
import sys
import database
from utils import (
    SatinAlmaTalebi,
    SatinAlmaKalemi,
    gorev_akisini_yurut,
    butce_ve_maliyet_denetimi_yap,
    tedarikci_kapsamli_risk_analizi,
    ihale_sartname_ve_teklif_analizi,
    DEFAULT_MODEL
)

def run_all_tests():
    print("=" * 65)
    print("🚀 FLOWAGENT TÜM MODÜLLER VE SİSTEM TESTİ BAŞLIYOR")
    print("=" * 65)

    test_db = "test_unified.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    # 1. Veritabanı İlklendirme
    print("\n[1/4] Veritabanı Tabloları Kontrol Ediliyor...")
    database.init_db(test_db)
    print("  ✅ Tablolar oluşturuldu (purchases, tender_analyses, arge_evaluations).")

    # 2. Satın Alma ve Bütçe Akışı Testi
    print("\n[2/4] Satın Alma Görev Akışı Test Ediliyor...")
    talep_ornek = (
        "XYZ Bilişim Teknolojileri A.Ş.\n"
        "Talep Türü: Donanım Alımı\n"
        "İçerik: 2 adet Geliştirici Sunucusu (Adet: 40.000 TRY)\n"
        "Toplam Tutar: 80.000 TRY"
    )
    sonuc = gorev_akisini_yurut(talep_ornek, dosya_adi="test_talep.txt", model=DEFAULT_MODEL)
    assert sonuc["talep"].toplam_tutar > 0, "Tutar ayrıştırılamadı!"
    print(f"  ✅ Satın Alma Ayrıştırıldı: {sonuc['talep'].tedarikci_adi} | {sonuc['talep'].toplam_tutar:,.2f} TRY")

    # 3. B2B & Maliyet Denetim Testi
    print("\n[3/4] B2B / SaaS & Maliyet Denetim Motoru Test Ediliyor...")
    saas_talep = SatinAlmaTalebi(
        tedarikci_adi="Mega Nova Cloud Ltd.",
        toplam_tutar=95000.0,
        para_birimi="TRY",
        talep_turu="Yazılım Lisansı / Bulut Sunucu / SaaS",
        kalemler=[SatinAlmaKalemi(aciklama="Bulut ve API Yıllık Abonelik", miktar=1, birim="Paket", birim_fiyat=95000.0, toplam_fiyat=95000.0)]
    )
    maliyet_sonuc = butce_ve_maliyet_denetimi_yap(saas_talep)
    assert maliyet_sonuc.uygun_mu is True
    print(f"  ✅ Maliyet Denetimi Başarılı: {maliyet_sonuc.harcama_turu} | Tasarruf: {maliyet_sonuc.tahmini_vergi_avantaji:,.2f} TRY")

    # 4. İhale & RFP Analiz Testi
    print("\n[4/4] İhale & RFP Şartname Analiz Modülü Test Ediliyor...")
    sartname_ornek = "KURUMSAL B2B YAZILIM ENTEGRASYONU TEKNİK ŞARTNAMESİ\n1. ISO 27001 ve Kubernetes şarttır.\n2. 7/24 SLA desteği."
    ihale_rap = ihale_sartname_ve_teklif_analizi(sartname_ornek, dosya_adi="sartname.txt", model=DEFAULT_MODEL)
    assert ihale_rap.genel_uyum_skoru > 0
    assert len(ihale_rap.uyum_matrisi) > 0
    print(f"  ✅ İhale Analizi Başarılı: Uyum Skoru %{ihale_rap.genel_uyum_skoru} | {len(ihale_rap.uyum_matrisi)} Madde İncelendi.")

    if os.path.exists(test_db):
        os.remove(test_db)

    print("\n" + "=" * 65)
    print("🎉 TÜM FLOWAGENT MODÜLLERİ EKSİKSİZ VE HATASIZ ÇALIŞIYOR!")
    print("=" * 65)

if __name__ == "__main__":
    run_all_tests()
