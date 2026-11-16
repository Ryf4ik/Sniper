[app]
title = Username Sniper
package.name = usersniper
package.domain = org.sniper
source.dir = .
source.include_exts = py
version = 1.0
requirements = python3,openssl,sqlite3,telethon,pyaes,rsa,pyasn1
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WAKE_LOCK
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.bootstrap = webview
p4a.port = 8080

[buildozer]
log_level = 2
warn_on_root = 1
