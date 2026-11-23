"""
FlowAgent İhale & RFP Uyum Analiz Modülü Doğrulama Testi
"""
from utils import (
    ihale_sartname_ve_teklif_analizi,
    sirket_yetkinliklerini_chromaya_indeksle,
    DEFAULT_MODEL
)

def test_ihale_modulu():
    print("=" * 60)
    print("🚀 İHALE & RFP ANALİZ MODÜLÜ DOĞRULAMA TESTİ BAŞLIYOR")
    print("=" * 60)

    # 1. Şirket yetkinliklerini indeksle
    print("\n[Test 1] Şirket Yetkinlik Dokümanı ChromaDB İndeksleme...")
    coll = sirket_yetkinliklerini_chromaya_indeksle()
    print(f" -> ChromaDB Koleksiyonu Hazır. Doküman Sayısı: {coll.count()}")
    assert coll.count() > 0, "Yetkinlik dokümanı indekslenemedi!"

    # 2. Örnek İhale Şartnamesi ile Uyum Analizi
    ornek_sartname = (
        "KAMU İHALE KURUMU YAZILIM HİZMET ALIMI TEKNİK ŞARTNAMESİ\n"
        "1. İstekli firmanın ISO 27001 Bilgi Güvenliği belgesi olmalıdır.\n"
        "2. Çözüm Kubernetes üzerinde mikroservis mimarisinde koşmalıdır.\n"
        "3. Veri şifrelemede TLS 1.3 ve AES-256 standartları kullanılmalıdır.\n"
        "4. En az 2 adet PMP sertifikalı proje yöneticisi bulunmalıdır.\n"
        "5. 7/24 kesintisiz teknik destek ve kritik arızalara 30 dk müdahale taahhüt edilmelidir."
    )

    print("\n[Test 2] İhale Şartnamesi & Şirket Yetkinlikleri RAG Karşılaştırması...")
    rapor = ihale_sartname_ve_teklif_analizi(
        sartname_girdisi=ornek_sartname,
        dosya_adi="ornek_sartname.txt",
        model=DEFAULT_MODEL
    )

    print(f" -> İhale Başlığı: {rapor.ihale_basligi}")
    print(f" -> Genel Uyum Skoru: %{rapor.genel_uyum_skoru}")
    print(f" -> Çıkarılan Kriter Sayısı: {len(rapor.uyum_matrisi)}")

    print("\n[Uyum Matrisi Özeti]")
    for m in rapor.uyum_matrisi:
        print(f"  [{m.durum}] {m.madde_no} ({m.kategori}): {m.kriter_tanimi[:50]}... -> {m.sirket_karsiligi[:50]}...")

    print("\n[Otomatik Teklif Taslağı İlk 300 Karakter]")
    print(rapor.teklif_taslagi[:300] + "...\n")

    assert rapor.genel_uyum_skoru > 0, "Uyum skoru hesaplanamadı!"
    assert len(rapor.uyum_matrisi) > 0, "Uyum matrisi boş!"
    assert len(rapor.teklif_taslagi) > 100, "Teklif taslağı üretilemedi!"

    print("=" * 60)
    print("🎉 İHALE & RFP UYUM ANALİZ TESTİ BAŞARIYLA GEÇTİ!")
    print("=" * 60)

if __name__ == "__main__":
    test_ihale_modulu()

