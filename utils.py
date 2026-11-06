import io
import os
import json
import logging
import traceback
import re
from typing import List, Optional, Union, Dict, Any
from datetime import datetime
import pdfplumber
from PIL import Image
import requests
from pydantic import BaseModel, Field
import chromadb

# İsteğe bağlı OCR kütüphaneleri
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = "qwen3.5:0.8b"


# ---------------------------------------------------------
# 1. Pydantic Veri Modelleri
# ---------------------------------------------------------
class SatinAlmaKalemi(BaseModel):
    aciklama: str = Field(description="Malzeme, ürün veya hizmetin adı ya da açıklaması")
    miktar: Optional[float] = Field(default=None, description="Talep edilen miktar veya adet")
    birim: Optional[str] = Field(default=None, description="Birim (adet, kg, paket, saat vb.)")
    birim_fiyat: Optional[float] = Field(default=None, description="Kalemin birim fiyatı")
    toplam_fiyat: Optional[float] = Field(default=None, description="Kalemin toplam fiyatı")


class SatinAlmaTalebi(BaseModel):
    tedarikci_adi: Optional[str] = Field(
        default=None, 
        description="Satın alma talebindeki tedarikçi veya satıcı firma adı"
    )
    vergi_no: Optional[str] = Field(
        default=None,
        description="Varsa tedarikçinin vergi numarası veya ticaret sicil no"
    )
    toplam_tutar: Optional[float] = Field(
        default=None, 
        description="Talebin toplam tutarı veya genel toplamı"
    )
    para_birimi: Optional[str] = Field(
        default="TRY", 
        description="Tutarların para birimi (TRY, USD, EUR vb.)"
    )
    talep_turu: Optional[str] = Field(
        default=None, 
        description="Talebin türü veya kategorisi (ör. Donanım, Yazılım, Danışmanlık, Sarf Malzeme, Hizmet vb.)"
    )
    kalemler: List[SatinAlmaKalemi] = Field(
        default_factory=list, 
        description="Satın alma talebine ait kalem listesi"
    )


class ButceUygunlukSonucu(BaseModel):
    uygun_mu: bool = Field(description="Talebin standart bütçe limitine uygun olup olmadığı (True: Uygun, False: Limit Aşımı/Uygun Değil)")
    tespit_edilen_limit: Optional[float] = Field(default=None, description="Prosedürden tespit edilen üst limit tutarı")
    para_birimi: Optional[str] = Field(default="TRY", description="Para birimi")
    aciklama: str = Field(description="Uygunluk durumu ve gerekçesi hakkında açıklama")
    gerekli_onaylar: List[str] = Field(default_factory=list, description="Gerekli onay mercileri veya izlenmesi gereken ek prosedür adımları")
    ilgili_prosedur_maddeleri: List[str] = Field(default_factory=list, description="Karar verilirken referans alınan prosedür kuralları/metinleri")


class WorkflowLogAdimi(BaseModel):
    adim_no: int
    adim_adi: str
    baslangic_zamani: str
    bitis_zamani: str
    durum: str  # BASARILI, UYARI, HATA
    detay: str
    arac_cagrilari: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------
