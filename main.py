import os
import re
import time
import html
import asyncio
import sys
import traceback
import httpx #type:ignore
from bs4 import BeautifulSoup #type:ignore
from urllib.parse import unquote, urljoin

WAIT_REGEXES = [
    r"(?:veuillez\s+)?patiente[rz]\s*(\d+)\s*(?:sec|secondes?|s)\b",
    r"please\s+wait\s*(\d+)\s*(?:sec|seconds?)\b",
    r"t[ée]l[ée]chargement\s+gratuit\s+dans\s*(\d+)",
    r"vous\s+devez\s+attendre\s+encore\s+(\d+)\s+minutes?",  # 'Vous devez attendre encore 1 minutes'
    r"var\s+ct\s*=\s*(\d+)\s*;",  # var ct = 60;
    r"var\s+ct\s*=\s*(\d+)\s*\*\s*60\s*;",  # var ct = 1*60;
]

DOWNLOAD_BUTTON_PATTERNS = [
    re.compile(r"cliquez\s+ici", re.I),
    re.compile(r"click\s+here", re.I),
    re.compile(r"télécharger", re.I),
    re.compile(r"download", re.I),
]

def human_duration(secs: int) -> str:
    if secs >= 3600:
        return f"{secs//3600}h{(secs%3600)//60:02d}m{secs%60:02d}s"
    if secs >= 60:
        return f"{secs//60}m{secs%60:02d}s"
    return f"{secs}s"

def extract_wait_seconds(text: str) -> int:
    low = text.lower()
    for pat in WAIT_REGEXES:
        m = re.search(pat, low)
        if m:
            val = m.group(1)
            try:
                secs = int(val)
                if "minute" in pat:
                    return secs * 60
                return secs
            except ValueError:
                pass
    # Fallback explicite si expression multiplicative non couverte
    expr = re.search(r"var\s+ct\s*=\s*(\d+)\s*\*\s*60", low)
    if expr:
        try:
            return int(expr.group(1)) * 60
        except ValueError:
            pass
    return 0

def choose_filename_from_headers(resp, fallback="fichier_1fichier.bin"):
    dispo = resp.headers.get("Content-Disposition") or resp.headers.get("content-disposition")
    if dispo:
        m = re.search(r'filename\*?=(?:UTF-8\'\')?("?)([^";]+)\1', dispo, re.IGNORECASE)
        if m:
            return os.path.basename(html.unescape(unquote(m.group(2))))
    # httpx.Response.url est un objet URL; convertissons-le en chaîne
    url_str = str(getattr(resp, "url", ""))
    tail = url_str.rsplit("/", 1)[-1]
    if tail:
        return os.path.basename(unquote(tail))
    return fallback

DISPLAY_NAME_EXT_REGEX = re.compile(r"\.(?:7z|zip|rar|mp4|mkv|avi|mp3|flac|iso|xci|nsp|exe|pdf|epub|apk|tar|gz|bz2|xz|part\d+|bin|img|dmg|msi|wav|aac|mov|srt|ass|txt)(?:$|[\s])", re.I)

def extract_display_filename(soup) -> str | None:
    """Tente d'extraire le nom de fichier humainement affiché sur la page.
    Heuristiques:
      - span / b / strong contenant une extension connue
      - cellule de tableau (td) avec texte bold et extension
    Retourne None si rien de fiable.
    """
    candidates: list[str] = []
    # Bold spans
    for tag in soup.find_all(["span", "b", "strong"]):
        txt = (tag.get_text(" ") or "").strip()
        if not txt or len(txt) < 5:
            continue
        if DISPLAY_NAME_EXT_REGEX.search(txt):
            candidates.append(txt)
    # td normal
    for td in soup.find_all("td"):
        txt = (td.get_text(" ") or "").strip()
        if DISPLAY_NAME_EXT_REGEX.search(txt):
            candidates.append(txt)
    if not candidates:
        return None
    # Garder le plus long (souvent inclut extension complète)
    candidates.sort(key=len, reverse=True)
    name = candidates[0]
    # Nettoyage simple: supprimer multiples espaces et caractères de contrôle
    name = re.sub(r"[\r\n\t]+", " ", name).strip()
    # Éviter d'inclure taille ou unité séparée sur même chaîne
    # Si la chaîne contient une taille (ex 101.81 Mo), on coupe avant si possible
    size_match = re.search(r"\b\d+[.,]\d+\s*(?:k|m|g|t)o?\b", name, re.I)
    if size_match and size_match.start() > 10:  # taille plus loin; coupe probable
        name = name[:size_match.start()].strip()
    return name

