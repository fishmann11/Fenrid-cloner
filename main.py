# -*- coding: utf-8 -*-
"""
Fenrid Server Cloner - main.py
Kaynak sunucudan hedef sunucuya roller, kanallar ve sunucu adını kopyalar.
"""

import requests
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE    = "https://fenrid.com"
DELAY   = 0.65   



def ask(prompt):
    return input(prompt + ": ").strip()

def yn(prompt):
    while True:
        r = input(prompt + " (e/h): ").strip().lower()
        if r in ("e", "y", "evet", "yes"):
            return True
        if r in ("h", "n", "hayir", "hayır", "no"):
            return False

def build_session(cookie_raw):
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    cookie_raw = cookie_raw.strip()

    if ";;;" in cookie_raw:
        parts = cookie_raw.split(";;;")
        p0 = parts[0].strip()
        p1 = parts[1].strip() if len(parts) > 1 else ""
        s.cookies.set("sb-db-auth-token.0", p0, domain="fenrid.com", path="/")
        if p1:
            s.cookies.set("sb-db-auth-token.1", p1, domain="fenrid.com", path="/")
        return s


    if "sb-db-auth-token" in cookie_raw:
        for part in cookie_raw.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                s.cookies.set(k.strip(), v.strip(), domain="fenrid.com", path="/")
        return s


    if cookie_raw.startswith("eyJ"):
        s.headers.update({"Authorization": f"Bearer {cookie_raw}"})

    return s

def api_get(s, path):
    r = s.get(BASE + path)
    r.raise_for_status()
    return r.json()

def api_post(s, path, body):
    r = s.post(BASE + path,
               json=body,
               headers={"Content-Type": "application/json"})
    return r

def api_patch(s, path, body):
    r = s.patch(BASE + path,
                json=body,
                headers={"Content-Type": "application/json"})
    return r

def api_delete(s, path):
    return s.delete(BASE + path)

def ok(r):
    return "OK" if r.ok else f"HATA {r.status_code}"



