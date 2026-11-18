# Android — build, patch, sign APK di Termux

Gunakan saat user minta decompile, patch smali, repack, atau sign APK.

## Tool
- `pkg install openjdk-17 apktool aapt apksigner` (cek `pkg search` bila nama beda).
- jadx (decompile Java): `pkg install jadx` atau binary rilis.
- Dekompilasi: `apktool d -f app.apk -o out`.
- Build: `apktool b out -o unsigned.apk`.
- Align + sign:
  `zipalign -p -f 4 unsigned.apk aligned.apk`
  `apksigner sign --ks key.keystore --ks-pass pass:... --out signed.apk aligned.apk`
- Verifikasi: `apksigner verify --print-certs signed.apk`.

## Aturan split
- Base + split (abi/density/language) harus di-sign dengan key yang sama.
- Jangan paksa standalone kalau manifest punya `requiredSplitTypes`.
- Untuk bundle split, buat XAPK (manifest.json + base + split) lalu install via SAI.

## Patch dex
- Prioritas: patch smali kecil (1–3 method), bukan rebuild resource.
- Jangan rebuild `resources.arsc` kalau resource tersebar di split; pertahankan
  resource asli dan ganti hanya dex/manifest.
- Binary manifest bisa diedit tanpa decode resource; hindari aapt2 link ulang
  kalau ID resource tidak lengkap.

## Pitfall
- Re-sign APK = signature berubah; app dengan integrity check bisa menolak.
- `pm install` bisa gagal di ROM tertentu; pakai installer UI/SAI.
- Selalu uji `apksigner verify` dan `unzip -l` (dex/lib/asset ada) sebelum menyerahkan.