HTML_ERROR_MARKERS = [
    "fichier demandé n'existe plus",
    "le fichier demandé n'existe plus",
    "file not found",
    "a été supprimé",
    "copyright",
    "dmca",
]

def looks_like_error_html(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in HTML_ERROR_MARKERS)

def probable_file_response(resp: httpx.Response) -> bool:
    ct = resp.headers.get("content-type", "").lower()
    dispo = resp.headers.get("content-disposition")
    if dispo:
        return True
    if ct and not ct.startswith("text/html"):
        return True
    # If HTML but very large (unlikely to be legal page) treat as file anyway
    clen = int(resp.headers.get("content-length", 0) or 0)
    if ct.startswith("text/html") and clen < 20000:  # small html page likely error/legal
        return False
    return False if ct.startswith("text/html") else True

async def fetch_html(client, url):
    r = await client.get(url, timeout=30)
    r.raise_for_status()
    return r

def find_direct_link(soup, base_url):
    base_url_str = str(base_url)
    KEYWORDS = ["cliquez ici", "cliquer ici", "click here", "télécharger", "telecharger", "download"]
    # 1. Recherche par texte explicite contenant un mot-clé
    for a in soup.find_all("a", href=True):
        txt = (a.get_text(" ") or "").strip().lower()
        if any(k in txt for k in KEYWORDS):
            return urljoin(base_url_str, a["href"])
    # 2. Ancres avec motif /dl/ ou param dl
    for a in soup.find_all("a", href=True):
        if re.search(r"/dl/|[?&]dl=", a["href"], re.IGNORECASE):
            return urljoin(base_url_str, a["href"])
    # 3. Domaine 1fichier + identifiant plausible (ex: https://a-33.1fichier.com/cXXXXXXXX)
    for a in soup.find_all("a", href=True):
        if re.search(r"1fichier\.com/", a["href"], re.I):
            return urljoin(base_url_str, a["href"])
    return None

DIRECT_LINK_REGEXES = [
    re.compile(r"https?://[a-z0-9.-]*1fichier\.com/[A-Za-z0-9]{8,}[^\s\"'<>]*", re.I),
    re.compile(r"https?://[a-z0-9.-]*1fichier\.com/\?\w{10,}", re.I),
]

def search_direct_link_in_html(html_text: str) -> str | None:
    for rg in DIRECT_LINK_REGEXES:
        m = rg.search(html_text)
        if m:
            return m.group(0)
    return None
def detect_captcha(soup):
    if soup.find(attrs={"data-sitekey": True}) or soup.find(class_=re.compile("captcha", re.I)) or soup.find(id=re.compile("captcha", re.I)):
        return True
    return False

def find_download_form(soup):
    # Cherche un formulaire avec un bouton submit cohérent
    for form in soup.find_all("form"):
        # Inspecte inputs et boutons
        submit_candidate = False
        texts = []
        # Collect possible textual indicators
        for inp in form.find_all(["input", "button"]):
            t = (inp.get("value") or "").strip()
            if t:
                texts.append(t)
            if inp.name == "input" and inp.get("type", "").lower() == "submit":
                submit_candidate = True
            if inp.name == "button" and (inp.get("type") in (None, "submit")):
                submit_candidate = True
        # Also consider direct text inside form
        form_text = " ".join(texts + [form.get_text(" ").strip()])
        if submit_candidate and any(p.search(form_text) for p in DOWNLOAD_BUTTON_PATTERNS):
            return form
    return None

async def submit_download_form(client, form, base_url):
    base_url_str = str(base_url)
    raw_action = None
    try:
        raw_action = form.get("action")  # type: ignore[attr-defined]
    except Exception:
        raw_action = None
    action = str(raw_action) if raw_action else base_url_str
    action_abs = urljoin(base_url_str, action)
    data = {}
    submit_name = None
    submit_value = None
    # Collect hidden + submit fields
    for inp in form.find_all("input"):
        itype = (inp.get("type") or "").lower()
        name = inp.get("name")
        if not name:
            continue
        if itype in ("hidden", "text"):
            data[name] = inp.get("value") or ""
        elif itype == "submit":
            # Retient un premier bouton submit
            if submit_name is None:
                submit_name = name
                submit_value = inp.get("value") or ""  # souvent vide
    # Ajoute le paramètre submit si nécessaire
    if submit_name and submit_name not in data:
        data[submit_name] = submit_value or ""
    headers = {
        "Referer": base_url_str,
        "Origin": base_url_str.rsplit("/", 1)[0],
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }
    # Force cast to str to avoid TypeError "Cannot mix str and non-str arguments"
    cast_data = {str(k): ("" if v is None else str(v)) for k, v in data.items()}
    r = await client.post(action_abs, data=cast_data, headers=headers, timeout=60, follow_redirects=True)
    r.raise_for_status()
    return r

