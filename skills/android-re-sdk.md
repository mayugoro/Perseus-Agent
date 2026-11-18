# Reverse engineering an SDK inside an APK

Use to understand how an SDK (payment, analytics, auth, QRIS) works.

## Steps
1. **Identify the SDK**: `jadx -d out app.apk`; look for vendor packages in
   `AndroidManifest`, `assets`, `lib/`, and `strings classes*.dex`.
2. **API surface**: grep hosts/endpoints (`https://`, `/v1/`, `Retrofit`, `OkHttp`),
   class names `*Client`, `*Service`, `*Api`.
3. **Request contract**: find DTOs/`@SerializedName`, builders, header interceptors,
   signature/HMAC/AES helpers. Note order: token → endpoint → body → headers.
4. **Native**: `readelf -d lib/*.so`, `strings` for endpoints/keys; JNI methods
   (`Java_...`) bridge Java ↔ C.
5. **Dynamic verification**: hook key methods with Frida (not HAR capture), log
   args/return values; for protected SDKs, dump dex/native first.

## What to look for
- Base URL, path, query, required headers (Device-ID, X-Signature, Authorization).
- Auth flow: client_credentials, OTP, refresh token, 2FA challenge.
- Body encryption: AES-GCM key/IV, RSA, HMAC secret.
- Device fingerprint: which parts the server actually uses.

## Pitfalls
- Don't assume a class name equals behavior; verify via hooks.
- R8 obfuscation renames classes; use strings/endpoints as anchors.
- Third-party SDKs may use cert pinning; prepare targeted unpinning.
- Document findings as an API contract, not guesses.
