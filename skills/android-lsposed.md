# Android — LSPosed (Xposed) modules

Use when building/debugging an Xposed module for a specific app.

## Module layout
```
AndroidManifest.xml  # meta-data xposedmodule, xposeddescription, xposedminversion
assets/xposed_init   # class implementing IXposedHookLoadPackage
classes.dex          # compile against android.jar + stub API
```
- Build without Gradle: `aapt2 link` → add classes.dex + assets → zipalign → apksigner.
- LSPosed's stub API is needed at compile; the runtime is provided by LSPosed.

## Hook patterns
- Filter package: `if (!lpp.packageName.equals(TARGET)) return;`
- `XposedBridge.hookAllMethods(cls, "name", cb)`; log with `XposedBridge.log`.
- Hooking native methods is often unstable → prefer Java, avoid native hooks.
- Don't hook too early, before the classloader is ready.

## Pitfalls
- Enable the module and check its scope; force-stop the app after changing scope.
- DenyList + Enforce ON disables Zygisk injection → module never appears in logs.
- Module logs: `logcat | grep -E 'LSPosed|ModuleName'`.
- Module APK signature need not match the target.
