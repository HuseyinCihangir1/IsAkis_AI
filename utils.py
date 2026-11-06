import io
import os
from typing import List, Optional, Union
import pdfplumber
from openai import OpenAI
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# Pydantic Veri Modelleri
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


# ---------------------------------------------------------
# Yardımcı Fonksiyonlar
# ---------------------------------------------------------
def pdf_metin_cikar(pdf_kaynak: Union[str, bytes, io.BytesIO]) -> str:
    """
    Dosya yolu veya dosya benzeri (BytesIO/Streamlit UploadedFile) nesneden metin çıkarır.
    """
    metin = ""
    if isinstance(pdf_kaynak, bytes):
        pdf_kaynak = io.BytesIO(pdf_kaynak)
        
    with pdfplumber.open(pdf_kaynak) as pdf:
        for sayfa in pdf.pages:
            sayfa_metni = sayfa.extract_text()
            if sayfa_metni:
                metin += sayfa_metni + "\n"
    return metin.strip()


def satin_alma_talebi_ayikla(
    girdi: Union[str, bytes, io.BytesIO],
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini"
) -> SatinAlmaTalebi:
    """
    Verilen metin veya PDF girdisinden (dosya yolu, bytes veya BytesIO)
    Pydantic kullanarak yapılandırılmış SatinAlmaTalebi nesnesi çıkarır.
    
    Args:
        girdi: Ham metin string'i veya PDF (dosya yolu/bytes/BytesIO).
        api_key: OpenAI API anahtarı (belirtilmezse OPENAI_API_KEY ortam değişkeninden okunur).
        model: Kullanılacak model adı.
        
    Returns:
        SatinAlmaTalebi: Yapılandırılmış Pydantic veri modeli.
    """
    # Girdi PDF mi yoksa doğrudan metin mi kontrol et
    metin = ""
    if isinstance(girdi, (bytes, io.BytesIO)):
        metin = pdf_metin_cikar(girdi)
    elif isinstance(girdi, str):
        # Dosya yolu olup olmadığını kontrol et (ve .pdf uzantılıysa)
        if (girdi.lower().endswith(".pdf") or "\n" not in girdi) and os.path.exists(girdi):
            metin = pdf_metin_cikar(girdi)
        else:
            metin = girdi
    else:
        raise ValueError("Desteklenmeyen girdi türü. Metin string'i, dosya yolu veya dosya baytları beklenmektedir.")

    if not metin.strip():
        raise ValueError("İşlenecek metin bulunamadı veya PDF boş.")

    client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    sistem_mesaji = (
        "Sen satın alma belgeleri ve faturaları analiz eden uzman bir asistansın. "
        "Verilen satın alma talebi metninden tedarikçi adını, toplam tutarı, talep türünü "
        "ve talep kalemlerini eksiksiz ve doğru bir şekilde tespit edip yapısal formatta sun."
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