def save_debug(debug, label, content):
    if not debug:
        return
    try:
        fname = f"debug_{int(time.time())}_{label}.html"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[debug] Sauvegardé {fname}")
    except Exception as e:
        print(f"[debug] Échec sauvegarde {label}: {e}")

async def download_file(client, url, outdir=".", debug=False, force_wait=False, save_html=False, log_cb=None, progress_cb=None, wait_cb=None, pause_event: asyncio.Event | None = None):
    """Télécharge un fichier avec callbacks optionnels.
    log_cb(msg) et progress_cb(url, filename, downloaded, total, percent)
    """
    def _log(msg: str):
        if log_cb:
            try:
                log_cb(msg)
            except Exception:
                print(msg)
        else:
            print(msg)
    def _progress(filename, downloaded, total):
        if progress_cb:
            pct = (downloaded / total * 100) if total else None
            try:
                progress_cb(url, filename, downloaded, total, pct)
            except Exception:
                pass
    def _wait_update(remaining, total_wait):
        if wait_cb:
            try:
                wait_cb(url, remaining, total_wait)
            except Exception:
                pass
    _log(f"\n🔗 Traitement de {url}")
    r = await fetch_html(client, url)
    soup = BeautifulSoup(r.text, "html.parser")
    save_debug(debug, "initial", r.text)

    # Nom affiché (avant toute action), pour feedback utilisateur
    page_display_name = extract_display_filename(soup)
    if page_display_name:
        _log(f"📄 Nom: {page_display_name}")

    if detect_captcha(soup):
        _log("⚠️ Captcha détecté. Résolution manuelle requise (ouvrir l'URL dans un navigateur, résoudre, puis récupérer le cookie / token).")
        if save_html:
            save_debug(True, "captcha_page", r.text)
        return

    # Détection page erreur précoce
    if looks_like_error_html(r.text):
        # Ignore faux positifs si lien direct présent
        if not find_direct_link(soup, str(r.url)):
            _log("❌ Page reçue indique indisponibilité / conditions. (Fichier supprimé ou limites atteintes.)")
            if save_html:
                save_debug(True, "early_error", r.text)
            return

    # Vérif temps d’attente (compte à rebours free 1fichier)
    wait_s = extract_wait_seconds(r.text)
    form_after_wait_submitted = False
    form_tag_initial = soup.find("form", id="f1")

    # Soumission immédiate seulement si PAS de compte à rebours détecté
    immediate_attempt_done = False
    if form_tag_initial and wait_s == 0:
        try:
            r_immediate = await submit_download_form(client, form_tag_initial, str(r.url))
            immediate_attempt_done = True
            ct0 = r_immediate.headers.get("content-type", "")
            if debug:
                print(f"[debug] Soumission immédiate: status={r_immediate.status_code} url_finale={r_immediate.url} ct={ct0}")
            if "text/html" not in ct0.lower():
                head_like = r_immediate
                filename = choose_filename_from_headers(head_like)
                final_path = os.path.join(outdir, filename)
                part_path = final_path + ".part"
                with open(part_path, "wb") as f:
                    f.write(r_immediate.content)
                os.replace(part_path, final_path)
                _log(f"✅ Terminé → {final_path} (sans attente)")
                return
            else:
                save_debug(debug, "after_immediate_submit", r_immediate.text)
                soup_after = BeautifulSoup(r_immediate.text, "html.parser")
                direct_imm = find_direct_link(soup_after, str(r_immediate.url))
                if direct_imm:
                    direct = direct_imm
                    form_after_wait_submitted = True
                    soup = soup_after
                    r = r_immediate
        except Exception as e:
            if debug:
                print("[debug] Soumission immédiate échouée: " + str(e))

    if wait_s > 0 and not form_after_wait_submitted:
        # Attente automatique toujours (suppression des seuils et abandons)
        _log(f"⏳ Attente {human_duration(wait_s)} (mode gratuit)…")
        fast_factor = 1
        try:
            if os.environ.get("F1_FAST"):
                fast_factor = max(1, int(os.environ.get("F1_FAST") or 1))
        except ValueError:
            fast_factor = 1
        # Affichage dynamique
        for remaining in range(wait_s, 0, -1):
            if pause_event and not pause_event.is_set():
                # Attente de reprise
                await pause_event.wait()
            _wait_update(remaining, wait_s)
            if not log_cb:
                print(f"\r⏳ {human_duration(remaining):>8} restantes", end="")
            await asyncio.sleep(1 / fast_factor)
        _wait_update(0, wait_s)
        if not log_cb:
            print()  # newline
        if form_tag_initial and not immediate_attempt_done:
            try:
                r_after = await submit_download_form(client, form_tag_initial, str(r.url))
                form_after_wait_submitted = True
                soup = BeautifulSoup(r_after.text, "html.parser")
                save_debug(debug, "after_wait_submit", r_after.text)
                if detect_captcha(soup):
                    print("⚠️ Captcha détecté après soumission. Abandon.")
                    return
                r = r_after
            except Exception as e:
                print(f"❌ Soumission après attente échouée: {e}")
                if debug:
                    print("[debug] Trace:\n" + traceback.format_exc())
        if not form_after_wait_submitted:
            r = await fetch_html(client, url)
            soup = BeautifulSoup(r.text, "html.parser")
            save_debug(debug, "after_wait_fallback_get", r.text)
            if detect_captcha(soup):
                _log("⚠️ Captcha détecté après attente. Abandon.")
                return

    # Lien direct (heuristique initiale)
    direct = find_direct_link(soup, r.url)
    if not direct:
        dl_regex_hit = search_direct_link_in_html(r.text)
        if dl_regex_hit:
            direct = dl_regex_hit
    if not direct:
        # Essai via formulaire
        # Si on a déjà soumis après attente, éviter double POST; sinon chercher un formulaire à soumettre
        form = None if form_after_wait_submitted else find_download_form(soup)
        if form:
            _log("📝 Soumission du formulaire de téléchargement…")
            attempt = 0
            while attempt < 3 and not direct:
                attempt += 1
                try:
                    r2 = await submit_download_form(client, form, str(r.url))
                except Exception as e:
                    if debug:
                        print("[debug] Trace:\n" + traceback.format_exc())
                    _log(f"❌ Échec soumission formulaire (tentative {attempt}): {e}")
                    break
                ct = r2.headers.get("content-type", "")
                if "text/html" in ct.lower():
                    soup2 = BeautifulSoup(r2.text, "html.parser")
                    save_debug(debug, f"after_manual_submit_{attempt}", r2.text)
                    if detect_captcha(soup2):
                        _log("⚠️ Captcha détecté après soumission. Abandon.")
                        return
                    direct = find_direct_link(soup2, r2.url)
                    if not direct:
                        dl_regex_hit = search_direct_link_in_html(r2.text)
                        if dl_regex_hit:
                            direct = dl_regex_hit
                    if not direct:
                        # Meta refresh
                        meta = soup2.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
                        if meta:
                            meta_dict = {}
                            try:
                                meta_dict = dict(meta.attrs)  # type: ignore[attr-defined]
                            except Exception:
                                meta_dict = {}
                            content_attr = meta_dict.get("content")
                            if isinstance(content_attr, str):
                                parts = content_attr.split(";", 1)
                                if len(parts) == 2 and "url=" in parts[1].lower():
                                    dest = parts[1].split("=", 1)[1].strip()
                                    direct = urljoin(r2.url, dest)
                    # Réactualise form avec nouvelle page si encore échec (peut contenir nouveau token hidden)
                    if not direct:
                        new_form = find_download_form(soup2) or soup2.find("form", id="f1")
                        if new_form:
                            form = new_form
                else:
                    # Fichier directement
                    direct = str(r2.url)
                    break
        if not direct:
            _log("❌ Impossible de trouver le lien direct (peut-être Captcha ou changement de page). Active --debug pour plus d'info.")
            return

    # HEAD pour nom + taille
    head = await client.head(direct, follow_redirects=True)
    if head.status_code >= 400 or "content-length" not in head.headers:
        head = await client.get(direct, follow_redirects=True)
    # Si la réponse semble être une page HTML d'erreur, on fait un GET complet et vérifie contenu
    if head.headers.get("content-type", "").lower().startswith("text/html") and not head.headers.get("content-disposition"):
        full_html = head.text if hasattr(head, "text") else ""
        if looks_like_error_html(full_html):
            _log("❌ Page HTML reçue au lieu du fichier (probablement indisponible / supprimé / conditions). Aucune sauvegarde.")
            if debug:
                save_debug(True, "error_page", full_html)
            return
    filename = choose_filename_from_headers(head)
    final_path = os.path.join(outdir, filename)
    part_path = final_path + ".part"

    total_size = int(head.headers.get("content-length", 0))
    accept_ranges = "bytes" in head.headers.get("accept-ranges", "").lower()
    existing = os.path.getsize(part_path) if os.path.exists(part_path) else 0

    headers = {}
    mode = "wb"
    if existing > 0 and accept_ranges:
        headers["Range"] = f"bytes={existing}-"
        mode = "ab"
        _log(f"▶️ Reprise à {existing/1024/1024:.2f} MB")
    elif existing > 0:
        _log("ℹ️ Reprise impossible, redémarrage complet.")
        existing = 0

    # Téléchargement
    async with client.stream("GET", direct, headers=headers, follow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0)) + existing if total_size else None
        downloaded = existing
        _log(f"⬇️ Téléchargement → {filename} ({total/1024/1024:.2f} MB)" if total else f"⬇️ Téléchargement → {filename}")

        with open(part_path, mode) as f:
            async for chunk in resp.aiter_bytes(1024*128):
                if pause_event and not pause_event.is_set():
                    await pause_event.wait()
                f.write(chunk)
                downloaded += len(chunk)
                if total and not log_cb:
                    pct = downloaded / total * 100
                    print(f"\rProgression: {pct:5.1f}% ({downloaded/1024/1024:.2f} / {total/1024/1024:.2f} MB)", end="")
                _progress(filename, downloaded, total)
        if not log_cb:
            print()

    os.replace(part_path, final_path)
    _log(f"✅ Terminé → {final_path}")
    _progress(filename, total_size or os.path.getsize(final_path), total_size or os.path.getsize(final_path))

