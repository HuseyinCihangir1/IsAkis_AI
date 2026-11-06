import io
import os
import json
import logging
import traceback
from typing import List, Optional, Union, Dict, Any
from datetime import datetime
import pdfplumber
from PIL import Image
from openai import OpenAI
from pydantic import BaseModel, Field
import chromadb

# İsteğe bağlı OCR kütüphaneleri
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


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
# 2. OCR ve Metin Çıkarma
# ---------------------------------------------------------
def ocr_gorselden_metin_cikar(image: Image.Image) -> str:
    """Görselden (PNG, JPEG, taranmış belge) OCR ile metin okur."""
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
    """
    Streamlit UploadedFile, bytes, io.BytesIO, dosya yolu veya düz metinden güvenli metin çıkarır.
    """
    metin = ""
    yontem = "dijital_pdf"
    
    # 1. Kaynağın bayt içeriğini güvenle oku
    baytlar = b""
    if hasattr(kaynak, "read"):
        # Streamlit UploadedFile veya BytesIO
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
            # Doğrudan metin string'i
            return {"metin": kaynak.strip(), "yontem": "duz_metin"}
    else:
        raise ValueError(f"Desteklenmeyen dosya/girdi türü: {type(kaynak)}")

    if not baytlar:
        raise ValueError("Yüklenen dosya boş veya okunamadı.")

    # 2. Dosya türü kontrolü: Görsel mi PDF mi?
    is_image = any(dosya_adi.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"])
    
    if is_image:
        try:
            img = Image.open(io.BytesIO(baytlar))
            metin = ocr_gorselden_metin_cikar(img)
            yontem = "ocr_goruntu"
        except Exception as e:
            raise ValueError(f"Görsel dosya işlenirken hata oluştu: {str(e)}")
    else:
        # PDF olarak açmayı dene
        try:
            with pdfplumber.open(io.BytesIO(baytlar)) as pdf:
                for sayfa in pdf.pages:
                    sayfa_metni = sayfa.extract_text()
                    if sayfa_metni:
                        metin += sayfa_metni + "\n"
        except Exception as pdf_err:
            # PDF okunamadıysa resim PDF olabilir veya taranmış olabilir
            metin = ""

        # Eğer PDF'ten dijital metin çıkmadıysa (Taranmış Resim PDF ise OCR'a başvur)
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
        # Dosya içinde okunabilir metin bulunamadıysa kullanıcıya bilgilendirici hata ver
        raise ValueError("Belgeden okunabilir metin çıkarılamadı. Belgenin dijital metin içerdiğinden veya okunabilir olduğundan emin olun.")

    return {
        "metin": metin.strip(),
        "yontem": yontem
    }


# ---------------------------------------------------------
# 3. Dış Sistem Simülatörleri (API / Araçlar)
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
            "mesaj": "Tedarikçi ERP sisteminde kayıtlı ve onaylı."
        }
    else:
        return {
            "sorgulanan_tedarikci": tedarikci_adi,
            "sistem_kaydi": "Yeni / Onaysız",
            "tedarikci_statu": "Ön Onaysız Tedarikçi",
            "risk_skoru": "Bilinmiyor",
            "odeme_vadesi": "Peşin / Tanımsız",
            "mesaj": "Tedarikçi kurumsal onaylı listede bulunamadı."
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


TOOL_TANIMLARI = [
    {
        "type": "function",
        "function": {
            "name": "api_tedarikci_dogrula",
            "description": "Şirket ERP sisteminden tedarikçinin onay durumunu ve risk puanını sorgular.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tedarikci_adi": {"type": "string", "description": "Tedarikçi firma adı"},
                    "vergi_no": {"type": "string", "description": "Varsa vergi numarası"}
                },
                "required": ["tedarikci_adi"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "api_departman_kalan_butce_sorgula",
            "description": "İlgili kategori/departmanın kalan kullanılabilir bütçesini sorgular.",
            "parameters": {
                "type": "object",
                "properties": {
                    "departman": {"type": "string", "description": "Departman veya harcama kategorisi"}
                },
                "required": ["departman"]
            }
        }
    }
]


# ---------------------------------------------------------
# 4. LLM Yapısal Veri Çıkarımı
# ---------------------------------------------------------
def satin_alma_talebi_ayikla(
    metin: str,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini"
) -> SatinAlmaTalebi:
    actual_key = api_key or os.getenv("OPENAI_API_KEY")
    if not actual_key:
        raise ValueError("OpenAI API Anahtarı bulunamadı. Lütfen sol panelden API anahtarınızı girin.")

    client = OpenAI(api_key=actual_key)
    sistem_mesaji = (
        "Sen kurumsal satın alma departmanında çalışan uzman bir veri analistisin. "
        "Verilen metinden tedarikçi adını, vergi numarasını, "
        "toplam tutarı, para birimini, talep türünü ve tüm kalemleri yapısal çıkar."
    )

    response = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": sistem_mesaji},
            {"role": "user", "content": f"Aşağıdaki satın alma talebini analiz et:\n\n{metin}"}
        ],
        response_format=SatinAlmaTalebi,
        temperature=0.0
    )
    return response.choices[0].message.parsed