def main():
    print()
    print("=" * 48)
    print("         Fenrid Server Cloner")
    print("=" * 48)
    print()

    src = ask("Kaynak sunucu ID")
    tgt = ask("Hedef  sunucu ID")
    print()

    do_roles    = yn("Roller kopyalansın mı?     ")
    do_channels = yn("Kanallar kopyalansın mı?   ")
    do_name     = yn("Sunucu adı kopyalansın mı? ")
    print()

    del_existing = False
    if do_roles or do_channels:
        del_existing = yn("Hedef sunucudaki mevcut roller/kanallar silinsin mi?")
        print()

    print("Tarayici konsoluna (F12 > Console) su komutu yaz ve ciktıyı yapıştır:")
    print()
    print("  (function(){var p=document.cookie.split(';').map(c=>c.trim());")
    print("   var p0=p.find(c=>c.startsWith('sb-db-auth-token.0=')).replace('sb-db-auth-token.0=','');")
    print("   var p1=p.find(c=>c.startsWith('sb-db-auth-token.1=')).replace('sb-db-auth-token.1=','');")
    print("   return p0+';;;'+p1;})()")
    print()
    cookie_raw = input("Cikti > ").strip()
    print()

    s = build_session(cookie_raw)

    # Baglanti testi
    test = s.get(BASE + f"/api/servers/{src}/roles")
    if test.status_code == 401:
        print("HATA: 401 – Token gecersiz ya da suresi dolmus.")
        print("Fenrid'de tekrar giris yap ve tekrar dene.")
        return
    if not test.ok:
        print(f"HATA: {test.status_code}\n{test.text[:200]}")
        return

    print("  Baglantı OK!\n")

  
    if do_name:
        print("[1/4] Sunucu adı alınıyor...")
   
        boot = api_get(s, "/api/sidebar/bootstrap")
        server_name = None

        disc = s.get(BASE + f"/api/livekit/server-participants?serverId={src}")
        name_endpoints = [
            f"/api/servers/{src}",
            f"/api/chat/servers/{src}",
        ]
        for ep in name_endpoints:
            r = s.get(BASE + ep)
            if r.ok and r.headers.get("content-type", "").startswith("application/json"):
                data = r.json()
                if isinstance(data, dict) and data.get("name"):
                    server_name = data["name"]
                    break

        if server_name:
            print(f"  Kaynak ad: {server_name}")
            for patch_ep in [f"/api/servers/{tgt}", f"/api/chat/servers/{tgt}"]:
                pr = api_patch(s, patch_ep, {"name": server_name})
                if pr.ok:
                    print(f"  Hedef sunucu adı '{server_name}' olarak guncellendi.")
                    break
                form_r = s.patch(BASE + patch_ep, data={"name": server_name})
                if form_r.ok:
                    print(f"  Hedef sunucu adı '{server_name}' olarak guncellendi.")
                    break
            else:
                print("  Sunucu adı güncellenemedi (endpoint doğrulanamadı).")
        else:
            print("  Kaynak sunucu adı alınamadı (API desteklemiyor olabilir).")
        print()

 
    if del_existing:
        step = 2 if do_name else 1

        if do_roles:
            print(f"[{step}/4] Hedef sunucudaki mevcut roller siliniyor...")
            try:
                roles = api_get(s, f"/api/servers/{tgt}/roles")
                for role in roles:
                    if role["id"] == tgt:   
                        continue
                    r = api_delete(s, f"/api/servers/{tgt}/roles/{role['id']}")
                    print(f"  {ok(r)}  {role['name']}")
                    time.sleep(DELAY)
            except Exception as e:
                print(f"  Silinirken hata: {e}")
            step += 1
            print()

        if do_channels:
            print(f"[{step}/4] Hedef sunucudaki mevcut kanallar siliniyor...")
            try:
                ch_data = api_get(s, f"/api/servers/{tgt}/channels")
                channels = ch_data.get("channels", ch_data) if isinstance(ch_data, dict) else ch_data
                for ch in channels:
                    r = api_delete(s, f"/api/channels/{ch['id']}")
                    print(f"  {ok(r)}  #{ch['name']}")
                    time.sleep(DELAY)
            except Exception as e:
                print(f"  Silinirken hata: {e}")
            print()


    if do_roles:
        print("[ROLLER] Kopyalanıyor...")
        try:
            roles = api_get(s, f"/api/servers/{src}/roles")
            roles = sorted(
                [r for r in roles if r["id"] != src],
                key=lambda r: r["position"]
            )
            for role in roles:
                body = {
                    "name":        role["name"],
                    "color":       role["color"],
                    "permissions": role["permissions"],
                    "hoist":       role["hoist"],
                    "mentionable": role["mentionable"],
                }
                res = api_post(s, f"/api/servers/{tgt}/roles", body)
                time.sleep(DELAY)
                print(f"  {ok(res)}  {role['name']}")
        except Exception as e:
            print(f"  Hata: {e}")
        print()

   
    if do_channels:
        print("[KANALLAR] Kopyalanıyor...")
        try:
            ch_data = api_get(s, f"/api/servers/{src}/channels")
            channels = ch_data.get("channels", ch_data) if isinstance(ch_data, dict) else ch_data

            cats   = sorted([c for c in channels if c["type"] == 4],  key=lambda c: c["position"])
            others = sorted([c for c in channels if c["type"] != 4],  key=lambda c: c["position"])
            cat_map = {}

            print("  --- Kategoriler ---")
            for cat in cats:
                body = {"serverId": tgt, "name": cat["name"], "type": 4, "parent_id": None}
                res  = api_post(s, "/api/chat/channels", body)
                time.sleep(DELAY)
                if res.ok:
                    data = res.json()
                    cat_map[cat["id"]] = data.get("id")
                    print(f"  OK   [Kategori] {cat['name']}")
                else:
                    print(f"  HATA [{res.status_code}] [Kategori] {cat['name']}  {res.text[:80]}")

            print("  --- Kanallar ---")
            for ch in others:
                new_parent = cat_map.get(ch.get("parent_id"))
                body = {
                    "serverId":  tgt,
                    "name":      ch["name"],
                    "type":      ch["type"],
                    "parent_id": new_parent,
                }
                res  = api_post(s, "/api/chat/channels", body)
                time.sleep(DELAY)
                kind = "ses  " if ch["type"] == 2 else "metin"
                if res.ok:
                    print(f"  OK   [{kind}] {ch['name']}")
                else:
                    print(f"  HATA [{res.status_code}] [{kind}] {ch['name']}  {res.text[:80]}")
        except Exception as e:
            print(f"  Hata: {e}")
        print()

    print("=" * 48)
    print("  Kopyalama tamamlandı!")
    print("=" * 48)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nIptal edildi.")
