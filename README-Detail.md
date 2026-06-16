# Dokumentasi Analisis Kode: Sistem Pendeteksi Keausan Roda Gigi

Dokumen ini membedah logika pemrograman secara mendalam untuk dua komponen utama sistem: perangkat keras (ESP32) dan  *cloud server*. Penjelasan disusun berdasarkan alur eksekusi baris kode agar memudahkan proses penelusuran logika sistem.

## Bagian 1: Logika Perangkat Keras (ESP32 - File .ino)

### 1. Deklarasi _Library_ dan Variabel Global
Kode dimulai dengan pemanggilan _library_ dasar seperti `Wire.h` untuk komunikasi I2C, `Adafruit_ADXL345_U.h` untuk membaca sensor, serta `WiFi.h` dan `HTTPClient.h` untuk transmisi jaringan. Setelah itu, sistem mendefinisikan kredensial WiFi dan alamat URL *cloud server* Railway tempat data akan dikirim. Terdapat variabel `BUFFER_SIZE` yang diatur sebesar 512. Angka ini dipilih secara sengaja agar mikrokontroler tidak mengirim data setiap milidetik yang dapat menyebabkan *server* kewalahan. Data percepatan sumbu X, Y, dan Z akan ditampung sementara di dalam *array* `xBuff`, `yBuff`, dan `zBuff`.

### 2. Konfigurasi Awal (void setup)
Pada blok `setup()`, mikrokontroler memulai komunikasi serial dengan *baud rate* 115200. Baris `accel.begin()` dipanggil untuk memastikan sensor ADXL345 terhubung dengan baik melalui jalur I2C. Logika krusial ada pada baris `accel.setRange(ADXL345_RANGE_16_G)`. Rentang deteksi sensor dimaksimalkan hingga 16G agar hentakan fisik yang sangat keras dari jalan berlubang tidak terpotong oleh batasan perangkat keras (*hardware clipping*). Selanjutnya, baris `accel.setDataRate(ADXL345_DATARATE_1600_HZ)` mengatur kecepatan pengambilan sampel menjadi 1600 kali per detik. Kecepatan tinggi ini merupakan prasyarat mutlak agar transformasi frekuensi (FFT) di *server* nantinya memiliki resolusi yang cukup untuk melihat anomali getaran mesin. Terakhir, mikrokontroler akan mencoba terhubung ke jaringan WiFi melalui fungsi `WiFi.begin()`.

### 3. Eksekusi Berulang (void loop)
Fungsi `loop()` merupakan jantung dari proses akuisisi data. Pada bagian awal, terdapat logika pembacaan input serial untuk fitur *Pause/Resume*. Jika pengguna mengirim karakter 's', variabel `isPaused` menjadi *true* dan sistem akan berhenti membaca sensor. Jika dikirim karakter 'r', sistem akan kembali berjalan dan indeks *buffer* diatur ulang ke nol agar data lama tidak bercampur dengan data baru. 

Apabila sistem tidak dalam keadaan jeda, baris `accel.getEvent(&event)` akan mengekstraksi nilai percepatan gravitasi pada ketiga sumbu. Nilai-nilai ini langsung dimasukkan ke dalam *array* *buffer* sesuai indeks saat ini. Indeks kemudian ditambah satu. Ketika indeks mencapai batas 512, sistem memanggil fungsi `sendDataBatch()` untuk mengirim paket data tersebut dan mengatur indeks kembali ke nol. Di akhir blok, terdapat fungsi `delayMicroseconds(400)`. Angka 400 mikrodetik ini dihitung berdasarkan target *sampling rate* 1600 Hz (sekitar 625 mikrodetik per siklus), dengan memberikan ruang toleransi untuk waktu eksekusi kode itu sendiri.

### 4. Pengiriman Paket Data (void sendDataBatch)
Fungsi ini bertugas mengemas 512 baris data mentah ke dalam format JSON yang bisa dibaca oleh *server* Python. Mikrokontroler menyusun *string* JSON secara manual melalui perulangan `for` yang menggabungkan nilai X, Y, dan Z. Setelah kerangka JSON terbentuk, sistem memanggil metode `http.POST(json)` untuk menembakkan data tersebut ke alamat URL Railway. Sistem juga memanfaatkan fungsi `millis()` sebelum dan sesudah perintah POST untuk menghitung latensi jaringan secara langsung. Jika pengiriman berhasil, kode respons HTTP 200 akan dicetak di layar Serial beserta waktu tempuhnya.


## Bagian 2: Logika file operasional fitur dan model dalam _cloud server_ (Python - File server.py)

### 1. Konfigurasi dan Pemuatan Model Kecerdasan Buatan
File Python diawali dengan impor berbagai _library_ penting seperti `Flask` untuk *web server*, `numpy` dan `scipy.fft` untuk komputasi matematis, `joblib` untuk memuat model *machine learning*, serta _library_ integrasi Telegram. Terdapat pengaturan `matplotlib.use('Agg')` yang sangat penting karena *server cloud* tidak memiliki antarmuka grafis, sehingga grafik harus dirender di balik layar dan disimpan sebagai gambar *buffer*. 

Fungsi `load_model()` bertugas memanggil *file* `MODEL_SIAP_DEPLOY.pkl` ke dalam memori. Model ini berisi tiga komponen utama yang sudah dilatih sebelumnya: objek *Scaler* untuk normalisasi data, objek *PCA* untuk reduksi dimensi, dan objek algoritma *Random Forest* itu sendiri.