# ---------------------------------------------------------
# 5. RAG: Prosedür İndeksleme ve Vektör Arama
# ---------------------------------------------------------
def get_embedding(text: str, client: OpenAI, model: str = "text-embedding-3-small") -> List[float]:
    text = text.replace("\n", " ")
    res = client.embeddings.create(input=[text], model=model)
    return res.data[0].embedding


def prosedurleri_chromaya_indeksle(
    prosedur_metni: str,
    api_key: Optional[str] = None,
    collection_name: str = "satin_alma_prosedurleri",
    persist_dir: str = "./chroma_db"
) -> chromadb.Collection:
    actual_key = api_key or os.getenv("OPENAI_API_KEY")
    if not actual_key:
        raise ValueError("OpenAI API Anahtarı girilmedi.")

    client = OpenAI(api_key=actual_key)
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
    embeddings = []
    ids = []
    metadatas = []

    for idx, parca in enumerate(ham_parcalar):
        if len(parca) < 15:
            continue
        emb = get_embedding(parca, client)
        docs.append(parca)
        embeddings.append(emb)
        ids.append(f"prosedur_{idx}")
        metadatas.append({"madde_id": idx})

    if docs:
        collection.add(
            documents=docs,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
    return collection


def butce_uygunluk_kontrol_et(
    talep: SatinAlmaTalebi,
    prosedur_metni: Optional[str] = None,
    api_key: Optional[str] = None,
    collection_name: str = "satin_alma_prosedurleri",
    persist_dir: str = "./chroma_db",
    model: str = "gpt-4o-mini"
) -> ButceUygunlukSonucu:
    actual_key = api_key or os.getenv("OPENAI_API_KEY")
    if not actual_key:
        raise ValueError("OpenAI API Anahtarı girilmedi.")

    client = OpenAI(api_key=actual_key)
    chroma_client = chromadb.PersistentClient(path=persist_dir)

    collection = None
    try:
        collection = chroma_client.get_collection(name=collection_name)
    except Exception:
        pass

    # Koleksiyon yoksa veya boşsa otomatik indeksle
    if collection is None or collection.count() == 0:
        metin = prosedur_metni
        if not metin and os.path.exists("prosedurler.txt"):
            with open("prosedurler.txt", "r", encoding="utf-8") as f:
                metin = f.read()
        if metin:
            collection = prosedurleri_chromaya_indeksle(
                prosedur_metni=metin,
                api_key=actual_key,
                collection_name=collection_name,
                persist_dir=persist_dir
            )
        else:
            raise ValueError("ChromaDB koleksiyonu bulunamadı ve indekslenecek prosedür metni yok.")

    kalem_ozet = ", ".join([k.aciklama for k in talep.kalemler[:4]])
    query_text = f"Talep türü: {talep.talep_turu or 'Genel'}, Kalemler: {kalem_ozet}, Tutar: {talep.toplam_tutar} {talep.para_birimi} limit ve bütçe onay kuralları"
    query_embedding = get_embedding(query_text, client)

    n_count = min(3, max(1, collection.count()))
    results = collection.query(query_embeddings=[query_embedding], n_results=n_count)
    ilgili_dokumanlar = results["documents"][0] if results.get("documents") else []
    baglam_metni = "\n\n---\n\n".join(ilgili_dokumanlar)

    sistem_mesaji = (
        "Sen şirketin bütçe kontrol ve satın alma uygunluk denetçisisin. "
        "Sana sağlanan şirket prosedür kurallarını referans alarak gelen satın alma talebinin "
        "bütçe limitine uygun olup olmadığını denetle. Standart limitin aşılması durumunda "
        "uygun_mu değerini False yap, gerekçesini ve gerekli onay mercilerini listele."
    )

    kullanici_mesaji = f"""
Talep Bilgileri:
- Tedarikçi: {talep.tedarikci_adi or 'Belirtilmemiş'}
- Kategori: {talep.talep_turu or 'Genel'}
- Toplam Tutar: {talep.toplam_tutar} {talep.para_birimi}

Referans Alınan Kurallar (ChromaDB):
{baglam_metni}
"""

    response = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": sistem_mesaji},
            {"role": "user", "content": kullanici_mesaji}
        ],
        response_format=ButceUygunlukSonucu,
        temperature=0.0
    )

    sonuc = response.choices[0].message.parsed
    if not sonuc.ilgili_prosedur_maddeleri:
        sonuc.ilgili_prosedur_maddeleri = ilgili_dokumanlar

    return sonuc