async def prefetch_display_names(client, urls, log_cb=None):
    """Précharge les noms de fichiers (nom affiché) pour une liste d'URLs avant lancement des téléchargements.
    Ne déclenche pas d'attente ni de soumission de formulaire: simple GET initial.
    Retour: dict {url: nom_ou_None}.
    """
    results: dict[str, str | None] = {}

    async def _one(u: str):
        name = None
        try:
            r = await fetch_html(client, u)
            soup = BeautifulSoup(r.text, "html.parser")
            name = extract_display_filename(soup)
        except Exception:
            name = None
        results[u] = name
        if log_cb:
            if name:
                log_cb(f"📄 Nom détecté: {name} ← {u}")
            else:
                log_cb(f"📄 Nom introuvable (pour l'instant) ← {u}")

    sem = asyncio.Semaphore(6)
    async def _wrapped(u: str):
        async with sem:
            await _one(u)
    await asyncio.gather(*[_wrapped(u) for u in urls])
    return results

def parse_args(argv):
    urls = []
    outdir = "."
    debug = False
    save_html = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--debug", "-d"):
            debug = True
        elif a in ("--output", "-o") and i + 1 < len(argv):
            outdir = argv[i+1]
            i += 1
        elif a == "--save-html":
            save_html = True
        elif a.startswith("-"):
            # unrecognized flag ignored
            pass
        else:
            urls.append(a)
        i += 1
    return urls, outdir, debug or bool(os.environ.get("F1_DEBUG")), save_html