### 2. Pra-pemrosesan Sinyal dan Ekstraksi Fitur (extract_features_live)
Saat data mentah masuk, fungsi `extract_features_live()` mengambil alih. Logika paling awal yang dieksekusi adalah `np.clip(signal_data, -5.0, 5.0)`. Fungsi inilah yang bertindak sebagai *software clipping* untuk membuang lonjakan amplitudo ekstrem yang berasal dari gangguan jalan (misalnya motor menerjang lubang). Dengan memotong nilai getaran di ambang 5G, kita memastikan bahwa algoritma AI hanya fokus pada getaran konstan dari putaran mesin.

Setelah dibersihkan, sinyal yang tadinya berbentuk urutan waktu (*time-domain*) diubah menjadi urutan frekuensi (*frequency-domain*) menggunakan fungsi `fft()`. Algoritma hanya mengambil nilai absolut dari spektrum gelombang tersebut. Komponen *Direct Current* atau frekuensi nol pada indeks pertama dibuang karena hanya merepresentasikan bias gravitasi bumi statis. Nilai rata-rata kemiringan sensor pada sumbu X, Y, dan Z dihitung dan digabungkan dengan susunan data spektrum frekuensi untuk menjadi matriks fitur utuh.

### 3. Reduksi Dimensi dan Prediksi Logika (predict_chunk)
Matriks fitur yang sudah terbentuk akan dilempar ke fungsi `predict_chunk()`. Tahap pertama adalah menyamakan skala fitur menggunakan `scaler.transform()`, karena algoritma AI sangat sensitif terhadap perbedaan besaran angka. Setelah skalanya setara, sistem menjalankan fungsi `pca.transform()` untuk memampatkan ratusan variabel frekuensi menjadi beberapa Komponen Utama (*Principal Components*) saja. Hal ini membuat komputasi model Random Forest menjadi sangat ringan.

Data yang sudah terkompresi dimasukkan ke dalam fungsi `model.predict_proba()`. Berbeda dengan prediksi biasa yang hanya mengeluarkan satu jawaban pasti, fungsi probabilitas ini mengeluarkan persentase keyakinan model untuk masing-masing kelas (Normal, Aus Ringan, Aus Parah). Dari probabilitas tersebut, sistem menghitung angka matematis `damage_score` dengan memberikan bobot 1.0 untuk probabilitas aus parah dan 0.5 untuk aus ringan. Skor akhir ini mencerminkan kondisi keausan secara proporsional.

### 4. Stabilisasi Prediksi dengan Exponential Moving Average (EMA)
Agar sistem tidak kacau akibat fluktuasi sesaat, nilai probabilitas yang dihasilkan tidak langsung ditelan mentah-mentah. Di dalam rute *endpoint* `/raw_data`, terdapat logika perhitungan *Exponential Moving Average*. Nilai bobot (alpha) ditentukan, misalnya 0.3. Rumus `(probabilitas_baru * alpha) + (probabilitas_lama * (1 - alpha))` diterapkan untuk kelas kerusakan. Mekanisme matematis ini berfungsi sebagai semacam peredam kejut logika. Jika sistem mendeteksi kerusakan yang hanya muncul sepersekian detik akibat anomali, nilai EMA-nya tidak akan langsung melonjak melewati ambang batas. Namun jika kerusakan terdeteksi secara konsisten, nilai EMA akan perlahan naik hingga akhirnya memicu status peringatan.

### 5. Logika Rute API Utama (/raw_data)
Blok `@app.route('/raw_data', methods=['POST'])` merupakan pintu masuk tempat ESP32 mengirim datanya. Karena *server* dapat menerima permintaan secara bersamaan, fungsi ini diamankan menggunakan objek `threading.Lock()` agar variabel sesi tidak bertabrakan (*race condition*). Data JSON yang dikirim ESP32 dibongkar dan dimasukkan ke dalam penyangga memori sementara. Ketika data di penyangga mencapai ukuran jendela komputasi yang ditetapkan (misalnya 256 baris), fungsi pemotongan matriks dieksekusi untuk menyerahkan data tersebut ke fungsi `predict_chunk()`.

Sistem juga mendeteksi pergerakan motor berdasarkan variansi amplitudo getaran. Jika variansi sangat rendah, artinya motor sedang diam (mesin mati atau berhenti di lampu merah). Dalam kondisi ini, variabel penanda waktu `last_movement_time` tidak diperbarui. Hal ini mencegah model menebak-nebak kondisi saat tidak ada putaran roda gigi yang nyata.

### 6. Transmisi Peringatan dan Visualisasi Data (Telegram Bot API)
Ketika hasil nilai prediksi yang sudah dihaluskan EMA menyatakan bahwa motor dalam bahaya dan waktu tunggu (*cooldown*) notifikasi sudah terlewati, logika pelaporan diaktifkan. Sistem memanggil _library_ `matplotlib` untuk menggambar plot gelombang getaran sumbu Z. Gambar ini disimpan ke dalam variabel bertipe *BytesIO*, sehingga *server* tidak perlu menyimpan *file* gambar secara fisik di dalam *hardisk*. Gambar tersebut bersama dengan pesan peringatan berbasis teks dikirim langsung ke ID Telegram pengguna yang sudah diatur dengan metode penembakan API Telegram sinkron. Logika komprehensif dari sensor fisik hingga sampai ke genggaman layar ponsel pengguna ditutup dengan pengembalian respons JSON sukses ke ESP32.
