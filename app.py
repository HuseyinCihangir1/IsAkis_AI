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
    SatinAlmaTalebi,
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
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }
    .metric-card {
        background: #ffffff;
        border-radius: 10px;
        padding: 16px 18px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
        margin-bottom: 12px;
    }
    .metric-title {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        color: #6c757d;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 1.3rem;
        font-weight: 700;
        color: #212529;
        margin-top: 4px;
    }
    .workflow-step {
        background-color: #f8f9fa;
        border-left: 4px solid #0d6efd;
        padding: 10px 15px;
        margin-bottom: 8px;
        border-radius: 0 8px 8px 0;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        font-size: 0.85rem;
        font-weight: 600;
        border-radius: 16px;
    }
    .badge-approved { background-color: #d1e7dd; color: #0f5132; }
    .badge-rejected { background-color: #f8d7da; color: #842029; }
    .badge-pending  { background-color: #fff3cd; color: #664d03; }
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
# Kenar Çubuğu (Yerel Ollama Yapılandırması)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9440/9440409.png", width=54)
    st.title("FlowAgent Mimarisi")
    st.caption("Yerel LLM (Ollama) • Tool Calling • RAG • SQLite")
    
    st.divider()
    st.markdown("### 🖥️ Yerel Model Yapılandırması")
    
    if ollama_online:
        st.success("🟢 Ollama Sunucusu Aktif (`localhost:11434`)")
    else:
        st.warning("⚠️ Ollama Servisi Kapalı (`localhost:11434`). Otomatik Kural Fallback Motoru devrede.")

    selected_model = st.text_input(
        "Ollama Model Adı",
        value=DEFAULT_MODEL,
        help="Bilgisayarınızda çalışan Ollama modeli (örn: qwen3.5:0.8b)"
    )

    st.divider()
    st.markdown("### 📚 Şirket Politikası (ChromaDB)")
    varsayilan_prosedur = ""
    if os.path.exists("prosedurler.txt"):
        with open("prosedurler.txt", "r", encoding="utf-8") as f:
            varsayilan_prosedur = f.read()

    prosedur_metni = st.text_area("Prosedür Metni", value=varsayilan_prosedur, height=120)
    if st.button("🔄 ChromaDB'yi Yenile & İndeksle", use_container_width=True):
        with st.spinner("Politika metni ChromaDB'ye indeksleniyor..."):
            try:
                prosedurleri_chromaya_indeksle(prosedur_metni)
                st.success("ChromaDB başarıyla güncellendi!")
            except Exception as e:
                st.error(f"Hata: {e}")

    st.divider()
    st.markdown("### ⚡ Hızlı Test Senaryoları")
    if st.button("📌 Senaryo 1: Onaylı Tedarikçi & Bütçe İçi", use_container_width=True):
        st.session_state["hizli_metin"] = (
            "XYZ Bilişim Teknolojileri A.Ş.\n"
            "Talep Türü: Donanım Alımı\n"
            "İçerik: 2 adet Geliştirici Bilgisayarı (Adet: 35.000 TRY) ve 2 adet Monitör (Adet: 5.000 TRY).\n"
            "Toplam Tutar: 80.000 TRY."
        )
    if st.button("⚠️ Senaryo 2: Onaysız Tedarikçi & Limit Aşımı", use_container_width=True):
        st.session_state["hizli_metin"] = (
            "Mega Nova Global Ltd. Şti.\n"
            "Talep Türü: Donanım Alımı\n"
            "İçerik: 4 adet AI GPU Sunucu Kabini (Adet: 45.000 TRY).\n"
            "Toplam Tutar: 180.000 TRY."
        )


# -----------------------------------------------------------------------------
# Ana Sayfa Üst Sekmeleri: İş Akışı vs. Yönetim & Analitik Paneli
# -----------------------------------------------------------------------------
tab_ana_akis, tab_analitik = st.tabs(["🚀 Satın Alma & Görev Akışı", "📊 Yönetim & Bütçe Dashboard"])

# =============================================================================
# SEKME 1: DOKÜMAN İŞLEME & ONAY AKIŞI
# =============================================================================
with tab_ana_akis:
    st.title("⚡ FlowAgent: Yerel LLM Destekli Doküman İşleme Paneli")
    st.markdown(
        f"Yerel bilgisayarınızda çalışan **Ollama ({selected_model})**, **OCR**, "
        "**Tool Calling (API)**, **ChromaDB RAG** ve yerleşik **SQLite Veritabanı** ile kurumsal satın alma platformu."
    )

    st.markdown("---")

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
                        prosedur_metni=prosedur_metni,
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
# SEKME 2: YÖNETİM & BÜTÇE DASHBOARD
# =============================================================================
with tab_analitik:
    st.title("📊 Satın Alma & Bütçe Yönetim Paneli")
    st.markdown("Veritabanında kayıtlı tüm taleplerin özet istatistikleri, kategori dağılımı ve dışa aktarma araçları.")
    
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