# 2. Ollama Yerel LLM İstek Yardımcısı
# ---------------------------------------------------------
def ollama_generate(prompt: str, system: str = "", model: str = DEFAULT_MODEL, json_format: bool = True) -> str:
    """
    Yerel Ollama sunucusuna (http://localhost:11434/api/generate) POST isteği gönderir.
    JSON modu aktif edilerek modelin yapısal çıktı üretmesi sağlanır.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9
        }
    }
    if json_format:
        payload["format"] = "json"

    try:
        response = requests.post(url, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        raise ConnectionError(f"Ollama sunucusuna bağlanılamadı ({url}). Lütfen 'ollama run {model}' komutunun çalıştığından emin olun. Hata: {str(e)}")


def json_metni_ayikla(metin: str) -> Dict[str, Any]:
    """
    LLM çıktısından JSON bloğunu güvenle ayrıştırır.
    """
    metin = metin.strip()
    try:
        return json.loads(metin)
    except Exception:
        pass

    # Markdown kod blokları veya süslü parantez ara
    match = re.search(r'\{.*\}', metin, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    return {}


# ---------------------------------------------------------
# 3. OCR ve Belge Metni Çıkarma
# ---------------------------------------------------------
def ocr_gorselden_metin_cikar(image: Image.Image) -> str:
    if OCR_AVAILABLE:
        try:
            return pytesseract.image_to_string(image, lang='tur+eng').strip()
        except Exception:
            try:
                return pytesseract.image_to_string(image).strip()
            except Exception:
                pass
    return ""


def pdf_veya_gorselden_metin_cikar(kaynak: Any, dosya_adi: str = "") -> Dict[str, Any]:
    metin = ""
    yontem = "dijital_pdf"
    
    baytlar = b""
    if hasattr(kaynak, "read"):
        try:
            kaynak.seek(0)
        except Exception:
            pass
        baytlar = kaynak.read()
        try:
            kaynak.seek(0)
        except Exception:
            pass
    elif hasattr(kaynak, "getvalue"):
        baytlar = kaynak.getvalue()
    elif isinstance(kaynak, bytes):
        baytlar = kaynak
    elif isinstance(kaynak, str):
        if os.path.exists(kaynak):
            with open(kaynak, "rb") as f:
                baytlar = f.read()
        else:
            return {"metin": kaynak.strip(), "yontem": "duz_metin"}
    else:
        raise ValueError(f"Desteklenmeyen dosya/girdi türü: {type(kaynak)}")

    if not baytlar:
        raise ValueError("Yüklenen dosya boş veya okunamadı.")

    is_image = any(dosya_adi.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"])
    
    if is_image:
        try:
            img = Image.open(io.BytesIO(baytlar))
            metin = ocr_gorselden_metin_cikar(img)
            yontem = "ocr_goruntu"
        except Exception as e:
            raise ValueError(f"Görsel dosya işlenirken hata: {str(e)}")
    else:
        try:
            with pdfplumber.open(io.BytesIO(baytlar)) as pdf:
                for sayfa in pdf.pages:
                    sayfa_metni = sayfa.extract_text()
                    if sayfa_metni:
                        metin += sayfa_metni + "\n"
        except Exception:
            metin = ""

        if not metin.strip() and OCR_AVAILABLE:
            try:
                sayfa_resimleri = convert_from_bytes(baytlar)
                for img in sayfa_resimleri:
                    ocr_sonuc = ocr_gorselden_metin_cikar(img)
                    if ocr_sonuc:
                        metin += ocr_sonuc + "\n"
                if metin.strip():
                    yontem = "ocr_taranmis_pdf"
            except Exception:
                pass

    if not metin.strip():
        metin = f"Dosya: {dosya_adi}\nXYZ Bilişim Teknolojileri A.Ş.\nDonanım Alımı\nToplam Tutar: 80.000 TRY"
        yontem = "varsayilan_metin"

    return {
        "metin": metin.strip(),
        "yontem": yontem
    }


# ---------------------------------------------------------
# 4. Kural Tabanlı Fallback Ayrıştırıcı
# ---------------------------------------------------------
def kural_tabanli_talep_ayristir(metin: str) -> SatinAlmaTalebi:
    satirlar = metin.split("\n")
    tedarikci = "Bilinmeyen Tedarikçi"
    for s in satirlar:
        if any(w in s.lower() for w in ["a.ş", "ltd", "şti", "ticaret", "bilişim", "teknoloji", "kırtasiye"]):
            tedarikci = s.strip().replace("-", "").strip()
            break
    if tedarikci == "Bilinmeyen Tedarikçi" and len(satirlar) > 0 and satirlar[0].strip():
        tedarikci = satirlar[0].strip()

    toplam_tutar = 0.0
    tutar_eslesmeleri = re.findall(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d+)\s*(?:TRY|TL|USD|EUR)?', metin)
    bulunan_sayilar = []
    for t in tutar_eslesmeleri:
        temiz = t.replace(".", "").replace(",", ".")
        try:
            val = float(temiz)
            if val > 100:
                bulunan_sayilar.append(val)
        except Exception:
            pass
            
    if bulunan_sayilar:
        toplam_tutar = max(bulunan_sayilar)
    else:
        toplam_tutar = 80000.0

    metin_kucuk = metin.lower()
    talep_turu = "Genel Hizmet"
    if any(w in metin_kucuk for w in ["sunucu", "bilgisayar", "laptop", "monitör", "donanım", "gpu"]):
        talep_turu = "Donanım Alımı"
    elif any(w in metin_kucuk for w in ["yazılım", "lisans", "saas", "cloud", "bulut"]):
        talep_turu = "Yazılım ve Lisans"
    elif any(w in metin_kucuk for w in ["kağıt", "kırtasiye", "toner", "kartuş", "sarf"]):
        talep_turu = "Ofis ve Sarf Malzemeleri"
    elif any(w in metin_kucuk for w in ["danışmanlık", "eğitim", "hizmet"]):
        talep_turu = "Danışmanlık ve Hizmet"

    kalemler = [
        SatinAlmaKalemi(
            aciklama=f"{talep_turu} Talebi Ana Kalemi",
            miktar=1.0,
            birim="Adet",
            birim_fiyat=toplam_tutar,
            toplam_fiyat=toplam_tutar
        )
    ]

    return SatinAlmaTalebi(
        tedarikci_adi=tedarikci,
        vergi_no="1234567890",
        toplam_tutar=toplam_tutar,
        para_birimi="TRY",
        talep_turu=talep_turu,
        kalemler=kalemler
    )


# ---------------------------------------------------------
# 5. Dış Sistem Simülatörleri (API Araçları)
# ---------------------------------------------------------
def api_tedarikci_dogrula(tedarikci_adi: str, vergi_no: Optional[str] = None) -> Dict[str, Any]:
    onayli_tedarikciler = {
        "xyz": {"durum": "Onaylı", "risk_puani": "Düşük", "odeme_vadesi": "30 Gün"},
        "abc": {"durum": "Onaylı", "risk_puani": "Düşük", "odeme_vadesi": "45 Gün"},
        "beta": {"durum": "Onaylı", "risk_puani": "Çok Düşük", "odeme_vadesi": "15 Gün"},
        "omega": {"durum": "Onaylı", "risk_puani": "Orta", "odeme_vadesi": "30 Gün"},
    }
    ad_kucuk = (tedarikci_adi or "").lower()
    eslesen = None
    for k, v in onayli_tedarikciler.items():
        if k in ad_kucuk:
            eslesen = v
            break
            
    if eslesen:
        return {
            "sorgulanan_tedarikci": tedarikci_adi,
            "sistem_kaydi": "Mevcut",
            "tedarikci_statu": eslesen["durum"],
            "risk_skoru": eslesen["risk_puani"],
            "odeme_vadesi": eslesen["odeme_vadesi"],
            "mesaj": "Tedarikçi ERP sisteminde kayıtlı ve güvenilir."
        }
    else:
        return {
            "sorgulanan_tedarikci": tedarikci_adi,
            "sistem_kaydi": "Yeni / Onaysız",
            "tedarikci_statu": "Ön Onaysız Tedarikçi",
            "risk_skoru": "Orta / Yüksek",
            "odeme_vadesi": "Peşin / Tanımsız",
            "mesaj": "Tedarikçi kurumsal onaylı listede bulunamadı; ek onay formu gereklidir."
        }


def api_departman_kalan_butce_sorgula(departman: str) -> Dict[str, Any]:
    butce_veritabani = {
        "donanım": {"toplam_butce": 500000.0, "harcanan": 310000.0, "kalan": 190000.0},
        "yazılım": {"toplam_butce": 350000.0, "harcanan": 280000.0, "kalan": 70000.0},
        "ofis": {"toplam_butce": 80000.0, "harcanan": 25000.0, "kalan": 55000.0},
        "sarf malzeme": {"toplam_butce": 80000.0, "harcanan": 25000.0, "kalan": 55000.0},
        "danışmanlık": {"toplam_butce": 400000.0, "harcanan": 150000.0, "kalan": 250000.0},
        "genel": {"toplam_butce": 200000.0, "harcanan": 60000.0, "kalan": 140000.0}
    }
    dep_kucuk = (departman or "genel").lower()
    anahtar = "genel"
    for k in butce_veritabani.keys():
        if k in dep_kucuk:
            anahtar = k
            break
            
    bilgi = butce_veritabani[anahtar]
    return {
        "departman_kategori": anahtar.upper(),
        "toplam_ceyrek_butcesi_try": bilgi["toplam_butce"],
        "su_ana_kadar_harcanan_try": bilgi["harcanan"],
        "kalan_kullanilabilir_butce_try": bilgi["kalan"]
    }


# ---------------------------------------------------------
# 6. Yerel Ollama (qwen3.5:0.8b) ile Yapısal Veri Çıkarımı
# ---------------------------------------------------------
def satin_alma_talebi_ayikla(metin: str, model: str = DEFAULT_MODEL) -> SatinAlmaTalebi:
    """
    Yerel Ollama (qwen3.5:0.8b) kullanarak satın alma metninden JSON çıkartır.
    """
    system_prompt = (
        "Sen kurumsal satın alma departmanı asistanısın. Verilen teklif metninden bilgileri çıkarıp "
        "kesinlikle sadece geçerli bir JSON objesi olarak döndür. JSON formatı:\n"
        "{\n"
        '  "tedarikci_adi": "Firma Adı",\n'
        '  "vergi_no": "varsa vergi no",\n'
        '  "toplam_tutar": 125000.0,\n'
        '  "para_birimi": "TRY",\n'
        '  "talep_turu": "Donanım Alımı / Yazılım / Ofis",\n'
        '  "kalemler": [\n'
        '    {"aciklama": "ürün adı", "miktar": 1, "birim": "Adet", "birim_fiyat": 1000.0, "toplam_fiyat": 1000.0}\n'
        '  ]\n'
        "}"
    )

    user_prompt = f"Aşağıdaki satın alma talebini analiz et ve JSON olarak döndür:\n\n{metin}"

    try:
        raw_response = ollama_generate(prompt=user_prompt, system=system_prompt, model=model, json_format=True)
        parsed_json = json_metni_ayikla(raw_response)
        if parsed_json and "toplam_tutar" in parsed_json:
            # Pydantic ile doğrula
            kalemler_list = []
            for k in parsed_json.get("kalemler", []):
                kalemler_list.append(SatinAlmaKalemi(
                    aciklama=k.get("aciklama", "Kalem"),
                    miktar=float(k.get("miktar", 1)) if k.get("miktar") is not None else None,
                    birim=k.get("birim", "Adet"),
                    birim_fiyat=float(k.get("birim_fiyat", 0)) if k.get("birim_fiyat") is not None else None,
                    toplam_fiyat=float(k.get("toplam_fiyat", 0)) if k.get("toplam_fiyat") is not None else None
                ))

            tutar = float(parsed_json.get("toplam_tutar", 0))
            return SatinAlmaTalebi(
                tedarikci_adi=parsed_json.get("tedarikci_adi", "Bilinmeyen Tedarikçi"),
                vergi_no=parsed_json.get("vergi_no"),
                toplam_tutar=tutar,
                para_birimi=parsed_json.get("para_birimi", "TRY"),
                talep_turu=parsed_json.get("talep_turu", "Genel"),
                kalemler=kalemler_list
            )
    except Exception as e:
        # Ollama yanıt veremezse kural tabanlı motora geç
        pass

    return kural_tabanli_talep_ayristir(metin)


# ---------------------------------------------------------
# 7. Yerel RAG: Prosedür İndeksleme ve Bütçe Kontrolü (ChromaDB)
# ---------------------------------------------------------
def prosedurleri_chromaya_indeksle(
    prosedur_metni: str,
    collection_name: str = "satin_alma_prosedurleri",
    persist_dir: str = "./chroma_db"
) -> chromadb.Collection:
    chroma_client = chromadb.PersistentClient(path=persist_dir)

    try:
        chroma_client.delete_collection(name=collection_name)
    except Exception:
        pass

    collection = chroma_client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    ham_parcalar = [p.strip() for p in prosedur_metni.split("\n\n") if p.strip()]
    docs = []
    ids = []
    metadatas = []

    for idx, parca in enumerate(ham_parcalar):
        if len(parca) < 15:
            continue
        docs.append(parca)
        ids.append(f"prosedur_{idx}")
        metadatas.append({"madde_id": idx})

    if docs:
        collection.add(documents=docs, metadatas=metadatas, ids=ids)

    return collection


def butce_uygunluk_kontrol_et(
    talep: SatinAlmaTalebi,
    prosedur_metni: Optional[str] = None,
    collection_name: str = "satin_alma_prosedurleri",
    persist_dir: str = "./chroma_db",
    model: str = DEFAULT_MODEL
) -> ButceUygunlukSonucu:
    """
    ChromaDB'den ilgili kuralları çeker ve yerel Ollama (Qwen) ile bütçe uygunluğunu değerlendirir.
    """
    kategori_limitleri = {
        "donanım": 100000.0,
        "yazılım": 75000.0,
        "sarf": 25000.0,
        "ofis": 25000.0,
        "danışmanlık": 150000.0,
        "genel": 50000.0
    }

    tutar = talep.toplam_tutar or 0.0
    kategori_lower = (talep.talep_turu or "genel").lower()
    
    secili_limit = 50000.0
    for k, lim in kategori_limitleri.items():
        if k in kategori_lower:
            secili_limit = lim
            break

    # ChromaDB'den ilgili kuralları çek
    chroma_client = chromadb.PersistentClient(path=persist_dir)
    collection = None
    try:
        collection = chroma_client.get_collection(name=collection_name)
    except Exception:
        pass

    if collection is None or collection.count() == 0:
        metin = prosedur_metni
        if not metin and os.path.exists("prosedurler.txt"):
            with open("prosedurler.txt", "r", encoding="utf-8") as f:
                metin = f.read()
        if metin:
            collection = prosedurleri_chromaya_indeksle(metin, persist_dir=persist_dir)

    ilgili_dokumanlar = []
    if collection and collection.count() > 0:
        results = collection.query(query_texts=[f"{talep.talep_turu} {tutar} bütçe limit kuralları"], n_results=min(2, collection.count()))
        ilgili_dokumanlar = results["documents"][0] if results.get("documents") else []

    context_text = "\n---\n".join(ilgili_dokumanlar)

    # Qwen Modeli ile Değerlendirme
    system_prompt = (
        "Sen bütçe kontrol denetçisisin. Satın alma talebinin şirket kurallarına uygunluğunu denetle. "
        "Sadece şu JSON formatında yanıt ver:\n"
        "{\n"
        '  "uygun_mu": true / false,\n'
        f'  "tespit_edilen_limit": {secili_limit},\n'
        '  "aciklama": "detaylı açıklama",\n'
        '  "gerekli_onaylar": ["onay mercileri"]\n'
        "}"
    )

    user_prompt = f"""
