import streamlit as st
import pandas as pd
import json
import os
import traceback
import requests
import io
from datetime import datetime
from utils import (
    gorev_akisini_yurut,
    prosedurleri_chromaya_indeksle,
    ihale_sartname_ve_teklif_analizi,
    sirket_yetkinliklerini_chromaya_indeksle,
    butce_ve_maliyet_denetimi_yap,
    tedarikci_kapsamli_risk_analizi,
    SatinAlmaTalebi,
    IhaleAnalizRaporu,
    ButceVeMaliyetDenetimi,
    TedarikciRiskSkoru,
    OCR_AVAILABLE,
    OLLAMA_BASE_URL,
    DEFAULT_MODEL
)
import database

# -----------------------------------------------------------------------------
# Veritabanını İlklendir
# -----------------------------------------------------------------------------
database.init_db()

# -----------------------------------------------------------------------------
# Sayfa Yapılandırması ve Kurumsal Stil
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="FlowAgent - Yerel AI Doküman İşleme Paneli",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* 1. Streamlit 'Deploy' butonunu, üst hamburger menüsünü ve alt 'Made with Streamlit' imzasını tamamen gizle */
    .stDeployButton,
    [data-testid="stToolbarActions"],
    [data-testid="stDecoration"],
    #MainMenu,
    footer {
        visibility: hidden !important;
        display: none !important;
    }
    
    /* 2. Üst Header çubuğunu temizle ve sayfa yerleşimini kusursuzlaştır */
    header[data-testid="stHeader"] {
        background: rgba(255, 255, 255, 0.7) !important;
        backdrop-filter: blur(8px) !important;
        height: 2.8rem !important;
        border-bottom: 1px solid rgba(226, 232, 240, 0.8) !important;
    }

    /* 3. Ana Gövde & Modern Tipografi / Boşluklar */
    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 1320px !important;
    }

    /* 4. Kurumsal Sekme (Tabs) Tasarımı - SaaS / Web Sitesi Düzeyinde */
    div[data-baseweb="tab-list"] {
        gap: 8px !important;
        background: #f1f5f9 !important;
        padding: 6px !important;
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        margin-bottom: 1.5rem !important;
    }
    
    button[data-baseweb="tab"] {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        padding: 8px 18px !important;
        border-radius: 8px !important;
        color: #475569 !important;
        border: none !important;
        background: transparent !important;
        transition: all 0.2s ease-in-out !important;
    }
    
    button[data-baseweb="tab"]:hover {
        color: #0f172a !important;
        background: rgba(255, 255, 255, 0.6) !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        background: #ffffff !important;
        color: #0284c7 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04) !important;
    }

    /* 5. Kartlar ve Göstergeler (Glassmorphism & Soft Shadow) */
    .metric-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
        border: 1px solid #e2e8f0;
        margin-bottom: 12px;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -4px rgba(0, 0, 0, 0.04);
    }
    .metric-title {
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.6px;
    }
    .metric-value {
        font-size: 1.35rem;
        font-weight: 700;
        color: #0f172a;
        margin-top: 5px;
    }

    /* 6. İş Akışı Zaman Çizelgesi Kartları */
    .workflow-step {
        background-color: #f8fafc;
        border-left: 4px solid #0284c7;
        padding: 12px 16px;
        margin-bottom: 10px;
        border-radius: 0 10px 10px 0;
        border-top: 1px solid #f1f5f9;
        border-right: 1px solid #f1f5f9;
        border-bottom: 1px solid #f1f5f9;
    }

    /* 7. Butonlar - SaaS Görünümü */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.55rem 1.25rem !important;
        box-shadow: 0 2px 4px rgba(2, 132, 199, 0.25) !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 8px rgba(2, 132, 199, 0.35) !important;
    }

    /* 8. Rozetler */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        font-size: 0.85rem;
        font-weight: 600;
        border-radius: 20px;
    }
    .badge-approved { background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
    .badge-rejected { background-color: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
    .badge-pending  { background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Session State Yönetimi
# -----------------------------------------------------------------------------
if "is_akisi_sonucu" not in st.session_state:
    st.session_state["is_akisi_sonucu"] = None
if "karar_durumu" not in st.session_state:
    st.session_state["karar_durumu"] = "BEKLEMEDE"
if "secili_dosya_adi" not in st.session_state:
    st.session_state["secili_dosya_adi"] = "Bilinmiyor"
if "aktif_purchase_id" not in st.session_state:
    st.session_state["aktif_purchase_id"] = None
if "ihale_raporu" not in st.session_state:
    st.session_state["ihale_raporu"] = None


# -----------------------------------------------------------------------------
# Ollama Durum Kontrolü
# -----------------------------------------------------------------------------
def check_ollama_status() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

ollama_online = check_ollama_status()

# -----------------------------------------------------------------------------
# Varsayılan Doküman Metinleri (Prosedür & Şirket Yetkinlikleri)
# -----------------------------------------------------------------------------
varsayilan_prosedur = ""
if os.path.exists("prosedurler.txt"):
    with open("prosedurler.txt", "r", encoding="utf-8") as f:
        varsayilan_prosedur = f.read()
else:
    varsayilan_prosedur = "Standart şirket satın alma ve bütçe onay prosedürü."

varsayilan_yetkinlik = ""
if os.path.exists("sirket_yetkinlikleri.txt"):
    with open("sirket_yetkinlikleri.txt", "r", encoding="utf-8") as f:
        varsayilan_yetkinlik = f.read()
else:
    varsayilan_yetkinlik = "Şirket ISO 9001 ve ISO 27001 sertifikalarına sahiptir. 7/24 teknik destek ve Kubernetes altyapısı mevcuttur."


# -----------------------------------------------------------------------------
# Kenar Çubuğu (Yerel LLM Model Seçimi)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9440/9440409.png", width=48)
    st.title("FlowAgent AI")
    st.caption("Yerel LLM Altyapısı")
    st.divider()

    st.markdown("### 🖥️ Model Seçimi")
    
    # Kullanıcı isteği: qwen3.5:0.8b ve daha düşük/hafif model seçeneği
    model_secenekleri = ["qwen3.5:0.8b", "qwen2.5:0.5b", "phi3:mini", "llama3.2:1b"]
    selected_model = st.selectbox(
        "Kullanılacak Yerel Model",
        options=model_secenekleri,
        index=0,
        help="qwen3.5:0.8b standart modeldir. Daha düşük kaynak için qwen2.5:0.5b seçebilirsiniz."
    )

    if ollama_online:
        st.success("🟢 Ollama Aktif (`11434`)")
    else:
        st.warning("⚠️ Ollama Kapalı (Yerel Kural Motoru Aktif)")

    st.divider()
    st.caption("🔒 **Veri Gizliliği:** Tüm analizler buluta veri göndermeden tamamen yerel makinede çalıştırılır.")


# -----------------------------------------------------------------------------
# Ana Sayfa Üst Sekmeleri: İş Akışı, İhale/RFP Modülü vs. Yönetim & Analitik
# -----------------------------------------------------------------------------
tab_ana_akis, tab_ihale, tab_arge_mevzuat, tab_analitik = st.tabs([
    "🚀 Satın Alma & Görev Akışı", 
    "📑 İhale & RFP Analiz Modülü",
    "💼 B2B / SaaS & Proje Maliyet Denetimi",
    "📊 Yönetim & Bütçe Dashboard"
])

# =============================================================================
# SEKME 1: DOKÜMAN İŞLEME & ONAY AKIŞI
# =============================================================================
with tab_ana_akis:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); padding: 22px 26px; border-radius: 14px; border: 1px solid #cbd5e1; margin-bottom: 20px;">
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <div>
                <h2 style="margin: 0; font-size: 1.65rem; color: #0f172a; font-weight: 800;">⚡ FlowAgent: Akıllı Doküman İşleme ve Onay Masası</h2>
                <p style="margin: 6px 0 0 0; color: #475569; font-size: 0.95rem;">
                    Yerel Yapay Zeka <strong>(Ollama Qwen)</strong>, <strong>OCR</strong>, <strong>Tool Calling</strong> ve <strong>RAG</strong> ile kurumsal satın alma otomasyonu.
                </p>
            </div>
            <div style="background: #ffffff; padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; color: #0284c7; box-shadow: 0 1px 3px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;">
                Model: """ + selected_model + """
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_input1, col_input2 = st.tabs(["📄 PDF veya Görsel Belge Yükle (OCR Destekli)", "✍️ Serbest Metin Olarak Gir"])
    girdi_data = None
    dosya_ismi = "Serbest Metin"

    with col_input1:
        yuklenen_dosya = st.file_uploader(
            "Fatura, Teklif Formu veya Satın Alma Belgesi (PDF, PNG, JPG)",
            type=["pdf", "png", "jpg", "jpeg"]
        )
        if yuklenen_dosya is not None:
            girdi_data = yuklenen_dosya
            dosya_ismi = yuklenen_dosya.name

    with col_input2:
        varsayilan_hizli = st.session_state.get("hizli_metin", "")
        metin_alani = st.text_area(
            "Talep metnini buraya yapıştırın",
            value=varsayilan_hizli,
            height=120,
            placeholder="Örn: ABC Teknoloji firmasından 2 adet sunucu toplam 70.000 TRY..."
        )
        if st.button("Metin Girişini Kullan", type="secondary"):
            if metin_alani.strip():
                girdi_data = metin_alani
                dosya_ismi = "Metin Girişi"
                st.session_state["aktif_metin_girisi"] = metin_alani
        elif varsayilan_hizli and girdi_data is None:
            girdi_data = varsayilan_hizli
            dosya_ismi = "Hızlı Test Metni"

    if "aktif_metin_girisi" in st.session_state and girdi_data is None:
        girdi_data = st.session_state["aktif_metin_girisi"]

    st.markdown("<br>", unsafe_allow_html=True)
    if girdi_data is not None:
        if st.button("🚀 Uçtan Uca Görev Akışını Çalıştır (Ollama Qwen)", type="primary"):
            st.session_state["karar_durumu"] = "BEKLEMEDE"
            st.session_state["secili_dosya_adi"] = dosya_ismi
            
            with st.status(f"🔄 Görev Akışı Yürütülüyor ({selected_model})...", expanded=True) as status:
                try:
                    sonuc = gorev_akisini_yurut(
                        girdi=girdi_data,
                        dosya_adi=dosya_ismi,
                        prosedur_metni=varsayilan_prosedur,
                        model=selected_model
                    )
                    st.session_state["is_akisi_sonucu"] = sonuc

                    talep_obj: SatinAlmaTalebi = sonuc["talep"]
                    butce_obj = sonuc["butce_sonucu"]
                    
                    yeni_id = database.add_request(
                        dosya_adi=dosya_ismi,
                        tedarikci=talep_obj.tedarikci_adi or "Belirtilmemiş",
                        vergi_no=talep_obj.vergi_no,
                        tutar=talep_obj.toplam_tutar or 0.0,
                        para_birimi=talep_obj.para_birimi or "TRY",
                        talep_turu=talep_obj.talep_turu or "Genel",
                        politika_uygun_mu=butce_obj.uygun_mu,
                        durum="BEKLEMEDE",
                        kalemler=[k.model_dump() for k in talep_obj.kalemler],
                        ek_veriler={
                            "arac_cagrilari": sonuc["arac_cagrilari"],
                            "butce_aciklama": butce_obj.aciklama,
                            "tespit_edilen_limit": butce_obj.tespit_edilen_limit
                        },
                        workflow_loglari=sonuc["workflow_loglari"]
                    )
                    st.session_state["aktif_purchase_id"] = yeni_id

                    status.update(label=f"✅ Görev Akışı Tamamlandı! Kayıt ID #{yeni_id} - İnsan Onayı Bekleniyor.", state="complete")
                except Exception as e:
                    status.update(label="❌ Akış sırasında hata oluştu!", state="error")
                    st.error(f"**Hata Detayı:** {str(e)}")
                    with st.expander("Detaylı Hata İzi (Traceback)"):
                        st.code(traceback.format_exc())

    # Görev Akışı Zaman Çizelgesi
    if st.session_state["is_akisi_sonucu"] is not None:
        akıs = st.session_state["is_akisi_sonucu"]
        talep: SatinAlmaTalebi = akıs["talep"]
        butce = akıs["butce_sonucu"]
        araclar = akıs["arac_cagrilari"]
        loglar = akıs["workflow_loglari"]

        st.markdown("---")
        st.subheader(f"⏱️ İzlenebilir Görev Akışı (Kayıt #{st.session_state.get('aktif_purchase_id', '-')})")
        
        col_log1, col_log2, col_log3, col_log4 = st.columns(4)
        adımlar = [
            ("1. OCR & Metin", loglar[0] if len(loglar) > 0 else None, col_log1),
            ("2. Yerel LLM (Qwen)", loglar[1] if len(loglar) > 1 else None, col_log2),
            ("3. Tool / API Calling", loglar[2] if len(loglar) > 2 else None, col_log3),
            ("4. RAG Politika", loglar[3] if len(loglar) > 3 else None, col_log4)
        ]
        
        for baslik, adim, col in adımlar:
            with col:
                if adim:
                    durum_renk = "#198754" if adim.durum == "BASARILI" else "#ffc107"
                    st.markdown(f"""
                    <div class="workflow-step" style="border-left-color: {durum_renk};">
                        <div style="font-weight:700; font-size:0.9rem;">{adim.adim_no}. {adim.adim_adi}</div>
                        <div style="font-size:0.75rem; color:#6c757d;">🕒 {adim.baslangic_zamani} - {adim.bitis_zamani}</div>
                        <div style="font-size:0.8rem; margin-top:4px;">{adim.detay}</div>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("📊 Ayrıştırılan Veriler & API Araç Yanıtları")
        
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Tedarikçi Firma</div>
                <div class="metric-value">{talep.tedarikci_adi or 'Bilinmiyor'}</div>
            </div>
            """, unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Toplam Tutar</div>
                <div class="metric-value">{talep.toplam_tutar:,.2f} {talep.para_birimi}</div>
            </div>
            """, unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Talep Türü</div>
                <div class="metric-value">{talep.talep_turu or 'Genel'}</div>
            </div>
            """, unsafe_allow_html=True)
        with m4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Model & Okuma</div>
                <div class="metric-value" style="font-size:1.05rem;">{selected_model} ({akıs['metin_cikarma_yontemi'].upper()})</div>
            </div>
            """, unsafe_allow_html=True)

        col_d1, col_d2 = st.columns([1.1, 0.9])

        with col_d1:
            st.markdown("##### 📦 Kalem Detayları (Qwen JSON Parser)")
            if talep.kalemler:
                df_kalem = pd.DataFrame([k.model_dump() for k in talep.kalemler])
                df_kalem.columns = ["Açıklama", "Miktar", "Birim", "Birim Fiyat", "Toplam Fiyat"]
                st.dataframe(df_kalem, use_container_width=True, hide_index=True)
            else:
                st.info("Kalem detayı bulunamadı.")

        with col_d2:
            st.markdown("##### 🔌 Tool Calling (ERP & Finans API Sonuçları)")
            if araclar:
                for item in araclar:
                    arac_adi = item["arac"]
                    yanit = item["api_yaniti"]
                    with st.container():
                        st.markdown(f"**🛠️ Araç:** `{arac_adi}`")
                        st.json(yanit, expanded=False)
            else:
                st.warning("Bu talep için dış API aracı tetiklenmedi.")

        st.markdown("##### 🛡️ RAG Şirket Politikası Denetimi")
        if butce.uygun_mu:
            st.success(f"✔️ **POLİTİKAYA UYGUN:** Standart limit: {butce.tespit_edilen_limit:,.2f} {butce.para_birimi}. Gerekçe: {butce.aciklama}")
        else:
            st.warning(f"⚠️ **EK ONAY / LİMİT AŞIMI:** Standart limit: {butce.tespit_edilen_limit:,.2f} {butce.para_birimi}. Gerekçe: {butce.aciklama}")
            if butce.gerekli_onaylar:
                st.markdown("**Gerekli Onay Mercileri:** " + ", ".join([f"`{o}`" for o in butce.gerekli_onaylar]))

        # Teknokent / KOBİ Maliyet & Teşvik Değerlendirmesi
        st.markdown("---")
        st.subheader("💼 B2B & Proje Maliyet / Teşvik Uygunluğu")
        arge_analiz = butce_ve_maliyet_denetimi_yap(talep)
        
        col_ar1, col_ar2, col_ar3 = st.columns(3)
        with col_ar1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Harcama Sınıfı</div>
                <div class="metric-value" style="font-size:1.05rem;">{arge_analiz.harcama_turu}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_ar2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Proje Maliyet Faslı</div>
                <div class="metric-value" style="font-size:1.05rem;">{arge_analiz.tubitak_butce_kodu}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_ar3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Tahmini Vergi/Teşvik Avantajı</div>
                <div class="metric-value" style="color:#0d6efd;">{arge_analiz.tahmini_vergi_avantaji:,.2f} TRY</div>
            </div>
            """, unsafe_allow_html=True)

        with st.expander("📋 Maliyet Optimizasyonu & YMM Notu"):
            st.write(f"**Tasarruf Tavsiyesi:** {arge_analiz.maliyet_optimizasyon_onerisi}")
            st.info(f"**Denetçi & Muhasebe Notu:** {arge_analiz.denetim_ve_ymm_notu}")

        # Tedarikçi Risk Puanlaması
        risk_bilgi = tedarikci_kapsamli_risk_analizi(talep.tedarikci_adi or "", talep.toplam_tutar or 0.0)
        with st.expander(f"🛡️ Tedarikçi Risk Değerlendirmesi ({risk_bilgi.risk_seviyesi} - Güven Skoru: {risk_bilgi.skor}/100)"):
            st.write(f"**Tavsiye Edilen Ödeme Vadesi:** `{risk_bilgi.tavsiye_edilen_odeme_sartlari}`")
            for f in risk_bilgi.risk_faktörleri:
                st.markdown(f"- 📌 {f}")

        # İnsan Onay Paneli
        st.markdown("---")
        st.subheader("✍️ İnsan Onayı ve Karar Masası (Human-in-the-Loop)")

        durum = st.session_state["karar_durumu"]
        if durum == "BEKLEMEDE":
            st.info("🕒 **Onay Bekliyor:** Yerel AI ve politika kontrolleri tamamlandı. Lütfen inceleyip nihai kararı verin.")
        elif durum == "ONAYLANDI":
            st.success("✅ **Talep Onaylandı:** Yönetici tarafından onaylandı ve veritabanına kaydedildi.")
        elif durum == "REDDEDILDI":
            st.error("❌ **Talep Reddedildi:** Talep bütçe/tedarikçi uygunsuzluğu nedeniyle reddedildi.")

        col_not, col_butonlar = st.columns([1.2, 0.8])
        with col_not:
            yonetici_notu = st.text_area(
                "Yönetici Karar Notu",
                placeholder="Gerekçe veya ek açıklama yazabilirsiniz...",
                height=90
            )
        with col_butonlar:
            st.markdown("<p style='font-size:0.85rem; font-weight:600;'>Yetkili Kararı:</p>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            aktif_id = st.session_state.get("aktif_purchase_id")
            
            with b1:
                if st.button("✅ Onayla", type="primary", use_container_width=True):
                    st.session_state["karar_durumu"] = "ONAYLANDI"
                    if aktif_id:
                        database.update_request_status(
                            purchase_id=aktif_id,
                            durum="ONAYLANDI",
                            yonetici_notu=yonetici_notu or "Yönetici tarafından onaylandı.",
                            onaylayan="Yetkili Yönetici"
                        )
                    st.rerun()
            with b2:
                if st.button("❌ Reddet", type="secondary", use_container_width=True):
                    st.session_state["karar_durumu"] = "REDDEDILDI"
                    if aktif_id:
                        database.update_request_status(
                            purchase_id=aktif_id,
                            durum="REDDEDILDI",
                            yonetici_notu=yonetici_notu or "Yönetici tarafından reddedildi.",
                            onaylayan="Yetkili Yönetici"
                        )
                    st.rerun()

        with st.expander("🔍 Görev Akışı ve Karar Verilerini JSON İndir"):
            rapor = {
                "purchase_id": st.session_state.get("aktif_purchase_id"),
                "dosya": st.session_state["secili_dosya_adi"],
                "model": selected_model,
                "talep": talep.model_dump(),
                "api_tool_cagrilari": araclar,
                "rag_politika_sonucu": butce.model_dump(),
                "workflow_zamanlari": [log.model_dump() for log in loglar],
                "insan_karari": {
                    "durum": st.session_state["karar_durumu"],
                    "yonetici_notu": yonetici_notu,
                    "tarih": datetime.now().isoformat()
                }
            }
            json_txt = json.dumps(rapor, ensure_ascii=False, indent=2)
            st.code(json_txt, language="json")
            st.download_button(
                "💾 Uçtan Uca Raporu İndir (.json)",
                data=json_txt,
                file_name=f"flowagent_ollama_rapor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )


# =============================================================================
# SEKME 2: İHALE & RFP ANALİZ MODÜLÜ (UYUM MATRİSİ & TEKLİF TASLAĞI)
# =============================================================================
with tab_ihale:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); padding: 22px 26px; border-radius: 14px; border: 1px solid #cbd5e1; margin-bottom: 20px;">
        <h2 style="margin: 0; font-size: 1.65rem; color: #0f172a; font-weight: 800;">📑 İhale / RFP Teknik Uyum ve Otomatik Teklif Modülü</h2>
        <p style="margin: 6px 0 0 0; color: #475569; font-size: 0.95rem;">
            Şartname kriterlerini şirket yetkinlik dokümanlarıyla <strong>(ChromaDB RAG)</strong> karşılaştırarak <strong>Teknik Uyum Matrisi</strong> ve <strong>Resmi Teklif Mektubu</strong> üretir.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # İhale Girdisi
    col_ihale_sol, col_ihale_sag = st.columns([1, 1])

    with col_ihale_sol:
        st.subheader("1. İhale Şartnamesi / RFP Yükleme")
        ihale_dosya = st.file_uploader(
            "İhale Teknik Şartnamesi (PDF, PNG, JPG)",
            type=["pdf", "png", "jpg", "jpeg"],
            key="ihale_uploader"
        )
        
        ihale_ornek_metin = (
            "T.C. ULAŞTIRMA VE ALTYAPI BAKANLIĞI BİLGİ İŞLEM DAİRESİ BAŞKANLIĞI\n"
            "KURUMSAL MİKROSERVİS VE VERİ GÜVENLİĞİ ENTEGRASYON PROJESİ TEKNİK ŞARTNAMESİ\n\n"
            "1. Yüklenici firmanın ISO 27001 Bilgi Güvenliği ve CMMI Seviye 3 sertifikalarına sahip olması şarttır.\n"
            "2. Sistem, Kubernetes kümeleme üzerinde yüksek erişilebilir mikroservis mimarisinde çalışacaktır.\n"
            "3. Veri tabanı ve ağ iletişiminde TLS 1.3 ve AES-256 uçtan uca şifreleme sağlanacaktır.\n"
            "4. Proje ekibinde en az 2 adet PMP sertifikalı kıdemli proje yöneticisi görevlendirilecektir.\n"
            "5. Canlıya geçişten sonra 7/24 kesintisiz teknik destek, P1 arızalara 30 dakika içinde müdahale ve %99.95 Uptime taahhüdü verilecektir."
        )

        ihale_metin_alani = st.text_area(
            "Veya Şartname Metnini Buraya Yapıştırın",
            value=ihale_ornek_metin,
            height=160,
            key="ihale_text_input"
        )

    with col_ihale_sag:
        st.subheader("2. Karşılaştırılacak Şirket Profili (RAG Kaynağı)")
        st.info("💡 Sistem, ChromaDB'de kayıtlı olan kurumsal yetkinliklerinizi, Ar-Ge sertifikalarınızı ve SLA taahhütlerinizi referans alarak analiz yapar.")
        st.text_area(
            "Aktif Şirket Yetkinlik Dokümanı (sirket_yetkinlikleri.txt)",
            value=varsayilan_yetkinlik,
            height=210,
            disabled=True
        )

    # Analiz Başlatma Butonu
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔍 İhale Şartnamesini Analiz Et & Teklif Taslağı Üret", type="primary"):
        girdi_ihale = ihale_dosya if ihale_dosya is not None else ihale_metin_alani
        dosya_adi_ihale = ihale_dosya.name if ihale_dosya is not None else "Şartname Metni"

        with st.status(f"🔄 İhale Kriterleri & Şirket Yetkinlikleri Karşılaştırılıyor ({selected_model})...", expanded=True) as status_ihale:
            try:
                st.write("📑 Adım 1: Şartname metni ve teknik gereksinimler çıkarılıyor...")
                st.write("🏢 Adım 2: ChromaDB vektör veri tabanından şirket yetkinlik maddeleri sorgulanıyor (RAG)...")
                st.write(f"🧠 Adım 3: Yerel Qwen modeli ({selected_model}) ile teknik kriter uyum matrisi ve teklif mektubu oluşturuluyor...")
                
                rapor_ihale = ihale_sartname_ve_teklif_analizi(
                    sartname_girdisi=girdi_ihale,
                    dosya_adi=dosya_adi_ihale,
                    sirket_yetkinlik_metni=varsayilan_yetkinlik,
                    model=selected_model
                )
                st.session_state["ihale_raporu"] = rapor_ihale
                # İhale Analizini Kalıcı SQLite Veritabanına Kaydet
                database.add_tender_analysis(
                    ihale_basligi=rapor_ihale.ihale_basligi,
                    kurum_adi=rapor_ihale.kurum_adi or "İhale Makamı",
                    tahmini_butce=rapor_ihale.tahmini_butce or "Belirtilmedi",
                    genel_uyum_skoru=rapor_ihale.genel_uyum_skoru,
                    kriter_sayisi=len(rapor_ihale.uyum_matrisi),
                    uyum_matrisi=[m.model_dump() for m in rapor_ihale.uyum_matrisi],
                    eksikler=rapor_ihale.eksik_ve_riskler,
                    teklif_taslagi=rapor_ihale.teklif_taslagi
                )
                
                status_ihale.update(label="✅ İhale Uyum Analizi ve Teklif Taslağı Başarıyla Üretildi & Veritabanına Kaydedildi!", state="complete")
            except Exception as e:
                status_ihale.update(label="❌ İhale analizi sırasında hata oluştu!", state="error")
                st.error(f"Hata detayı: {str(e)}")
                with st.expander("Hata Ayrıntısı"):
                    st.code(traceback.format_exc())

    # İhale Raporu Sonuç Ekranı
    if st.session_state["ihale_raporu"] is not None:
        rap: IhaleAnalizRaporu = st.session_state["ihale_raporu"]

        st.markdown("---")
        st.subheader("🎯 1. İhale Özeti ve Genel Uyum Durumu")

        c_ih1, c_ih2, c_ih3, c_ih4 = st.columns(4)
        with c_ih1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">İhale Konusu / Başlık</div>
                <div class="metric-value" style="font-size:1.05rem;">{rap.ihale_basligi[:40]}...</div>
            </div>
            """, unsafe_allow_html=True)
        with c_ih2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">İlgili Kurum / İdare</div>
                <div class="metric-value" style="font-size:1.1rem;">{rap.kurum_adi or 'Bakanlık / Kamu'}</div>
            </div>
            """, unsafe_allow_html=True)
        with c_ih3:
            skor_renk = "#155724" if rap.genel_uyum_skoru >= 80 else "#856404"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Teknik Uyum Skoru</div>
                <div class="metric-value" style="color: {skor_renk};">%{rap.genel_uyum_skoru}</div>
            </div>
            """, unsafe_allow_html=True)
        with c_ih4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Toplam Kriter Sayısı</div>
                <div class="metric-value">{len(rap.uyum_matrisi)} Madde</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # UYUM MATRİSİ TABLOSU
        st.subheader("📊 2. İhale / Teklif Uyum Matrisi")
        st.caption("Şartnamede aranan her bir maddenin şirketimizin mevcut yetkinlik, sertifika ve altyapı dokümanlarıyla karşılaştırması.")

        matris_data = []
        for m in rap.uyum_matrisi:
            durum_simge = "✅ UYGUN" if m.durum.upper() == "UYGUN" else ("⚠️ KISMEN" if "KISMEN" in m.durum.upper() else "❌ UYGUN DEĞİL")
            matris_data.append({
                "Madde No": m.madde_no,
                "Kategori": m.kategori,
                "Şartname Gereksinimi": m.kriter_tanimi,
                "Uyum Durumu": durum_simge,
                "Şirket Karşılığı & Altyapı Notu": m.sirket_karsiligi
            })

        df_matris = pd.DataFrame(matris_data)
        st.dataframe(df_matris, use_container_width=True, hide_index=True)

        if rap.eksik_ve_riskler:
            with st.expander("⚠️ Olası Riskler ve Tamamlanması Gereken Eksikler"):
                for risk in rap.eksik_ve_riskler:
                    st.markdown(f"- 🔸 {risk}")

        st.markdown("---")

        # OTOMATİK TEKLİF TASLAĞI
        st.subheader("📝 3. Otomatik Oluşturulan Kurumsal İhale Teklif Taslağı")
        st.caption("Teknik kriterlerin şirket yetkinlikleriyle eşleştirilmesi sonucunda üretilen resmi teklif mektubu.")

        st.markdown(rap.teklif_taslagi)

        col_ih_down1, col_ih_down2 = st.columns(2)
        with col_ih_down1:
            st.download_button(
                label="📄 Teklif Taslağını İndir (.md / Word)",
                data=rap.teklif_taslagi,
                file_name=f"ihale_teklif_taslagi_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown",
                use_container_width=True
            )
        with col_ih_down2:
            matris_csv = df_matris.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📊 Uyum Matrisini İndir (.csv / Excel)",
                data=matris_csv,
                file_name=f"ihale_uyum_matrisi_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )


# =============================================================================
# SEKME 3: B2B / SAAS & PROJE MALİYET DENETİMİ (KOBİ & KURUMSAL AR-GE)
# =============================================================================
with tab_arge_mevzuat:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); padding: 22px 26px; border-radius: 14px; border: 1px solid #cbd5e1; margin-bottom: 20px;">
        <h2 style="margin: 0; font-size: 1.65rem; color: #0f172a; font-weight: 800;">💼 B2B / SaaS & Proje Maliyet Denetim Modülü</h2>
        <p style="margin: 6px 0 0 0; color: #475569; font-size: 0.95rem;">
            Bulut/SaaS lisans optimizasyonu, proje bütçe sınırları ve <strong>5746/4691 Ar-Ge Kurumlar Vergisi İstisnası</strong> denetim motoru.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_arge_sol, col_arge_sag = st.columns([1.1, 0.9])
    with col_arge_sol:
        st.subheader("1. Proje & Harcama Detayları")
        arge_proje_adi = st.text_input(
            "Proje / Ürün Adı",
            value="Kurumsal B2B Bulut ve Büyük Dil Modeli Entegrasyonu"
        )
        arge_kategori = st.selectbox(
            "Harcama Sınıfı",
            [
                "Yazılım Lisansı / Bulut Sunucu / SaaS (AWS, Azure, OpenAI vb.)",
                "Donanım / Ar-Ge Ekipmanı / Sunucu Alımı",
                "Dış Kaynak Yazılım & Teknik Danışmanlık",
                "Test, Kalite Güvence ve Sertifikasyon",
                "Genel Ofis ve Sarf Malzemesi"
            ]
        )
        arge_tedarikci = st.text_input("Tedarikçi / Sağlayıcı Firma", value="Mega Nova Cloud & AI Services Ltd.")
        arge_tutar = st.number_input("Harcama Tutarı (KDV Hariç TRY)", min_value=1000.0, value=120000.0, step=5000.0)
        arge_aciklama = st.text_area(
            "Harcama Amacı ve Kullanım Kapsamı",
            value="Müşteri B2B projeleri için yıllık ayrılmış bulut sunucu kapasitesi ve mikroservis API aboneliği."
        )

    with col_arge_sag:
        st.subheader("2. Maliyet Optimizasyonu & Teşvik Analizi")
        st.caption("Şirket bütçe kuralları, KOBİ tasarruf önerileri ve Teknokent mevzuatı birlikte değerlendirilir.")

        sahte_talep = SatinAlmaTalebi(
            tedarikci_adi=arge_tedarikci,
            toplam_tutar=arge_tutar,
            para_birimi="TRY",
            talep_turu=arge_kategori,
            kalemler=[{"aciklama": arge_aciklama, "miktar": 1, "birim": "Adet", "birim_fiyat": arge_tutar, "toplam_fiyat": arge_tutar}]
        )
        degerlendirme = butce_ve_maliyet_denetimi_yap(sahte_talep, proje_adi=arge_proje_adi)

        c_ar_m1, c_ar_m2 = st.columns(2)
        with c_ar_m1:
            st.metric("Ar-Ge / Vergi İstisnası Oranı", f"%{degerlendirme.muafiyet_veya_tesvik_orani}")
        with c_ar_m2:
            st.metric("Tahmini Vergi & Teşvik Tasarrufu", f"{degerlendirme.tahmini_vergi_avantaji:,.2f} TRY")

        if degerlendirme.uygun_mu:
            st.success(f"✔️ **BÜTÇEYE UYGUN:** {degerlendirme.tubitak_butce_kodu}")
        else:
            st.warning(f"⚠️ **KONTROL GEREKLİ:** {degerlendirme.tubitak_butce_kodu}")

        st.markdown(f"**💡 Maliyet & Tasarruf Önerisi:** {degerlendirme.maliyet_optimizasyon_onerisi}")
        st.info(f"**📋 YMM & Denetçi Notu:** {degerlendirme.denetim_ve_ymm_notu}")

        if st.button("💾 Değerlendirmeyi Şirket Arşivine Kaydet", use_container_width=True):
            database.add_arge_evaluation(
                talep_id=None,
                tedarikci=arge_tedarikci,
                tutar=arge_tutar,
                kategori=arge_kategori,
                arge_kapsaminda_mi=degerlendirme.uygun_mu,
                muafiyet_orani=degerlendirme.muafiyet_veya_tesvik_orani,
                tahmini_vergi_avantaji=degerlendirme.tahmini_vergi_avantaji,
                tubitak_butce_kodu=degerlendirme.tubitak_butce_kodu,
                teknokent_gerekce=degerlendirme.maliyet_optimizasyon_onerisi,
                denetim_notu=degerlendirme.denetim_ve_ymm_notu
            )
            st.success("✅ Maliyet ve bütçe denetim kaydı başarıyla SQLite veritabanına işlendi.")

    st.markdown("---")
    st.subheader("📜 Geçmiş B2B / Ar-Ge Maliyet ve Teşvik Denetim Kayıtları")
    arge_gecmis = database.get_arge_evaluations(limit=30)
    if arge_gecmis:
        df_arge = pd.DataFrame(arge_gecmis)
        kolonlar_ar = ["id", "tarih", "tedarikci", "tutar", "kategori", "tubitak_butce_kodu", "tahmini_vergi_avantaji", "teknokent_gerekce"]
        mevcut_ar = [c for c in kolonlar_ar if c in df_arge.columns]
        st.dataframe(df_arge[mevcut_ar], use_container_width=True, hide_index=True)
    else:
        st.info("Kayıtlı maliyet/bütçe denetim kaydı bulunamadı.")


# =============================================================================
# SEKME 4: YÖNETİM & BÜTÇE DASHBOARD
# =============================================================================
with tab_analitik:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); padding: 22px 26px; border-radius: 14px; border: 1px solid #cbd5e1; margin-bottom: 20px;">
        <h2 style="margin: 0; font-size: 1.65rem; color: #0f172a; font-weight: 800;">📊 Satın Alma & Bütçe Yönetim Paneli</h2>
        <p style="margin: 6px 0 0 0; color: #475569; font-size: 0.95rem;">
            Veritabanında kayıtlı tüm taleplerin özet istatistikleri, kategori dağılımı ve kurumsal rapor dışa aktarma araçları.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    db_kayitlari = database.get_requests(limit=100)
    
    if db_kayitlari:
        df = pd.DataFrame(db_kayitlari)
        
        # Üst Metrikler
        toplam_talep = len(df)
        onaylananlar = df[df["durum"] == "ONAYLANDI"]
        reddedilenler = df[df["durum"] == "REDDEDILDI"]
        bekleyenler = df[df["durum"] == "BEKLEMEDE"]
        
        toplam_tutar = df["tutar"].sum()
        onaylanan_tutar = onaylananlar["tutar"].sum()
        
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Toplam Talep Sayısı", f"{toplam_talep} Adet")
        with k2:
            st.metric("Onaylanan Toplam Bütçe", f"{onaylanan_tutar:,.2f} TRY")
        with k3:
            st.metric("Onay Oranı", f"%{(len(onaylananlar)/toplam_talep*100):.1f}" if toplam_talep > 0 else "%0")
        with k4:
            st.metric("Bekleyen Talep", f"{len(bekleyenler)} Adet")

        st.markdown("---")

        # Grafikler
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("📁 Talep Türü / Kategori Dağılımı")
            if "talep_turu" in df.columns:
                kategori_sayilari = df["talep_turu"].value_counts()
                st.bar_chart(kategori_sayilari)

        with col_g2:
            st.subheader("⚖️ Onay Durumları Dağılımı")
            durum_sayilari = df["durum"].value_counts()
            st.bar_chart(durum_sayilari)

        # İhale Kayıtları Özeti (Dashboard)
        st.markdown("---")
        st.subheader("🏆 Kayıtlı İhale & Teklif Geçmişi")
        ihale_gecmis = database.get_tender_analyses(limit=10)
        if ihale_gecmis:
            df_ih = pd.DataFrame(ihale_gecmis)
            kolon_ih = ["id", "tarih", "ihale_basligi", "kurum_adi", "tahmini_butce", "genel_uyum_skoru", "kriter_sayisi"]
            mevcut_ih = [c for c in kolon_ih if c in df_ih.columns]
            st.dataframe(df_ih[mevcut_ih], use_container_width=True, hide_index=True)
        else:
            st.caption("Henüz kayıtlı ihale analizi bulunmuyor.")

        st.markdown("---")
        st.subheader("📑 Tüm Satın Alma Kayıtları (SQLite Tablosu)")
        
        # Filtreleme Seçenekleri
        filtre_kolon1, filtre_kolon2 = st.columns([1, 2])
        with filtre_kolon1:
            durum_filtre = st.selectbox("Duruma Göre Filtrele", ["Tümü", "BEKLEMEDE", "ONAYLANDI", "REDDEDILDI"])
        
        df_gosterim = df.copy()
        if durum_filtre != "Tümü":
            df_gosterim = df_gosterim[df_gosterim["durum"] == durum_filtre]

        kolonlar = ["id", "olusturulma_tarihi", "tedarikci", "tutar", "para_birimi", "talep_turu", "durum", "onaylayan", "yonetici_notu"]
        mevcut_kolonlar = [c for c in kolonlar if c in df_gosterim.columns]
        st.dataframe(df_gosterim[mevcut_kolonlar], use_container_width=True, hide_index=True)

        # CSV / Excel Dışa Aktarma
        csv_data = df_gosterim[mevcut_kolonlar].to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Kayıtları CSV Olarak İndir (Excel Uyumlu)",
            data=csv_data,
            file_name=f"satin_alma_kayitlari_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("Veritabanında henüz analiz edilecek satın alma talebi bulunmuyor. Birinci sekmeden belge yükleyebilirsiniz.")
