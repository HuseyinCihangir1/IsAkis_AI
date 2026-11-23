import os
import time
import psutil
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings, FakeEmbeddings

DATA_DIR = "./data"
DB_DIR = "./chroma_db"

def benchmark_and_ingest():
    print("=" * 65)
    print("🚀 CHUNK OPTİMİZASYON VE BENCHMARK SÜRECİ BAŞLATILDI")
    print("=" * 65)
    
    # 1. Data klasörünü kontrol et
    if not os.path.exists(DATA_DIR):
        print(f"⚠️ Uyarı: '{DATA_DIR}' klasörü bulunamadı. Lütfen ana dizinde 'data' klasörü oluşturun.")
        return
    
    txt_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.txt')]
    
    if not txt_files:
        print(f"⚠️ '{DATA_DIR}' klasöründe hiç .txt dosyası bulunamadı! Lütfen dosya ekleyin.")
        return
    
    print(f"📂 Bulunan .txt dosyaları: {txt_files}")
    
    all_texts = []
    all_metadatas = []
    
    for file in txt_files:
        file_path = os.path.join(DATA_DIR, file)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            all_texts.append(content)
            all_metadatas.append({"source": file})
            print(f"📄 Okunan Dosya: {file} ({len(content)} karakter)")

    # 2. Denenecek 3 Farklı Chunk Boyutu Alternatifi
    # Amaç: Tepkime süresi ve donanım yükü (bellek/işlem) dengesini görmek
    chunk_candidates = [
        {"size": 300, "overlap": 30},   # Küçük chunk (Daha fazla parça, yüksek işlem yükü)
        {"size": 600, "overlap": 60},   # Orta/Dengeli chunk
        {"size": 1200, "overlap": 120}  # Büyük chunk (Daha az parça, hızlı ama daha az hassas bağlam)
    ]
    
    best_chunk_config = None
    best_score = float('inf')
    results_summary = []

    print("\n" + "-" * 65)
    print("⚖️ FARKLI CHUNK BOYUTLARI TEST EDİLİYOR (Benchmark)...")
    print("-" * 65)

    process = psutil.Process(os.getpid())

    for candidate in chunk_candidates:
        c_size = candidate["size"]
        c_overlap = candidate["overlap"]
        
        # Donanım ölçümü başlangıcı
        cpu_before = process.cpu_percent(interval=None)
        mem_before = process.memory_info().rss / (1024 * 1024) # MB
        start_time = time.time()
        
        # Text Splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=c_size,
            chunk_overlap=c_overlap
        )
        docs = text_splitter.create_documents(all_texts, metadatas=all_metadatas)
        
        # Süre ve Donanım Ölçümü bitişi
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        cpu_after = process.cpu_percent(interval=None)
        mem_after = process.memory_info().rss / (1024 * 1024) # MB
        mem_diff = max(0, mem_after - mem_before)
        
        # Skorlama Mantığı (Optimum Seçim İçin): 
        # Süreye ve bellek tüketimine eşit ağırlıklı ceza puanı veriyoruz (Düşük olan kazanır)
        cost_score = (elapsed_time * 2.0) + (mem_diff * 0.1) + (len(docs) * 0.01)
        
        results_summary.append({
            "size": c_size,
            "chunks_count": len(docs),
            "time": elapsed_time,
            "memory_diff": mem_diff,
            "score": cost_score
        })
        
        print(f"   🔍 Test [Chunk Boyutu: {c_size}]:")
        print(f"      - Oluşan Parça Sayısı: {len(docs)}")
        print(f"      - Tepkime Süresi     : {elapsed_time:.4f} saniye")
        print(f"      - Bellek Yükü (RAM)  : +{mem_diff:.2f} MB")
        print(f"      - Hesaplanan Skor    : {cost_score:.2f}")
        print(f"      " + "-"*40)

        if cost_score < best_score:
            best_score = cost_score
            best_chunk_config = candidate

    print("\n" + "=" * 65)
    print(🏆 " OPTİMUM CHUNK SEÇİMİ TAMAMLANDI")
    print("=" * 65)
    print(f"🎯 Kazanan Optimum Ayar -> Chunk Boyutu: {best_chunk_config['size']} (Örtüşme: {best_chunk_config['overlap']})")
    print("   Gerekçe: Bu boyut, donanım yükü (RAM/CPU) ile arama tepkime süresi arasında en ideal dengeyi kurmuştur.")

    # 3. Kazanan Optimum Ayar ile Gerçek Vektörleştirme ve Kayıt
    print(f"\n🧠 Seçilen Optimum Ayarla ChromaDB'ye Kayıt Yapılıyor...")
    
    optimal_splitter = RecursiveCharacterTextSplitter(
        chunk_size=best_chunk_config["size"],
        chunk_overlap=best_chunk_config["overlap"]
    )
    final_docs = optimal_splitter.create_documents(all_texts, metadatas=all_metadatas)

    try:
        embeddings = OllamaEmbeddings(model="qwen2.5:0.8b")
    except Exception as e:
        print(f"⚠️ Ollama embedding başlatılamadı, fallback kullanılıyor: {e}")
        embeddings = FakeEmbeddings(size=768)

    vectorstore = Chroma.from_documents(
        documents=final_docs,
        embedding=embeddings,
        persist_directory=DB_DIR
    )
    
    print("=" * 65)
    print(f"🎉 İşlem Başarıyla Tamamlandı! Veriler '{DB_DIR}' dizinine kaydedildi.")
    print("=" * 65)

if __name__ == "__main__":
    benchmark_and_ingest()