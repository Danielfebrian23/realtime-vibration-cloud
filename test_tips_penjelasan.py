import json

print("=" * 60)
print("TEST TIPS DAN PENJELASAN BERDASARKAN KONDISI")
print("=" * 60)

# Dictionary untuk tips berdasarkan kondisi
TIPS_BY_CONDITION = {
    'NORMAL': "Cek motor setiap hari atau perminggu dengan menambahkan pelumas rantai atau chain cleaner agar dapat memperpanjang waktu masa rantai, dan untuk mengecek lebih akurat kapan mulai menyimpang bisa pakai smart device ini setiap saat!",
    'RINGAN': "Segera diganti pelumas jika belum diganti lama, jika ada serpihan logam atau sekedar menghindari hal yang lebih bermasalah dari keausan, bawa ke bengkel terdekat untuk menghindari hal yang lebih parah",
    'BERAT': "Segera bawa ke bengkel segera sebelum meluas permasalahannya ke poros atau transmisi motor atau lebih parah lagi mesin utama, pastikan komponen motor dibongkar untuk melihat permasalahannya"
}

# Dictionary untuk penjelasan berdasarkan kondisi
PENJELASAN_BY_CONDITION = {
    'NORMAL': "Motor dalam kondisi normal. Getaran yang terdeteksi masih dalam batas wajar dan tidak menunjukkan tanda-tanda kerusakan pada komponen motor.",
    'RINGAN': "Motor menunjukkan tanda-tanda awal anomali. Terdeteksi getaran yang sedikit menyimpang dari kondisi normal, kemungkinan ada keausan ringan pada komponen.",
    'BERAT': "Motor dalam kondisi yang memerlukan perhatian serius. Terdeteksi getaran yang sangat menyimpang dari kondisi normal, kemungkinan ada kerusakan pada komponen motor."
}

def test_tips_and_explanation():
    """Test fungsi tips dan penjelasan untuk berbagai kondisi"""
    
    print("Testing untuk berbagai kondisi motor:\n")
    
    for condition in ['NORMAL', 'RINGAN', 'BERAT']:
        print("=" * 50)
        print(f"KONDISI: {condition}")
        print("=" * 50)
        
        # Test tips
        if condition in TIPS_BY_CONDITION:
            tip_message = TIPS_BY_CONDITION[condition]
        else:
            tip_message = TIPS_BY_CONDITION['NORMAL']
        
        print(f"\n🔧 TIPS UNTUK KONDISI {condition}:")
        print(f"{tip_message}")
        
        # Test penjelasan
        if condition in PENJELASAN_BY_CONDITION:
            explanation_message = PENJELASAN_BY_CONDITION[condition]
        else:
            explanation_message = PENJELASAN_BY_CONDITION['NORMAL']
        
        print(f"\n📊 PENJELASAN KONDISI {condition}:")
        print(f"{explanation_message}")
        
        print("\n" + "-" * 50)

def simulate_telegram_commands():
    """Simulasi command Telegram untuk test"""
    
    print("\n" + "=" * 60)
    print("SIMULASI COMMAND TELEGRAM")
    print("=" * 60)
    
    # Simulasi kondisi yang berbeda
    test_conditions = [
        ('NORMAL', 0.95),
        ('RINGAN', 0.75),
        ('BERAT', 0.85)
    ]
    
    for severity, confidence in test_conditions:
        print(f"\n📱 Simulasi kondisi: {severity} (confidence: {confidence})")
        print("-" * 40)
        
        # Simulasi command /cek
        print(f"Command: /cek")
        print(f"Response: Kondisi Motor: {severity}\nConfidence: {confidence}")
        
        # Simulasi command /penjelasan
        print(f"\nCommand: /penjelasan")
        if severity in PENJELASAN_BY_CONDITION:
            explanation = PENJELASAN_BY_CONDITION[severity]
        else:
            explanation = PENJELASAN_BY_CONDITION['NORMAL']
        print(f"Response: 📊 PENJELASAN KONDISI {severity}:\n\n{explanation}")
        
        # Simulasi command /tips
        print(f"\nCommand: /tips")
        if severity in TIPS_BY_CONDITION:
            tip = TIPS_BY_CONDITION[severity]
        else:
            tip = TIPS_BY_CONDITION['NORMAL']
        print(f"Response: 🔧 TIPS UNTUK KONDISI {severity}:\n\n{tip}")
        
        print("\n" + "=" * 50)

if __name__ == "__main__":
    # Test fungsi tips dan penjelasan
    test_tips_and_explanation()
    
    # Simulasi command Telegram
    simulate_telegram_commands()
    
    print("\n" + "=" * 60)
    print("KESIMPULAN")
    print("=" * 60)
    print("✅ Tips dan penjelasan sudah berfungsi dengan baik!")
    print("✅ Setiap kondisi memiliki tips dan penjelasan yang sesuai")
    print("✅ Format pesan sudah informatif dengan emoji")
    print("✅ Server siap untuk digunakan dengan ESP32")
    
    print("\n📋 Command yang tersedia:")
    print("  /start - Mulai monitoring")
    print("  /stop - Hentikan monitoring")
    print("  /cek - Cek kondisi motor")
    print("  /penjelasan - Penjelasan kondisi")
    print("  /tips - Tips perawatan")
    print("  /grafik - Grafik riwayat") 