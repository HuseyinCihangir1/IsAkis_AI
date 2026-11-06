"""
FlowAgent Yerel Ollama (Qwen3.5:0.8b) Doğrulama Testi
"""
import database
from utils import (
    gorev_akisini_yurut,
    api_tedarikci_dogrula,
    api_departman_kalan_butce_sorgula,
    kural_tabanli_talep_ayristir,
    DEFAULT_MODEL
)

def run_tests():
    print("=" * 60)
    print(f"🚀 FLOWAGENT YEREL OLLAMA ({DEFAULT_MODEL}) TESTİ BAŞLIYOR")
    print("=" * 60)

    # 1. SQLite Veritabanı Kontrolü
    database.init_db("test_ollama.db")
    print(" ✅ Veritabanı başarıyla ilklendirildi.")

    # 2. Görev Akışını Yerel Model ile Yürütme Testi
    ornek_metin = (
        "XYZ Bilişim Teknolojileri A.Ş.\n"
        "Talep Türü: Donanım Alımı\n"
        "İçerik: 2 adet Geliştirici Sunucusu (Adet: 40.000 TRY)\n"
        "Toplam Tutar: 80.000 TRY"
    )

    print("\n[Workflow Testi] Yerel görev akışı yürütülüyor...")
    sonuc = gorev_akisini_yurut(
        girdi=ornek_metin,
        dosya_adi="test_talep.txt",
        model=DEFAULT_MODEL
    )

    talep = sonuc["talep"]
    print(f" -> Ayrıştırılan Tedarikçi: {talep.tedarikci_adi}")
    print(f" -> Ayrıştırılan Tutar: {talep.toplam_tutar} {talep.para_birimi}")
    print(f" -> Kategori: {talep.talep_turu}")
    print(f" -> Kalem Sayısı: {len(talep.kalemler)}")

    assert talep.toplam_tutar > 0, "Tutar tespit edilemedi!"

    # 3. RAG Politika Testi
    butce = sonuc["butce_sonucu"]
    print(f" -> RAG Politika Kararı: {'UYGUN' if butce.uygun_mu else 'LİMİT AŞIMI'}")
    print(f" -> Tespit Edilen Limit: {butce.tespit_edilen_limit} {butce.para_birimi}")
    print(f" -> Gerekçe: {butce.aciklama}")

    # 4. Tool Calling Testi
    araclar = sonuc["arac_cagrilari"]
    print(f" -> Çalıştırılan Araç Sayısı: {len(araclar)}")
    for a in araclar:
        print(f"    - Araç: {a['arac']} -> Yanıt: {a['api_yaniti']}")

    # 5. Workflow Logları
    print("\n[Zaman Çizelgesi]")
    for log in sonuc["workflow_loglari"]:
        print(f" -> Adım {log.adim_no}: {log.adim_adi} ({log.baslangic_zamani} - {log.bitis_zamani}) [{log.durum}]")

    print("\n" + "=" * 60)
    print("🎉 YEREL OLLAMA & QWEN ENTEGRASYON TESTİ BAŞARIYLA TAMAMLANDI!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()