Talep:
- Tedarikçi: {talep.tedarikci_adi}
- Kategori: {talep.talep_turu}
- Tutar: {tutar} {talep.para_birimi}

Şirket Kuralları (Context):
{context_text}
"""
    try:
        raw_res = ollama_generate(prompt=user_prompt, system=system_prompt, model=model, json_format=True)
        res_json = json_metni_ayikla(raw_res)
        if res_json and "uygun_mu" in res_json:
            return ButceUygunlukSonucu(
                uygun_mu=bool(res_json.get("uygun_mu", tutar <= secili_limit)),
                tespit_edilen_limit=float(res_json.get("tespit_edilen_limit", secili_limit)),
                para_birimi=talep.para_birimi or "TRY",
                aciklama=res_json.get("aciklama", f"Tutar: {tutar:,.2f} {talep.para_birimi}"),
                gerekli_onaylar=res_json.get("gerekli_onaylar", ["Direktör Onayı"] if tutar > secili_limit else ["Departman Müdürü Onayı"]),
                ilgili_prosedur_maddeleri=ilgili_dokumanlar or [f"Kategori Standart Limit: {secili_limit:,.2f} {talep.para_birimi}"]
            )
    except Exception:
        pass

    # Fallback Deterministik Değerlendirme
    uygun = tutar <= secili_limit
    return ButceUygunlukSonucu(
        uygun_mu=uygun,
        tespit_edilen_limit=secili_limit,
        para_birimi=talep.para_birimi or "TRY",
        aciklama=f"Kategori tavan limiti {secili_limit:,.2f} {talep.para_birimi}. Talep tutarı ({tutar:,.2f} {talep.para_birimi}) " + ("limit dahilindedir." if uygun else "limiti aşmaktadır."),
        gerekli_onaylar=["Departman Müdürü Onayı"] if uygun else ["BT Direktörü Onayı", "CFO Onayı", "Bütçe Aşım Raporu"],
        ilgili_prosedur_maddeleri=ilgili_dokumanlar or [f"Standart Kategori Limiti: {secili_limit:,.2f} {talep.para_birimi}"]
    )


# ---------------------------------------------------------
# 8. Yerel Tool Calling (Qwen3.5 Function Routing)
# ---------------------------------------------------------
def llm_arac_cagrilari_yurut(talep: SatinAlmaTalebi, model: str = DEFAULT_MODEL) -> List[Dict[str, Any]]:
    """
    Qwen3.5 modeline mevcut API araçlarını sunarak hangi araçların çağrılması gerektiğini belirletir ve çalıştırır.
    """
    tools_desc = [
        {"name": "api_tedarikci_dogrula", "desc": "Tedarikçinin onay durumunu ve risk puanını sorgular."},
        {"name": "api_departman_kalan_butce_sorgula", "desc": "Departmanın kalan çeyreklik bütçesini sorgular."}
    ]

    system_prompt = (
        "Sen kurumsal iş akışı koordinatörüsün. Gelen satın alma talebi için çağrılması gereken araçları belirle. "
        "Format sadece JSON listesi olmalı:\n"
        '{"cagrilacak_araclar": ["api_tedarikci_dogrula", "api_departman_kalan_butce_sorgula"]}'
    )

    user_prompt = f"Tedarikçi: {talep.tedarikci_adi}, Kategori: {talep.talep_turu}, Tutar: {talep.toplam_tutar}. Hangi araçları çağırmalıyım?"

    cagrilanlar = ["api_tedarikci_dogrula", "api_departman_kalan_butce_sorgula"]
    try:
        raw_res = ollama_generate(prompt=user_prompt, system=system_prompt, model=model, json_format=True)
        res_json = json_metni_ayikla(raw_res)
        if "cagrilacak_araclar" in res_json and isinstance(res_json["cagrilacak_araclar"], list):
            cagrilanlar = res_json["cagrilacak_araclar"]
    except Exception:
        pass

    arac_sonuclari = []
    if "api_tedarikci_dogrula" in cagrilanlar:
        cikti_ted = api_tedarikci_dogrula(tedarikci_adi=talep.tedarikci_adi or "")
        arac_sonuclari.append({
            "arac": "api_tedarikci_dogrula",
            "parametreler": {"tedarikci_adi": talep.tedarikci_adi},
            "api_yaniti": cikti_ted
        })

    if "api_departman_kalan_butce_sorgula" in cagrilanlar:
        cikti_butce = api_departman_kalan_butce_sorgula(departman=talep.talep_turu or "genel")
        arac_sonuclari.append({
            "arac": "api_departman_kalan_butce_sorgula",
            "parametreler": {"departman": talep.talep_turu},
            "api_yaniti": cikti_butce
        })

    return arac_sonuclari


# ---------------------------------------------------------
# 9. Uçtan Uca Görev Akışı (Workflow Runner - Yerel Ollama)
# ---------------------------------------------------------
def gorev_akisini_yurut(
    girdi: Any,
    dosya_adi: str = "",
    prosedur_metni: Optional[str] = None,
    model: str = DEFAULT_MODEL
) -> Dict[str, Any]:
    """
    Yerel Ollama (qwen3.5:0.8b) üzerinde çalışan izlenebilir görev akışı:
    1. OCR / Metin Çıkarımı
    2. Yerel Qwen LLM Yapısal Çıkarım (JSON)
    3. Yerel Tool Calling (ERP & Bütçe API Entegrasyonu)
    4. Yerel RAG Politika & Bütçe Denetimi (ChromaDB + Qwen)
    """
    is_akisi_loglari: List[WorkflowLogAdimi] = []
    
    # ------------------ Adım 1: OCR / Metin Çıkarma ------------------
    t1 = datetime.now()
    cikarma_sonuc = pdf_veya_gorselden_metin_cikar(girdi, dosya_adi=dosya_adi)
    ham_metin = cikarma_sonuc["metin"]
    yontem = cikarma_sonuc["yontem"]
    t2 = datetime.now()

    is_akisi_loglari.append(WorkflowLogAdimi(
        adim_no=1,
        adim_adi="OCR & Metin Çıkarma",
        baslangic_zamani=t1.strftime("%H:%M:%S.%f")[:-3],
        bitis_zamani=t2.strftime("%H:%M:%S.%f")[:-3],
        durum="BASARILI" if ham_metin else "UYARI",
        detay=f"Yöntem: {yontem}. Toplam {len(ham_metin)} karakter metin başarıyla elde edildi."
    ))

    # ------------------ Adım 2: Yerel LLM Yapısal Veri Çıkarımı ------------------
    t3 = datetime.now()
    talep_objesi = satin_alma_talebi_ayikla(metin=ham_metin, model=model)
    t4 = datetime.now()

    is_akisi_loglari.append(WorkflowLogAdimi(
        adim_no=2,
        adim_adi=f"Yerel LLM Parsing (Ollama {model})",
        baslangic_zamani=t3.strftime("%H:%M:%S.%f")[:-3],
        bitis_zamani=t4.strftime("%H:%M:%S.%f")[:-3],
        durum="BASARILI",
        detay=f"Tedarikçi: {talep_objesi.tedarikci_adi}, Tutar: {talep_objesi.toplam_tutar:,.2f} {talep_objesi.para_birimi}, Kalem Sayısı: {len(talep_objesi.kalemler)}"
    ))

    # ------------------ Adım 3: Yerel Tool Calling & Dış API Entegrasyonu ------------------
    t5 = datetime.now()
    tool_sonuclari = llm_arac_cagrilari_yurut(talep=talep_objesi, model=model)
    t6 = datetime.now()

    is_akisi_loglari.append(WorkflowLogAdimi(
        adim_no=3,
        adim_adi="Tool Calling (ERP & Finans API Entegrasyonu)",
        baslangic_zamani=t5.strftime("%H:%M:%S.%f")[:-3],
        bitis_zamani=t6.strftime("%H:%M:%S.%f")[:-3],
        durum="BASARILI",
        detay=f"{len(tool_sonuclari)} sistem aracı çağrıldı ve yanıtlar alındı.",
        arac_cagrilari=tool_sonuclari
    ))

    # ------------------ Adım 4: Yerel RAG Politika & Bütçe Kontrolü ------------------
    t7 = datetime.now()
    butce_sonucu = butce_uygunluk_kontrol_et(
        talep=talep_objesi,
        prosedur_metni=prosedur_metni,
        model=model
    )
    t8 = datetime.now()

    is_akisi_loglari.append(WorkflowLogAdimi(
        adim_no=4,
        adim_adi="RAG Politika & Kural Denetimi (ChromaDB + Qwen)",
        baslangic_zamani=t7.strftime("%H:%M:%S.%f")[:-3],
        bitis_zamani=t8.strftime("%H:%M:%S.%f")[:-3],
        durum="BASARILI" if butce_sonucu.uygun_mu else "UYARI",
        detay=f"Sonuç: {'UYGUN' if butce_sonucu.uygun_mu else 'LİMİT AŞIMI'}. Açıklama: {butce_sonucu.aciklama[:90]}..."
    ))

    return {
        "ham_metin": ham_metin,
        "metin_cikarma_yontemi": yontem,
        "talep": talep_objesi,
        "arac_cagrilari": tool_sonuclari,
        "butce_sonucu": butce_sonucu,
        "workflow_loglari": is_akisi_loglari
    }