# ---------------------------------------------------------
# 6. LLM Tool Calling (Dış Araç / API Çağırma Koordinatörü)
# ---------------------------------------------------------
def llm_arac_cagrilari_yurut(
    talep: SatinAlmaTalebi,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini"
) -> List[Dict[str, Any]]:
    actual_key = api_key or os.getenv("OPENAI_API_KEY")
    if not actual_key:
        raise ValueError("OpenAI API Anahtarı girilmedi.")

    client = OpenAI(api_key=actual_key)

    mesajlar = [
        {
            "role": "system",
            "content": (
                "Sen kurumsal iş akışı orkestratörüsün. Gelen satın alma talebi için "
                "sağlanan araçları (API) kullanarak: "
                "1. Tedarikçinin onay durumunu sorgula (api_tedarikci_dogrula). "
                "2. İlgili departmanın kalan çeyreklik bütçesini sorgula (api_departman_kalan_butce_sorgula)."
            )
        },
        {
            "role": "user",
            "content": (
                f"Tedarikçi: '{talep.tedarikci_adi}', Kategori: '{talep.talep_turu}', "
                f"Talep Edilen Tutar: {talep.toplam_tutar} {talep.para_birimi}. "
                "Lütfen gerekli kontroller için araçları çağır."
            )
        }
    ]

    response = client.chat.completions.create(
        model=model,
        messages=mesajlar,
        tools=TOOL_TANIMLARI,
        tool_choice="auto"
    )

    arac_sonuclari = []
    response_msg = response.choices[0].message
    tool_calls = response_msg.tool_calls

    if tool_calls:
        for tool_call in tool_calls:
            fonksiyon_adi = tool_call.function.name
            argumanlar = {}
            try:
                argumanlar = json.loads(tool_call.function.arguments)
            except Exception:
                argumanlar = {}

            if fonksiyon_adi == "api_tedarikci_dogrula":
                cikti = api_tedarikci_dogrula(
                    tedarikci_adi=argumanlar.get("tedarikci_adi", talep.tedarikci_adi or ""),
                    vergi_no=argumanlar.get("vergi_no")
                )
            elif fonksiyon_adi == "api_departman_kalan_butce_sorgula":
                cikti = api_departman_kalan_butce_sorgula(
                    departman=argumanlar.get("departman", talep.talep_turu or "genel")
                )
            else:
                cikti = {"hata": "Bilinmeyen fonksiyon"}

            arac_sonuclari.append({
                "arac": fonksiyon_adi,
                "parametreler": argumanlar,
                "api_yaniti": cikti
            })

    return arac_sonuclari


