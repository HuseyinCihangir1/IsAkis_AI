"""
FlowAgent KOBİ & Kurumsal B2B Maliyet ve İhale Doğrulama Testi
"""
import os
import database
from utils import (
    SatinAlmaTalebi,
    SatinAlmaKalemi,
    butce_ve_maliyet_denetimi_yap,
    tedarikci_kapsamli_risk_analizi,
    ihale_sartname_ve_teklif_analizi,
    DEFAULT_MODEL
)

def run_b2b_tests():
    print("=" * 65)
    print("🚀 FLOWAGENT B2B & KOBİ / KURUMSAL SİSTEM TESTİ")
    print("=" * 65)

    test_db = "test_b2b.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    # 1. Veritabanı ve Şema Testi
    database.init_db(test_db)
    print(" ✅ Veritabanı tabloları hazır.")

    # 2. B2B / SaaS & Bulut Maliyet Denetim Testi
    talep_saas = SatinAlmaTalebi(
        tedarikci_adi="Mega Nova Cloud & AI Services Ltd.",
        toplam_tutar=95000.0,
        para_birimi="TRY",
        talep_turu="Yazılım Lisansı / Bulut Sunucu / SaaS",
        kalemler=[SatinAlmaKalemi(aciklama="AWS & LLM API Yıllık Abonelik", miktar=1, birim="Paket", birim_fiyat=95000.0, toplam_fiyat=95000.0)]
    )
    denetim = butce_ve_maliyet_denetimi_yap(talep_saas)
    print(f" -> Harcama Sınıfı: {denetim.harcama_turu}")
    print(f" -> Bütçeye Uygun mu: {denetim.uygun_mu}")
    print(f" -> Tasarruf / Optimizasyon Önerisi: {denetim.maliyet_optimizasyon_onerisi[:60]}...")
    print(f" -> Tahmini Vergi/Teşvik Avantajı: {denetim.tahmini_vergi_avantaji:,.2f} TRY")
    assert denetim.uygun_mu is True
    assert denetim.tahmini_vergi_avantaji > 0

    # 3. İhale Analizi ve DB Kaydı
    sartname = "KURUMSAL B2B BULUT YAZILIM ENTEGRASYONU TEKNİK ŞARTNAMESİ\n1. ISO 27001 ve Kubernetes şarttır.\n2. 7/24 SLA desteği."
    rap = ihale_sartname_ve_teklif_analizi(sartname, dosya_adi="b2b_sartname.txt", model=DEFAULT_MODEL)
    print(f" -> İhale Uyum Skoru: %{rap.genel_uyum_skoru}")
    assert rap.genel_uyum_skoru > 0

    if os.path.exists(test_db):
        os.remove(test_db)

    print("\n" + "=" * 65)
    print("🎉 B2B & KOBİ / KURUMSAL MALİYET TESTLERİNİN TÜMÜ BAŞARILI!")
    print("=" * 65)

if __name__ == "__main__":
    run_b2b_tests()
