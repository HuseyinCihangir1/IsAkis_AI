"""
Bu script projenin OCR ve Doküman İşleme yeteneklerini test etmek üzere
örnek iki farklı PDF dosyası üretir:
1. Dijital Metin PDF'i (Donanım Alımı - Limit Aşımı Senaryosu)
2. Taranmış Belge Görünümlü PDF / Görsel (Ofis Malzemesi - Onaylı Senaryo)
"""
import os
import io

def generate_sample_pdfs():
    try:
        # ReportLab varsa şık bir PDF üretelim, yoksa standart text tabanlı oluşturucu
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        
        # 1. Örnek PDF: XYZ Bilişim Donanım Teklif Formu
        pdf1_path = "ornek_talep_donanim.pdf"
        c1 = canvas.Canvas(pdf1_path, pagesize=letter)
        c1.setFont("Helvetica-Bold", 16)
        c1.drawString(50, 750, "XYZ BILISIM TEKNOLOJILERI A.S.")
        c1.setFont("Helvetica", 10)
        c1.drawString(50, 735, "Vergi No: 9876543210 | Maslak / Istanbul")
        c1.line(50, 725, 550, 725)
        
        c1.setFont("Helvetica-Bold", 12)
        c1.drawString(50, 700, "SATIN ALMA TEKLIF VE TALEP FORMU")
        c1.setFont("Helvetica", 10)
        c1.drawString(50, 680, "Talep Turu: Donanim Alimi")
        c1.drawString(50, 665, "Tarih: 06.11.2026")
        
        c1.drawString(50, 630, "Kalemler:")
        c1.drawString(70, 610, "- 4 adet AI GPU Sunucu Kabini (Birim Fiyat: 35.000 TRY) -> Toplam: 140.000 TRY")
        c1.drawString(70, 590, "- 2 adet 4K UltraSharp Monitor (Birim Fiyat: 10.000 TRY) -> Toplam: 20.000 TRY")
        
        c1.setFont("Helvetica-Bold", 11)
        c1.drawString(50, 550, "GENEL TOPLAM TUTAR: 160.000 TRY")
        c1.setFont("Helvetica-Oblique", 9)
        c1.drawString(50, 520, "Not: Fiyatlara KDV dahildir. Teslimat suresi 7 is gunudur.")
        c1.save()
        print(f"Olusturuldu: {pdf1_path}")

        # 2. Örnek PDF: Beta Kırtasiye Sarf Malzeme Teklifi
        pdf2_path = "ornek_talep_sarf_malzeme.pdf"
        c2 = canvas.Canvas(pdf2_path, pagesize=letter)
        c2.setFont("Helvetica-Bold", 16)
        c2.drawString(50, 750, "BETA KIRTASIYE VE OFIS GERECLERI LTD. STI.")
        c2.setFont("Helvetica", 10)
        c2.drawString(50, 735, "Vergi No: 1234567890 | Kadikoy / Istanbul")
        c2.line(50, 725, 550, 725)
        
        c2.setFont("Helvetica-Bold", 12)
        c2.drawString(50, 700, "SATIN ALMA TALEP FORMU")
        c2.setFont("Helvetica", 10)
        c2.drawString(50, 680, "Talep Turu: Ofis ve Sarf Malzemeleri")
        c2.drawString(50, 665, "Tarih: 06.11.2026")
        
        c2.drawString(50, 630, "Kalemler:")
        c2.drawString(70, 610, "- 20 koli A4 Fotokopi Kagidi (Birim Fiyat: 500 TRY) -> Toplam: 10.000 TRY")
        c2.drawString(70, 590, "- 5 adet Lazer Toner Kartusu (Birim Fiyat: 1.200 TRY) -> Toplam: 6.000 TRY")
        
        c2.setFont("Helvetica-Bold", 11)
        c2.drawString(50, 550, "GENEL TOPLAM TUTAR: 16.000 TRY")
        c2.save()
        print(f"Olusturuldu: {pdf2_path}")

    except ImportError:
        # reportlab yoksa Pillow ile örnek bir görsel (fatura resmi) oluşturalım
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (600, 350), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((30, 30), "XYZ BILISIM TEKNOLOJILERI A.S.", fill=(0, 0, 0))
        d.text((30, 60), "Talep Turu: Donanim Alimi", fill=(0, 0, 0))
        d.text((30, 90), "4 Adet Sunucu: 140000 TRY", fill=(0, 0, 0))
        d.text((30, 120), "Toplam Tutar: 140000 TRY", fill=(0, 0, 0))
        img.save("ornek_fatura_gorseli.png")
        print("Olusturuldu: ornek_fatura_gorseli.png")

if __name__ == "__main__":
    generate_sample_pdfs()