# ---------------------------------------------------------
# 7. İzlenebilir Uçtan Uca Görev Akışı (Workflow Runner)
# ---------------------------------------------------------
def gorev_akisini_yurut(
    girdi: Any,
    dosya_adi: str = "",
    prosedur_metni: Optional[str] = None,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini"
) -> Dict[str, Any]:
    """
    OCR -> LLM Parsing -> Tool Calling (API) -> RAG Politika Denetimi
    aşamalarını sırasıyla yürüten ve her adımın süresini/çıktısını kaydeden workflow yöneticisi.
    """
    actual_key = api_key or os.getenv("OPENAI_API_KEY")
    if not actual_key:
        raise ValueError("Lütfen sol taraftaki menüden OpenAI API Anahtarınızı giriniz.")

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

    # ------------------ Adım 2: LLM Yapısal Veri Çıkarımı ------------------
    t3 = datetime.now()
    talep_objesi = satin_alma_talebi_ayikla(metin=ham_metin, api_key=actual_key, model=model)
    t4 = datetime.now()

    is_akisi_loglari.append(WorkflowLogAdimi(
        adim_no=2,
        adim_adi="LLM Yapısal Çıkarım (Structured Output)",
        baslangic_zamani=t3.strftime("%H:%M:%S.%f")[:-3],
        bitis_zamani=t4.strftime("%H:%M:%S.%f")[:-3],
        durum="BASARILI",
        detay=f"Tedarikçi: {talep_objesi.tedarikci_adi}, Tutar: {talep_objesi.toplam_tutar} {talep_objesi.para_birimi}, Kalem Sayısı: {len(talep_objesi.kalemler)}"
    ))

    # ------------------ Adım 3: Tool Calling & Dış API Entegrasyonu ------------------
    t5 = datetime.now()
    tool_sonuclari = llm_arac_cagrilari_yurut(talep=talep_objesi, api_key=actual_key, model=model)
    t6 = datetime.now()

    is_akisi_loglari.append(WorkflowLogAdimi(
        adim_no=3,
        adim_adi="Tool Calling (ERP & Finans API Entegrasyonu)",
        baslangic_zamani=t5.strftime("%H:%M:%S.%f")[:-3],
        bitis_zamani=t6.strftime("%H:%M:%S.%f")[:-3],
        durum="BASARILI",
        detay=f"{len(tool_sonuclari)} harici sistem aracı (API) çağrıldı ve yanıtlar alındı.",
        arac_cagrilari=tool_sonuclari
    ))

    # ------------------ Adım 4: RAG Politika & Bütçe Kontrolü ------------------
    t7 = datetime.now()
    butce_sonucu = butce_uygunluk_kontrol_et(
        talep=talep_objesi,
        prosedur_metni=prosedur_metni,
        api_key=actual_key,
        model=model
    )
    t8 = datetime.now()

    is_akisi_loglari.append(WorkflowLogAdimi(
        adim_no=4,
        adim_adi="RAG Politika & Kural Denetimi (ChromaDB)",
        baslangic_zamani=t7.strftime("%H:%M:%S.%f")[:-3],
        bitis_zamani=t8.strftime("%H:%M:%S.%f")[:-3],
        durum="BASARILI" if butce_sonucu.uygun_mu else "UYARI",
        detay=f"Sonuç: {'UYGUN' if butce_sonucu.uygun_mu else 'LİMİT AŞIMI'}. Açıklama: {butce_sonucu.aciklama[:100]}..."
    ))

    return {
        "ham_metin": ham_metin,
        "metin_cikarma_yontemi": yontem,
        "talep": talep_objesi,
        "arac_cagrilari": tool_sonuclari,
        "butce_sonucu": butce_sonucu,
        "workflow_loglari": is_akisi_loglari
    }
