# FlowAgent: Yerel AI Destekli Kurumsal Doküman İşleme & Onay Platformu

FlowAgent, Teknokent ve Ar-Ge ekosistemindeki şirketler (KOBİ Yazılım Şirketleri, B2B SaaS Girişimleri ve Kurumsal Ar-Ge Ofisleri) için geliştirilmiş; satın alma onaylarını, fatura ayrıştırmayı, B2B maliyet denetimini ve kamu/özel sektör ihalelerini otomatikleştiren uçtan uca yerel yapay zeka platformudur.

---

## 🌟 Temel Modüller & Özellikler

1. **🚀 Satın Alma & Görev Akışı:**
   - Dijital/taranmış PDF veya fatura görsellerinden OCR ile veri okuma.
   - Yerel LLM (`qwen3.5:0.8b` / `qwen2.5:0.5b`) ile yapısal Pydantic JSON ayrıştırma.
   - ERP tedarikçi doğrulaması ve bütçe aşım kontrolü (Tool Calling & RAG).
   - İnsan Onayı (Human-in-the-Loop) ile Onay/Ret karar masası.

2. **📑 İhale & RFP Analiz Modülü:**
   - Şartname maddelerini şirketin yetkinlikleri ve sertifikalarıyla (ISO 27001, CMMI, Kubernetes vb.) karşılaştıran **Teknik Uyum Matrisi (Compliance Matrix)**.
   - Şartnameye özel otomatik resmi **Teknik ve Ticari Teklif Mektubu Taslağı**.
   - Çıktıları tek tıkla `.md` (Word) ve `.csv` (Excel) olarak indirme.

3. **💼 B2B / SaaS & Proje Maliyet Denetimi:**
   - Bulut (AWS/Azure) ve SaaS lisans harcamalarında tasarruf ve optimizasyon önerileri.
   - 4691 & 5746 Sayılı Kanunlar kapsamında Kurumlar Vergisi ve KDV muafiyet hesabı.
   - TÜBİTAK 1501 / 1507 TEYDEB bütçe fasıl kodu ataması ve denetçi tavsiyeleri.

4. **📊 Yönetim & Bütçe Dashboard:**
   - Onaylanan/bekleyen bütçe analizleri ve kategori dağılım grafikleri.
   - Geçmiş ihale ve satın alma kararlarının SQLite veritabanından filtrelenip Excel/CSV olarak dışa aktarılması.

---

## 📁 Proje Dizin Yapısı

```text
IsAkis_AI_Project/
├── app.py                     # Streamlit tabanlı modern SaaS kullanıcı arayüzü
├── utils.py                   # Yerel LLM (Ollama), OCR, Tool Calling, RAG ve Workflow motoru
├── database.py                # Yerleşik SQLite bağlantı, tablo oluşturma ve CRUD katmanı
├── prosedurler.txt            # Şirket satın alma prosedürleri ve kategori limitleri
├── sirket_yetkinlikleri.txt   # Şirket yetkinlik profili, sertifikalar ve SLA taahhütleri
├── test_all.py                # Uçtan uca tüm modülleri doğrulayan birleşik test scripti
├── generate_samples.py        # Demo için örnek teklif/fatura PDF ve görsel üretici
├── requirements.txt           # Gerekli hafif Python bağımlılıkları
├── .gitignore                 # Git versiyon kontrolü hariç tutma kuralları
└── README.md                  # Proje dokümantasyonu
```

---

## 🚀 Kurulum ve Çalıştırma

### 1. Bağımlılıkları Yükleyin
```bash
pip install -r requirements.txt
```

### 2. Yerel Modeli Başlatın (Ollama)
```bash
ollama run qwen3.5:0.8b
```

### 3. Arayüzü Başlatın
```bash
streamlit run app.py
```
