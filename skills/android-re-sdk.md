# Reverse engineering SDK di APK

Gunakan saat perlu memahami cara SDK (payment, analytics, auth, QRIS) bekerja.

## Langkah
1. **Identifikasi SDK**: `jadx -d out app.apk`; cari package vendor di
   `AndroidManifest`, `assets`, `lib/`, dan string (`strings classes*.dex`).
2. **API surface**: grep host/endpoint (`https://`, `/v1/`, `Retrofit`, `OkHttp`),
   nama class `*Client`, `*Service`, `*Api`.
3. **Kontrak request**: cari DTO/`@SerializedName`, builder, interceptor header,
   signature/HMAC/AES helper. Catat urutan: token → endpoint → body → header.
4. **Native**: `readelf -d lib/*.so`, `strings` untuk endpoint/key; JNI method
   (`Java_...`) menghubungkan Java ↔ C.
5. **Verifikasi dinamis**: hook method kunci via Frida (bukan capture HAR), log
   argumen/return; untuk SDK terproteksi, dump dex/native dulu.

## Yang dicari
- Base URL, path, query, header wajib (Device-ID, X-Signature, Authorization).
- Alur auth: client_credentials, OTP, refresh token, 2FA challenge.
- Enkripsi body: AES-GCM key/IV, RSA, HMAC secret.
- Device fingerprint: mana yang benar-benar dipakai server.

## Pitfall
- Jangan menganggap nama class = perilaku; verifikasi lewat hook.
- Obfuscation (R8) mengubah nama; pakai string/endpoint sebagai jangkar.
- SDK pihak ketiga bisa memakai certificate pinning; siapkan unpin terarah.
- Dokumentasikan temuan sebagai kontrak API, bukan tebakan.
