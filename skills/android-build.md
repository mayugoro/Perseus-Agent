# Android — build, patch, sign APKs in Termux

Use when asked to decompile, patch smali, repack, or sign an APK.

## Tools
- `pkg install openjdk-17 apktool aapt apksigner` (check `pkg search` if names differ).
- jadx (Java decompile): `pkg install jadx` or a release binary.
- Decompile: `apktool d -f app.apk -o out`.
- Rebuild: `apktool b out -o unsigned.apk`.
- Align + sign:
  `zipalign -p -f 4 unsigned.apk aligned.apk`
  `apksigner sign --ks key.keystore --ks-pass pass:... --out signed.apk aligned.apk`
- Verify: `apksigner verify --print-certs signed.apk`.

## Split rules
- Base + splits (abi/density/language) must be signed with the same key.
- Don't force standalone if the manifest has `requiredSplitTypes`.
- For split bundles, make an XAPK (manifest.json + base + splits) and install via SAI.

## Dex patching
- Prefer small smali patches (1–3 methods) over rebuilding resources.
- Don't rebuild `resources.arsc` when resources live in splits; keep the originals
  and replace only dex/manifest.
- A binary manifest can be edited without decoding resources; avoid relinking with
  aapt2 when resource IDs are incomplete.

## Pitfalls
- Re-signing changes the signature; apps with integrity checks may reject it.
- `pm install` can fail on some ROMs; use the UI installer / SAI.
- Always run `apksigner verify` and check `unzip -l` before delivering.