async def main(argv=None):
    # Si lancé en binaire PyInstaller (frozen) sans arguments -> ouvrir GUI automatiquement
    if argv is None:
        if getattr(sys, 'frozen', False) and len(sys.argv) == 1:
            argv = ['--gui']
        else:
            argv = sys.argv[1:]
    if "--gui" in argv:
        import gui  # type: ignore
        gui.launch_gui()
        return
    urls, outdir, debug, save_html = parse_args(argv)
    force_wait = any(a in ("--force-wait",) for a in argv)
    if not urls:
        urls = input("Entre les URLs 1fichier (séparées par espace ou retour ligne) :\n").split()
    if outdir and not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)
    async with httpx.AsyncClient(headers={"User-Agent":"Mozilla/5.0"}) as client:
        # Pré-récupération des noms si plusieurs URLs
        clean_urls = [u.strip() for u in urls if u.strip()]
        if len(clean_urls) > 1:
            print("🔍 Pré-récupération des noms...")
            name_map = await prefetch_display_names(client, clean_urls, log_cb=lambda m: print(m))
            print("— Récapitulatif —")
            for idx, u in enumerate(clean_urls, 1):
                nm = name_map.get(u) or "(nom inconnu)"
                print(f"{idx:2d}. {nm}")
            print()
        tasks = [download_file(client, u, outdir=outdir, debug=debug, force_wait=force_wait, save_html=save_html) for u in clean_urls]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
